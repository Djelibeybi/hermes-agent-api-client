"""Bounded transport-independent decoding for Hermes SSE streams."""

from __future__ import annotations

import asyncio
import codecs
import json
from typing import TYPE_CHECKING, Never, Protocol, cast, runtime_checkable

from .models import (
    AssistantDeltaEvent,
    HermesEvent,
    KeepaliveEvent,
    TerminalEvent,
    TerminalFailureReason,
    TerminalOutcome,
    ToolProgressEvent,
    ToolProgressStatus,
    UsageEvent,
)
from .protocol import (
    _MISSING_JSON_MEMBER,  # pyright: ignore[reportPrivateUsage]
    HermesProtocolError,
    HermesTransportError,
    _json_object_pairs_hook,  # pyright: ignore[reportPrivateUsage]
    _parse_chat_chunk,  # pyright: ignore[reportPrivateUsage]
    _parse_tool_progress,  # pyright: ignore[reportPrivateUsage]
    _project_chat_chunk_object,  # pyright: ignore[reportPrivateUsage]
    _project_tool_progress_object,  # pyright: ignore[reportPrivateUsage]
    _TerminalMetadata,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Iterator


# A single unterminated wire line may retain at most 256 KiB of raw input.
MAX_PENDING_BYTES = 262_144
# Joined application data is limited to 64 KiB of decoded Unicode characters.
MAX_EVENT_DATA_CHARS = 65_536
_CR = 0x0D
_LF = 0x0A
_TERMINAL_MAPPING_FAILURE = object()


@runtime_checkable
class _SupportsAclose(Protocol):
    """An owned asynchronous iterator that supports explicit closure."""

    async def aclose(self) -> None:
        """Release the iterator's upstream resources."""


def _raise_protocol_failure() -> Never:
    """Raise a fresh protocol failure from a raw-record-free frame."""
    raise HermesProtocolError


def _raise_transport_failure() -> Never:
    """Raise a fresh retryable transport failure from a safe frame."""
    failure = HermesTransportError(transient=True)
    try:
        raise failure
    except HermesTransportError as caught:
        BaseException.__setattr__(caught, "__cause__", None)
        BaseException.__setattr__(caught, "__context__", None)
        raise


def _reraise_cancellation(cancellation: asyncio.CancelledError) -> Never:
    """Re-raise one cancellation after removing retained package traceback state."""
    cancellation = cancellation.with_traceback(None)
    try:
        raise cancellation
    except asyncio.CancelledError as caught:
        BaseException.__setattr__(caught, "__cause__", None)
        BaseException.__setattr__(caught, "__context__", None)
        raise


def _load_json_safely(data: str) -> tuple[bool, object]:
    """Parse JSON without retaining a value-bearing parser exception."""
    try:
        return (True, json.loads(data, object_pairs_hook=_json_object_pairs_hook))
    except (ValueError, RecursionError, UnicodeError):
        return (False, None)


def _decode_utf8_safely(
    decoder: codecs.IncrementalDecoder,
    data: bytes,
    *,
    final: bool,
) -> tuple[bool, str]:
    """Decode UTF-8 without retaining the rejected bytes in an exception."""
    try:
        return (True, decoder.decode(data, final=final))
    except UnicodeDecodeError:
        return (False, "")


def _map_terminal_event(  # noqa: PLR0911 - closed total matrix exits per row
    finish_reason: str | None,
    metadata: _TerminalMetadata,
) -> TerminalEvent | None | object:
    """Map only the locked total terminal rows into closed public values."""
    missing = _MISSING_JSON_MEMBER
    if finish_reason is None:
        if any(
            value is not missing
            for value in (
                metadata.completed,
                metadata.failed,
                metadata.partial,
                metadata.error_code,
            )
        ):
            return _TERMINAL_MAPPING_FAILURE
        return None

    if finish_reason == "stop":
        if (
            metadata.completed not in (missing, True)
            or metadata.failed not in (missing, False)
            or metadata.partial not in (missing, False)
            or metadata.error_code is not missing
        ):
            return _TERMINAL_MAPPING_FAILURE
        return TerminalEvent(
            outcome=TerminalOutcome.SUCCESS,
            partial=False,
            failure_reason=None,
        )

    if finish_reason == "length":
        if (
            metadata.completed not in (missing, False)
            or metadata.failed not in (missing, False)
            or metadata.partial not in (missing, True)
            or metadata.error_code not in (missing, "output_truncated")
        ):
            return _TERMINAL_MAPPING_FAILURE
        return TerminalEvent(
            outcome=TerminalOutcome.LENGTH,
            partial=True,
            failure_reason=TerminalFailureReason.OUTPUT_TRUNCATED,
        )

    if (
        not metadata.root_present
        or metadata.completed not in (missing, False)
        or metadata.failed not in (missing, True)
        or metadata.partial is missing
    ):
        return _TERMINAL_MAPPING_FAILURE
    failure_reason = (
        TerminalFailureReason.AGENT_ERROR
        if metadata.error_code in (missing, "agent_error")
        else TerminalFailureReason.UNKNOWN
    )
    return TerminalEvent(
        outcome=TerminalOutcome.UPSTREAM_ERROR,
        partial=cast("bool", metadata.partial),
        failure_reason=failure_reason,
    )


def _decode_application_record(  # noqa: C901, PLR0911 - invalid wire shapes exit locally
    event_name: str | None,
    data: str,
) -> tuple[HermesEvent, ...] | None:
    """Return translated events or a sentinel without retaining rejected data."""
    valid_json, document = _load_json_safely(data)
    if not valid_json:
        return None
    if event_name == "hermes.tool.progress":
        projected = _project_tool_progress_object(document)
        document = None
        if projected is None:
            return None
        progress = _parse_tool_progress(projected)
        projected = None
        if progress is None:
            return None
        return (
            ToolProgressEvent(
                tool_call_id=progress.tool_call_id,
                tool_name=progress.tool,
                status=ToolProgressStatus(progress.status),
            ),
        )
    if event_name not in (None, "", "message"):
        return None

    projected = _project_chat_chunk_object(document)
    document = None
    if projected is None:
        return None
    chat_document = projected.document
    terminal_metadata = projected.terminal_metadata
    projected = None
    chunk = _parse_chat_chunk(chat_document)
    chat_document = None
    if chunk is None:
        terminal_metadata = None
        return None
    choice = chunk.choices[0]
    delta = choice.delta
    finish_reason = choice.finish_reason
    terminal_event = _map_terminal_event(finish_reason, terminal_metadata)
    terminal_metadata = None
    if terminal_event is _TERMINAL_MAPPING_FAILURE:
        terminal_event = None
        return None

    events: list[HermesEvent] = []
    role = delta.role
    content = delta.content
    if content is not None:
        events.append(AssistantDeltaEvent(text=content))

    usage = chunk.usage
    if usage is not None:
        events.append(
            UsageEvent(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
        )

    if isinstance(terminal_event, TerminalEvent):
        events.append(terminal_event)

    if not events and role != "assistant":
        return None
    return tuple(events)


class _SSEDecoder:
    """Own all bounded framing and terminal state for one stream invocation."""

    def __init__(self) -> None:
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        self._line_chars: list[str] = []
        self._raw_line_bytes = 0
        self._text_previous_cr = False
        self._data_lines: list[str] = []
        self._data_chars = 0
        self._event_name: str | None = None
        self._comment_seen = False
        self._record_touched = False
        self._pending_terminal: TerminalEvent | None = None
        self._done_seen = False
        self._failed = False

    @property
    def failed(self) -> bool:
        """Report whether a raw-input-free protocol failure is pending."""
        return self._failed

    def _clear_record(self) -> None:
        """Discard all state derived from the current framed record."""
        self._data_lines = []
        self._data_chars = 0
        self._event_name = None
        self._comment_seen = False
        self._record_touched = False

    def scrub(self) -> None:
        """Discard every raw-input-bearing state field before public failure."""
        self._clear_record()
        self._line_chars = []
        self._raw_line_bytes = 0
        self._text_previous_cr = False
        self._pending_terminal = None
        self._done_seen = False

    def _fail(self) -> None:
        """Mark an expected protocol failure after clearing decoded state."""
        self.scrub()
        self._failed = True

    def _events_for_data(self) -> tuple[HermesEvent, ...] | None:
        """Translate joined record data or return a sanitized failure sentinel."""
        data = "\n".join(self._data_lines)
        if data != "[DONE]":
            return _decode_application_record(self._event_name, data)
        if self._event_name not in (None, "", "message") or self._done_seen:
            return None
        self._done_seen = True
        if self._pending_terminal is None:
            return (TerminalEvent(outcome=TerminalOutcome.SUCCESS),)
        return ()

    def _accept_events(
        self,
        events: tuple[HermesEvent, ...],
    ) -> tuple[HermesEvent, ...] | None:
        """Enforce the one-terminal boundary without retaining raw events."""
        accepted: list[HermesEvent] = []
        for event in events:
            if self._pending_terminal is not None:
                return None
            if isinstance(event, TerminalEvent):
                self._pending_terminal = event
            else:
                accepted.append(event)
        return tuple(accepted)

    def _dispatch_record(self) -> tuple[HermesEvent, ...]:
        """Dispatch one complete record and reset its framing state."""
        if self._data_lines:
            events = self._events_for_data()
        elif self._comment_seen:
            events = (KeepaliveEvent(),)
        else:
            events = ()

        self._clear_record()
        if events is None:
            self._fail()
            return ()
        accepted = self._accept_events(events)
        events = ()
        if accepted is None:
            self._fail()
            return ()
        return accepted

    def _consume_line(self, line: str) -> tuple[HermesEvent, ...]:
        """Apply WHATWG field parsing to one decoded line."""
        if not line:
            return self._dispatch_record()

        self._record_touched = True
        if line.startswith(":"):
            self._comment_seen = True
            return ()

        field, separator, value = line.partition(":")
        if not separator:
            value = ""
        elif value.startswith(" "):
            value = value[1:]

        if field == "data":
            next_size = self._data_chars + len(value) + bool(self._data_lines)
            if next_size > MAX_EVENT_DATA_CHARS:
                self._fail()
                return ()
            self._data_lines.append(value)
            self._data_chars = next_size
        elif field == "event":
            self._event_name = value
        return ()

    def _consume_text(self, text: str) -> Iterator[HermesEvent]:
        """Frame decoded text while preserving CR/LF/CRLF boundaries."""
        for char in text:
            if self._text_previous_cr:
                self._text_previous_cr = False
                if char == "\n":
                    continue
            if char == "\r":
                yield from self._consume_line("".join(self._line_chars))
                self._line_chars = []
                self._text_previous_cr = True
            elif char == "\n":
                yield from self._consume_line("".join(self._line_chars))
                self._line_chars = []
            else:
                self._line_chars.append(char)

    def consume_chunk(self, chunk: object) -> Iterator[HermesEvent]:
        """Consume one bounded raw transport chunk."""
        if not isinstance(chunk, bytes):
            self._fail()
            return

        for value in chunk:
            if self._failed:
                return
            if value in (_CR, _LF):
                self._raw_line_bytes = 0
            else:
                self._raw_line_bytes += 1
                if self._raw_line_bytes > MAX_PENDING_BYTES:
                    self._fail()
                    return
            valid_utf8, decoded = _decode_utf8_safely(
                self._utf8_decoder,
                bytes((value,)),
                final=False,
            )
            if not valid_utf8:
                self._fail()
                return
            yield from self._consume_text(decoded)

    def finalize(self) -> TerminalEvent | None:
        """Return a terminal or a sanitized failure sentinel after validation."""
        valid_utf8, _ = _decode_utf8_safely(self._utf8_decoder, b"", final=True)
        if not valid_utf8:
            self._fail()
            return None
        if self._line_chars or self._record_touched:
            self._fail()
            return None
        if self._pending_terminal is None:
            self._fail()
            return None
        return self._pending_terminal


async def async_decode_hermes_sse(  # noqa: C901, PLR0912, PLR0915 - explicit outcome precedence
    byte_chunks: AsyncIterable[bytes],
) -> AsyncIterator[HermesEvent]:
    """Decode strict bounded SSE bytes into the closed Hermes event vocabulary."""
    decoder = _SSEDecoder()
    source: AsyncIterator[bytes] | None = None
    raw_chunk = b""
    event: HermesEvent | None = None
    terminal: TerminalEvent | None = None
    protocol_failed = False
    transport_failed = False
    cancellation: asyncio.CancelledError | None = None
    try:
        source = aiter(byte_chunks)
    except asyncio.CancelledError as caught:
        cancellation = caught.with_traceback(None)
    except Exception:  # noqa: BLE001 - map opaque iterator acquisition failures safely
        transport_failed = True
    if cancellation is not None:
        decoder.scrub()
        del source
        del byte_chunks
        del raw_chunk
        event = None
        terminal = None
        del decoder
        _reraise_cancellation(cancellation)
    if transport_failed:
        decoder.scrub()
        del source
        del byte_chunks
        del raw_chunk
        event = None
        terminal = None
        del decoder
        _raise_transport_failure()
    source = cast("AsyncIterator[bytes]", source)
    try:
        try:
            async for raw_chunk in source:
                for event in decoder.consume_chunk(raw_chunk):
                    yield event
                event = None
                if decoder.failed:
                    protocol_failed = True
                    break
            if not protocol_failed:
                terminal = decoder.finalize()
                protocol_failed = terminal is None
        except asyncio.CancelledError as caught:
            cancellation = caught.with_traceback(None)
        except Exception:  # noqa: BLE001 - map opaque source failures safely
            transport_failed = True
    finally:
        cleanup_failed = False
        cleanup_cancellation: asyncio.CancelledError | None = None
        try:
            if isinstance(source, _SupportsAclose):
                await source.aclose()
        except asyncio.CancelledError as caught:
            if cancellation is None and not protocol_failed and not transport_failed:
                cleanup_cancellation = caught.with_traceback(None)
        except Exception:  # noqa: BLE001 - map opaque cleanup failures safely
            if cancellation is None and not protocol_failed and not transport_failed:
                cleanup_failed = True
        if cleanup_cancellation is not None:
            decoder.scrub()
            del source
            del byte_chunks
            del raw_chunk
            event = None
            terminal = None
            del decoder
            _reraise_cancellation(cleanup_cancellation)
        if cleanup_failed:
            decoder.scrub()
            del source
            del byte_chunks
            del raw_chunk
            event = None
            terminal = None
            del decoder
            _raise_transport_failure()
    del source
    del byte_chunks
    del raw_chunk
    event = None
    if cancellation is not None:
        decoder.scrub()
        terminal = None
        del decoder
        _reraise_cancellation(cancellation)
    if protocol_failed:
        decoder.scrub()
        terminal = None
        del decoder
        _raise_protocol_failure()
    if transport_failed:
        decoder.scrub()
        terminal = None
        del decoder
        _raise_transport_failure()
    del decoder
    yield cast("TerminalEvent", terminal)
