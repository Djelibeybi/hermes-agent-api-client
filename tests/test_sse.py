"""Bounded transport-independent Hermes SSE contract tests."""

from __future__ import annotations

import asyncio
import json
import traceback
from itertools import product
from typing import TYPE_CHECKING, Any, Protocol, cast

import pytest

import hermes_agent_api_client as hermes_api
from hermes_agent_api_client import (
    AssistantDeltaEvent,
    HermesProtocolError,
    HermesTransportError,
    KeepaliveEvent,
    TerminalEvent,
    TerminalFailureReason,
    TerminalOutcome,
    ToolProgressEvent,
    ToolProgressStatus,
    UsageEvent,
)
from hermes_agent_api_client.sse import (
    MAX_EVENT_DATA_CHARS,
    MAX_PENDING_BYTES,
    async_decode_hermes_sse,
)
from tests.helpers.hermes import (
    load_golden_bytes,
    load_golden_json,
    partition_bytes,
    raw_json_object_sse_record,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Iterable
    from types import FrameType

_BOOLEAN_TOKEN_COUNT: object = True
_OMITTED = object()


class _HasAsyncGeneratorFrame(Protocol):
    """Structural view of the CPython async-generator inspection surface."""

    @property
    def ag_frame(self) -> FrameType | None:
        """Return the retained generator frame, if the generator is open."""
        ...


async def _chunks(parts: tuple[bytes, ...]) -> AsyncIterator[bytes]:
    """Yield deterministic asynchronous byte chunks."""
    for part in parts:
        await asyncio.sleep(0)
        yield part


class _UnclosableChunks:
    """A valid async byte iterator without an optional close method."""

    def __init__(self, parts: tuple[bytes, ...]) -> None:
        self._parts = iter(parts)

    def __aiter__(self) -> _UnclosableChunks:
        return self

    async def __anext__(self) -> bytes:
        await asyncio.sleep(0)
        try:
            return next(self._parts)
        except StopIteration:
            raise StopAsyncIteration from None


class _ClosableChunks:
    """Deterministic async bytes with independently controlled read and close errors."""

    def __init__(
        self,
        parts: tuple[bytes, ...],
        *,
        read_failure: BaseException | None = None,
        close_failure: BaseException | None = None,
    ) -> None:
        self._parts = iter(parts)
        self._read_failure = read_failure
        self._close_failure = close_failure
        self.closed = False

    def __aiter__(self) -> _ClosableChunks:
        return self

    async def __anext__(self) -> bytes:
        """Return chunks before raising the configured source-read failure."""
        await asyncio.sleep(0)
        try:
            return next(self._parts)
        except StopIteration:
            pass
        if self._read_failure is not None:
            failure = self._read_failure
            self._read_failure = None
            raise failure
        raise StopAsyncIteration

    async def aclose(self) -> None:
        """Record close ownership before raising the configured cleanup failure."""
        self.closed = True
        if self._close_failure is not None:
            raise self._close_failure


class _AiterFailure:
    """Hostile async iterable that fails before yielding an iterator."""

    def __init__(self, failure: BaseException, *, canary: str) -> None:
        self._failure = failure
        self._canary = canary

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Raise the configured acquisition error without returning an iterator."""
        raise self._failure


async def _decode(parts: tuple[bytes, ...]) -> tuple[object, ...]:
    """Collect all typed events from one isolated decoder invocation."""
    return tuple([event async for event in async_decode_hermes_sse(_chunks(parts))])


async def _consume_into(events: list[object], parts: tuple[bytes, ...]) -> None:
    """Retain each decoded prefix event before a later failure is raised."""
    async for event in async_decode_hermes_sse(_chunks(parts)):
        events.extend((event,))


async def _decode_prefix_before_failure(
    parts: tuple[bytes, ...],
) -> tuple[object, ...]:
    """Return events observed before the required protocol failure."""
    events: list[object] = []
    with pytest.raises(HermesProtocolError):
        await _consume_into(events, parts)
    return tuple(events)


def _package_traceback_locals(error: BaseException) -> tuple[dict[str, object], ...]:
    """Snapshot every package-owned frame retained by one decoder failure."""
    frames: list[dict[str, object]] = []
    cursor = error.__traceback__
    while cursor is not None:
        module_name = cursor.tb_frame.f_globals.get("__name__")
        if isinstance(module_name, str) and module_name.startswith(
            "hermes_agent_api_client"
        ):
            frames.append(dict(cursor.tb_frame.f_locals))
        cursor = cursor.tb_next
    assert frames
    return tuple(frames)


def _assert_package_traceback_is_scrubbed(
    error: BaseException,
    *,
    canaries: tuple[str, ...],
    forbidden_objects: tuple[object, ...],
) -> None:
    """Reject raw records and nested canaries from retained decoder state."""
    rendered_error = " | ".join(
        (str(error), repr(error), repr(error.args), repr(vars(error)))
    )
    assert all(canary not in rendered_error for canary in canaries)
    assert error.__cause__ is None
    assert error.__context__ is None

    for frame_locals in _package_traceback_locals(error):
        pending: list[object] = list(frame_locals.values())
        visited: set[int] = set()
        while pending:
            referenced = pending.pop()
            identity = id(referenced)
            if identity in visited:
                continue
            visited.add(identity)
            assert all(referenced is not forbidden for forbidden in forbidden_objects)
            rendered = f"{referenced!s} | {referenced!r}"
            assert all(canary not in rendered for canary in canaries)
            if isinstance(referenced, dict):
                mapping = cast("dict[object, object]", referenced)
                pending.extend(mapping.keys())
                pending.extend(mapping.values())
            elif isinstance(referenced, (list, tuple, set, frozenset)):
                pending.extend(cast("Iterable[object]", referenced))


def _completion_chunk(content: str, **extra: object) -> str:
    """Build one minimal OpenAI-shaped assistant content chunk."""
    document: dict[str, object] = {
        "choices": [
            {
                "index": 0,
                "delta": {"content": content},
                "finish_reason": None,
            }
        ],
        **extra,
    }
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def _successful_stream(
    content: str = "cafe\N{COMBINING ACUTE ACCENT} \N{HOUSE BUILDING}",
    *,
    newline: bytes = b"\n",
) -> bytes:
    """Build one content record followed by an explicit done terminal."""
    data = _completion_chunk(content).encode()
    return b"data: " + data + newline * 2 + b"data: [DONE]" + newline * 2


def _canonical_records() -> tuple[bytes, ...]:
    """Return fresh complete records derived from the immutable composite golden."""
    payload = load_golden_bytes("chat_completions/complete.sse")
    return tuple(record + b"\n\n" for record in payload.rstrip(b"\n").split(b"\n\n"))


def _record_document(record: bytes) -> dict[str, Any]:
    """Return a fresh application document from one canonical data record."""
    data_line = next(line for line in record.splitlines() if line.startswith(b"data:"))
    value = data_line.partition(b":")[2]
    if value.startswith(b" "):
        value = value[1:]
    document = json.loads(value)
    assert isinstance(document, dict)
    return cast("dict[str, Any]", document)


def _data_record(document: object, *, event: str | None = None) -> bytes:
    """Serialize one derived complete SSE application record."""
    event_line = b"" if event is None else f"event: {event}\n".encode()
    data = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode()
    return event_line + b"data: " + data + b"\n\n"


def _derived_finish_record(
    *,
    finish_reason: object,
    include_usage: bool,
) -> bytes:
    """Derive a fresh finish/usage record from the canonical composite fixture."""
    document = _record_document(_canonical_records()[5])
    choices = document["choices"]
    assert isinstance(choices, list)
    assert isinstance(choices[0], dict)
    choices[0]["finish_reason"] = finish_reason
    if not include_usage:
        del document["usage"]
    return _data_record(document)


def _derived_usage_record(field: str, value: object) -> bytes:
    """Build a chat record with one deliberately replaced usage value."""
    usage: dict[str, object] = {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
    }
    usage[field] = value
    return _data_record(
        {
            "choices": [{"delta": {"role": "assistant"}, "finish_reason": None}],
            "usage": usage,
        }
    )


def _terminal_record(
    *,
    finish_reason: object = _OMITTED,
    hermes: object = _OMITTED,
    extra: dict[str, object] | None = None,
) -> bytes:
    """Build one terminal candidate while preserving field omission."""
    choice: dict[str, object] = {"delta": {}}
    if finish_reason is not _OMITTED:
        choice["finish_reason"] = finish_reason
    document: dict[str, object] = {"choices": [choice]}
    if hermes is not _OMITTED:
        document["hermes"] = hermes
    if extra is not None:
        document.update(extra)
    return _data_record(document)


def _terminal_metadata(
    *,
    completed: object = _OMITTED,
    failed: object = _OMITTED,
    partial: object = _OMITTED,
    error_code: object = _OMITTED,
) -> dict[str, object]:
    """Build lifecycle metadata while keeping absent distinct from null."""
    values = {
        "completed": completed,
        "failed": failed,
        "partial": partial,
        "error_code": error_code,
    }
    return {name: value for name, value in values.items() if value is not _OMITTED}


_ACCEPTED_STOP_METADATA = (
    _OMITTED,
    *(
        _terminal_metadata(completed=completed, failed=failed, partial=partial)
        for completed, failed, partial in product(
            (_OMITTED, True),
            (_OMITTED, False),
            (_OMITTED, False),
        )
    ),
)
_ACCEPTED_LENGTH_METADATA = (
    _OMITTED,
    *(
        _terminal_metadata(
            completed=completed,
            failed=failed,
            partial=partial,
            error_code=error_code,
        )
        for completed, failed, partial, error_code in product(
            (_OMITTED, False),
            (_OMITTED, False),
            (_OMITTED, True),
            (_OMITTED, "output_truncated"),
        )
    ),
)
_ACCEPTED_ERROR_METADATA = tuple(
    _terminal_metadata(
        completed=completed,
        failed=failed,
        partial=partial,
        error_code=error_code,
    )
    for completed, failed, partial, error_code in product(
        (_OMITTED, False),
        (_OMITTED, True),
        (False, True),
        (_OMITTED, "agent_error", "future_safe_error"),
    )
)


@pytest.mark.asyncio
async def test_utf8_partitioning_preserves_identical_ordered_events() -> None:
    """Whole, bytewise, and multibyte-split input decode identically."""
    payload = _successful_stream()
    house_start = payload.index("\N{HOUSE BUILDING}".encode())
    partitions = (
        (payload,),
        partition_bytes(payload),
        partition_bytes(
            payload, (1, house_start + 1, house_start + 2, len(payload) - 1)
        ),
    )

    results = tuple([await _decode(parts) for parts in partitions])

    expected = (
        AssistantDeltaEvent(text="cafe\N{COMBINING ACUTE ACCENT} \N{HOUSE BUILDING}"),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )
    assert results == (expected,) * len(partitions)


@pytest.mark.asyncio
@pytest.mark.parametrize("newline", [b"\n", b"\r", b"\r\n"])
async def test_framing_accepts_lf_cr_and_crlf_blank_lines(newline: bytes) -> None:
    """Every standard SSE line ending dispatches complete records."""
    payload = _successful_stream("line-endings", newline=newline)
    split_points = tuple(
        index
        for index in range(1, len(payload))
        if payload[index - 1 : index + 1] == b"\r\n"
    )

    assert await _decode(partition_bytes(payload, split_points)) == (
        AssistantDeltaEvent(text="line-endings"),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_framing_joins_data_and_ignores_standard_unknown_fields() -> None:
    """One optional space is removed and multiline data joins with newline."""
    payload = (
        b"id: contract-1\n"
        b"retry: 1000\n"
        b"future-field: ignored\n"
        b'data:{"choices":\n'
        b'data: [{"delta":{"content":"joined"},"finish_reason":null}]}\n\n'
        b"data: [DONE]\n\n"
    )

    assert await _decode(partition_bytes(payload)) == (
        AssistantDeltaEvent(text="joined"),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_empty_records_and_valueless_unknown_fields_are_ignored() -> None:
    """Empty dispatches and valueless extension fields do not create events."""
    payload = b"\nfuture-field\n\ndata: [DONE]\n\n"

    assert await _decode(partition_bytes(payload)) == (
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_consecutive_framing_records_remain_distinct() -> None:
    """Adjacent application events are dispatched without being merged."""
    first = _completion_chunk("first").encode()
    second = _completion_chunk("second").encode()
    payload = b"data: " + first + b"\n\ndata: " + second + b"\n\ndata: [DONE]\n\n"

    assert await _decode((payload,)) == (
        AssistantDeltaEvent(text="first"),
        AssistantDeltaEvent(text="second"),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["malformed", "oversized"])
async def test_valid_prefix_is_independent_of_failure_chunking(
    failure_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Later invalid bytes cannot erase an already complete event prefix."""
    valid = b"data: " + _completion_chunk("kept").encode() + b"\n\n"
    if failure_kind == "malformed":
        invalid = b"data: {not-json}\n\n"
    else:
        limit = len(valid) + 16
        monkeypatch.setattr("hermes_agent_api_client.sse.MAX_PENDING_BYTES", limit)
        invalid = b"data: " + (b"x" * limit)
    payload = valid + invalid
    partitions = (
        (payload,),
        (valid, invalid),
        partition_bytes(payload),
    )

    results = tuple(
        [await _decode_prefix_before_failure(parts) for parts in partitions]
    )

    assert results == ((AssistantDeltaEvent(text="kept"),),) * len(partitions)


@pytest.mark.asyncio
async def test_comment_record_is_a_keepalive() -> None:
    """A complete comment-only record maps to non-content keepalive state."""
    assert await _decode((b": contract keepalive\n\ndata: [DONE]\n\n",)) == (
        KeepaliveEvent(),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        b"data: \xff\n\n",
        b"data: \xf0\x9f\x8f\n\n",
        b"data: [DONE]",
        b'data: {"choices": []}',
    ],
)
async def test_utf8_and_unterminated_records_fail_safely(payload: bytes) -> None:
    """Invalid encoding and incomplete final records are protocol failures."""
    with pytest.raises(HermesProtocolError):
        await _decode(partition_bytes(payload))


