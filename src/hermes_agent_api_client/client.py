"""Bounded HTTP operations for the Hermes API protocol contracts."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import httpx

from .models import HermesCapabilities, HermesEvent, TerminalEvent
from .protocol import (
    HermesAuthenticationError,
    HermesContractError,
    HermesHttpStatusError,
    HermesProtocolError,
    HermesTransportError,
    validate_capabilities,
)
from .sse import async_decode_hermes_sse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping


_CAPABILITY_REQUEST_TIMEOUT = httpx.Timeout(10.0)
_CAPABILITIES_DEADLINE_SECONDS = 10.0
_MAX_CAPABILITIES_BYTES = 65_536

# Hermes v2026.7.7.2 emits SSE keepalives after 30 seconds of inactivity.
_HERMES_SSE_KEEPALIVE_SECONDS = 30.0
# A 15-second margin tolerates normal keepalive scheduling and network jitter.
_CHAT_STREAM_READ_TIMEOUT_SECONDS = 45.0
_CHAT_STREAM_TIMEOUT = httpx.Timeout(
    10.0,
    read=_CHAT_STREAM_READ_TIMEOUT_SECONDS,
)

_SUPPORTED_SCHEMES = frozenset({"http", "https"})
_VISIBLE_ASCII_MIN = 0x21
_VISIBLE_ASCII_MAX = 0x7E
_MAX_CONTENT_LENGTH_DIGITS = 20


def _normalize_base_url(  # pyright: ignore[reportUnusedFunction]
    base_url: str,
) -> httpx.URL:
    """Normalize one absolute HTTP base URL without retaining invalid input."""
    parsed: httpx.URL | None = None
    try:
        if isinstance(base_url, str) and base_url.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
            parsed = httpx.URL(base_url)
    except (TypeError, ValueError, httpx.InvalidURL):
        pass
    if (
        parsed is None
        or parsed.scheme not in _SUPPORTED_SCHEMES
        or not parsed.is_absolute_url
        or not parsed.host
        or bool(parsed.userinfo)
    ):
        raise HermesTransportError(transient=False)
    return parsed


def _operation_url(base_url: httpx.URL, path: str) -> httpx.URL:
    """Append an ASCII operation path while preserving encoded base semantics."""
    encoded_base_path = base_url.raw_path.split(b"?", 1)[0].rstrip(b"/")
    return base_url.copy_with(
        raw_path=encoded_base_path + path.encode("ascii"),
        query=None,
        fragment=None,
    )


def _request_headers(  # pyright: ignore[reportUnusedFunction]
    bearer_key: str,
    *,
    json_body: bool = False,
) -> dict[str, str]:
    """Build bearer headers from visible ASCII without retaining bad input."""
    if (
        not isinstance(bearer_key, str)  # pyright: ignore[reportUnnecessaryIsInstance]
        or not bearer_key
        or not bearer_key.isascii()
        or any(
            not _VISIBLE_ASCII_MIN <= ord(character) <= _VISIBLE_ASCII_MAX
            for character in bearer_key
        )
    ):
        raise HermesTransportError(transient=False)
    headers = {"Authorization": f"Bearer {bearer_key}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _serialize_request(request: Mapping[str, object]) -> bytes:
    """Serialize compact strict JSON without retaining serialization failures."""
    invalid_body = False
    payload = b""
    try:
        payload = json.dumps(
            dict(request),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    except (TypeError, ValueError, RecursionError, UnicodeError):
        invalid_body = True
    if invalid_body:
        raise HermesTransportError(transient=False)
    return payload


def _status_failure(status_code: int) -> HermesContractError:
    """Classify an HTTP status without retaining its response exception."""
    if status_code in {401, 403}:
        return HermesAuthenticationError(status_code=status_code)
    return HermesHttpStatusError(status_code=status_code)


def _declared_content_length(response: httpx.Response) -> tuple[bool, int | None]:
    """Validate a bounded decimal Content-Length value."""
    value = response.headers.get("content-length")
    if value is None:
        return (True, None)
    if (
        len(value) > _MAX_CONTENT_LENGTH_DIGITS
        or not value.isascii()
        or not value.isdigit()
    ):
        return (False, None)
    length = int(value)
    if length > _MAX_CAPABILITIES_BYTES:
        return (False, None)
    return (True, length)


async def _read_capabilities_body(
    http_client: httpx.AsyncClient,
    endpoint: httpx.URL,
    headers: Mapping[str, str],
) -> bytes | None:
    """Read one capability response incrementally within the byte budget."""
    payload = bytearray()
    async with http_client.stream(
        "GET",
        endpoint,
        headers=headers,
        timeout=_CAPABILITY_REQUEST_TIMEOUT,
        follow_redirects=False,
    ) as response:
        response.raise_for_status()
        valid_length, _ = _declared_content_length(response)
        if valid_length:
            async for chunk in response.aiter_bytes():
                if len(chunk) > _MAX_CAPABILITIES_BYTES - len(payload):
                    valid_length = False
                    break
                payload.extend(chunk)
        if not valid_length:
            return None
    return bytes(payload)


def _load_json(payload: bytes) -> tuple[bool, object]:
    """Decode JSON without retaining parser errors or rejected response bytes."""
    try:
        return (True, json.loads(payload))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return (False, None)


async def _probe_capabilities(  # pyright: ignore[reportUnusedFunction]
    http_client: httpx.AsyncClient,
    base_url: httpx.URL,
    headers: Mapping[str, str],
) -> HermesCapabilities:
    """Fetch and validate bounded capabilities using a caller-owned client."""
    endpoint = _operation_url(base_url, "/v1/capabilities")
    payload: bytes | None = None
    transport_failure: HermesContractError | None = None
    try:
        async with asyncio.timeout(_CAPABILITIES_DEADLINE_SECONDS):
            payload = await _read_capabilities_body(http_client, endpoint, headers)
    except TimeoutError:
        transport_failure = HermesTransportError(transient=True)
    except httpx.HTTPStatusError as error:
        transport_failure = _status_failure(error.response.status_code)
    except httpx.RequestError:
        transport_failure = HermesTransportError(transient=True)
    if transport_failure is not None:
        raise transport_failure
    if payload is None:
        raise HermesProtocolError

    valid_json, document = _load_json(payload)
    if not valid_json:
        raise HermesProtocolError
    return validate_capabilities(document)


async def _stream_chat_events(  # pyright: ignore[reportUnusedFunction]
    http_client: httpx.AsyncClient,
    base_url: httpx.URL,
    headers: Mapping[str, str],
    request: Mapping[str, object],
) -> AsyncIterator[HermesEvent]:
    """Stream events while owning only the individual response lifetime."""
    endpoint = _operation_url(base_url, "/v1/chat/completions")
    request_headers = dict(headers)
    request_headers["Content-Type"] = "application/json"
    request_body = _serialize_request(request)

    protocol_failure: HermesProtocolError | None = None
    terminal_events: list[TerminalEvent] = []
    transport_failure: HermesContractError | None = None
    try:
        async with http_client.stream(
            "POST",
            endpoint,
            headers=request_headers,
            content=request_body,
            timeout=_CHAT_STREAM_TIMEOUT,
            follow_redirects=False,
        ) as response:
            response.raise_for_status()
            try:
                async for event in async_decode_hermes_sse(response.aiter_bytes()):
                    if isinstance(event, TerminalEvent):
                        terminal_events.append(event)
                    else:
                        yield event
            except HermesProtocolError as error:
                protocol_failure = error
    except httpx.HTTPStatusError as error:
        transport_failure = _status_failure(error.response.status_code)
    except httpx.RequestError:
        transport_failure = HermesTransportError(transient=True)

    if transport_failure is not None:
        raise transport_failure
    if protocol_failure is not None:
        raise protocol_failure
    yield terminal_events[0]
