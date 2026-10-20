"""Public client lifecycle, ownership, and bound-operation tests."""

from __future__ import annotations

import asyncio
import inspect
import json
import ssl
import traceback
from contextlib import asynccontextmanager
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol, cast
from unittest.mock import patch

import httpx
import pytest

from hermes_agent_api_client import (
    AssistantDeltaEvent,
    HermesAgentApiClient,
    HermesAuthenticationError,
    HermesEvent,
    HermesHttpStatusError,
    HermesProtocolError,
    HermesTransportError,
    KeepaliveEvent,
    TerminalEvent,
    TerminalOutcome,
)
from hermes_agent_api_client.client import (
    _MAX_CAPABILITIES_BYTES,  # pyright: ignore[reportPrivateUsage]
)
from hermes_agent_api_client.models import FailureCategory
from hermes_agent_api_client.protocol import (
    HermesCapabilityError,
    HermesIdentityError,
)
from hermes_agent_api_client.sse import (
    MAX_EVENT_DATA_CHARS,  # pyright: ignore[reportPrivateUsage]
)
from tests.helpers.hermes import load_golden_json

if TYPE_CHECKING:
    from collections.abc import (
        AsyncGenerator,
        AsyncIterator,
        Callable,
        Iterable,
        Mapping,
    )
    from types import FrameType, TracebackType


_INACTIVE_MESSAGE = "HermesAgentApiClient is not active"
_SINGLE_USE_MESSAGE = "HermesAgentApiClient instances are single-use"
_VERIFY_INJECTION_MESSAGE = "verify cannot be supplied with an injected HTTP client"
_BASE_URL_CANARY = "https://hermes.example/private-base"
_BEARER_KEY_CANARY = "lifecycle-bearer-key-canary"
_UPSTREAM_STATUS_CODE = 503
_AUTHENTICATION_STATUS_CODE = 401
_UPSTREAM_STATUS_MESSAGE = "upstream status"
_MIN_UNIQUE_CANARY_LENGTH = 4
_LOCAL_INPUT_FAILURE_TEXT = "Hermes transport failure (status=none, retryable=false)"
_LOCAL_INPUT_FAILURE_REPR = (
    "HermesTransportError(category='transport', status_code=None, retryable=False)"
)
_GATE_TIMEOUT_SECONDS = 5


class AsyncClientFactorySpy:
    """Return one real client and record the owned-client constructor options."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """Store the client returned by each constructor call."""
        self.http_client = http_client
        self.calls: list[tuple[ssl.SSLContext | bool, bool]] = []

    def __call__(
        self,
        *,
        verify: ssl.SSLContext | bool,
        follow_redirects: bool,
    ) -> httpx.AsyncClient:
        """Record constructor options and return the configured client."""
        self.calls.append((verify, follow_redirects))
        return self.http_client


class RaisingCloseTransport(httpx.AsyncBaseTransport):
    """Raise a controlled failure when an owned HTTP client closes."""

    def __init__(self, failure: BaseException) -> None:
        """Store the exact close failure for graph-identity assertions."""
        self.failure = failure

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Reject requests because this transport exists only for close."""
        raise AssertionError(request)

    async def aclose(self) -> None:
        """Raise the controlled close failure."""
        raise self.failure


class CancellingRequestTransport(httpx.AsyncBaseTransport):
    """Raise one exact cancellation while opening a public operation."""

    def __init__(self, cancellation: asyncio.CancelledError) -> None:
        """Store the exact cancellation for identity assertions."""
        self.cancellation = cancellation

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Raise the configured cancellation before a response exists."""
        del request
        raise self.cancellation


class StatusFailingRequestTransport(httpx.AsyncBaseTransport):
    """Raise a controlled HTTP status error while opening one request."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Raise the status error with the request-local response."""
        response = httpx.Response(_UPSTREAM_STATUS_CODE, request=request)
        raise httpx.HTTPStatusError(
            _UPSTREAM_STATUS_MESSAGE,
            request=request,
            response=response,
        )


class TrackingAsyncByteStream(httpx.AsyncByteStream):
    """Yield controlled SSE bytes and record response-scope closure."""

    def __init__(
        self,
        chunks: tuple[bytes, ...],
        *,
        close_failure: BaseException | None = None,
        iteration_failure: BaseException | None = None,
    ) -> None:
        """Store chunks, optional failures, and a close marker."""
        self.chunks = chunks
        self.close_failure = close_failure
        self.iteration_failure = iteration_failure
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield each configured chunk cooperatively."""
        for chunk in self.chunks:
            yield chunk
        if self.iteration_failure is not None:
            raise self.iteration_failure

    async def aclose(self) -> None:
        """Record response cleanup."""
        self.closed = True
        if self.close_failure is not None:
            raise self.close_failure


class GatedAsyncByteStream(httpx.AsyncByteStream):
    """Yield one chunk, signal the gate, then block until cancelled."""

    def __init__(self, first_chunk: bytes) -> None:
        """Store the first chunk, the gate and a close marker."""
        self.first_chunk = first_chunk
        self.blocked = asyncio.Event()
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield the first chunk, signal the gate and then wait forever."""
        yield self.first_chunk
        self.blocked.set()
        await asyncio.Event().wait()

    async def wait_until_blocked(self, consumer: asyncio.Task[None]) -> None:
        """Wait for the gate, failing fast if the consumer ends or stalls first."""
        gate = asyncio.create_task(self.blocked.wait())
        try:
            async with asyncio.timeout(_GATE_TIMEOUT_SECONDS):
                await asyncio.wait(
                    {consumer, gate},
                    return_when=asyncio.FIRST_COMPLETED,
                )
        except TimeoutError:
            consumer.cancel()
            raise
        finally:
            gate.cancel()
        if consumer.done():
            # Surface the consumer failure that ended the stream early.
            await consumer
        assert self.blocked.is_set(), "stream ended before reaching the gate"

    async def aclose(self) -> None:
        """Record response-scope closure."""
        self.closed = True


class UnclosableHermesEvents:
    """A valid delegated event iterator without optional close support."""

    def __init__(self, events: tuple[HermesEvent, ...]) -> None:
        """Store deterministic events for asynchronous iteration."""
        self.events = iter(events)

    def __aiter__(self) -> UnclosableHermesEvents:
        """Return this asynchronous iterator."""
        return self

    async def __anext__(self) -> HermesEvent:
        """Return the next event cooperatively."""
        await asyncio.sleep(0)
        try:
            return next(self.events)
        except StopIteration:
            raise StopAsyncIteration from None


class CancellingCloseHermesEvents(UnclosableHermesEvents):
    """A delegated iterator whose explicit close is cancelled."""

    def __init__(self, cancellation: asyncio.CancelledError) -> None:
        """Store the exact cancellation object for identity checks."""
        super().__init__(())
        self.cancellation = cancellation

    async def aclose(self) -> None:
        """Raise the exact configured cancellation."""
        await asyncio.sleep(0)
        raise self.cancellation


class FailingCloseHermesEvents:
    """Raise one primary iteration failure and a distinct close cancellation."""

    def __init__(
        self,
        primary_failure: BaseException,
        close_cancellation: asyncio.CancelledError,
    ) -> None:
        """Store exact primary and secondary failures for identity assertions."""
        self.primary_failure = primary_failure
        self.close_cancellation = close_cancellation

    def __aiter__(self) -> FailingCloseHermesEvents:
        """Return this iterator for one public delegated stream."""
        return self

    async def __anext__(self) -> HermesEvent:
        """Raise the configured primary failure while reading the stream."""
        raise self.primary_failure

    async def aclose(self) -> None:
        """Raise the distinct cancellation while public cleanup runs."""
        raise self.close_cancellation


class _HasAsyncGeneratorFrame(Protocol):
    """Structural view of the CPython async-generator inspection surface."""

    @property
    def ag_frame(self) -> FrameType | None:
        """Return the retained generator frame, if the generator is open."""
        ...


def _assert_suspended_stream_retains_no_secrets(
    stream: object,
    *,
    canaries: tuple[str, ...],
) -> None:
    """Assert a paused public stream frame holds no session or bearer values.

    This check must run while the generator is suspended, because that is the
    only window in which its locals are observable. CPython always clears
    ``ag_frame`` once a generator finishes, so post-exit checks prove nothing
    about retention.
    """
    frame = cast("_HasAsyncGeneratorFrame", stream).ag_frame
    assert frame is not None
    frame_locals: dict[str, object] = dict(frame.f_locals)
    assert frame_locals
    rendered = repr(frame_locals)
    assert all(canary not in rendered for canary in canaries)


def _package_traceback_locals(error: BaseException) -> tuple[dict[str, object], ...]:
    """Snapshot package-owned traceback locals for lifecycle secrecy checks."""
    frames: list[dict[str, object]] = []
    cursor: TracebackType | None = error.__traceback__
    while cursor is not None:
        module_name = cursor.tb_frame.f_globals.get("__name__")
        if isinstance(module_name, str) and module_name.startswith(
            "hermes_agent_api_client"
        ):
            frames.append(dict(cursor.tb_frame.f_locals))
        cursor = cursor.tb_next
    assert frames
    return tuple(frames)


def _assert_safe_lifecycle_error(
    error: BaseException,
    *,
    expected_message: str,
    client: HermesAgentApiClient | None = None,
    canaries: tuple[str, ...] = (_BASE_URL_CANARY, _BEARER_KEY_CANARY),
) -> None:
    """Assert constant text and no retained client carrying bound secrets."""
    assert str(error) == expected_message
    assert all(canary not in str(error) for canary in canaries)
    for frame_locals in _package_traceback_locals(error):
        if client is not None:
            assert all(value is not client for value in frame_locals.values())
        rendered = repr(frame_locals)
        assert all(canary not in rendered for canary in canaries)