@pytest.mark.asyncio
async def test_pending_byte_bound_accepts_limit_and_rejects_limit_plus_one() -> None:
    """The raw pending-line byte bound has an exact auditable threshold."""
    limit = MAX_PENDING_BYTES
    assert isinstance(limit, int)
    assert not isinstance(limit, bool)
    assert limit > 0

    at_limit = b":" + (b"x" * (limit - 1)) + b"\n\ndata: [DONE]\n\n"
    assert await _decode((at_limit,)) == (
        KeepaliveEvent(),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )

    over_limit = b":" + (b"x" * limit) + b"\n\ndata: [DONE]\n\n"
    with pytest.raises(HermesProtocolError):
        await _decode((over_limit,))


def _data_value_at_size(size: int) -> tuple[str, str]:
    """Build valid application JSON with an exact serialized character size."""
    prefix = '{"choices":[{"delta":{"content":"'
    suffix = '"},"finish_reason":null}]}'
    content_size = size - len(prefix) - len(suffix)
    assert content_size >= 0
    content = "x" * content_size
    return prefix + content + suffix, content


@pytest.mark.asyncio
async def test_event_data_bound_accepts_limit_and_rejects_limit_plus_one() -> None:
    """The joined event-data character bound rejects the first excess value."""
    limit = MAX_EVENT_DATA_CHARS
    assert isinstance(limit, int)
    assert not isinstance(limit, bool)
    assert limit > 0

    at_limit, content = _data_value_at_size(limit)
    payload = f"data: {at_limit}\n\ndata: [DONE]\n\n".encode()
    assert await _decode((payload,)) == (
        AssistantDeltaEvent(text=content),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )

    over_limit, _ = _data_value_at_size(limit + 1)
    with pytest.raises(HermesProtocolError):
        await _decode((f"data: {over_limit}\n\ndata: [DONE]\n\n".encode(),))


