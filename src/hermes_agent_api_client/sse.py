"""Bounded transport-independent decoding for Hermes SSE streams."""

from __future__ import annotations

import codecs
import json
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .models import (
    AssistantDeltaEvent,
    HermesEvent,
    KeepaliveEvent,
    TerminalEvent,
    TerminalOutcome,
    ToolProgressEvent,
    UsageEvent,
)
from .protocol import (
    HermesProtocolError,
    _parse_chat_chunk,  # pyright: ignore[reportPrivateUsage]
    _parse_tool_progress,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Iterator


# A single unterminated wire line may retain at most 256 KiB of raw input.
MAX_PENDING_BYTES = 262_144
# Joined application data is limited to 64 KiB of decoded Unicode characters.
MAX_EVENT_DATA_CHARS = 65_536
_CR = 0x0D
_LF = 0x0A


@runtime_checkable
class _SupportsAclose(Protocol):
    """An owned asynchronous iterator that supports explicit closure."""

    async def aclose(self) -> None:
        """Release the iterator's upstream resources."""


def _protocol_failure() -> HermesProtocolError:
    """Return the stable metadata-only protocol failure."""
    return HermesProtocolError()


def _load_json_safely(data: str) -> tuple[bool, object]:
    """Parse JSON without retaining a value-bearing parser exception."""
    try:
        return (True, json.loads(data))
    except (json.JSONDecodeError, UnicodeError):
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


def _decode_application_record(
    event_name: str | None,
    data: str,
) -> tuple[HermesEvent, ...]:
    """Decode one strict documented Hermes/OpenAI application record."""
    valid_json, document = _load_json_safely(data)
    if not valid_json:
        raise _protocol_failure()
    if event_name == "hermes.tool.progress":
        progress = _parse_tool_progress(document)
        if progress is None:
            raise _protocol_failure()
        return (ToolProgressEvent(tool_name=progress.tool, status=progress.status),)
    if event_name not in (None, "", "message"):
        raise _protocol_failure()

    chunk = _parse_chat_chunk(document)
    if chunk is None:
        raise _protocol_failure()
    choice = chunk.choices[0]
    delta = choice.delta
    finish_reason = choice.finish_reason

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

    terminal_outcome = {
        None: None,
        "stop": TerminalOutcome.SUCCESS,
        "length": TerminalOutcome.LENGTH,
        "error": TerminalOutcome.UPSTREAM_ERROR,
    }[finish_reason]
    if terminal_outcome is not None:
        events.append(TerminalEvent(outcome=terminal_outcome))

    if not events and role != "assistant":
        raise _protocol_failure()
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

    def _events_for_data(self) -> tuple[HermesEvent, ...]:
        """Translate joined record data into application events."""
        data = "\n".join(self._data_lines)
        if data != "[DONE]":
            return _decode_application_record(self._event_name, data)
        if self._event_name not in (None, "", "message") or self._done_seen:
            raise _protocol_failure()
        self._done_seen = True
        if self._pending_terminal is None:
            return (TerminalEvent(outcome=TerminalOutcome.SUCCESS),)
        return ()

    def _accept_events(
        self,
        events: tuple[HermesEvent, ...],
    ) -> tuple[HermesEvent, ...]:
        """Enforce the one-terminal boundary for dispatched events."""
        accepted: list[HermesEvent] = []
        for event in events:
            if self._pending_terminal is not None:
                raise _protocol_failure()
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

        self._data_lines = []
        self._data_chars = 0
        self._event_name = None
        self._comment_seen = False
        self._record_touched = False
        return self._accept_events(events)

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
                raise _protocol_failure()
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
            raise _protocol_failure()

        for value in chunk:
            if value in (_CR, _LF):
                self._raw_line_bytes = 0
            else:
                self._raw_line_bytes += 1
                if self._raw_line_bytes > MAX_PENDING_BYTES:
                    raise _protocol_failure()
            valid_utf8, decoded = _decode_utf8_safely(
                self._utf8_decoder,
                bytes((value,)),
                final=False,
            )
            if not valid_utf8:
                raise _protocol_failure()
            yield from self._consume_text(decoded)

    def finalize(self) -> TerminalEvent:
        """Return a terminal only after all framing and boundary validation."""
        valid_utf8, _ = _decode_utf8_safely(self._utf8_decoder, b"", final=True)
        if not valid_utf8:
            raise _protocol_failure()
        if self._line_chars or self._record_touched:
            raise _protocol_failure()
        if self._pending_terminal is None:
            raise _protocol_failure()
        return self._pending_terminal


async def async_decode_hermes_sse(
    byte_chunks: AsyncIterable[bytes],
) -> AsyncIterator[HermesEvent]:
    """Decode strict bounded SSE bytes into the closed Hermes event vocabulary."""
    decoder = _SSEDecoder()
    source = aiter(byte_chunks)
    try:
        async for chunk in source:
            for event in decoder.consume_chunk(chunk):
                yield event
        terminal = decoder.finalize()
    finally:
        if isinstance(source, _SupportsAclose):
            await source.aclose()
    yield terminal