def _assert_no_sensitive_traceback_references(
    error: BaseException,
    *,
    canaries: tuple[str, ...],
    forbidden_objects: tuple[object, ...],
) -> None:
    """Reject raw cleanup state from all package traceback-local containers."""
    rendered_error = "".join(traceback.format_exception(error))
    assert all(canary not in rendered_error for canary in canaries)
    for frame_locals in _package_traceback_locals(error):
        pending: list[object] = list(frame_locals.values())
        visited: set[int] = set()
        while pending:
            value = pending.pop()
            identity = id(value)
            if identity in visited:
                continue
            visited.add(identity)
            assert all(value is not forbidden for forbidden in forbidden_objects)
            assert not isinstance(
                value,
                (httpx.AsyncClient, httpx.Response, HermesAgentApiClient),
            )
            rendered = repr(value)
            assert all(canary not in rendered for canary in canaries)
            if isinstance(value, dict):
                mapping = cast("dict[object, object]", value)
                pending.extend(mapping.keys())
                pending.extend(mapping.values())
            elif isinstance(value, (list, tuple, set, frozenset)):
                pending.extend(cast("Iterable[object]", value))


def _assert_fresh_cleanup_transport_failure(
    error: HermesTransportError,
    *,
    raw_error: Exception,
    canaries: tuple[str, ...],
    forbidden_objects: tuple[object, ...],
) -> None:
    """Assert cleanup errors become fresh metadata-only transport failures."""
    assert type(error) is HermesTransportError
    assert error.category is FailureCategory.TRANSPORT
    assert error.status_code is None
    assert error.retryable is True
    assert str(error) == "Hermes transport failure (status=none, retryable=true)"
    assert repr(error) == (
        "HermesTransportError(category='transport', status_code=None, retryable=True)"
    )
    assert error is not raw_error
    assert error.__cause__ is None
    assert error.__context__ is None
    _assert_no_sensitive_traceback_references(
        error,
        canaries=canaries,
        forbidden_objects=(raw_error, *forbidden_objects),
    )


async def _assert_operations_inactive(client: HermesAgentApiClient) -> None:
    """Assert both public operations reject an inactive lifecycle state."""
    with pytest.raises(RuntimeError) as probe_failure:
        await client.probe_capabilities()
    _assert_safe_lifecycle_error(
        probe_failure.value,
        expected_message=_INACTIVE_MESSAGE,
        client=client,
    )

    request = {"private": "inactive-request-canary"}
    with pytest.raises(RuntimeError) as stream_failure:
        await anext(
            client.stream_chat_events(
                request,
                session_id="inactive-session-canary",
                session_key="inactive-key-canary",
            )
        )
    _assert_safe_lifecycle_error(
        stream_failure.value,
        expected_message=_INACTIVE_MESSAGE,
        client=client,
        canaries=(
            _BASE_URL_CANARY,
            _BEARER_KEY_CANARY,
            "inactive-request-canary",
            "inactive-session-canary",
            "inactive-key-canary",
        ),
    )


def _successful_transport(
    requests: list[httpx.Request],
) -> Callable[[httpx.Request], httpx.Response]:
    """Build a transport handler for one stream followed by one probe."""

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/v1/capabilities"):
            return httpx.Response(
                200,
                request=request,
                json=load_golden_json("capabilities/supported.json"),
            )
        return httpx.Response(
            200,
            request=request,
            content=(
                b'data: {"choices":[{"index":0,"delta":{"content":"hello"},'
                b'"finish_reason":null}]}\n\ndata: [DONE]\n\n'
            ),
        )

    return respond


def _post_dispatch_failure_case(
    case: str,
    requests: list[httpx.Request],
    cancellation: asyncio.CancelledError,
) -> tuple[Callable[[httpx.Request], httpx.Response], type[BaseException]]:
    """Build a recording failure handler and its exact public failure type."""

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if case == "authentication-401":
            return httpx.Response(_AUTHENTICATION_STATUS_CODE, request=request)
        if case == "status-503":
            return httpx.Response(_UPSTREAM_STATUS_CODE, request=request)
        if case == "protocol-malformed-sse":
            return httpx.Response(
                200,
                request=request,
                content=b"data: {malformed}\n\n",
            )
        if case == "transport-connect-error":
            message = (
                f"connect failed for {request.headers['X-Hermes-Session-Id']} "
                f"with {request.headers['X-Hermes-Session-Key']}"
            )
            raise httpx.ConnectError(message, request=request)
        raise cancellation

    expected_types: dict[str, type[BaseException]] = {
        "authentication-401": HermesAuthenticationError,
        "status-503": HermesHttpStatusError,
        "protocol-malformed-sse": HermesProtocolError,
        "transport-connect-error": HermesTransportError,
        "request-stage-cancellation": asyncio.CancelledError,
    }
    return respond, expected_types[case]


def _advertise_wrong_platform(document: dict[str, object]) -> None:
    """Make one otherwise-supported document fail endpoint identity."""
    document["platform"] = "public-identity-body-canary"


def _advertise_unsupported_chat(document: dict[str, object]) -> None:
    """Make one otherwise-supported document fail required chat support."""
    features = cast("dict[str, object]", document["features"])
    features["chat_completions"] = "public-capability-body-canary"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("session_id", "session_key", "expected_headers"),
    [
        (None, None, {}),
        ("profile.chat-001", None, {"X-Hermes-Session-Id": "profile.chat-001"}),
        (None, "instance-key-001", {"X-Hermes-Session-Key": "instance-key-001"}),
        ("!", None, {"X-Hermes-Session-Id": "!"}),
        ("~" * 256, None, {"X-Hermes-Session-Id": "~" * 256}),
        (
            None,
            "../opaque\\key",
            {"X-Hermes-Session-Key": "../opaque\\key"},
        ),
        (
            "profile.chat-001",
            "instance-key-001",
            {
                "X-Hermes-Session-Id": "profile.chat-001",
                "X-Hermes-Session-Key": "instance-key-001",
            },
        ),
    ],
    ids=[
        "neither",
        "session-id",
        "session-key",
        "minimum-session-id",
        "maximum-session-id",
        "path-shaped-session-key",
        "both",
    ],
)
async def test_stream_session_headers_are_independent_and_request_scoped(
    session_id: str | None,
    session_key: str | None,
    expected_headers: dict[str, str],
) -> None:
    """Session arguments map independently without mutating caller state."""
    requests: list[httpx.Request] = []
    request_document: dict[str, object] = {
        "model": "hermes",
        "messages": (),
        "stream": True,
    }
    original_document = request_document.copy()
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    bound_headers = client._headers.copy()  # pyright: ignore[reportPrivateUsage]
    try:
        async with client:
            events = tuple(
                [
                    event
                    async for event in client.stream_chat_events(
                        request_document,
                        session_id=session_id,
                        session_key=session_key,
                    )
                ]
            )

        assert events == (
            AssistantDeltaEvent(text="hello"),
            TerminalEvent(outcome=TerminalOutcome.SUCCESS),
        )
        assert len(requests) == 1
        sent = requests[0]
        for name in ("X-Hermes-Session-Id", "X-Hermes-Session-Key"):
            if name in expected_headers:
                assert sent.headers[name] == expected_headers[name]
            else:
                assert name not in sent.headers
        assert request_document == original_document
        assert client._headers == bound_headers  # pyright: ignore[reportPrivateUsage]
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