@pytest.mark.asyncio
async def test_framing_replay_and_concurrency_are_state_isolated() -> None:
    """Repeated and overlapping calls own independent decoder state."""
    alpha = _successful_stream("alpha")
    beta = _successful_stream("beta")
    expected_alpha = (
        AssistantDeltaEvent(text="alpha"),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )
    expected_beta = (
        AssistantDeltaEvent(text="beta"),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )

    assert await _decode(partition_bytes(alpha)) == expected_alpha
    assert await _decode(partition_bytes(alpha)) == expected_alpha
    results = await asyncio.gather(
        _decode(partition_bytes(alpha)),
        _decode(partition_bytes(beta)),
        _decode((alpha,)),
        _decode((beta,)),
    )
    assert results == [expected_alpha, expected_beta, expected_alpha, expected_beta]


@pytest.mark.asyncio
async def test_role_only_record_is_an_accepted_noop() -> None:
    """The canonical role chunk emits no assistant or metadata event."""
    role, *_, done = _canonical_records()
    assert await _decode((role + done,)) == (
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_assistant_content_record_is_an_isolated_delta() -> None:
    """The canonical content chunk becomes assistant-visible text only."""
    records = _canonical_records()
    assert await _decode((records[1] + records[6],)) == (
        AssistantDeltaEvent(text="The lamp "),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_tool_progress_record_is_isolated_metadata() -> None:
    """The canonical named progress event maps to the closed progress value."""
    records = _canonical_records()
    assert await _decode((records[2] + records[6],)) == (
        ToolProgressEvent(
            tool_call_id="call-contract-001",
            tool_name="home_assistant",
            status=hermes_api.ToolProgressStatus.RUNNING,
        ),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("toolCallId", "!"),
        ("toolCallId", "~" * 256),
        ("tool", "!"),
        ("tool", "~" * 256),
    ],
)
async def test_tool_progress_wire_text_matches_public_exact_bounds(
    field: str,
    value: str,
) -> None:
    """Wire identifiers share the exact public visible-ASCII contract."""
    document = {
        "toolCallId": "call-contract-001",
        "tool": "home_assistant",
        "status": "running",
    }
    document[field] = value

    record = _data_record(document, event="hermes.tool.progress")
    assert await _decode((record + _canonical_records()[6],)) == (
        ToolProgressEvent(
            tool_call_id=value if field == "toolCallId" else "call-contract-001",
            tool_name=value if field == "tool" else "home_assistant",
            status=hermes_api.ToolProgressStatus.RUNNING,
        ),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("toolCallId", ""),
        ("toolCallId", "x" * 257),
        ("toolCallId", "contains space"),
        ("toolCallId", "line\nbreak"),
        ("toolCallId", "café"),
        ("toolCallId", 7),
        ("toolCallId", True),
        ("toolCallId", None),
        ("tool", ""),
        ("tool", "x" * 257),
        ("tool", "contains space"),
        ("tool", "\t"),
        ("tool", "café"),
        ("tool", 7),
        ("tool", True),
        ("tool", None),
    ],
)
async def test_tool_progress_wire_rejects_non_contract_text(
    field: str,
    value: object,
) -> None:
    """Malformed wire lifecycle text fails as a safe protocol error."""
    document: dict[str, object] = {
        "toolCallId": "call-contract-001",
        "tool": "home_assistant",
        "status": "running",
    }
    document[field] = value

    with pytest.raises(HermesProtocolError):
        await _decode((_data_record(document, event="hermes.tool.progress"),))


