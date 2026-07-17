"""Bounded HTTP operations for the Hermes API protocol contracts."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Never, Protocol, cast, runtime_checkable

import httpx

from .models import (
    HermesCapabilities,
    HermesEvent,
    TerminalEvent,
    _require_lifecycle_text,  # pyright: ignore[reportPrivateUsage]
)
from .protocol import (
    HermesAuthenticationError,
    HermesContractError,
    HermesHttpStatusError,
    HermesProtocolError,
    HermesTransportError,
    _CapabilityFailureKind,  # pyright: ignore[reportPrivateUsage]
    _parse_capabilities,  # pyright: ignore[reportPrivateUsage]
    _raise_capability_failure,  # pyright: ignore[reportPrivateUsage]
)
from .sse import async_decode_hermes_sse

if TYPE_CHECKING:
    import ssl
    from collections.abc import AsyncIterator, Mapping
    from types import TracebackType
    from typing import Self


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
_WINDOWS_DRIVE_PREFIX_LENGTH = 2
_MAX_CONTENT_LENGTH_DIGITS = 20

_INACTIVE_CLIENT_MESSAGE = "HermesAgentApiClient is not active"
_SINGLE_USE_CLIENT_MESSAGE = "HermesAgentApiClient instances are single-use"
_VERIFY_INJECTION_MESSAGE = "verify cannot be supplied with an injected HTTP client"


@runtime_checkable
class _SupportsAclose(Protocol):
    """An owned asynchronous iterator that supports explicit closure."""

    async def aclose(self) -> None:
        """Release the iterator's upstream resources."""


def _raise_inactive_client() -> Never:
    """Raise the constant inactive error from a secret-free frame."""
    raise RuntimeError(_INACTIVE_CLIENT_MESSAGE)


def _raise_single_use_client() -> Never:
    """Raise the constant single-use error from a secret-free frame."""
    raise RuntimeError(_SINGLE_USE_CLIENT_MESSAGE)


def _raise_verify_injection_conflict() -> Never:
    """Raise the constant injection conflict from a secret-free frame."""
    raise ValueError(_VERIFY_INJECTION_MESSAGE)


def _reraise_scrubbed_failure(failure: BaseException) -> Never:
    """Re-raise a failure after its package traceback state was scrubbed."""
    if isinstance(failure, asyncio.CancelledError):
        failure = failure.with_traceback(None)
        BaseException.__setattr__(failure, "__cause__", None)
        BaseException.__setattr__(failure, "__context__", None)
    raise failure


def _raise_transport_failure(*, transient: bool) -> Never:
    """Raise one metadata-only transport failure from a safe frame."""
    raise HermesTransportError(transient=transient)


def _raise_protocol_failure() -> Never:
    """Raise one fresh metadata-only protocol failure from a safe frame."""
    raise HermesProtocolError


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
        base_url = ""
        parsed = None
        _raise_transport_failure(transient=False)
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
        bearer_key = ""
        _raise_transport_failure(transient=False)
    return {"Authorization": f"Bearer {bearer_key}"}


def _is_valid_session_value(value: object, *, reject_path_shape: bool) -> bool:
    """Return whether one optional session value meets the exact local contract."""
    if value is None:
        return True
    try:
        validated = _require_lifecycle_text(value)
    except ValueError:
        return False
    return not (
        reject_path_shape
        and (
            ".." in validated
            or "/" in validated
            or "\\" in validated
            or (
                len(validated) >= _WINDOWS_DRIVE_PREFIX_LENGTH
                and validated[0].isalpha()
                and validated[1] == ":"
            )
        )
    )