class _SessionStringSubclass(str):
    """A string subclass forbidden by the exact public session contract."""

    __slots__ = ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        "",
        " ",
        " leading-space",
        "leading-space ",
        "embedded space",
        "line\nbreak",
        "nul\x00byte",
        "delete\x7fbyte",
        "café",
        "x" * 257,
        _SessionStringSubclass("subclass-canary"),
        7,
    ],
    ids=[
        "empty",
        "space",
        "leading-space",
        "trailing-space",
        "embedded-space",
        "newline",
        "nul",
        "delete",
        "non-ascii",
        "too-long",
        "subclass",
        "non-string",
    ],
)
@pytest.mark.parametrize("argument", ["session_id", "session_key"])
async def test_invalid_session_arguments_fail_locally_without_dispatch(
    argument: str,
    invalid: object,
) -> None:
    """Invalid session values use the safe non-retryable input failure."""
    requests: list[httpx.Request] = []
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            if argument == "session_id":
                stream = client.stream_chat_events(
                    {"model": "hermes"},
                    session_id=cast("str", invalid),
                )
            else:
                stream = client.stream_chat_events(
                    {"model": "hermes"},
                    session_key=cast("str", invalid),
                )
            with pytest.raises(HermesTransportError) as caught:
                await anext(stream)

        assert caught.value.retryable is False
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert requests == []
        _assert_no_sensitive_traceback_references(
            caught.value,
            canaries=(
                (str(invalid),)
                if isinstance(invalid, str)
                and len(invalid.strip()) >= _MIN_UNIQUE_CANARY_LENGTH
                else ()
            ),
            forbidden_objects=(invalid, client, injected_http_client),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_session_id",
    ["..", "profile/child", "profile\\child", "C:profile"],
    ids=["parent", "slash", "backslash", "drive-prefix"],
)
async def test_path_shaped_session_ids_fail_before_dispatch(
    invalid_session_id: str,
) -> None:
    """Transcript identifiers cannot be interpreted as filesystem paths."""
    requests: list[httpx.Request] = []
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesTransportError) as caught:
                await anext(
                    client.stream_chat_events(
                        {"model": "hermes"},
                        session_id=invalid_session_id,
                    )
                )

        assert caught.value.retryable is False
        assert requests == []
        _assert_no_sensitive_traceback_references(
            caught.value,
            canaries=(
                (invalid_session_id,)
                if len(invalid_session_id) >= _MIN_UNIQUE_CANARY_LENGTH
                else ()
            ),
            forbidden_objects=(
                invalid_session_id,
                client,
                injected_http_client,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("session_id", "session_key"),
    [
        ("valid-session-id-canary", "invalid session-key-canary"),
        ("invalid session-id-canary", "valid-session-key-canary"),
    ],
    ids=["invalid-key", "invalid-id"],
)
async def test_invalid_session_pair_is_atomic_and_secret_free(
    session_id: str,
    session_key: str,
) -> None:
    """One invalid value prevents dispatch without retaining either value."""
    requests: list[httpx.Request] = []
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesTransportError) as caught:
                await anext(
                    client.stream_chat_events(
                        {"model": "hermes"},
                        session_id=session_id,
                        session_key=session_key,
                    )
                )

        assert caught.value.retryable is False
        assert requests == []
        _assert_no_sensitive_traceback_references(
            caught.value,
            canaries=(session_id, session_key),
            forbidden_objects=(client, injected_http_client),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_concurrent_streams_isolate_session_headers() -> None:
    """Concurrent calls use fresh headers without cross-request contamination."""
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)
        requests.append(request)
        return httpx.Response(
            200,
            request=request,
            content=(
                b'data: {"choices":[{"index":0,"delta":{"content":"ok"},'
                b'"finish_reason":null}]}\n\ndata: [DONE]\n\n'
            ),
        )

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    bound_headers = client._headers.copy()  # pyright: ignore[reportPrivateUsage]

    async def collect(index: int) -> tuple[HermesEvent, ...]:
        return tuple(
            [
                event
                async for event in client.stream_chat_events(
                    {"model": "hermes"},
                    session_id=f"session-{index}",
                    session_key=f"key-{index}",
                )
            ]
        )

    try:
        async with client:
            results = await asyncio.gather(*(collect(index) for index in range(8)))

        assert all(
            result
            == (
                AssistantDeltaEvent(text="ok"),
                TerminalEvent(outcome=TerminalOutcome.SUCCESS),
            )
            for result in results
        )
        assert {
            (
                request.headers["X-Hermes-Session-Id"],
                request.headers["X-Hermes-Session-Key"],
            )
            for request in requests
        } == {(f"session-{index}", f"key-{index}") for index in range(8)}
        assert client._headers == bound_headers  # pyright: ignore[reportPrivateUsage]
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_injected_client_survives_public_stream_task_cancellation() -> None:
    """Mid-iteration task cancellation closes only the response and propagates."""
    session_id = "cancel-mid-session-id-canary"
    session_key = "cancel-mid-session-key-canary"
    gated = GatedAsyncByteStream(
        b'data: {"choices":[{"index":0,"delta":{"content":"hello"},'
        b'"finish_reason":null}]}\n\n'
    )
    requests: list[httpx.Request] = []
    later = _successful_transport(requests)

    def respond(request: httpx.Request) -> httpx.Response:
        if not requests:
            requests.append(request)
            return httpx.Response(200, request=request, stream=gated)
        return later(request)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    received: list[HermesEvent] = []
    recorded: list[asyncio.CancelledError] = []
    try:
        async with client:
            public_stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(
                    {"model": "hermes"},
                    session_id=session_id,
                    session_key=session_key,
                ),
            )

            async def consume() -> None:
                try:
                    while True:
                        received.append(await anext(public_stream))
                except asyncio.CancelledError as caught:
                    recorded.append(caught)
                    raise

            task = asyncio.create_task(consume())
            await gated.wait_until_blocked(task)
            _assert_suspended_stream_retains_no_secrets(
                public_stream,
                canaries=(session_id, session_key, _BEARER_KEY_CANARY),
            )
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

            assert task.cancelled() is True
            assert received == [AssistantDeltaEvent(text="hello")]
            assert gated.closed is True
            assert injected_http_client.is_closed is False
            # Lifecycle check only: CPython clears ag_frame once a generator
            # finishes, so this is not retention evidence.
            assert cast("_HasAsyncGeneratorFrame", public_stream).ag_frame is None
            assert requests[0].headers["X-Hermes-Session-Id"] == session_id
            assert requests[0].headers["X-Hermes-Session-Key"] == session_key

            later_events = tuple(
                [
                    event
                    async for event in client.stream_chat_events({"model": "hermes"})
                ]
            )
            assert later_events == (
                AssistantDeltaEvent(text="hello"),
                TerminalEvent(outcome=TerminalOutcome.SUCCESS),
            )
            assert "X-Hermes-Session-Id" not in requests[-1].headers
            assert "X-Hermes-Session-Key" not in requests[-1].headers

        assert injected_http_client.is_closed is False
        assert len(recorded) == 1
        failure = recorded[0]
        assert failure.__cause__ is None
        assert failure.__context__ is None
        assert all(
            canary not in str(failure) and canary not in repr(failure)
            for canary in (session_id, session_key)
        )
        _assert_no_sensitive_traceback_references(
            failure,
            canaries=(session_id, session_key),
            forbidden_objects=(client, injected_http_client),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_injected_client_survives_public_stream_early_close() -> None:
    """Early public stream closure keeps the injected client open and reusable."""
    session_id = "early-close-reuse-session-id-canary"
    session_key = "early-close-reuse-session-key-canary"
    response_stream = TrackingAsyncByteStream(
        (
            b'data: {"choices":[{"index":0,"delta":{"content":"hello"},'
            b'"finish_reason":null}]}\n\n',
        )
    )
    requests: list[httpx.Request] = []
    later = _successful_transport(requests)

    def respond(request: httpx.Request) -> httpx.Response:
        if not requests:
            requests.append(request)
            return httpx.Response(200, request=request, stream=response_stream)
        return later(request)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            public_stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(
                    {"model": "hermes"},
                    session_id=session_id,
                    session_key=session_key,
                ),
            )
            assert await anext(public_stream) == AssistantDeltaEvent(text="hello")
            assert response_stream.closed is False
            _assert_suspended_stream_retains_no_secrets(
                public_stream,
                canaries=(session_id, session_key, _BEARER_KEY_CANARY),
            )

            await public_stream.aclose()

            assert response_stream.closed is True
            assert injected_http_client.is_closed is False
            # Lifecycle check only: CPython clears ag_frame once a generator
            # finishes, so this is not retention evidence.
            assert cast("_HasAsyncGeneratorFrame", public_stream).ag_frame is None
            assert requests[0].headers["X-Hermes-Session-Id"] == session_id
            assert requests[0].headers["X-Hermes-Session-Key"] == session_key

            later_events = tuple(
                [
                    event
                    async for event in client.stream_chat_events({"model": "hermes"})
                ]
            )
            assert later_events == (
                AssistantDeltaEvent(text="hello"),
                TerminalEvent(outcome=TerminalOutcome.SUCCESS),
            )
            assert "X-Hermes-Session-Id" not in requests[-1].headers
            assert "X-Hermes-Session-Key" not in requests[-1].headers

            await client.probe_capabilities()
            assert requests[-1].url.path.endswith("/v1/capabilities")

        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("session_id", "session_key"),
    [
        ("only-header-session-id-canary", None),
        (None, "only-header-session-key-canary"),
        ("only-header-session-id-canary", "only-header-session-key-canary"),
    ],
    ids=["id-only", "key-only", "both"],
)
async def test_session_values_appear_only_in_their_exact_headers(
    session_id: str | None,
    session_key: str | None,
) -> None:
    """Each supplied session value is sent once, verbatim, in its own header only."""
    requests: list[httpx.Request] = []
    request_document: dict[str, object] = {
        "model": "hermes",
        "messages": (),
        "stream": True,
    }
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    bound_headers = client._headers.copy()  # pyright: ignore[reportPrivateUsage]
    supplied = {
        name: value
        for name, value in (
            ("X-Hermes-Session-Id", session_id),
            ("X-Hermes-Session-Key", session_key),
        )
        if value is not None
    }
    try:
        async with client:
            async for _event in client.stream_chat_events(
                request_document,
                session_id=session_id,
                session_key=session_key,
            ):
                pass

        assert len(requests) == 1
        sent = requests[0]
        for name in ("X-Hermes-Session-Id", "X-Hermes-Session-Key"):
            if name in supplied:
                assert sent.headers.get_list(name) == [supplied[name]]
            else:
                assert name not in sent.headers
        session_header_names = {"x-hermes-session-id", "x-hermes-session-key"}
        for name, value in sent.headers.multi_items():
            if name.lower() not in session_header_names:
                assert all(canary not in value for canary in supplied.values())
        assert all(canary not in sent.content.decode() for canary in supplied.values())
        assert all(canary not in str(sent.url) for canary in supplied.values())
        assert client._headers == bound_headers  # pyright: ignore[reportPrivateUsage]
    finally:
        await injected_http_client.aclose()