@pytest.mark.asyncio
@pytest.mark.parametrize("bytewise", [False, True], ids=["whole", "bytewise"])
async def test_tool_progress_pair_fixture_preserves_exact_correlation_and_order(
    bytewise: object,
) -> None:
    """The immutable pair remains running then completed with one exact ID."""
    assert isinstance(bytewise, bool)
    payload = load_golden_bytes("chat_completions/tool_progress_pair.sse")
    parts = partition_bytes(payload) if bytewise else (payload,)

    assert await _decode(parts) == (
        ToolProgressEvent(
            tool_call_id="call_terminal_1",
            tool_name="terminal",
            status=ToolProgressStatus.RUNNING,
        ),
        ToolProgressEvent(
            tool_call_id="call_terminal_1",
            tool_name="terminal",
            status=ToolProgressStatus.COMPLETED,
        ),
        UsageEvent(input_tokens=1, output_tokens=1, total_tokens=2),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_tool_progress_preserves_punctuation_case_repeats_and_interleaving() -> (
    None
):
    """Accepted lifecycle facts are neither normalized, deduplicated, nor reordered."""
    records = tuple(
        _data_record(
            {"toolCallId": call_id, "tool": tool, "status": status},
            event="hermes.tool.progress",
        )
        for call_id, tool, status in (
            ("Call/A?=1", "Tool.Name+CASE", "running"),
            ("other", "second", "running"),
            ("Call/A?=1", "Tool.Name+CASE", "running"),
            ("other", "second", "completed"),
        )
    )

    prefix = await _decode_prefix_before_failure(
        (*records, b"data: {interruption-canary}\n\n")
    )

    assert prefix == (
        ToolProgressEvent(
            tool_call_id="Call/A?=1",
            tool_name="Tool.Name+CASE",
            status=ToolProgressStatus.RUNNING,
        ),
        ToolProgressEvent(
            tool_call_id="other",
            tool_name="second",
            status=ToolProgressStatus.RUNNING,
        ),
        ToolProgressEvent(
            tool_call_id="Call/A?=1",
            tool_name="Tool.Name+CASE",
            status=ToolProgressStatus.RUNNING,
        ),
        ToolProgressEvent(
            tool_call_id="other",
            tool_name="second",
            status=ToolProgressStatus.COMPLETED,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["toolCallId", "tool", "status"])
@pytest.mark.parametrize("conflicting", [False, True], ids=["same", "conflicting"])
async def test_duplicate_approved_tool_members_fail_before_dictionary_collapse(
    field: str,
    conflicting: object,
) -> None:
    """Every repeated approved singleton fails, even when both values agree."""
    assert isinstance(conflicting, bool)
    values = {
        "toolCallId": '"call-contract-001"',
        "tool": '"home_assistant"',
        "status": '"running"',
    }
    duplicate = values[field]
    if conflicting:
        duplicate = {
            "toolCallId": '"call-contract-002"',
            "tool": '"other_tool"',
            "status": '"completed"',
        }[field]
    members = (*values.items(), (field, duplicate))
    record = raw_json_object_sse_record(
        members,
        event="hermes.tool.progress",
    )

    with pytest.raises(HermesProtocolError):
        await _decode((record + _canonical_records()[6],))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["root-hermes", "choice-finish-reason"])
@pytest.mark.parametrize("conflicting", [False, True], ids=["same", "conflicting"])
async def test_duplicate_approved_chat_members_fail_before_materialization(
    path: str,
    conflicting: object,
) -> None:
    """Chat duplicate evidence is checked before nested pairs become mappings."""
    assert isinstance(conflicting, bool)
    if path == "root-hermes":
        duplicate = '{"partial":true}' if conflicting else '{"partial":false}'
        members = (
            (
                "choices",
                '[{"delta":{"content":"kept"},"finish_reason":null}]',
            ),
            ("hermes", '{"partial":false}'),
            ("hermes", duplicate),
        )
    else:
        duplicate = '"stop"' if conflicting else "null"
        members = (
            (
                "choices",
                "["
                '{"delta":{"content":"kept"},'
                f'"finish_reason":null,"finish_reason":{duplicate}'
                "}]",
            ),
        )
    record = raw_json_object_sse_record(members)

    with pytest.raises(HermesProtocolError):
        await _decode((record + _canonical_records()[6],))


@pytest.mark.asyncio
async def test_duplicates_inside_ignored_additive_objects_remain_compatible() -> None:
    """Duplicate spelling outside approved paths does not become an alias."""
    progress = raw_json_object_sse_record(
        (
            ("toolCallId", '"call-contract-001"'),
            ("tool", '"home_assistant"'),
            ("status", '"running"'),
            ("future", '{"status":"running","status":"completed"}'),
        ),
        event="hermes.tool.progress",
    )

    assert await _decode((progress + _canonical_records()[6],)) == (
        ToolProgressEvent(
            tool_call_id="call-contract-001",
            tool_name="home_assistant",
            status=ToolProgressStatus.RUNNING,
        ),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_tool_raw_payloads_and_pair_tree_are_scrubbed_on_failure() -> None:
    """Raw additive data and duplicate evidence never survive protocol failure."""
    canaries = (
        "tool-emoji-canary",
        "tool-label-canary",
        "tool-arguments-canary",
        "tool-results-canary",
        "tool-nested-canary",
    )
    record = raw_json_object_sse_record(
        (
            ("toolCallId", '"call-contract-001"'),
            ("tool", '"home_assistant"'),
            ("status", '"running"'),
            ("status", '"completed"'),
            ("emoji", f'"{canaries[0]}"'),
            ("label", f'"{canaries[1]}"'),
            ("arguments", f'{{"value":"{canaries[2]}"}}'),
            ("results", f'["{canaries[3]}"]'),
            ("raw", f'{{"nested":"{canaries[4]}"}}'),
        ),
        event="hermes.tool.progress",
    )
    stream = cast("AsyncGenerator[object]", async_decode_hermes_sse(_chunks((record,))))

    with pytest.raises(HermesProtocolError) as caught:
        await anext(stream)

    _assert_package_traceback_is_scrubbed(
        caught.value,
        canaries=canaries,
        forbidden_objects=(record,),
    )
    assert cast("_HasAsyncGeneratorFrame", stream).ag_frame is None


@pytest.mark.asyncio
async def test_keepalive_record_is_isolated_metadata() -> None:
    """The canonical comment remains a non-content keepalive event."""
    records = _canonical_records()
    assert await _decode((records[3] + records[6],)) == (
        KeepaliveEvent(),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_usage_record_is_isolated_metadata() -> None:
    """Canonical-derived usage maps exact integer token counts."""
    usage = _derived_finish_record(finish_reason=None, include_usage=True)
    done = _canonical_records()[6]
    assert await _decode((usage + done,)) == (
        UsageEvent(input_tokens=12, output_tokens=6, total_tokens=18),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_finish_record_is_an_isolated_success_terminal() -> None:
    """Canonical-derived stop maps to one explicit success without DONE."""
    finish = _derived_finish_record(finish_reason="stop", include_usage=False)
    assert await _decode((finish,)) == (TerminalEvent(outcome=TerminalOutcome.SUCCESS),)


@pytest.mark.asyncio
async def test_done_record_is_an_isolated_success_terminal() -> None:
    """The canonical DONE sentinel independently establishes success."""
    done = _canonical_records()[6]
    assert await _decode((done,)) == (TerminalEvent(outcome=TerminalOutcome.SUCCESS),)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_name", "accepted"),
    [
        ("message", True),
        ("", True),
        ("hermes.tool.progress", False),
        ("hermes.unknown", False),
    ],
)
@pytest.mark.parametrize("bytewise", [False, True], ids=["whole", "bytewise"])
async def test_done_record_enforces_closed_event_names(
    event_name: str,
    accepted: object,
    bytewise: object,
) -> None:
    """Only unnamed, empty, or explicit message events may carry DONE."""
    assert isinstance(accepted, bool)
    assert isinstance(bytewise, bool)
    record = f"event: {event_name}\ndata: [DONE]\n\n".encode()
    parts = partition_bytes(record) if bytewise else (record,)

    if accepted:
        assert await _decode(parts) == (TerminalEvent(outcome=TerminalOutcome.SUCCESS),)
    else:
        with pytest.raises(HermesProtocolError):
            await _decode(parts)


@pytest.mark.asyncio
async def test_composite_golden_emits_one_success_in_closed_event_order() -> None:
    """Stop plus DONE is one success and all composite records remain ordered."""
    payload = load_golden_bytes("chat_completions/complete.sse")
    assert await _decode(partition_bytes(payload)) == (
        AssistantDeltaEvent(text="The lamp "),
        ToolProgressEvent(
            tool_call_id="call-contract-001",
            tool_name="home_assistant",
            status=hermes_api.ToolProgressStatus.RUNNING,
        ),
        KeepaliveEvent(),
        AssistantDeltaEvent(text="is on."),
        UsageEvent(input_tokens=12, output_tokens=6, total_tokens=18),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_additive_application_fields_are_ignored_at_every_wire_level() -> None:
    """Approved future JSON fields do not alter strict required semantics."""
    document = {
        "future_root": {"ignored": True},
        "choices": [
            {
                "future_choice": 1,
                "delta": {"content": "future-safe", "future_delta": [1, 2]},
                "finish_reason": None,
            }
        ],
        "usage": {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
            "future_usage": "ignored",
        },
    }

    assert await _decode((_data_record(document) + _canonical_records()[6],)) == (
        AssistantDeltaEvent(text="future-safe"),
        UsageEvent(input_tokens=1, output_tokens=2, total_tokens=3),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("hermes", _ACCEPTED_STOP_METADATA)
async def test_stop_terminal_accepts_only_the_total_success_rows(
    hermes: object,
) -> None:
    """Every D-01 accepted omission/boolean row has one exact public value."""
    record = _terminal_record(finish_reason="stop", hermes=hermes)

    assert await _decode((record + _canonical_records()[6],)) == (
        TerminalEvent(
            outcome=TerminalOutcome.SUCCESS,
            partial=False,
            failure_reason=None,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("hermes", _ACCEPTED_LENGTH_METADATA)
async def test_length_terminal_accepts_only_the_total_truncation_rows(
    hermes: object,
) -> None:
    """Every D-02 accepted omission/boolean/code row maps identically."""
    record = _terminal_record(finish_reason="length", hermes=hermes)

    assert await _decode((record + _canonical_records()[6],)) == (
        TerminalEvent(
            outcome=TerminalOutcome.LENGTH,
            partial=True,
            failure_reason=TerminalFailureReason.OUTPUT_TRUNCATED,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("hermes", _ACCEPTED_ERROR_METADATA)
async def test_error_terminal_accepts_only_the_total_upstream_error_rows(
    hermes: object,
) -> None:
    """Every D-03 accepted row preserves partial and closes public reasons."""
    assert isinstance(hermes, dict)
    metadata = cast("dict[str, object]", hermes)
    code = metadata.get("error_code")
    expected_reason = (
        TerminalFailureReason.UNKNOWN
        if code == "future_safe_error"
        else TerminalFailureReason.AGENT_ERROR
    )
    record = _terminal_record(finish_reason="error", hermes=metadata)

    assert await _decode((record + _canonical_records()[6],)) == (
        TerminalEvent(
            outcome=TerminalOutcome.UPSTREAM_ERROR,
            partial=cast("bool", metadata["partial"]),
            failure_reason=expected_reason,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("finish_reason", "hermes"),
    [
        ("stop", _terminal_metadata(completed=False)),
        ("stop", _terminal_metadata(failed=True)),
        ("stop", _terminal_metadata(partial=True)),
        ("stop", _terminal_metadata(error_code="output_truncated")),
        ("length", _terminal_metadata(completed=True)),
        ("length", _terminal_metadata(failed=True)),
        ("length", _terminal_metadata(partial=False)),
        ("length", _terminal_metadata(error_code="agent_error")),
        ("error", _terminal_metadata(partial=False, completed=True)),
        ("error", _terminal_metadata(partial=False, failed=False)),
    ],
    ids=[
        "stop-completed-false",
        "stop-failed-true",
        "stop-partial-true",
        "stop-code-present",
        "length-completed-true",
        "length-failed-true",
        "length-partial-false",
        "length-wrong-code",
        "error-completed-true",
        "error-failed-false",
    ],
)
async def test_contradictory_terminal_rows_fail_without_precedence(
    finish_reason: str,
    hermes: dict[str, object],
) -> None:
    """Every field-level contradiction is rejected rather than normalized."""
    with pytest.raises(HermesProtocolError):
        await _decode(
            (
                _terminal_record(finish_reason=finish_reason, hermes=hermes)
                + _canonical_records()[6],
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason", ["stop", "length", "error"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("completed", None),
        ("completed", 1),
        ("completed", "true"),
        ("failed", None),
        ("failed", 0),
        ("failed", "false"),
        ("partial", None),
        ("partial", 1),
        ("partial", "true"),
        ("error_code", None),
        ("error_code", ""),
        ("error_code", "x" * 257),
        ("error_code", "contains space"),
        ("error_code", 7),
    ],
)
async def test_present_terminal_metadata_requires_exact_types_and_bounds(
    finish_reason: str,
    field: str,
    value: object,
) -> None:
    """Nulls, coercible lookalikes, and unsafe codes fail for every finish."""
    metadata = _terminal_metadata(
        partial=False if finish_reason == "error" else _OMITTED
    )
    metadata[field] = value

    with pytest.raises(HermesProtocolError):
        await _decode(
            (
                _terminal_record(finish_reason=finish_reason, hermes=metadata)
                + _canonical_records()[6],
            )
        )


@pytest.mark.asyncio
async def test_error_requires_root_hermes_and_present_exact_partial() -> None:
    """D-10 rejects both a missing root and an omitted error partial flag."""
    invalid_metadata: tuple[object, ...] = (_OMITTED, {})
    for hermes in invalid_metadata:
        with pytest.raises(HermesProtocolError):
            await _decode(
                (
                    _terminal_record(finish_reason="error", hermes=hermes)
                    + _canonical_records()[6],
                )
            )


@pytest.mark.asyncio
async def test_finish_reason_omission_differs_from_explicit_null() -> None:
    """A missing choice member fails while explicit null remains nonterminal."""
    missing = _terminal_record()
    with pytest.raises(HermesProtocolError):
        await _decode((missing + _canonical_records()[6],))

    explicit_null = _terminal_record(finish_reason=None)
    assert await _decode((explicit_null + _canonical_records()[6],)) == (
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["completed", "failed", "partial", "error_code"],
)
@pytest.mark.parametrize("conflicting", [False, True], ids=["same", "conflicting"])
async def test_duplicate_approved_terminal_members_fail_before_collapse(
    field: str,
    conflicting: object,
) -> None:
    """Repeated lifecycle members fail even when their JSON values agree."""
    assert isinstance(conflicting, bool)
    base = {
        "completed": "false",
        "failed": "true",
        "partial": "false",
        "error_code": '"agent_error"',
    }
    alternate = {
        "completed": "true",
        "failed": "false",
        "partial": "true",
        "error_code": '"future_safe_error"',
    }
    duplicate = alternate[field] if conflicting else base[field]
    hermes_json = (
        "{"
        + ",".join(
            f"{json.dumps(name)}:{value}"
            for name, value in (*base.items(), (field, duplicate))
        )
        + "}"
    )
    record = raw_json_object_sse_record(
        (
            (
                "choices",
                '[{"delta":{},"finish_reason":"error"}]',
            ),
            ("hermes", hermes_json),
        )
    )

    with pytest.raises(HermesProtocolError):
        await _decode((record + _canonical_records()[6],))


@pytest.mark.asyncio
async def test_terminal_metadata_is_root_scoped_and_additive_data_is_discarded() -> (
    None
):
    """Aliases outside root and duplicate members in ignored objects are inert."""
    record = raw_json_object_sse_record(
        (
            (
                "choices",
                '[{"delta":{},"finish_reason":"length",'
                '"partial":false,"error_code":"agent_error"}]',
            ),
            (
                "hermes",
                '{"completed":false,"failed":false,"partial":true,'
                '"error_code":"output_truncated",'
                '"raw":{"partial":false,"partial":true},'
                '"error":{"message":"ignored","message":"still-ignored"}}',
            ),
            ("completed", "true"),
            ("failed", "true"),
            ("partial", "false"),
            ("error_code", '"agent_error"'),
        )
    )

    assert await _decode((record + _canonical_records()[6],)) == (
        TerminalEvent(
            outcome=TerminalOutcome.LENGTH,
            partial=True,
            failure_reason=TerminalFailureReason.OUTPUT_TRUNCATED,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("bytewise", [False, True], ids=["whole", "bytewise"])
@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        (
            "terminal_length.sse",
            (
                UsageEvent(input_tokens=8, output_tokens=4, total_tokens=12),
                TerminalEvent(
                    outcome=TerminalOutcome.LENGTH,
                    partial=True,
                    failure_reason=TerminalFailureReason.OUTPUT_TRUNCATED,
                ),
            ),
        ),
        (
            "terminal_agent_error.sse",
            (
                UsageEvent(input_tokens=8, output_tokens=2, total_tokens=10),
                TerminalEvent(
                    outcome=TerminalOutcome.UPSTREAM_ERROR,
                    partial=False,
                    failure_reason=TerminalFailureReason.AGENT_ERROR,
                ),
            ),
        ),
    ],
)
async def test_terminal_evidence_fixtures_map_to_exact_safe_public_events(
    fixture: str,
    expected: tuple[object, ...],
    bytewise: object,
) -> None:
    """Immutable tag-shaped terminal evidence decodes identically by chunks."""
    assert isinstance(bytewise, bool)
    payload = load_golden_bytes(f"chat_completions/{fixture}")
    parts = partition_bytes(payload) if bytewise else (payload,)

    assert await _decode(parts) == expected


@pytest.mark.asyncio
async def test_tagged_task_exception_contradiction_fails_without_public_prefix() -> (
    None
):
    """The canonical completed/failed contradiction cannot yield usage or terminal."""
    payload = load_golden_bytes(
        "chat_completions/terminal_task_exception_contradiction.sse"
    )

    assert await _decode_prefix_before_failure((payload,)) == ()


@pytest.mark.asyncio
async def test_design_terminal_matrix_is_executable_contract_evidence() -> None:
    """Every immutable design row produces its declared event or rejection."""
    matrix = load_golden_json("chat_completions/terminal_design_matrix.json")
    cases = cast("list[dict[str, Any]]", matrix["cases"])
    done = _canonical_records()[6]
    for case in cases:
        wire = cast("dict[str, object]", case["wire"])
        expected = cast("dict[str, Any]", case["expected"])
        record = _terminal_record(
            finish_reason=wire["finish_reason"],
            hermes=wire.get("hermes", _OMITTED),
        )
        if expected["disposition"] == "reject":
            with pytest.raises(HermesProtocolError):
                await _decode((record + done,))
            continue
        public = cast("dict[str, object]", expected["public_event"])
        assert await _decode((record + done,)) == (
            TerminalEvent(
                outcome=TerminalOutcome(cast("str", public["outcome"])),
                partial=cast("bool", public["partial"]),
                failure_reason=(
                    None
                    if public["failure_reason"] is None
                    else TerminalFailureReason(cast("str", public["failure_reason"]))
                ),
            ),
        )


@pytest.mark.asyncio
async def test_raw_terminal_errors_and_unknown_codes_are_never_retained() -> None:
    """Accepted and rejected terminal records expose only closed safe facts."""
    unknown_code = "terminal-future-private-code-canary"
    accepted = _terminal_record(
        finish_reason="error",
        hermes={
            "partial": True,
            "error_code": unknown_code,
            "error": {"message": "accepted-raw-terminal-error-canary"},
        },
        extra={
            "error": {
                "message": "accepted-root-terminal-error-canary",
                "type": "AcceptedPrivateExceptionCanary",
            }
        },
    )
    accepted_stream = cast(
        "AsyncGenerator[object]",
        async_decode_hermes_sse(_chunks((accepted + _canonical_records()[6],))),
    )
    event = await anext(accepted_stream)
    assert event == TerminalEvent(
        outcome=TerminalOutcome.UPSTREAM_ERROR,
        partial=True,
        failure_reason=TerminalFailureReason.UNKNOWN,
    )
    assert unknown_code not in repr(event)
    with pytest.raises(StopAsyncIteration):
        await anext(accepted_stream)
    assert cast("_HasAsyncGeneratorFrame", accepted_stream).ag_frame is None

    rejected_canaries = (
        "rejected-root-terminal-error-canary",
        "rejected-hermes-terminal-error-canary",
        "RejectedPrivateExceptionCanary",
    )
    rejected = _terminal_record(
        finish_reason="error",
        hermes={
            "completed": True,
            "failed": True,
            "partial": False,
            "error": {"message": rejected_canaries[1]},
        },
        extra={
            "error": {
                "message": rejected_canaries[0],
                "type": rejected_canaries[2],
            }
        },
    )
    with pytest.raises(HermesProtocolError) as caught:
        await _decode((rejected + _canonical_records()[6],))
    _assert_package_traceback_is_scrubbed(
        caught.value,
        canaries=rejected_canaries,
        forbidden_objects=(rejected,),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True], ids=["finish", "standalone"])
async def test_second_done_confirmation_is_rejected_before_terminal_delivery(
    standalone: object,
) -> None:
    """A duplicate DONE cannot expose a terminal before the protocol failure."""
    assert isinstance(standalone, bool)
    finish = _derived_finish_record(finish_reason="length", include_usage=False)
    done = _canonical_records()[6]
    prefix = done + done if standalone else finish + done + done

    assert await _decode_prefix_before_failure((prefix,)) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "parts",
    [
        (),
        (_canonical_records()[3],),
        (_canonical_records()[1],),
    ],
    ids=["empty", "keepalive-only", "clean-pre-terminal-eof"],
)
async def test_non_terminal_disconnects_never_report_success(
    parts: tuple[bytes, ...],
) -> None:
    """Ordinary EOF is a protocol failure without an accepted terminal."""
    with pytest.raises(HermesProtocolError):
        await _decode(parts)


@pytest.mark.asyncio
async def test_application_data_after_terminal_is_rejected() -> None:
    """Post-terminal content fails before the terminal becomes observable."""
    finish = _derived_finish_record(finish_reason="stop", include_usage=False)
    content = _canonical_records()[1]

    assert await _decode_prefix_before_failure((finish + content,)) == ()


@pytest.mark.asyncio
async def test_duplicate_finish_application_data_after_terminal_is_rejected() -> None:
    """Duplicate finish data fails before the terminal becomes observable."""
    finish = _derived_finish_record(finish_reason="stop", include_usage=False)

    assert await _decode_prefix_before_failure((finish + finish,)) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "record",
    [
        b"data: {not-json}\n\n",
        _data_record(None),
        _data_record([], event="hermes.tool.progress"),
        _data_record({"choices": []}),
        _data_record(
            cast("object", {"choices": [{"delta": [], "finish_reason": None}]})
        ),
        _data_record({"choices": [{"delta": {"content": 7}, "finish_reason": None}]}),
        _data_record(
            cast(
                "object",
                {
                    "choices": [{"delta": {}, "finish_reason": None}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2},
                },
            )
        ),
        _data_record({"tool": "home_assistant"}, event="hermes.tool.progress"),
        _data_record(
            {"tool": "home_assistant", "status": "running"},
            event="hermes.tool.progress",
        ),
        _data_record(
            {"toolCallId": "call-contract-001", "tool": "", "status": "running"},
            event="hermes.tool.progress",
        ),
        _data_record(
            {
                "toolCallId": "call-contract-001",
                "tool": "home_assistant",
                "status": "",
            },
            event="hermes.tool.progress",
        ),
        _data_record(
            {
                "toolCallId": "call-contract-001",
                "tool": "home_assistant",
                "status": "queued",
            },
            event="hermes.tool.progress",
        ),
        _derived_usage_record("prompt_tokens", _BOOLEAN_TOKEN_COUNT),
        _derived_usage_record("completion_tokens", -1),
        _derived_usage_record("total_tokens", "3"),
        _data_record(
            {
                "toolCallId": "call-contract-001",
                "tool": "home_assistant",
                "status": "running",
            },
            event="hermes.unknown",
        ),
        _derived_finish_record(finish_reason="mystery", include_usage=False),
    ],
    ids=[
        "invalid-json",
        "non-object",
        "non-object-progress",
        "empty-choices",
        "invalid-delta",
        "invalid-content",
        "invalid-usage",
        "invalid-progress",
        "missing-tool-call-id",
        "empty-tool",
        "empty-status",
        "unknown-status",
        "boolean-token-count",
        "negative-token-count",
        "coercible-token-count",
        "unknown-event",
        "unknown-finish",
    ],
)
async def test_malformed_or_unknown_application_records_fail(record: bytes) -> None:
    """Unknown names, reasons, JSON, and application shapes fail closed."""
    done = _canonical_records()[6]
    with pytest.raises(HermesProtocolError):
        await _decode((record + done,))


@pytest.mark.asyncio
async def test_parser_failures_retain_no_private_input_exception() -> None:
    """Malformed household content is absent from the exception graph."""
    canary = "private-household-parser-canary"
    with pytest.raises(HermesProtocolError) as caught:
        await _decode((f"data: {{{canary}}}\n\n".encode(),))

    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert canary not in "".join(traceback.format_exception(error))


@pytest.mark.asyncio
async def test_wire_validation_failures_retain_no_private_input_exception() -> None:
    """Pydantic validation details and raw values do not escape publicly."""
    canary = "private-pydantic-validation-canary"
    record = _data_record(
        {
            "choices": [
                {
                    "delta": {"role": canary},
                    "finish_reason": None,
                }
            ]
        }
    )
    with pytest.raises(HermesProtocolError) as caught:
        await _decode((record,))

    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert canary not in "".join(traceback.format_exception(error))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event", "document"),
    [
        (
            "hermes.tool.progress",
            {
                "toolCallId": "call-contract-001",
                "tool": "home_assistant",
                "status": "running",
            },
        ),
        (
            None,
            {
                "choices": [
                    {"delta": {"content": "not-retained"}, "finish_reason": None}
                ]
            },
        ),
    ],
    ids=["tool", "chat"],
)
async def test_pair_materialization_recursion_fails_as_protocol_error(
    event: str | None,
    document: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A projection recursion limit remains a sanitized protocol failure."""

    def fail_materialization(_: object) -> object:
        raise RecursionError

    monkeypatch.setattr(
        "hermes_agent_api_client.protocol._materialize_json_value",
        fail_materialization,
    )

    with pytest.raises(HermesProtocolError):
        await _decode((_data_record(document, event=event),))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("invalid_data", "canary"),
    [
        ("{direct-sse-json-frame-canary}", "direct-sse-json-frame-canary"),
        (
            '{"choices":[{"delta":{"role":"direct-sse-wire-frame-canary"},"finish_reason":null}]}',
            "direct-sse-wire-frame-canary",
        ),
    ],
    ids=["malformed-json", "invalid-wire"],
)
async def test_direct_sse_failures_scrub_raw_payloads_from_traceback_frames(
    invalid_data: str,
    canary: str,
) -> None:
    """Malformed records retain neither raw bytes nor decoded record values."""
    prior_canary = "direct-sse-prior-delta-canary"
    payload = (
        b"data: "
        + _completion_chunk(prior_canary).encode()
        + b"\n\ndata: "
        + invalid_data.encode()
        + b"\n\ntrailing-ignored-after-failure"
    )
    with pytest.raises(HermesProtocolError) as caught:
        await _decode((payload,))

    _assert_package_traceback_is_scrubbed(
        caught.value,
        canaries=(prior_canary, canary),
        forbidden_objects=(payload,),
    )


@pytest.mark.asyncio
async def test_iterator_acquisition_error_becomes_scrubbed_transport_failure() -> None:
    """An iterable's `__aiter__` error cannot escape as a raw public failure."""
    canary = "direct-sse-aiter-raw-canary"
    failure = RuntimeError(canary)
    source = _AiterFailure(failure, canary=canary)

    with pytest.raises(HermesTransportError) as caught:
        tuple([event async for event in async_decode_hermes_sse(source)])

    assert caught.value.retryable
    _assert_package_traceback_is_scrubbed(
        caught.value,
        canaries=(canary,),
        forbidden_objects=(source, failure),
    )


@pytest.mark.asyncio
async def test_iterator_acquisition_cancellation_preserves_identity_and_state() -> None:
    """A primary `__aiter__` cancellation remains exact and source-free."""
    canary = "direct-sse-aiter-source-canary"
    cancellation = asyncio.CancelledError("direct-sse-aiter-cancellation")
    source = _AiterFailure(cancellation, canary=canary)

    with pytest.raises(asyncio.CancelledError) as caught:
        tuple([event async for event in async_decode_hermes_sse(source)])

    assert caught.value is cancellation
    _assert_package_traceback_is_scrubbed(
        caught.value,
        canaries=(canary,),
        forbidden_objects=(source,),
    )


@pytest.mark.asyncio
async def test_iterator_acquisition_accepts_normal_iterables() -> None:
    """The guarded entry boundary retains normal iterator behavior."""
    source = _UnclosableChunks((_successful_stream("aiter-control"),))

    assert tuple([event async for event in async_decode_hermes_sse(source)]) == (
        AssistantDeltaEvent(text="aiter-control"),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_protocol_failure_wins_over_close_error_and_scrubs_cleanup_state() -> (
    None
):
    """A malformed record cannot be replaced by an opaque close failure."""
    payload_canary = "primary-sse-payload-close-canary"
    close_canary = "secondary-sse-close-canary"
    payload = f"data: {{{payload_canary}}}\n\n".encode()
    close_failure = RuntimeError(close_canary)
    source = _ClosableChunks((payload,), close_failure=close_failure)

    with pytest.raises(HermesProtocolError) as caught:
        tuple([event async for event in async_decode_hermes_sse(source)])

    assert source.closed
    _assert_package_traceback_is_scrubbed(
        caught.value,
        canaries=(payload_canary, close_canary),
        forbidden_objects=(source, payload, close_failure),
    )


@pytest.mark.asyncio
async def test_primary_source_cancellation_wins_over_close_cancellation() -> None:
    """The original cancellation identity survives secondary source cleanup."""
    primary = asyncio.CancelledError("primary-sse-read-cancellation")
    secondary = asyncio.CancelledError("secondary-sse-close-cancellation")
    source = _ClosableChunks((), read_failure=primary, close_failure=secondary)

    with pytest.raises(asyncio.CancelledError) as caught:
        tuple([event async for event in async_decode_hermes_sse(source)])

    assert caught.value is primary
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert source.closed


@pytest.mark.asyncio
async def test_cleanup_only_close_error_becomes_safe_transport_failure() -> None:
    """A close failure after a valid terminal never exposes the raw exception."""
    close_canary = "cleanup-only-sse-close-canary"
    payload = b"data: [DONE]\n\n"
    close_failure = RuntimeError(close_canary)
    source = _ClosableChunks((payload,), close_failure=close_failure)

    with pytest.raises(HermesTransportError) as caught:
        tuple([event async for event in async_decode_hermes_sse(source)])

    assert source.closed
    assert caught.value.retryable
    _assert_package_traceback_is_scrubbed(
        caught.value,
        canaries=(close_canary,),
        forbidden_objects=(source, payload, close_failure),
    )


@pytest.mark.asyncio
async def test_cleanup_only_close_cancellation_propagates_unchanged() -> None:
    """A cancellation from otherwise-successful cleanup remains observable."""
    cleanup = asyncio.CancelledError("cleanup-only-sse-cancellation")
    source = _ClosableChunks((b"data: [DONE]\n\n",), close_failure=cleanup)

    with pytest.raises(asyncio.CancelledError) as caught:
        tuple([event async for event in async_decode_hermes_sse(source)])

    assert caught.value is cleanup
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert source.closed


@pytest.mark.asyncio
async def test_early_close_error_becomes_safe_transport_failure() -> None:
    """Consumer-triggered shutdown maps an opaque cleanup failure safely."""
    close_canary = "early-close-sse-cleanup-canary"
    payload = b"data: " + _completion_chunk("early-close-content").encode() + b"\n\n"
    close_failure = RuntimeError(close_canary)
    source = _ClosableChunks((payload,), close_failure=close_failure)
    stream = cast("AsyncGenerator[object]", async_decode_hermes_sse(source))

    assert await anext(stream) == AssistantDeltaEvent(text="early-close-content")
    with pytest.raises(HermesTransportError) as caught:
        await stream.aclose()

    assert source.closed
    assert caught.value.retryable
    _assert_package_traceback_is_scrubbed(
        caught.value,
        canaries=(close_canary,),
        forbidden_objects=(source, payload, close_failure),
    )


@pytest.mark.asyncio
async def test_early_close_cancellation_propagates_unchanged() -> None:
    """Consumer shutdown preserves a cleanup-only cancellation identity."""
    cleanup = asyncio.CancelledError("early-close-sse-cleanup-cancellation")
    source = _ClosableChunks(
        (b"data: " + _completion_chunk("early-close-content").encode() + b"\n\n",),
        close_failure=cleanup,
    )
    stream = cast("AsyncGenerator[object]", async_decode_hermes_sse(source))

    assert await anext(stream) == AssistantDeltaEvent(text="early-close-content")
    with pytest.raises(asyncio.CancelledError) as caught:
        await stream.aclose()

    assert caught.value is cleanup
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert source.closed


@pytest.mark.asyncio
async def test_empty_delta_without_semantics_is_rejected() -> None:
    """A chat chunk must carry role, content, usage, or a finish reason."""
    record = _data_record(
        cast("object", {"choices": [{"delta": {}, "finish_reason": None}]})
    )
    with pytest.raises(HermesProtocolError):
        await _decode((record,))


@pytest.mark.asyncio
async def test_non_bytes_chunks_are_rejected() -> None:
    """The byte framing boundary rejects lookalike transport values."""
    with pytest.raises(HermesProtocolError):
        await _decode((cast("bytes", "not-bytes"),))


@pytest.mark.asyncio
async def test_incomplete_utf8_at_raw_eof_is_rejected() -> None:
    """An incomplete multibyte sequence cannot survive final decoder flush."""
    with pytest.raises(HermesProtocolError):
        await _decode((b"\xf0",))


@pytest.mark.asyncio
async def test_cancelled_stream_propagates_cancellation_unchanged() -> None:
    """Cancellation is never translated into a protocol event or success."""
    content = _canonical_records()[1]

    async def cancelled_chunks() -> AsyncIterator[bytes]:
        yield content
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        tuple([event async for event in async_decode_hermes_sse(cancelled_chunks())])


@pytest.mark.asyncio
async def test_decoder_close_closes_the_upstream_async_generator() -> None:
    """Early consumer closure releases an owned upstream stream immediately."""
    closed = False
    content = _canonical_records()[1]
    wait_forever = asyncio.Event()

    async def source() -> AsyncIterator[bytes]:
        nonlocal closed
        try:
            yield content
            await wait_forever.wait()
        finally:
            closed = True

    stream = cast("AsyncGenerator[object]", async_decode_hermes_sse(source()))
    assert await anext(stream) == AssistantDeltaEvent(text="The lamp ")

    await stream.aclose()

    assert closed


@pytest.mark.asyncio
async def test_decoder_accepts_an_async_iterator_without_close_support() -> None:
    """Optional upstream closure support is not required for valid decoding."""
    source = _UnclosableChunks((_successful_stream("plain-iterator"),))

    assert tuple([event async for event in async_decode_hermes_sse(source)]) == (
        AssistantDeltaEvent(text="plain-iterator"),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
    )


@pytest.mark.asyncio
async def test_only_assistant_deltas_contribute_to_assistant_text() -> None:
    """Progress, usage, keepalive, and terminal values never become text."""
    events = await _decode(
        partition_bytes(load_golden_bytes("chat_completions/complete.sse"))
    )
    assistant_text = "".join(
        event.text for event in events if isinstance(event, AssistantDeltaEvent)
    )

    assert assistant_text == "The lamp is on."
    for non_content in (
        "home_assistant",
        "running",
        "12",
        "18",
        TerminalOutcome.SUCCESS.value,
    ):
        assert non_content not in assistant_text


@pytest.mark.asyncio
async def test_composite_replay_and_concurrency_preserve_terminal_state() -> None:
    """Full application interpretation remains deterministic per invocation."""
    payload = load_golden_bytes("chat_completions/complete.sse")
    first = await _decode(partition_bytes(payload))
    replay, whole, bytewise = await asyncio.gather(
        _decode(partition_bytes(payload)),
        _decode((payload,)),
        _decode(partition_bytes(payload)),
    )
    assert replay == whole == bytewise == first
