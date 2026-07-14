"""Public client lifecycle, ownership, and bound-operation tests."""

from __future__ import annotations

import asyncio
import json
import ssl
import traceback
from contextlib import asynccontextmanager
from types import MappingProxyType
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import httpx
import pytest

from hermes_agent_api_client import (
    AssistantDeltaEvent,
    HermesAgentApiClient,
    HermesEvent,
    HermesHttpStatusError,
    HermesProtocolError,
    HermesTransportError,
    TerminalEvent,
    TerminalOutcome,
)
from hermes_agent_api_client.models import FailureCategory
from tests.helpers.hermes import load_golden_json

if TYPE_CHECKING:
    from collections.abc import (
        AsyncGenerator,
        AsyncIterator,
        Callable,
        Iterable,
        Mapping,
    )
    from types import TracebackType


_INACTIVE_MESSAGE = "HermesAgentApiClient is not active"
_SINGLE_USE_MESSAGE = "HermesAgentApiClient instances are single-use"
_VERIFY_INJECTION_MESSAGE = "verify cannot be supplied with an injected HTTP client"
_BASE_URL_CANARY = "https://hermes.example/private-base"
_BEARER_KEY_CANARY = "lifecycle-bearer-key-canary"
_UPSTREAM_STATUS_CODE = 503
_UPSTREAM_STATUS_MESSAGE = "upstream status"


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

    with pytest.raises(RuntimeError) as stream_failure:
        await anext(client.stream_chat_events({}))
    _assert_safe_lifecycle_error(
        stream_failure.value,
        expected_message=_INACTIVE_MESSAGE,
        client=client,
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
            with pytest.raises(asyncio.CancelledError) as failure:
                await anext(client.stream_chat_events({"model": "hermes"}))

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
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
                    {"model": "hermes", "messages": (), "stream": True}
                ),
            )
            assert await anext(public_stream) == AssistantDeltaEvent(text="hello")
            assert response_stream.closed is False

            await public_stream.aclose()

            assert response_stream.closed is True
            assert injected_http_client.is_closed is False
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