def test_stream_chat_events_accepts_no_arbitrary_headers() -> None:
    """The stream signature exposes only the two typed session arguments."""
    parameters = inspect.signature(HermesAgentApiClient.stream_chat_events).parameters

    assert list(parameters) == ["self", "request", "session_id", "session_key"]
    assert parameters["request"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    for name in ("session_id", "session_key"):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is None
    assert all(
        parameter.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for parameter in parameters.values()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("session_id", "session_key", "canaries"),
    [
        ("", None, ()),
        (None, "", ()),
        ("carriage\rreturn-session-id-canary", None, ("return-session-id-canary",)),
        (None, "carriage\rreturn-session-key-canary", ("return-session-key-canary",)),
        ("tab\tseparated-session-id-canary", None, ("separated-session-id-canary",)),
        (
            None,
            "tab\tseparated-session-key-canary",
            ("separated-session-key-canary",),
        ),
        (b"bytes-session-id-canary", None, ("bytes-session-id-canary",)),
        (None, b"bytes-session-key-canary", ("bytes-session-key-canary",)),
        ("profile..session-id-canary", None, ("profile..session-id-canary",)),
        ("profile/session-id-canary", None, ("profile/session-id-canary",)),
        ("C:session-id-canary", None, ("C:session-id-canary",)),
        (
            "invalid session-id-canary",
            "valid-session-key-canary",
            ("invalid session-id-canary", "valid-session-key-canary"),
        ),
        (
            "valid-session-id-canary",
            "invalid session-key-canary",
            ("valid-session-id-canary", "invalid session-key-canary"),
        ),
        (
            "invalid session-id-canary",
            "invalid session-key-canary",
            ("invalid session-id-canary", "invalid session-key-canary"),
        ),
    ],
    ids=[
        "session-id-empty",
        "session-key-empty",
        "session-id-carriage-return",
        "session-key-carriage-return",
        "session-id-tab",
        "session-key-tab",
        "session-id-bytes",
        "session-key-bytes",
        "session-id-embedded-parent",
        "session-id-slash",
        "session-id-drive-prefix",
        "pair-invalid-id",
        "pair-invalid-key",
        "pair-both-invalid",
    ],
)
async def test_rejected_session_values_leave_no_retained_state(
    session_id: object,
    session_key: object,
    canaries: tuple[str, ...],
) -> None:
    """Rejected session values fail locally with exact, value-free metadata."""
    requests: list[httpx.Request] = []
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    supplied = tuple(
        value
        for value in (session_id, session_key)
        if isinstance(value, (str, bytes)) and len(value) >= _MIN_UNIQUE_CANARY_LENGTH
    )
    try:
        async with client:
            stream = client.stream_chat_events(
                {"model": "hermes"},
                session_id=cast("str | None", session_id),
                session_key=cast("str | None", session_key),
            )
            with pytest.raises(HermesTransportError) as caught:
                await anext(stream)

        error = caught.value
        assert type(error) is HermesTransportError
        assert error.category is FailureCategory.TRANSPORT
        assert error.status_code is None
        assert error.retryable is False
        assert str(error) == _LOCAL_INPUT_FAILURE_TEXT
        assert repr(error) == _LOCAL_INPUT_FAILURE_REPR
        assert error.args == (_LOCAL_INPUT_FAILURE_TEXT,)
        assert error.__cause__ is None
        assert error.__context__ is None
        assert requests == []
        # Lifecycle check only: CPython clears ag_frame once a generator
        # finishes, so this is not retention evidence.
        assert cast("_HasAsyncGeneratorFrame", stream).ag_frame is None
        assert all(canary not in str(error) for canary in canaries)
        assert all(canary not in repr(error) for canary in canaries)
        _assert_no_sensitive_traceback_references(
            error,
            canaries=canaries,
            forbidden_objects=(*supplied, client, injected_http_client),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("session_id", "session_key"),
    [
        (None, "!"),
        (None, "~" * 256),
        ("profile.chat.session-id", None),
        ("profile:chat-session-id", None),
        ("1:digit-prefixed-session-id", None),
    ],
    ids=[
        "session-key-minimum",
        "session-key-maximum",
        "session-id-single-dots",
        "session-id-inner-colon",
        "session-id-digit-colon-prefix",
    ],
)
async def test_session_values_accept_exact_boundaries(
    session_id: str | None,
    session_key: str | None,
) -> None:
    """Boundary session values are accepted and sent without any change."""
    requests: list[httpx.Request] = []
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    bound_headers = client._headers.copy()  # pyright: ignore[reportPrivateUsage]
    try:
        async with client:
            events = tuple(
                [
                    event
                    async for event in client.stream_chat_events(
                        {"model": "hermes"},
                        session_id=session_id,
                        session_key=session_key,
                    )
                ]
            )

        assert events == (
            AssistantDeltaEvent(text="hello"),
            TerminalEvent(outcome=TerminalOutcome.SUCCESS),
        )
        assert len(requests) == 1
        sent = requests[0]
        for name, value in (
            ("X-Hermes-Session-Id", session_id),
            ("X-Hermes-Session-Key", session_key),
        ):
            if value is None:
                assert name not in sent.headers
            else:
                assert sent.headers.get_list(name) == [value]
        assert client._headers == bound_headers  # pyright: ignore[reportPrivateUsage]
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    ["completion", "early-close-after-event", "early-close-before-first-iteration"],
    ids=["completion", "early-close-after-event", "early-close-before-first-iteration"],
)
async def test_completed_and_closed_streams_retain_no_session_values(
    mode: str,
) -> None:
    """Suspended, completed and closed streams retain no session values.

    The retention evidence is the suspended-frame check made at every yield
    before the stream finishes or closes.
    """
    session_id = "retained-session-id-canary"
    session_key = "retained-session-key-canary"
    canaries = (session_id, session_key, _BEARER_KEY_CANARY)
    response_stream = TrackingAsyncByteStream(
        (
            b'data: {"choices":[{"index":0,"delta":{"content":"hello"},'
            b'"finish_reason":null}]}\n\n',
            b"data: [DONE]\n\n",
        )
    )
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, stream=response_stream)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(
                    {"model": "hermes"},
                    session_id=session_id,
                    session_key=session_key,
                ),
            )
            if mode == "completion":
                collected: list[HermesEvent] = []
                async for event in stream:
                    collected.append(event)
                    _assert_suspended_stream_retains_no_secrets(
                        stream, canaries=canaries
                    )
                assert tuple(collected) == (
                    AssistantDeltaEvent(text="hello"),
                    TerminalEvent(outcome=TerminalOutcome.SUCCESS),
                )
                await stream.aclose()
            elif mode == "early-close-after-event":
                assert await anext(stream) == AssistantDeltaEvent(text="hello")
                _assert_suspended_stream_retains_no_secrets(stream, canaries=canaries)
                await stream.aclose()
                assert response_stream.closed is True
            else:
                await stream.aclose()
                assert requests == []

            # Lifecycle check only: CPython clears ag_frame once a generator
            # finishes, so this is not retention evidence.
            assert cast("_HasAsyncGeneratorFrame", stream).ag_frame is None
            assert injected_http_client.is_closed is False
            if mode != "early-close-before-first-iteration":
                assert requests[0].headers["X-Hermes-Session-Id"] == session_id
                assert requests[0].headers["X-Hermes-Session-Key"] == session_key
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "authentication-401",
        "status-503",
        "protocol-malformed-sse",
        "transport-connect-error",
        "request-stage-cancellation",
    ],
    ids=[
        "authentication-401",
        "status-503",
        "protocol-malformed-sse",
        "transport-connect-error",
        "request-stage-cancellation",
    ],
)
async def test_post_dispatch_failures_carry_no_session_values(case: str) -> None:
    """Public failures raised after dispatch carry no session values anywhere."""
    session_id = "failure-session-id-canary"
    session_key = "failure-session-key-canary"
    requests: list[httpx.Request] = []
    cancellation = asyncio.CancelledError("post-dispatch-cancellation")
    respond, expected_type = _post_dispatch_failure_case(case, requests, cancellation)
    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(
                    {"model": "hermes"},
                    session_id=session_id,
                    session_key=session_key,
                ),
            )
            with pytest.raises(expected_type) as caught:
                await anext(stream)

        error = caught.value
        assert type(error) is expected_type
        assert requests[0].headers["X-Hermes-Session-Id"] == session_id
        assert requests[0].headers["X-Hermes-Session-Key"] == session_key
        assert error.__cause__ is None
        assert error.__context__ is None
        assert all(
            canary not in str(error) and canary not in repr(error)
            for canary in (session_id, session_key)
        )
        _assert_no_sensitive_traceback_references(
            error,
            canaries=(session_id, session_key),
            forbidden_objects=(client, injected_http_client),
        )
        # Lifecycle check only: CPython clears ag_frame once a generator
        # finishes, so this is not retention evidence.
        assert cast("_HasAsyncGeneratorFrame", stream).ag_frame is None
        assert injected_http_client.is_closed is False
        if isinstance(error, HermesAuthenticationError):
            assert error.status_code == _AUTHENTICATION_STATUS_CODE
        if isinstance(error, HermesHttpStatusError):
            assert error.status_code == _UPSTREAM_STATUS_CODE
        if case == "request-stage-cancellation":
            assert error is cancellation
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_owned_client_is_created_on_entry_and_closed_on_exit() -> None:
    """An internally created client starts at entry and closes at exit."""
    owned_http_client = httpx.AsyncClient()
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)

    with patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory):
        assert factory.calls == []
        assert owned_http_client.is_closed is False
        async with client as entered:
            assert entered is client
            assert factory.calls == [(True, False)]
            assert owned_http_client.is_closed is False

    assert owned_http_client.is_closed is True


@pytest.mark.asyncio
async def test_owned_client_closes_when_context_body_raises() -> None:
    """An owned client closes even when the context body raises."""
    owned_http_client = httpx.AsyncClient()
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)
    failure_message = "context body failure"

    with (
        patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory),
        pytest.raises(RuntimeError, match=failure_message),
    ):
        async with client:
            raise RuntimeError(failure_message)

    assert owned_http_client.is_closed is True


@pytest.mark.asyncio
async def test_owned_client_creation_failure_scrubs_bound_state() -> None:
    """An owned-client constructor failure does not retain the wrapper."""
    failure_message = "owned client creation failed"
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)

    def fail_create(
        *,
        verify: ssl.SSLContext | bool,
        follow_redirects: bool,
    ) -> httpx.AsyncClient:
        assert verify is True
        assert follow_redirects is False
        raise RuntimeError(failure_message)

    with (
        patch("hermes_agent_api_client.client.httpx.AsyncClient", new=fail_create),
        pytest.raises(RuntimeError, match=failure_message) as failure,
    ):
        await client.__aenter__()

    _assert_safe_lifecycle_error(
        failure.value,
        expected_message=failure_message,
        client=client,
    )