def _chat_request_headers(
    headers: Mapping[str, str],
    *,
    session_id: str | None,
    session_key: str | None,
) -> dict[str, str] | None:
    """Build fresh request headers after secret-safe session validation."""
    invalid = not _is_valid_session_value(
        session_id,
        reject_path_shape=True,
    ) or not _is_valid_session_value(
        session_key,
        reject_path_shape=False,
    )
    if invalid:
        return None

    request_headers = dict(headers)
    if session_id is not None:
        request_headers["X-Hermes-Session-Id"] = session_id
    if session_key is not None:
        request_headers["X-Hermes-Session-Key"] = session_key
    return request_headers


def _serialize_request(request: Mapping[str, object]) -> bytes:
    """Serialize compact strict JSON without retaining serialization failures."""
    invalid_body = False
    normalized_request: dict[str, object] = {}
    payload = b""
    try:
        normalized_request = dict(request)
        payload = json.dumps(
            normalized_request,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    except Exception:  # noqa: BLE001 - hostile mappings may raise any Exception
        invalid_body = True
    if invalid_body:
        request = {}
        normalized_request = {}
        payload = b""
        _raise_transport_failure(transient=False)
    return payload


def _serialize_request_safely(request: Mapping[str, object]) -> bytes | None:
    """Return serialized bytes or a sentinel after a sanitized failure."""
    try:
        return _serialize_request(request)
    except HermesTransportError:
        return None


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


async def _read_capabilities_body(  # noqa: C901, PLR0912, PLR0915
    http_client: httpx.AsyncClient,
    endpoint: httpx.URL,
    headers: Mapping[str, str],
) -> HermesCapabilities:
    """Read and validate one bounded capability response within its byte budget."""
    payload = bytearray()
    response: httpx.Response | None = None
    cancellation: asyncio.CancelledError | None = None
    status_code: int | None = None
    capability_failure: _CapabilityFailureKind | None = None
    read_transport_failed = False
    cleanup_failed = False
    primary_outcome = False
    chunk = b""
    capabilities: HermesCapabilities | None = None
    try:
        async with http_client.stream(
            "GET",
            endpoint,
            headers=headers,
            timeout=_CAPABILITY_REQUEST_TIMEOUT,
            follow_redirects=False,
        ) as response:
            try:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as error:
                    status_code = error.response.status_code
                    primary_outcome = True
                else:
                    valid_length, _ = _declared_content_length(response)
                    if valid_length:
                        try:
                            async for chunk in response.aiter_bytes():
                                if len(chunk) > _MAX_CAPABILITIES_BYTES - len(payload):
                                    valid_length = False
                                    break
                                payload.extend(chunk)
                        except Exception:  # noqa: BLE001 - classify read or close failures safely
                            if response.is_closed:
                                cleanup_failed = True
                            else:
                                read_transport_failed = True
                                primary_outcome = True
                    if not valid_length:
                        capability_failure = _CapabilityFailureKind.PROTOCOL
                        primary_outcome = True
                    elif not read_transport_failed:
                        capabilities, capability_failure = _parse_capabilities_payload(
                            bytes(payload)
                        )
                        primary_outcome = (
                            primary_outcome or capability_failure is not None
                        )
            except asyncio.CancelledError as caught:
                if not primary_outcome and response.is_closed:
                    capabilities, capability_failure = _parse_capabilities_payload(
                        bytes(payload)
                    )
                    primary_outcome = capability_failure is not None
                if not primary_outcome:
                    cancellation = caught.with_traceback(None)
    except (asyncio.CancelledError, Exception):
        if (
            cancellation is None
            and not primary_outcome
            and response is not None
            and response.is_closed
        ):
            capabilities, capability_failure = _parse_capabilities_payload(
                bytes(payload)
            )
            primary_outcome = capability_failure is not None
        if cancellation is None and not primary_outcome:
            raise
    if cancellation is not None:
        response = None
        payload.clear()
        payload = bytearray()
        del http_client, endpoint, headers
        _reraise_scrubbed_failure(cancellation)
    if status_code is not None:
        response = None
        payload.clear()
        payload = bytearray()
        del http_client, endpoint, headers
        raise _status_failure(status_code)
    if capability_failure is not None:
        response = None
        chunk = b""
        payload.clear()
        payload = bytearray()
        capabilities = None
        del http_client, endpoint, headers
        _raise_capability_failure(capability_failure)
    if read_transport_failed:
        response = None
        chunk = b""
        payload.clear()
        payload = bytearray()
        capabilities = None
        del http_client, endpoint, headers
        _raise_transport_failure(transient=True)
    if cleanup_failed:
        response = None
        chunk = b""
        payload.clear()
        payload = bytearray()
        capabilities = None
        del http_client, endpoint, headers
        _raise_transport_failure(transient=True)
    return cast("HermesCapabilities", capabilities)


def _load_json(payload: bytes) -> tuple[bool, object]:
    """Decode JSON without retaining parser errors or rejected response bytes."""
    try:
        return (True, json.loads(payload))
    except (ValueError, RecursionError, UnicodeError):
        return (False, None)


def _parse_capabilities_payload(
    payload: bytes,
) -> tuple[HermesCapabilities | None, _CapabilityFailureKind | None]:
    """Parse one bounded capability payload into a value or safe failure kind."""
    valid_json, document = _load_json(payload)
    if not valid_json:
        return (None, _CapabilityFailureKind.PROTOCOL)
    capabilities, failure_kind = _parse_capabilities(document)
    document = None
    if failure_kind is not None:
        return (None, failure_kind)
    if capabilities is None:
        return (None, _CapabilityFailureKind.PROTOCOL)
    return (capabilities, None)


async def _probe_capabilities(  # pyright: ignore[reportUnusedFunction]
    http_client: httpx.AsyncClient,
    base_url: httpx.URL,
    headers: Mapping[str, str],
) -> HermesCapabilities:
    """Fetch and validate bounded capabilities using a caller-owned client."""
    endpoint = _operation_url(base_url, "/v1/capabilities")
    capabilities: HermesCapabilities | None = None
    status_failure: HermesContractError | None = None
    transport_failed = False
    try:
        async with asyncio.timeout(_CAPABILITIES_DEADLINE_SECONDS):
            capabilities = await _read_capabilities_body(http_client, endpoint, headers)
    except TimeoutError:
        transport_failed = True
    except HermesContractError as error:
        status_failure = error
    except httpx.RequestError:
        transport_failed = True
    except Exception:  # noqa: BLE001 - translate opaque cleanup failures safely
        transport_failed = True
    if transport_failed:
        del http_client, base_url, headers, endpoint
        capabilities = None
        _raise_transport_failure(transient=True)
    if status_failure is not None:
        del http_client, base_url, headers, endpoint
        capabilities = None
        raise status_failure
    return cast("HermesCapabilities", capabilities)


async def _stream_chat_events(  # pyright: ignore[reportUnusedFunction]  # noqa: C901, PLR0912, PLR0915
    http_client: httpx.AsyncClient,
    base_url: httpx.URL,
    headers: Mapping[str, str],
    request: Mapping[str, object],
) -> AsyncIterator[HermesEvent]:
    """Stream events while owning only the individual response lifetime."""
    endpoint = _operation_url(base_url, "/v1/chat/completions")
    request_headers = dict(headers)
    request_headers["Content-Type"] = "application/json"
    headers = {}
    request_body = _serialize_request_safely(request)
    if request_body is None:
        del http_client, base_url, headers, request, endpoint
        request_headers.clear()
        _raise_transport_failure(transient=False)

    protocol_failed = False
    event: HermesEvent | None = None
    terminal_events: list[TerminalEvent] = []
    transport_failure: HermesContractError | None = None
    response: httpx.Response | None = None
    cancellation: asyncio.CancelledError | None = None
    try:
        async with http_client.stream(
            "POST",
            endpoint,
            headers=request_headers,
            content=request_body,
            timeout=_CHAT_STREAM_TIMEOUT,
            follow_redirects=False,
        ) as response:
            request_headers.clear()
            try:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as error:
                    transport_failure = _status_failure(error.response.status_code)
                else:
                    try:
                        async for event in async_decode_hermes_sse(
                            response.aiter_bytes()
                        ):
                            if isinstance(event, TerminalEvent):
                                terminal_events.append(event)
                            else:
                                yield event
                    except HermesProtocolError:
                        protocol_failed = True
                    except HermesTransportError:
                        transport_failure = HermesTransportError(transient=True)
            except asyncio.CancelledError as caught:
                cancellation = caught.with_traceback(None)
    except asyncio.CancelledError as caught:
        if cancellation is None:
            cancellation = caught.with_traceback(None)
    except httpx.HTTPStatusError as error:
        if cancellation is None and transport_failure is None and not protocol_failed:
            transport_failure = _status_failure(error.response.status_code)
    except httpx.RequestError:
        if cancellation is None and transport_failure is None and not protocol_failed:
            transport_failure = HermesTransportError(transient=True)
    except Exception:  # noqa: BLE001 - translate opaque cleanup failures safely
        if cancellation is None and transport_failure is None and not protocol_failed:
            transport_failure = HermesTransportError(transient=True)

    response = None
    event = None
    if protocol_failed:
        cancellation = None
        del http_client, base_url, headers, request, endpoint
        request_headers.clear()
        request_body = b""
        terminal_events.clear()
        _raise_protocol_failure()
    if transport_failure is not None:
        cancellation = None
        del http_client, base_url, headers, request, endpoint
        request_headers.clear()
        request_body = b""
        terminal_events.clear()
        raise transport_failure
    if cancellation is not None:
        del http_client, base_url, headers, request, endpoint
        request_headers.clear()
        request_body = b""
        terminal_events.clear()
        _reraise_scrubbed_failure(cancellation)
    terminal_event = terminal_events[0]
    terminal_events.clear()
    del http_client, base_url, headers, request, endpoint
    request_headers.clear()
    request_body = b""
    yield terminal_event


class HermesAgentApiClient:
    """Single-use async context manager for bound Hermes operations."""

    def __init__(
        self,
        base_url: str,
        bearer_key: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        verify: ssl.SSLContext | bool | None = None,
    ) -> None:
        """Bind endpoint, authentication, ownership, and TLS verification."""
        if http_client is not None and verify is not None:
            base_url = ""
            bearer_key = ""
            http_client = None
            verify = None
            del self
            _raise_verify_injection_conflict()
        bound_base_url: httpx.URL | None = None
        bound_headers: dict[str, str] | None = None
        binding_failure: BaseException | None = None
        try:
            bound_base_url = _normalize_base_url(base_url)
            bound_headers = _request_headers(bearer_key)
        except BaseException as caught:  # noqa: BLE001 - scrub on interruption
            caught = caught.with_traceback(None)
            binding_failure = caught
        base_url = ""
        bearer_key = ""
        if binding_failure is not None:
            bound_base_url = None
            bound_headers = None
            http_client = None
            verify = None
            del self
            _reraise_scrubbed_failure(binding_failure)
        self._base_url = cast("httpx.URL", bound_base_url)
        self._headers = cast("dict[str, str]", bound_headers)
        self._injected_http_client = http_client
        self._verify = True if verify is None else verify
        self._active_http_client: httpx.AsyncClient | None = None
        self._entered = False
        self._exited = False

    async def __aenter__(self) -> Self:
        """Activate this instance exactly once and create owned transport."""
        if self._entered or self._exited:
            del self
            _raise_single_use_client()
        active = self._injected_http_client
        if active is None:
            creation_failure: BaseException | None = None
            try:
                active = httpx.AsyncClient(
                    verify=self._verify,
                    follow_redirects=False,
                )
            except BaseException as caught:  # noqa: BLE001 - scrub on interruption
                caught = caught.with_traceback(None)
                creation_failure = caught
            if creation_failure is not None:
                del self
                _reraise_scrubbed_failure(creation_failure)
        self._active_http_client = active
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Deactivate this instance and close only an owned HTTP client."""
        active = self._active_http_client
        self._active_http_client = None
        self._exited = True
        owns_active = active is not None and self._injected_http_client is None
        body_failed = exc_value is not None
        cleanup_failed = False
        cleanup_cancellation: asyncio.CancelledError | None = None
        del self, exc_type, exc_value, traceback
        if owns_active:
            try:
                await cast("httpx.AsyncClient", active).aclose()
            except asyncio.CancelledError as cancellation:
                cleanup_cancellation = cancellation.with_traceback(None)
            except Exception:  # noqa: BLE001 - translate opaque cleanup failures safely
                cleanup_failed = True
        active = None
        if body_failed:
            return
        if cleanup_cancellation is not None:
            _reraise_scrubbed_failure(cleanup_cancellation)
        if cleanup_failed:
            _raise_transport_failure(transient=True)

    def _operation_bindings(
        self,
    ) -> tuple[httpx.AsyncClient, httpx.URL, Mapping[str, str]] | None:
        """Return active immutable operation bindings, if available."""
        active = self._active_http_client
        if active is None:
            return None
        return active, self._base_url, self._headers

    async def probe_capabilities(self) -> HermesCapabilities:
        """Fetch capabilities using this client's bound endpoint and auth."""
        bindings = self._operation_bindings()
        if bindings is None:
            del self, bindings
            _raise_inactive_client()
        active, base_url, headers = bindings
        bindings = None
        del self
        result: HermesCapabilities | None = None
        failure: BaseException | None = None
        try:
            result = await _probe_capabilities(active, base_url, headers)
        except BaseException as caught:  # noqa: BLE001 - scrub on cancellation too
            caught = caught.with_traceback(None)
            failure = caught
        active = None
        base_url = None
        headers = {}
        if failure is not None:
            _reraise_scrubbed_failure(failure)
        return cast("HermesCapabilities", result)

    async def stream_chat_events(
        self,
        request: Mapping[str, object],
        *,
        session_id: str | None = None,
        session_key: str | None = None,
    ) -> AsyncIterator[HermesEvent]:
        """Stream chat events using this client's bound endpoint and auth."""
        bindings = self._operation_bindings()
        if bindings is None:
            request, session_id, session_key = {}, None, None
            del self, bindings
            _raise_inactive_client()
        active, base_url, headers = bindings
        bindings = None
        del self
        operation_headers = _chat_request_headers(
            headers,
            session_id=session_id,
            session_key=session_key,
        )
        session_id = None
        session_key = None
        headers = {}
        if operation_headers is None:
            active = None
            base_url = None
            request = {}
            _raise_transport_failure(transient=False)
        event: HermesEvent | None = None
        operation_failure: BaseException | None = None
        delegated_stream: AsyncIterator[HermesEvent] | None = aiter(
            _stream_chat_events(
                active,
                base_url,
                operation_headers,
                request,
            )
        )
        operation_headers = {}
        try:
            async for event in delegated_stream:
                yield event
        except BaseException as caught:  # noqa: BLE001 - scrub on cancellation too
            if not isinstance(caught, GeneratorExit):
                caught = caught.with_traceback(None)
                operation_failure = caught
        finally:
            if isinstance(delegated_stream, _SupportsAclose):
                try:
                    await delegated_stream.aclose()
                except BaseException as caught:  # noqa: BLE001 - preserve close error
                    caught = caught.with_traceback(None)
                    if operation_failure is None:
                        operation_failure = caught
        active = None
        base_url = None
        request = {}
        event = None
        delegated_stream = None
        if operation_failure is not None:
            _reraise_scrubbed_failure(operation_failure)
