"""Public client lifecycle, ownership, and bound-operation tests."""

from __future__ import annotations

import ssl
from types import MappingProxyType
from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx
import pytest

from hermes_agent_api_client import (
    HermesAgentApiClient,
    HermesTransportError,
    TerminalEvent,
)
from tests.helpers.hermes import load_golden_json

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import TracebackType


_INACTIVE_MESSAGE = "HermesAgentApiClient is not active"
_SINGLE_USE_MESSAGE = "HermesAgentApiClient instances are single-use"
_VERIFY_INJECTION_MESSAGE = "verify cannot be supplied with an injected HTTP client"
_BASE_URL_CANARY = "https://hermes.example/private-base"
_BEARER_KEY_CANARY = "lifecycle-bearer-key-canary"


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

    def __init__(self, failure_message: str) -> None:
        """Store the safe close failure message."""
        self.failure_message = failure_message

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Reject requests because this transport exists only for close."""
        raise AssertionError(request)

    async def aclose(self) -> None:
        """Raise the controlled close failure."""
        raise RuntimeError(self.failure_message)


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
async def test_owned_client_close_failure_scrubs_bound_state() -> None:
    """An owned-client close failure does not retain the wrapper."""
    failure_message = "owned client close failed"
    owned_http_client = httpx.AsyncClient(
        transport=RaisingCloseTransport(failure_message)
    )
    factory = AsyncClientFactorySpy(owned_http_client)
    client = HermesAgentApiClient(_BASE_URL_CANARY, _BEARER_KEY_CANARY)

    with (
        patch("hermes_agent_api_client.client.httpx.AsyncClient", new=factory),
        pytest.raises(RuntimeError, match=failure_message) as failure,
    ):
        async with client:
            pass

    _assert_safe_lifecycle_error(
        failure.value,
        expected_message=failure_message,
        client=client,
    )


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