@pytest.mark.parametrize(
    ("base_url", "bearer_key", "canaries"),
    [
        (
            "ftp://private-invalid-base-canary",
            _BEARER_KEY_CANARY,
            ("private-invalid-base-canary", _BEARER_KEY_CANARY),
        ),
        (
            _BASE_URL_CANARY,
            "private-invalid-bearer-canary\n",
            (_BASE_URL_CANARY, "private-invalid-bearer-canary"),
        ),
    ],
)
def test_constructor_validation_failures_scrub_raw_inputs(
    base_url: str,
    bearer_key: str,
    canaries: tuple[str, ...],
) -> None:
    """Binding failures retain neither raw constructor input."""
    with pytest.raises(HermesTransportError) as failure:
        HermesAgentApiClient(base_url, bearer_key)

    assert failure.value.retryable is False
    _assert_safe_lifecycle_error(
        failure.value,
        expected_message=str(failure.value),
        canaries=canaries,
    )


@pytest.mark.asyncio
async def test_owned_client_close_failure_becomes_fresh_transport_error() -> None:
    """An owned-client cleanup failure exposes only fresh transport metadata."""
    raw_failure = RuntimeError("owned-client-close-canary")
    owned_http_client = httpx.AsyncClient(transport=RaisingCloseTransport(raw_failure))
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)

    with (
        patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory),
        pytest.raises(HermesTransportError) as failure,
    ):
        async with client:
            pass

    assert client._active_http_client is None  # pyright: ignore[reportPrivateUsage]
    assert client._exited is True  # pyright: ignore[reportPrivateUsage]
    _assert_fresh_cleanup_transport_failure(
        failure.value,
        raw_error=raw_failure,
        canaries=("owned-client-close-canary", _BASE_URL_CANARY, _BEARER_KEY_CANARY),
        forbidden_objects=(client, owned_http_client),
    )


@pytest.mark.asyncio
async def test_context_body_error_precedes_owned_client_close_failure() -> None:
    """A caller body failure remains primary when owned cleanup also fails."""
    raw_cleanup_failure = RuntimeError("owned-cleanup-secondary-canary")
    body_failure = RuntimeError("caller-body-primary-canary")
    owned_http_client = httpx.AsyncClient(
        transport=RaisingCloseTransport(raw_cleanup_failure)
    )
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)

    with (
        patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory),
        pytest.raises(RuntimeError) as failure,
    ):
        async with client:
            raise body_failure

    assert failure.value is body_failure
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None
    assert "owned-cleanup-secondary-canary" not in "".join(
        traceback.format_exception(failure.value)
    )
    assert client._active_http_client is None  # pyright: ignore[reportPrivateUsage]
    assert client._exited is True  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_context_body_runtime_failure_precedes_owned_close_cancellation() -> None:
    """A body runtime error remains primary over owned-close cancellation."""
    body_failure = RuntimeError("context-body-primary-canary")
    close_cancellation = asyncio.CancelledError("owned-close-secondary-cancellation")
    owned_http_client = httpx.AsyncClient(
        transport=RaisingCloseTransport(close_cancellation)
    )
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)

    with (
        patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory),
        pytest.raises(RuntimeError) as failure,
    ):
        async with client:
            raise body_failure

    assert failure.value is body_failure
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None
    assert "owned-close-secondary-cancellation" not in "".join(
        traceback.format_exception(failure.value)
    )
    assert client._active_http_client is None  # pyright: ignore[reportPrivateUsage]
    assert client._exited is True  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_context_body_cancellation_precedes_owned_close_cancellation() -> None:
    """The exact body cancellation remains primary over owned-close cancellation."""
    body_cancellation = asyncio.CancelledError("context-body-primary-cancellation")
    close_cancellation = asyncio.CancelledError("owned-close-secondary-cancellation")
    owned_http_client = httpx.AsyncClient(
        transport=RaisingCloseTransport(close_cancellation)
    )
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)

    with (
        patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory),
        pytest.raises(asyncio.CancelledError) as failure,
    ):
        async with client:
            raise body_cancellation

    assert failure.value is body_cancellation
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None
    assert "owned-close-secondary-cancellation" not in "".join(
        traceback.format_exception(failure.value)
    )
    assert client._active_http_client is None  # pyright: ignore[reportPrivateUsage]
    assert client._exited is True  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_injected_client_is_never_closed() -> None:
    """Exiting the wrapper never closes an injected HTTP client."""
    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            pass
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_capability_response_close_failure_becomes_fresh_transport_error() -> (
    None
):
    """Capability response cleanup cannot expose its raw close failure."""
    raw_failure = RuntimeError("capability-close-canary")
    body_canary = "capability-body-canary"
    body = json.dumps(
        {**load_golden_json("capabilities/supported.json"), "private": body_canary}
    ).encode()
    response_stream = TrackingAsyncByteStream((body,), close_failure=raw_failure)
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(200, request=request, stream=response_stream)
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesTransportError) as failure:
                await client.probe_capabilities()
            assert client._active_http_client is injected_http_client  # pyright: ignore[reportPrivateUsage]

        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_fresh_cleanup_transport_failure(
            failure.value,
            raw_error=raw_failure,
            canaries=(
                "capability-close-canary",
                body_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_capability_context_close_failure_becomes_fresh_transport_error() -> None:
    """An opaque response-context close failure remains safely mapped."""
    raw_failure = RuntimeError("capability-context-close-canary")
    body_canary = "capability-context-body-canary"
    body = json.dumps(
        {**load_golden_json("capabilities/supported.json"), "private": body_canary}
    ).encode()
    response_stream = TrackingAsyncByteStream((body,))
    request = httpx.Request(
        "GET",
        f"{_BASE_URL_CANARY}/v1/capabilities",
        headers={"Authorization": f"Bearer {_BEARER_KEY_CANARY}"},
    )
    response = httpx.Response(200, request=request, stream=response_stream)

    @asynccontextmanager
    async def failing_stream(
        *_args: object,
        **_kwargs: object,
    ) -> AsyncGenerator[httpx.Response]:
        try:
            yield response
        finally:
            raise raw_failure

    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        with patch.object(injected_http_client, "stream", new=failing_stream):
            async with client:
                with pytest.raises(HermesTransportError) as failure:
                    await client.probe_capabilities()
                assert client._active_http_client is injected_http_client  # pyright: ignore[reportPrivateUsage]

        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_fresh_cleanup_transport_failure(
            failure.value,
            raw_error=raw_failure,
            canaries=(
                "capability-context-close-canary",
                body_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                client,
                injected_http_client,
                response_stream,
                response,
                request,
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("body_kind", ["immediate", "partial", "complete"])
async def test_capability_read_transport_failure_precedes_response_close_cancellation(
    body_kind: str,
) -> None:
    """A primary capability read failure outranks close cancellation."""
    raw_source_failure = RuntimeError(f"capability-{body_kind}-read-transport-canary")
    close_cancellation = asyncio.CancelledError(
        f"capability-{body_kind}-transport-secondary-close-cancellation"
    )
    body_canary = f"capability-{body_kind}-read-transport-body-canary"
    header_canary = f"capability-{body_kind}-read-transport-header-canary"
    if body_kind == "complete":
        body = json.dumps(
            {**load_golden_json("capabilities/supported.json"), "private": body_canary}
        ).encode()
        chunks = (body,)
    elif body_kind == "partial":
        body = f'{{"platform":"{body_canary}"'.encode()
        chunks = (body,)
    else:
        body = body_canary.encode()
        chunks: tuple[bytes, ...] = ()
    response_stream = TrackingAsyncByteStream(
        chunks,
        close_failure=close_cancellation,
        iteration_failure=raw_source_failure,
    )
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            200,
            headers={"x-private-response-header": header_canary},
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesTransportError) as failure:
                await client.probe_capabilities()
            assert client._active_http_client is injected_http_client  # pyright: ignore[reportPrivateUsage]

        _assert_fresh_cleanup_transport_failure(
            failure.value,
            raw_error=raw_source_failure,
            canaries=(
                f"capability-{body_kind}-read-transport-canary",
                f"capability-{body_kind}-transport-secondary-close-cancellation",
                body_canary,
                header_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                close_cancellation,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
            ),
        )
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_capability_status_failure_precedes_response_close_failure() -> None:
    """A capability status failure remains typed when response cleanup also fails."""
    raw_failure = RuntimeError("capability-status-close-canary")
    body = b"capability-status-body-canary"
    header_canary = "capability-status-header-canary"
    response_stream = TrackingAsyncByteStream((body,), close_failure=raw_failure)
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            _UPSTREAM_STATUS_CODE,
            headers={"x-private-response-header": header_canary},
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesHttpStatusError) as failure:
                await client.probe_capabilities()
            assert client._active_http_client is injected_http_client  # pyright: ignore[reportPrivateUsage]

        error = failure.value
        assert type(error) is HermesHttpStatusError
        assert not isinstance(error, HermesTransportError)
        assert error.category is FailureCategory.HTTP_STATUS
        assert error.status_code == _UPSTREAM_STATUS_CODE
        assert error.retryable is True
        assert str(error) == "Hermes http_status failure (status=503, retryable=true)"
        assert repr(error) == (
            "HermesHttpStatusError(category='http_status', status_code=503, "
            "retryable=True)"
        )
        assert error.__cause__ is None
        assert error.__context__ is None
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_no_sensitive_traceback_references(
            error,
            canaries=(
                "capability-status-close-canary",
                "capability-status-body-canary",
                header_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                raw_failure,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_capability_status_failure_precedes_response_close_cancellation() -> None:
    """A capability status failure remains typed over close cancellation."""
    close_cancellation = asyncio.CancelledError("capability-status-close-cancellation")
    body = b"capability-status-cancellation-body-canary"
    header_canary = "capability-status-cancellation-header-canary"
    response_stream = TrackingAsyncByteStream(
        (body,),
        close_failure=close_cancellation,
    )
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            _UPSTREAM_STATUS_CODE,
            headers={"x-private-response-header": header_canary},
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesHttpStatusError) as failure:
                await client.probe_capabilities()

        error = failure.value
        assert type(error) is HermesHttpStatusError
        assert error.category is FailureCategory.HTTP_STATUS
        assert error.status_code == _UPSTREAM_STATUS_CODE
        assert error.retryable is True
        assert error.__cause__ is None
        assert error.__context__ is None
        assert error is not close_cancellation
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_no_sensitive_traceback_references(
            error,
            canaries=(
                "capability-status-close-cancellation",
                "capability-status-cancellation-body-canary",
                header_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                close_cancellation,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "body_canary"),
    [
        (b"capability-malformed-json-canary", "capability-malformed-json-canary"),
        (
            b'{"object":"hermes.api_server.capabilities",'
            b'"platform":"hermes-agent","model":"hermes-agent",'
            b'"auth":"capability-invalid-shape-canary",'
            b'"features":{"chat_completions":true,'
            b'"chat_completions_streaming":true}}',
            "capability-invalid-shape-canary",
        ),
    ],
    ids=["malformed-json", "invalid-shape"],
)
async def test_capability_protocol_failure_precedes_response_close_failure(
    body: bytes,
    body_canary: str,
) -> None:
    """A malformed capability body remains protocol failure over close failure."""
    raw_failure = RuntimeError("capability-protocol-close-canary")
    header_canary = "capability-protocol-header-canary"
    response_stream = TrackingAsyncByteStream((body,), close_failure=raw_failure)
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            200,
            headers={"x-private-response-header": header_canary},
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesProtocolError) as failure:
                await client.probe_capabilities()
            assert client._active_http_client is injected_http_client  # pyright: ignore[reportPrivateUsage]

        error = failure.value
        assert type(error) is HermesProtocolError
        assert error.category is FailureCategory.PROTOCOL
        assert error.status_code is None
        assert error.retryable is False
        assert str(error) == "Hermes protocol failure (status=none, retryable=false)"
        assert repr(error) == (
            "HermesProtocolError(category='protocol', status_code=None, "
            "retryable=False)"
        )
        assert error.__cause__ is None
        assert error.__context__ is None
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_no_sensitive_traceback_references(
            error,
            canaries=(
                "capability-protocol-close-canary",
                body_canary,
                header_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                raw_failure,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "body_canary"),
    [
        (
            b"capability-malformed-cancellation-body-canary",
            "capability-malformed-cancellation-body-canary",
        ),
        (
            b'{"object":"hermes.api_server.capabilities",'
            b'"platform":"hermes-agent","model":"hermes-agent",'
            b'"auth":"capability-invalid-cancellation-shape-canary",'
            b'"features":{"chat_completions":true,'
            b'"chat_completions_streaming":true}}',
            "capability-invalid-cancellation-shape-canary",
        ),
    ],
    ids=["malformed-json", "invalid-shape"],
)
async def test_capability_protocol_failure_precedes_response_close_cancellation(
    body: bytes,
    body_canary: str,
) -> None:
    """A malformed capability body remains protocol failure over close cancel."""
    close_cancellation = asyncio.CancelledError(
        "capability-protocol-close-cancellation"
    )
    header_canary = "capability-protocol-cancellation-header-canary"
    response_stream = TrackingAsyncByteStream(
        (body,),
        close_failure=close_cancellation,
    )
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            200,
            headers={"x-private-response-header": header_canary},
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesProtocolError) as failure:
                await client.probe_capabilities()

        error = failure.value
        assert type(error) is HermesProtocolError
        assert error.category is FailureCategory.PROTOCOL
        assert error.status_code is None
        assert error.retryable is False
        assert error.__cause__ is None
        assert error.__context__ is None
        assert error is not close_cancellation
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_no_sensitive_traceback_references(
            error,
            canaries=(
                "capability-protocol-close-cancellation",
                body_canary,
                header_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                close_cancellation,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("size_source", ["declared", "observed"])
async def test_capability_limit_failure_precedes_response_close_cancellation(
    size_source: str,
) -> None:
    """Declared and observed capability-limit failures outrank close cancel."""
    close_cancellation = asyncio.CancelledError("capability-limit-close-cancellation")
    header_canary = f"capability-{size_source}-limit-header-canary"
    body = f"capability-{size_source}-limit-body-canary".encode()
    if size_source == "observed":
        body += b"x" * (_MAX_CAPABILITIES_BYTES + 1 - len(body))
    headers = {"x-private-response-header": header_canary}
    if size_source == "declared":
        headers["content-length"] = str(_MAX_CAPABILITIES_BYTES + 1)
    response_stream = TrackingAsyncByteStream(
        (body,),
        close_failure=close_cancellation,
    )
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            200,
            headers=headers,
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesProtocolError) as failure:
                await client.probe_capabilities()

        error = failure.value
        assert type(error) is HermesProtocolError
        assert error.category is FailureCategory.PROTOCOL
        assert error.status_code is None
        assert error.retryable is False
        assert error.__cause__ is None
        assert error.__context__ is None
        assert error is not close_cancellation
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_no_sensitive_traceback_references(
            error,
            canaries=(
                "capability-limit-close-cancellation",
                f"capability-{size_source}-limit-body-canary",
                header_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                close_cancellation,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
                headers,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_response_close_failure_after_delta_becomes_transport_error() -> (
    None
):
    """Stream cleanup after a public delta exposes only safe transport metadata."""
    raw_failure = RuntimeError("stream-close-canary")
    event_canary = "stream-event-canary"
    request_document: dict[str, object] = {
        "model": "hermes",
        "messages": (),
        "stream": True,
        "private": "stream-request-canary",
    }
    body = (
        b'data: {"choices":[{"index":0,"delta":{"content":"'
        + event_canary.encode()
        + b'"},"finish_reason":null}]}\n\n'
    )
    response_stream = TrackingAsyncByteStream((body,), close_failure=raw_failure)
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(200, request=request, stream=response_stream)
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            public_stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(request_document),
            )
            event = await anext(public_stream)
            assert event == AssistantDeltaEvent(text=event_canary)

            with pytest.raises(HermesTransportError) as failure:
                await public_stream.aclose()

            assert client._active_http_client is injected_http_client  # pyright: ignore[reportPrivateUsage]

        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_fresh_cleanup_transport_failure(
            failure.value,
            raw_error=raw_failure,
            canaries=(
                "stream-close-canary",
                event_canary,
                "stream-request-canary",
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                request_document,
                body,
                event,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_protocol_failure_precedes_response_close_failure() -> None:
    """A primary stream protocol failure outranks secondary cleanup failure."""
    raw_cleanup_failure = RuntimeError("stream-cleanup-secondary-canary")
    body_canary = "stream-protocol-body-canary"
    body = f"data: {{{body_canary}}}\n\n".encode()
    response_stream = TrackingAsyncByteStream(
        (body,),
        close_failure=raw_cleanup_failure,
    )
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(200, request=request, stream=response_stream)
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesProtocolError) as failure:
                await anext(client.stream_chat_events({"model": "hermes"}))

        assert type(failure.value) is HermesProtocolError
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        _assert_no_sensitive_traceback_references(
            failure.value,
            canaries=(
                "stream-cleanup-secondary-canary",
                body_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                raw_cleanup_failure,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                body,
            ),
        )
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_transport_failure_precedes_response_close_cancellation() -> None:
    """A primary decoder transport failure outranks close cancellation."""
    raw_source_failure = RuntimeError("stream-primary-read-transport-canary")
    close_cancellation = asyncio.CancelledError(
        "stream-primary-transport-secondary-close-cancellation"
    )
    body_canary = "stream-primary-read-transport-body-canary"
    header_canary = "stream-primary-read-transport-header-canary"
    request_document: dict[str, object] = {
        "model": "hermes",
        "private": "stream-primary-read-transport-request-canary",
    }
    body = f": {body_canary}\n\n".encode()
    response_stream = TrackingAsyncByteStream(
        (body,),
        close_failure=close_cancellation,
        iteration_failure=raw_source_failure,
    )
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            200,
            headers={"x-private-response-header": header_canary},
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            public_stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(request_document),
            )
            event = await anext(public_stream)
            assert event == KeepaliveEvent()

            with pytest.raises(HermesTransportError) as failure:
                await anext(public_stream)

        error = failure.value
        _assert_fresh_cleanup_transport_failure(
            error,
            raw_error=raw_source_failure,
            canaries=(
                "stream-primary-read-transport-canary",
                "stream-primary-transport-secondary-close-cancellation",
                body_canary,
                header_canary,
                "stream-primary-read-transport-request-canary",
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                close_cancellation,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                request_document,
                body,
                event,
            ),
        )
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_status_failure_precedes_response_close_cancellation() -> None:
    """A stream status failure remains typed over response-close cancellation."""
    close_cancellation = asyncio.CancelledError(
        "stream-primary-secondary-close-cancellation"
    )
    body = b"stream-status-cancellation-body-canary"
    header_canary = "stream-status-cancellation-header-canary"
    request_document: dict[str, object] = {
        "model": "hermes",
        "private": "stream-status-cancellation-request-canary",
    }
    response_stream = TrackingAsyncByteStream(
        (body,),
        close_failure=close_cancellation,
    )
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            _UPSTREAM_STATUS_CODE,
            headers={"x-private-response-header": header_canary},
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesHttpStatusError) as failure:
                await anext(client.stream_chat_events(request_document))

        error = failure.value
        assert type(error) is HermesHttpStatusError
        assert error.category is FailureCategory.HTTP_STATUS
        assert error.status_code == _UPSTREAM_STATUS_CODE
        assert error.retryable is True
        assert error.__cause__ is None
        assert error.__context__ is None
        assert error is not close_cancellation
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_no_sensitive_traceback_references(
            error,
            canaries=(
                "stream-primary-secondary-close-cancellation",
                "stream-status-cancellation-body-canary",
                "stream-status-cancellation-request-canary",
                header_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                close_cancellation,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                request_document,
                body,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "body_canary"),
    [
        (
            b"data: {stream-malformed-sse-body-canary}\n\n",
            "stream-malformed-sse-body-canary",
        ),
        (
            b"data: stream-byte-limit-body-canary"
            + b"x" * (MAX_EVENT_DATA_CHARS + 1)
            + b"\n\n",
            "stream-byte-limit-body-canary",
        ),
    ],
    ids=["malformed-sse", "byte-limit"],
)
async def test_stream_protocol_failure_precedes_response_close_cancellation(
    body: bytes,
    body_canary: str,
) -> None:
    """Primary SSE protocol outcomes remain safe over close cancellation."""
    close_cancellation = asyncio.CancelledError(
        "stream-primary-secondary-close-cancellation"
    )
    header_canary = "stream-protocol-cancellation-header-canary"
    request_document: dict[str, object] = {
        "model": "hermes",
        "private": "stream-protocol-cancellation-request-canary",
    }
    response_stream = TrackingAsyncByteStream(
        (body,),
        close_failure=close_cancellation,
    )
    responses: list[httpx.Response] = []
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = httpx.Response(
            200,
            headers={"x-private-response-header": header_canary},
            request=request,
            stream=response_stream,
        )
        responses.append(response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesProtocolError) as failure:
                await anext(client.stream_chat_events(request_document))

        error = failure.value
        assert type(error) is HermesProtocolError
        assert error.category is FailureCategory.PROTOCOL
        assert error.status_code is None
        assert error.retryable is False
        assert error.__cause__ is None
        assert error.__context__ is None
        assert error is not close_cancellation
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
        _assert_no_sensitive_traceback_references(
            error,
            canaries=(
                "stream-primary-secondary-close-cancellation",
                body_canary,
                "stream-protocol-cancellation-request-canary",
                header_canary,
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
            ),
            forbidden_objects=(
                close_cancellation,
                client,
                injected_http_client,
                response_stream,
                responses[0],
                requests[0],
                client._headers,  # pyright: ignore[reportPrivateUsage]
                request_document,
                body,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_capability_response_close_cancellation_preserves_identity() -> None:
    """Capability cleanup cancellation remains the original cancellation object."""
    cancellation = asyncio.CancelledError("capability-close-cancellation")
    body = json.dumps(load_golden_json("capabilities/supported.json")).encode()
    response_stream = TrackingAsyncByteStream((body,), close_failure=cancellation)

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=response_stream)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(asyncio.CancelledError) as failure:
                await client.probe_capabilities()

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_response_close_cancellation_preserves_identity() -> None:
    """Stream cleanup cancellation remains the original cancellation object."""
    cancellation = asyncio.CancelledError("stream-close-cancellation")
    response_stream = TrackingAsyncByteStream(
        (
            b'data: {"choices":[{"index":0,"delta":{"content":"hello"},'
            b'"finish_reason":null}]}\n\n',
        ),
        close_failure=cancellation,
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=response_stream)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            public_stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events({"model": "hermes"}),
            )
            assert await anext(public_stream) == AssistantDeltaEvent(text="hello")
            with pytest.raises(asyncio.CancelledError) as failure:
                await public_stream.aclose()

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_owned_client_close_cancellation_preserves_identity() -> None:
    """Owned-client cleanup cancellation remains the original object."""
    cancellation = asyncio.CancelledError("owned-close-cancellation")
    owned_http_client = httpx.AsyncClient(transport=RaisingCloseTransport(cancellation))
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)

    with (
        patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory),
        pytest.raises(asyncio.CancelledError) as failure,
    ):
        async with client:
            pass

    assert failure.value is cancellation
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None
    assert client._active_http_client is None  # pyright: ignore[reportPrivateUsage]
    assert client._exited is True  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_capability_read_cancellation_precedes_response_close_failure() -> None:
    """Capability read cancellation remains primary over ordinary close failure."""
    cancellation = asyncio.CancelledError("capability-read-cancellation")
    response_stream = TrackingAsyncByteStream(
        (),
        close_failure=RuntimeError("capability-close-secondary-canary"),
        iteration_failure=cancellation,
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=response_stream)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(asyncio.CancelledError) as failure:
                await client.probe_capabilities()

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_read_cancellation_precedes_response_close_failure() -> None:
    """Stream read cancellation remains primary over ordinary close failure."""
    cancellation = asyncio.CancelledError("stream-read-cancellation")
    response_stream = TrackingAsyncByteStream(
        (),
        close_failure=RuntimeError("stream-close-secondary-canary"),
        iteration_failure=cancellation,
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=response_stream)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(asyncio.CancelledError) as failure:
                await anext(client.stream_chat_events({"model": "hermes"}))

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_read_cancellation_precedes_response_close_cancellation() -> None:
    """A primary stream read cancellation wins over actual close cancellation."""
    cancellation = asyncio.CancelledError("stream-read-primary-cancellation")
    close_cancellation = asyncio.CancelledError(
        "stream-read-secondary-close-cancellation"
    )
    response_stream = TrackingAsyncByteStream(
        (),
        close_failure=close_cancellation,
        iteration_failure=cancellation,
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=response_stream)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(asyncio.CancelledError) as failure:
                await anext(client.stream_chat_events({"model": "hermes"}))

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert response_stream.closed is True
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_capability_read_cancellation_precedes_close_cancellation() -> None:
    """The primary capability cancellation wins over a secondary close cancel."""
    cancellation = asyncio.CancelledError("capability-read-primary-cancellation")
    response_stream = TrackingAsyncByteStream(
        (),
        close_failure=asyncio.CancelledError("capability-close-secondary-cancellation"),
        iteration_failure=cancellation,
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=response_stream)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(asyncio.CancelledError) as failure:
                await client.probe_capabilities()

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert response_stream.closed is True
    finally:
        await injected_http_client.aclose()


def _secondary_status_close_failure(
    request: httpx.Request,
    response: httpx.Response,
) -> Exception:
    """Build a close-time status error tied to one real response."""
    return httpx.HTTPStatusError(
        "secondary close status", request=request, response=response
    )


def _secondary_request_close_failure(
    request: httpx.Request,
    _response: httpx.Response,
) -> Exception:
    """Build a close-time request error tied to one real request."""
    return httpx.ConnectError("secondary close request", request=request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "secondary_failure",
    [_secondary_status_close_failure, _secondary_request_close_failure],
    ids=["http-status", "request"],
)
async def test_stream_read_cancellation_precedes_httpx_close_failure(
    secondary_failure: Callable[[httpx.Request, httpx.Response], Exception],
) -> None:
    """A primary stream cancellation wins over secondary HTTPX close errors."""
    cancellation = asyncio.CancelledError("stream-read-primary-cancellation")
    response_stream = TrackingAsyncByteStream((), iteration_failure=cancellation)

    def respond(request: httpx.Request) -> httpx.Response:
        response = httpx.Response(200, request=request, stream=response_stream)
        response_stream.close_failure = secondary_failure(request, response)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(asyncio.CancelledError) as failure:
                await anext(client.stream_chat_events({"model": "hermes"}))

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert response_stream.closed is True
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_read_cancellation_precedes_context_close_cancellation() -> None:
    """Primary stream cancellation wins over a context-manager close cancel."""
    cancellation = asyncio.CancelledError("stream-read-primary-cancellation")
    secondary_cancellation = asyncio.CancelledError(
        "stream-context-close-secondary-cancellation"
    )
    response = httpx.Response(
        200,
        request=httpx.Request("POST", f"{_BASE_URL_CANARY}/v1/chat/completions"),
        stream=TrackingAsyncByteStream((), iteration_failure=cancellation),
    )

    @asynccontextmanager
    async def cancelling_stream(
        *_args: object,
        **_kwargs: object,
    ) -> AsyncGenerator[httpx.Response]:
        try:
            yield response
        finally:
            raise secondary_cancellation

    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        with patch.object(injected_http_client, "stream", new=cancelling_stream):
            async with client:
                with pytest.raises(asyncio.CancelledError) as failure:
                    await anext(client.stream_chat_events({"model": "hermes"}))

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_capability_request_cancellation_preserves_identity() -> None:
    """Capability request cancellation remains the original cancellation object."""
    cancellation = asyncio.CancelledError("capability-request-cancellation")
    injected_http_client = httpx.AsyncClient(
        transport=CancellingRequestTransport(cancellation)
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(asyncio.CancelledError) as failure:
                await client.probe_capabilities()

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_request_cancellation_preserves_identity() -> None:
    """Stream request cancellation remains the original cancellation object."""
    cancellation = asyncio.CancelledError("stream-request-cancellation")
    injected_http_client = httpx.AsyncClient(
        transport=CancellingRequestTransport(cancellation)
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            public_stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(
                    {"model": "hermes"},
                    session_id="cancel-session-canary",
                    session_key="cancel-key-canary",
                ),
            )
            with pytest.raises(asyncio.CancelledError) as failure:
                await anext(public_stream)

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert cast("_HasAsyncGeneratorFrame", public_stream).ag_frame is None
        _assert_no_sensitive_traceback_references(
            failure.value,
            canaries=("cancel-session-canary", "cancel-key-canary"),
            forbidden_objects=(client, injected_http_client),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_stream_request_status_error_remains_typed() -> None:
    """A request-stage status failure remains the typed public status error."""
    injected_http_client = httpx.AsyncClient(transport=StatusFailingRequestTransport())
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesHttpStatusError) as failure:
                await anext(client.stream_chat_events({"model": "hermes"}))

        assert failure.value.status_code == _UPSTREAM_STATUS_CODE
        assert failure.value.retryable is True
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_closing_public_stream_immediately_closes_delegated_response() -> None:
    """Early public stream closure releases its delegated response immediately."""
    response_stream = TrackingAsyncByteStream(
        (
            b'data: {"choices":[{"index":0,"delta":{"content":"hello"},'
            b'"finish_reason":null}]}\n\n',
        )
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=response_stream)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            public_stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(
                    {"model": "hermes", "messages": (), "stream": True},
                    session_id="early-close-session-canary",
                    session_key="early-close-key-canary",
                ),
            )
            assert await anext(public_stream) == AssistantDeltaEvent(text="hello")
            assert response_stream.closed is False

            await public_stream.aclose()

            assert response_stream.closed is True
            assert injected_http_client.is_closed is False
            assert cast("_HasAsyncGeneratorFrame", public_stream).ag_frame is None
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_public_stream_accepts_delegated_iterator_without_aclose() -> None:
    """A delegated iterator need not expose optional close support."""
    delegated_stream = UnclosableHermesEvents(
        (
            AssistantDeltaEvent(text="patched"),
            TerminalEvent(outcome=TerminalOutcome.SUCCESS),
        )
    )

    def delegate(
        _http_client: httpx.AsyncClient,
        _base_url: httpx.URL,
        _headers: Mapping[str, str],
        _request: Mapping[str, object],
    ) -> AsyncIterator[HermesEvent]:
        return delegated_stream

    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        with patch(
            "hermes_agent_api_client.client._stream_chat_events",
            new=delegate,
        ):
            async with client:
                events = tuple(
                    [
                        event
                        async for event in client.stream_chat_events(
                            {"model": "hermes"}
                        )
                    ]
                )
        assert events == (
            AssistantDeltaEvent(text="patched"),
            TerminalEvent(outcome=TerminalOutcome.SUCCESS),
        )
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_delegated_close_preserves_cancellation_and_scrubs_iterator() -> None:
    """Delegated close cancellation keeps identity without retaining iterator."""
    cancellation = asyncio.CancelledError()
    delegated_stream = CancellingCloseHermesEvents(cancellation)

    def delegate(
        _http_client: httpx.AsyncClient,
        _base_url: httpx.URL,
        _headers: Mapping[str, str],
        _request: Mapping[str, object],
    ) -> AsyncIterator[HermesEvent]:
        return delegated_stream

    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        with patch(
            "hermes_agent_api_client.client._stream_chat_events",
            new=delegate,
        ):
            async with client:
                with pytest.raises(asyncio.CancelledError) as failure:
                    await anext(client.stream_chat_events({"model": "hermes"}))

        assert failure.value is cancellation
        for frame_locals in _package_traceback_locals(failure.value):
            assert all(value is not delegated_stream for value in frame_locals.values())
            assert frame_locals.get("delegated_stream") is None
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "primary_failure",
    [
        RuntimeError("delegated-primary-operation-canary"),
        asyncio.CancelledError("delegated-primary-cancellation"),
    ],
    ids=["runtime-error", "cancellation"],
)
async def test_delegated_primary_failure_precedes_close_cancellation(
    primary_failure: BaseException,
) -> None:
    """Delegated operation failures remain primary over close cancellation."""
    close_cancellation = asyncio.CancelledError(
        "delegated-close-secondary-cancellation"
    )
    delegated_stream = FailingCloseHermesEvents(
        primary_failure,
        close_cancellation,
    )

    def delegate(
        _http_client: httpx.AsyncClient,
        _base_url: httpx.URL,
        _headers: Mapping[str, str],
        _request: Mapping[str, object],
    ) -> AsyncIterator[HermesEvent]:
        return delegated_stream

    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        with patch(
            "hermes_agent_api_client.client._stream_chat_events",
            new=delegate,
        ):
            async with client:
                with pytest.raises(type(primary_failure)) as failure:
                    await anext(client.stream_chat_events({"model": "hermes"}))

        assert failure.value is primary_failure
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert "delegated-close-secondary-cancellation" not in "".join(
            traceback.format_exception(failure.value)
        )
        for frame_locals in _package_traceback_locals(failure.value):
            assert all(value is not delegated_stream for value in frame_locals.values())
            assert frame_locals.get("delegated_stream") is None
            assert all(
                value is not close_cancellation for value in frame_locals.values()
            )
        assert injected_http_client.is_closed is False
    finally:
        await injected_http_client.aclose()


@pytest.mark.parametrize("verify", [False, ssl.create_default_context()])
@pytest.mark.asyncio
async def test_non_default_verify_is_rejected_with_injected_client(
    verify: ssl.SSLContext | bool,  # noqa: FBT001
) -> None:
    """Any explicit verification option conflicts with client injection."""
    injected_http_client = httpx.AsyncClient()
    try:
        with pytest.raises(ValueError, match=_VERIFY_INJECTION_MESSAGE) as failure:
            HermesAgentApiClient(
                _BASE_URL_CANARY,
                _BEARER_KEY_CANARY,
                http_client=injected_http_client,
                verify=verify,
            )
        assert str(failure.value) == _VERIFY_INJECTION_MESSAGE
        assert _BASE_URL_CANARY not in str(failure.value)
        assert _BEARER_KEY_CANARY not in str(failure.value)
        _assert_safe_lifecycle_error(
            failure.value,
            expected_message=_VERIFY_INJECTION_MESSAGE,
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_operations_before_entry_raise_constant_runtime_error() -> None:
    """Both public operations reject use before context entry."""
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)
    await _assert_operations_inactive(client)


@pytest.mark.asyncio
async def test_operations_after_exit_raise_constant_runtime_error() -> None:
    """Both public operations reject use after context exit."""
    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            pass
        await _assert_operations_inactive(client)
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_double_entry_is_rejected() -> None:
    """Entering an already active instance reports its single-use contract."""
    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(RuntimeError) as failure:
                await client.__aenter__()
            _assert_safe_lifecycle_error(
                failure.value,
                expected_message=_SINGLE_USE_MESSAGE,
                client=client,
            )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_reentry_after_exit_is_rejected() -> None:
    """An exited instance cannot begin a second lifecycle."""
    injected_http_client = httpx.AsyncClient()
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            pass
        with pytest.raises(RuntimeError) as failure:
            await client.__aenter__()
        _assert_safe_lifecycle_error(
            failure.value,
            expected_message=_SINGLE_USE_MESSAGE,
            client=client,
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_bound_endpoint_and_auth_are_reused_across_operations() -> None:
    """Both operations reuse normalized endpoint and immutable bound auth."""
    requests: list[httpx.Request] = []
    request_document: Mapping[str, object] = MappingProxyType(
        {"model": "hermes", "messages": (), "stream": True}
    )
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        f"{_BASE_URL_CANARY}/",
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            events = [
                event async for event in client.stream_chat_events(request_document)
            ]
            capabilities = await client.probe_capabilities()

        assert isinstance(events[-1], TerminalEvent)
        assert capabilities.object == "hermes.api_server.capabilities"
        assert capabilities.model == "hermes-agent"
        assert [request.url.path for request in requests] == [
            "/private-base/v1/chat/completions",
            "/private-base/v1/capabilities",
        ]
        assert [request.headers["Authorization"] for request in requests] == [
            f"Bearer {_BEARER_KEY_CANARY}",
            f"Bearer {_BEARER_KEY_CANARY}",
        ]
        assert requests[0].headers["Content-Type"] == "application/json"
        assert requests[1].headers.get("Content-Type") is None
        assert request_document == {
            "model": "hermes",
            "messages": (),
            "stream": True,
        }
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutate", "error_type", "body_canary"),
    [
        (
            _advertise_wrong_platform,
            HermesIdentityError,
            "public-identity-body-canary",
        ),
        (
            _advertise_unsupported_chat,
            HermesCapabilityError,
            "public-capability-body-canary",
        ),
    ],
)
async def test_public_probe_propagates_typed_capability_failures_safely(
    mutate: Callable[[dict[str, object]], None],
    error_type: type[HermesProtocolError],
    body_canary: str,
) -> None:
    """Public probes preserve exact typed failures after bound-state cleanup."""
    document = load_golden_json("capabilities/supported.json")
    mutate(document)
    response_stream = TrackingAsyncByteStream((json.dumps(document).encode(),))
    response: httpx.Response | None = None

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal response
        response = httpx.Response(200, request=request, stream=response_stream)
        return response

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(error_type) as caught:
                await client.probe_capabilities()

        assert type(caught.value) is error_type
        assert response is not None
        assert response.is_closed
        assert response_stream.closed
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert caught.value.args == (
            "Hermes protocol failure (status=none, retryable=false)",
        )
        _assert_no_sensitive_traceback_references(
            caught.value,
            canaries=(_BASE_URL_CANARY, _BEARER_KEY_CANARY, body_canary),
            forbidden_objects=(
                client,
                injected_http_client,
                response,
                document,
            ),
        )
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_operation_failures_scrub_bound_state_from_tracebacks() -> None:
    """Public operation frames do not retain the client or its bound secrets."""
    failure_message = "private transport detail"

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(failure_message, request=request)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesTransportError) as probe_failure:
                await client.probe_capabilities()
            with pytest.raises(HermesTransportError) as stream_failure:
                await anext(client.stream_chat_events({"private": "request"}))

        for failure in (probe_failure.value, stream_failure.value):
            assert failure.retryable is True
            for frame_locals in _package_traceback_locals(failure):
                assert all(value is not client for value in frame_locals.values())
                assert frame_locals.get("delegated_stream") is None
                rendered = repr(frame_locals)
                assert _BASE_URL_CANARY not in rendered
                assert _BEARER_KEY_CANARY not in rendered
    finally:
        await injected_http_client.aclose()


@pytest.mark.asyncio
async def test_owned_client_honors_verify_false() -> None:
    """An owned client receives an explicit disabled-verification option."""
    owned_http_client = httpx.AsyncClient()
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        verify=False,
    )

    with patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory):
        async with client:
            pass

    assert factory.calls == [(False, False)]
    assert owned_http_client.is_closed is True
