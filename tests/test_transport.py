"""Bounded HTTP transport and injected-client ownership tests."""

from __future__ import annotations

import asyncio
import json
import traceback
from types import MappingProxyType
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import httpx
import pytest

from hermes_agent_api_client.client import (
    _CAPABILITIES_DEADLINE_SECONDS,  # pyright: ignore[reportPrivateUsage]
    _CHAT_STREAM_READ_TIMEOUT_SECONDS,  # pyright: ignore[reportPrivateUsage]
    _HERMES_SSE_KEEPALIVE_SECONDS,  # pyright: ignore[reportPrivateUsage]
    _MAX_CAPABILITIES_BYTES,  # pyright: ignore[reportPrivateUsage]
    _normalize_base_url,  # pyright: ignore[reportPrivateUsage]
    _probe_capabilities,  # pyright: ignore[reportPrivateUsage]
    _request_headers,  # pyright: ignore[reportPrivateUsage]
    _stream_chat_events,  # pyright: ignore[reportPrivateUsage]
)
from hermes_agent_api_client.models import (
    AssistantDeltaEvent,
    FailureCategory,
    KeepaliveEvent,
    TerminalEvent,
    TerminalOutcome,
)
from hermes_agent_api_client.protocol import (
    HermesAuthenticationError,
    HermesContractError,
    HermesHttpStatusError,
    HermesProtocolError,
    HermesTransportError,
    validate_capabilities,
)
from tests.helpers.hermes import add_json_key, load_golden_json, reorder_json_keys

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Mapping

_EXPECTED_CAPABILITIES_DEADLINE = 10.0
_CONCURRENT_STREAM_COUNT = 12


class TrackingAsyncByteStream(httpx.AsyncByteStream):
    """Yield controlled bytes and record response cleanup."""

    def __init__(
        self,
        chunks: tuple[bytes, ...] = (),
        *,
        delay: float = 0,
        failure: BaseException | None = None,
    ) -> None:
        """Initialize controlled chunks, delay, and optional failure."""
        self.chunks = chunks
        self.delay = delay
        self.failure = failure
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield configured chunks cooperatively before an optional failure."""
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            else:
                await asyncio.sleep(0)
            yield chunk
        if self.failure is not None:
            raise self.failure

    async def aclose(self) -> None:
        """Record response-scope closure."""
        self.closed = True


def _supported_capabilities() -> dict[str, object]:
    return load_golden_json("capabilities/supported.json")


def _capabilities_body_at_size(size: int) -> bytes:
    document = _supported_capabilities()
    document["padding"] = ""
    base = json.dumps(document, separators=(",", ":")).encode()
    document["padding"] = "x" * (size - len(base))
    payload = json.dumps(document, separators=(",", ":")).encode()
    assert len(payload) == size
    return payload


def _successful_sse(text: str = "hello") -> bytes:
    chunk = json.dumps(
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": text},
                    "finish_reason": None,
                }
            ]
        },
        separators=(",", ":"),
    ).encode()
    return b"data: " + chunk + b"\n\ndata: [DONE]\n\n"


async def _probe(
    client: httpx.AsyncClient,
    *,
    base_url: str = "https://hermes.example",
    bearer_key: str = "capability-bearer",
) -> object:
    """Probe through normalized internal transport inputs."""
    return await _probe_capabilities(
        client,
        _normalize_base_url(base_url),
        _request_headers(bearer_key),
    )


async def _collect_stream(
    client: httpx.AsyncClient,
    *,
    base_url: str = "https://hermes.example",
    bearer_key: str = "stream-bearer",
    request: Mapping[str, object] | None = None,
) -> tuple[object, ...]:
    return tuple(
        [
            event
            async for event in _stream_chat_events(
                client,
                _normalize_base_url(base_url),
                _request_headers(bearer_key),
                request
                if request is not None
                else {"model": "hermes", "messages": [], "stream": True},
            )
        ]
    )


@pytest.mark.asyncio
async def test_probe_uses_exact_endpoint_timeout_and_refuses_redirects() -> None:
    """Capabilities use the exact endpoint, finite timeout, and no redirects."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json=_supported_capabilities())

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with patch.object(client, "send", wraps=client.send) as send:
            result = await _probe(
                client,
                base_url="https://hermes.example/private-base/",
                bearer_key="capability-bearer-canary",
            )

        assert result == validate_capabilities(_supported_capabilities())
        assert str(requests[0].url) == (
            "https://hermes.example/private-base/v1/capabilities"
        )
        assert requests[0].headers["Authorization"] == (
            "Bearer capability-bearer-canary"
        )
        timeout = requests[0].extensions["timeout"]
        assert all(isinstance(value, float) and value > 0 for value in timeout.values())
        assert send.await_args is not None
        assert send.await_args.kwargs["follow_redirects"] is False
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("base_url", "expected_endpoint"),
    [
        (
            "https://hermes.example/a%2Fb",
            "https://hermes.example/a%2Fb/v1/capabilities",
        ),
        (
            "https://hermes.example/a%3Fb",
            "https://hermes.example/a%3Fb/v1/capabilities",
        ),
        (
            "https://hermes.example/space here",
            "https://hermes.example/space%20here/v1/capabilities",
        ),
        (
            "https://hermes.example/caf\N{LATIN SMALL LETTER E WITH ACUTE}",
            "https://hermes.example/caf%C3%A9/v1/capabilities",
        ),
        (
            "https://hermes.example/base?old=query#old-fragment",
            "https://hermes.example/base/v1/capabilities",
        ),
    ],
)
async def test_probe_preserves_encoded_base_path(
    base_url: str,
    expected_endpoint: str,
) -> None:
    """Endpoint construction preserves encoded path meaning and drops suffixes."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json=_supported_capabilities())

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        await _probe(client, base_url=base_url, bearer_key="encoded-bearer")
        assert str(requests[0].url) == expected_endpoint
        assert requests[0].headers["Authorization"] == "Bearer encoded-bearer"
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_probe_accepts_exact_byte_limit() -> None:
    """A valid document exactly at the byte limit is accepted and cleaned up."""
    payload = _capabilities_body_at_size(_MAX_CAPABILITIES_BYTES)
    stream = TrackingAsyncByteStream((payload,))

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"content-length": str(len(payload))},
            stream=stream,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        result = await _probe(client)
        assert result == validate_capabilities(_supported_capabilities())
        assert stream.closed is True
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("size_source", ["observed", "declared"])
async def test_probe_rejects_limit_plus_one(size_source: str) -> None:
    """Declared and observed bodies over the limit fail before parsing."""
    declared = size_source == "declared"
    payload = _capabilities_body_at_size(_MAX_CAPABILITIES_BYTES + 1)
    chunks = (payload,) if declared else (payload[:-1], payload[-1:])
    stream = TrackingAsyncByteStream(chunks)

    def respond(request: httpx.Request) -> httpx.Response:
        headers = {"content-length": str(len(payload))} if declared else {}
        return httpx.Response(200, request=request, headers=headers, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(HermesProtocolError) as caught:
            await _probe(client)
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert stream.closed is True
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content_length",
    ["", "-1", "+1", "1.0", "9" * 21],
)
async def test_probe_rejects_invalid_declared_content_length(
    content_length: str,
) -> None:
    """Malformed declared lengths fail safely and still close the response."""
    stream = TrackingAsyncByteStream((_successful_sse(),))

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"content-length": content_length},
            stream=stream,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(HermesProtocolError):
            await _probe(client)
        assert stream.closed is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_probe_total_deadline_stops_trickle_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A trickle inside inactivity limits cannot evade the total deadline."""
    monkeypatch.setattr(
        "hermes_agent_api_client.client._CAPABILITIES_DEADLINE_SECONDS", 0.01
    )
    stream = TrackingAsyncByteStream((b"{", b'"object"', b":"), delay=0.05)

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(HermesTransportError) as caught:
            await _probe(client)
        assert _CAPABILITIES_DEADLINE_SECONDS == _EXPECTED_CAPABILITIES_DEADLINE
        assert caught.value.retryable is True
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert stream.closed is True
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_probe_preserves_additive_order_and_replay_semantics() -> None:
    """Repeated additive and reordered documents retain validated semantics."""
    canonical = _supported_capabilities()
    additive = add_json_key(canonical, ("future",), {"nested": [1, 2, 3]})
    reordered = reorder_json_keys(additive, tuple(reversed(tuple(additive))))
    payloads = iter([canonical, additive, reordered] * 4)

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=next(payloads))

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        expected = validate_capabilities(canonical)
        for _ in range(12):
            assert await _probe(client) == expected
            assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type", "retryable"),
    [
        (401, HermesAuthenticationError, False),
        (403, HermesAuthenticationError, False),
        (400, HermesHttpStatusError, False),
        (429, HermesHttpStatusError, True),
        (503, HermesHttpStatusError, True),
    ],
)
async def test_probe_classifies_status_without_leaking_response(
    status_code: int,
    error_type: type[HermesContractError],
    retryable: object,
) -> None:
    """Status failures retain only safe classification metadata."""
    assert isinstance(retryable, bool)
    endpoint = "https://private.invalid/private-path?url=canary"
    bearer = "status-bearer-canary"

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            request=request,
            headers={"x-private-header": "header-canary"},
            text="private-response-body-canary",
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(error_type) as caught:
            await _probe(client, base_url=endpoint, bearer_key=bearer)
        error = caught.value
        assert error.status_code == status_code
        assert error.retryable is retryable
        assert error.__cause__ is None
        assert error.__context__ is None
        public_state = " | ".join(
            (str(error), repr(error), repr(vars(error)), traceback.format_exc())
        )
        assert all(
            canary not in public_state
            for canary in (
                endpoint,
                "private.invalid",
                "private-path",
                bearer,
                "header-canary",
                "private-response-body-canary",
            )
        )
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("exception_type", [httpx.ConnectError, httpx.ReadTimeout])
async def test_probe_classifies_request_failures_as_safe_transport(
    exception_type: type[httpx.RequestError],
) -> None:
    """Request failures translate to safe retryable transport failures."""
    bearer = "transport-bearer-canary"
    base_url = "https://private.invalid/transport-canary"

    def fail(request: httpx.Request) -> httpx.Response:
        message = f"private-request-canary {request.url} {bearer}"
        raise exception_type(message, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    try:
        with pytest.raises(HermesTransportError) as caught:
            await _probe(client, base_url=base_url, bearer_key=bearer)
        error = caught.value
        assert error.retryable is True
        assert error.__cause__ is None
        assert error.__context__ is None
        public_state = " | ".join(
            (str(error), repr(error), repr(vars(error)), traceback.format_exc())
        )
        assert base_url not in public_state
        assert bearer not in public_state
        assert "private-request-canary" not in public_state
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [b"private-malformed-json-canary", b'{"platform":"wrong-private-shape"}'],
)
async def test_probe_maps_json_and_shape_failures_to_safe_protocol(
    content: bytes,
) -> None:
    """Malformed JSON and rejected shapes expose no parser or response data."""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=content)

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(HermesProtocolError) as caught:
            await _probe(client)
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        rendered = "".join(traceback.format_exception(caught.value))
        assert "private-malformed-json-canary" not in rendered
        assert "wrong-private-shape" not in rendered
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "not a URL",
        "https://hermes.example:not-a-port",
        "ftp://user:password@private.invalid/path?token=url-canary",
        "https://user@private.invalid/path",
        "https://user:password@private.invalid/path",
    ],
)
def test_normalize_base_url_rejects_invalid_values_safely(base_url: str) -> None:
    """Invalid URLs and userinfo fail without reaching HTTP or leaking input."""
    with pytest.raises(HermesTransportError) as caught:
        _normalize_base_url(base_url)
    assert caught.value.retryable is False
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    if base_url:
        assert base_url not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize(
    "bearer_key",
    ["", "has space", "line\nbreak", "non-ascii-\N{HOUSE BUILDING}"],
)
def test_request_headers_reject_invalid_bearer_safely(bearer_key: str) -> None:
    """Only non-empty visible ASCII bearer values are accepted."""
    with pytest.raises(HermesTransportError) as caught:
        _request_headers(bearer_key)
    assert caught.value.retryable is False
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    if bearer_key:
        assert bearer_key not in "".join(traceback.format_exception(caught.value))


def test_request_headers_can_add_json_content_type() -> None:
    """JSON requests receive a fresh content-type header."""
    assert _request_headers("visible-bearer", json_body=True) == {
        "Authorization": "Bearer visible-bearer",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_probe_classification_is_independent_under_concurrency() -> None:
    """Concurrent probes share one client without sharing outcomes."""

    async def respond(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)
        case = request.headers["Authorization"].removeprefix("Bearer ")
        if case == "success":
            return httpx.Response(200, request=request, json=_supported_capabilities())
        if case == "auth":
            return httpx.Response(401, request=request)
        return httpx.Response(200, request=request, json={"platform": "rejected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))

    async def classify(case: str) -> tuple[str, object]:
        try:
            result = await _probe(client, bearer_key=case)
        except HermesContractError as error:
            return ("failure", error.category)
        return ("success", result)

    cases = ("success", "auth", "protocol") * 8
    try:
        results = await asyncio.gather(*(classify(case) for case in cases))
        expected = validate_capabilities(_supported_capabilities())
        assert results == [
            (
                ("success", expected)
                if case == "success"
                else (
                    "failure",
                    FailureCategory.AUTHENTICATION
                    if case == "auth"
                    else FailureCategory.PROTOCOL,
                )
            )
            for case in cases
        ]
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_success_closes_response_and_refuses_redirects() -> None:
    """Success closes only the response and sends bounded request metadata."""
    stream = TrackingAsyncByteStream((_successful_sse("ordered text"),))
    responses: list[httpx.Response] = []

    def respond(request: httpx.Request) -> httpx.Response:
        response = httpx.Response(200, request=request, stream=stream)
        responses.append(response)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    original_headers = MappingProxyType({"Authorization": "Bearer stream-bearer"})
    request_body: Mapping[str, object] = {
        "model": "hermes",
        "messages": [],
        "stream": True,
    }
    try:
        with patch.object(client, "send", wraps=client.send) as send:
            events = tuple(
                [
                    event
                    async for event in _stream_chat_events(
                        client,
                        _normalize_base_url("https://hermes.example"),
                        original_headers,
                        request_body,
                    )
                ]
            )

        assert events == (
            AssistantDeltaEvent(text="ordered text"),
            TerminalEvent(outcome=TerminalOutcome.SUCCESS),
        )
        request = responses[0].request
        assert request.method == "POST"
        assert str(request.url) == "https://hermes.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer stream-bearer"
        assert request.headers["Content-Type"] == "application/json"
        assert dict(original_headers) == {"Authorization": "Bearer stream-bearer"}
        assert request.extensions["timeout"] == {
            "connect": 10.0,
            "read": _CHAT_STREAM_READ_TIMEOUT_SECONDS,
            "write": 10.0,
            "pool": 10.0,
        }
        assert json.loads(request.content) == request_body
        assert send.await_args is not None
        assert send.await_args.kwargs["follow_redirects"] is False
        assert stream.closed is True
        assert responses[0].is_closed is True
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_timeout_survives_one_virtual_keepalive_interval() -> None:
    """The read timeout exceeds Hermes' documented keepalive interval."""
    streams: list[TrackingAsyncByteStream] = []

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.extensions["timeout"]["read"] > _HERMES_SSE_KEEPALIVE_SECONDS
        stream = TrackingAsyncByteStream(
            (b": keepalive after virtual 30 seconds\n\n", _successful_sse())
        )
        streams.append(stream)
        return httpx.Response(200, request=request, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        assert await _collect_stream(client) == (
            KeepaliveEvent(),
            AssistantDeltaEvent(text="hello"),
            TerminalEvent(outcome=TerminalOutcome.SUCCESS),
        )
        assert streams[0].closed is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_terminal_is_delivered_only_after_response_cleanup() -> None:
    """Terminal delivery proves the response scope has already closed."""
    stream = TrackingAsyncByteStream((_successful_sse("ordered text"),))
    response: httpx.Response | None = None

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal response
        response = httpx.Response(200, request=request, stream=stream)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    generator = cast(
        "AsyncGenerator[object]",
        _stream_chat_events(
            client,
            _normalize_base_url("https://hermes.example"),
            _request_headers("stream-bearer"),
            {"model": "hermes", "messages": [], "stream": True},
        ),
    )
    try:
        assert await anext(generator) == AssistantDeltaEvent(text="ordered text")
        assert stream.closed is False
        assert await anext(generator) == TerminalEvent(outcome=TerminalOutcome.SUCCESS)
        assert stream.closed is True
        assert response is not None
        assert response.is_closed is True
    finally:
        await generator.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_post_terminal_content_fails_before_terminal_delivery() -> None:
    """Trailing application content fails before a terminal can escape."""
    content_record, done_record = _successful_sse("trailing").split(b"\n\n")[:2]
    stream = TrackingAsyncByteStream(
        (done_record + b"\n\n" + content_record + b"\n\n",)
    )
    response: httpx.Response | None = None

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal response
        response = httpx.Response(200, request=request, stream=stream)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    generator = cast(
        "AsyncGenerator[object]",
        _stream_chat_events(
            client,
            _normalize_base_url("https://hermes.example"),
            _request_headers("stream-bearer"),
            {"model": "hermes", "messages": [], "stream": True},
        ),
    )
    try:
        with pytest.raises(HermesProtocolError):
            await anext(generator)
        assert stream.closed is True
        assert response is not None
        assert response.is_closed is True
    finally:
        await generator.aclose()
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type", "retryable"),
    [
        (401, HermesAuthenticationError, False),
        (403, HermesAuthenticationError, False),
        (429, HermesHttpStatusError, True),
        (503, HermesHttpStatusError, True),
    ],
)
async def test_stream_status_failure_closes_response(
    status_code: int,
    error_type: type[HermesContractError],
    retryable: object,
) -> None:
    """Status failures close their response and preserve the injected client."""
    assert isinstance(retryable, bool)
    stream = TrackingAsyncByteStream()
    response: httpx.Response | None = None

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal response
        response = httpx.Response(status_code, request=request, stream=stream)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(error_type) as caught:
            await _collect_stream(client)
        assert caught.value.retryable is retryable
        assert caught.value.status_code == status_code
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert stream.closed is True
        assert response is not None
        assert response.is_closed is True
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_transport_failure_preserves_client() -> None:
    """Dispatch failures translate safely without closing the injected client."""
    transport_error = httpx.ConnectError("private-transport-canary")

    def fail(_request: httpx.Request) -> httpx.Response:
        raise transport_error

    client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    try:
        with pytest.raises(HermesTransportError) as caught:
            await _collect_stream(client)
        assert caught.value.retryable is True
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert "private-transport-canary" not in traceback.format_exc()
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["circular", "non-serializable", "nan"])
async def test_stream_rejects_invalid_json_before_request(case: str) -> None:
    """Invalid mappings fail compact serialization before dispatch."""
    requests: list[httpx.Request] = []
    if case == "circular":
        circular: list[object] = []
        circular.append(circular)
        request: Mapping[str, object] = {"value": circular}
    elif case == "non-serializable":
        request = {"value": {"private-body-canary"}}
    else:
        request = {"value": float("nan")}

    def dispatch(http_request: httpx.Request) -> httpx.Response:
        requests.append(http_request)
        return httpx.Response(500, request=http_request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(dispatch))
    try:
        with pytest.raises(HermesTransportError) as caught:
            await _collect_stream(client, request=request)
        assert caught.value.retryable is False
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert "private-body-canary" not in traceback.format_exc()
        assert requests == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_accepts_read_only_mapping_request() -> None:
    """Request serialization accepts the declared Mapping abstraction."""
    requests: list[httpx.Request] = []
    request = MappingProxyType({"model": "hermes", "messages": [], "stream": True})

    def respond(http_request: httpx.Request) -> httpx.Response:
        requests.append(http_request)
        return httpx.Response(
            200,
            request=http_request,
            stream=TrackingAsyncByteStream((_successful_sse("proxy"),)),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        assert await _collect_stream(client, request=request) == (
            AssistantDeltaEvent(text="proxy"),
            TerminalEvent(outcome=TerminalOutcome.SUCCESS),
        )
        assert json.loads(requests[0].content) == dict(request)
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stream", "error_type"),
    [
        (
            TrackingAsyncByteStream((b"data: private-malformed-json-canary\n\n",)),
            HermesProtocolError,
        ),
        (TrackingAsyncByteStream(), HermesProtocolError),
        (
            TrackingAsyncByteStream(
                (b": keepalive\n\n",),
                failure=httpx.ReadError("private-read-canary"),
            ),
            HermesTransportError,
        ),
    ],
    ids=["decoder-failure", "clean-preterminal-eof", "read-disconnect"],
)
async def test_streaming_failures_close_response(
    stream: TrackingAsyncByteStream,
    error_type: type[HermesContractError],
) -> None:
    """Decoder, EOF, and read failures clean their response independently."""
    response: httpx.Response | None = None

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal response
        response = httpx.Response(200, request=request, stream=stream)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(error_type) as caught:
            await _collect_stream(client)
        if isinstance(caught.value, HermesTransportError):
            assert caught.value.__cause__ is None
            assert caught.value.__context__ is None
            assert "private-read-canary" not in traceback.format_exc()
        assert stream.closed is True
        assert response is not None
        assert response.is_closed is True
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_cancellation_is_unchanged_after_response_cleanup() -> None:
    """Cancellation identity propagates unchanged after response cleanup."""
    cancellation = asyncio.CancelledError("cancellation-canary")
    stream = TrackingAsyncByteStream(failure=cancellation)
    response: httpx.Response | None = None

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal response
        response = httpx.Response(200, request=request, stream=stream)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(asyncio.CancelledError) as caught:
            await _collect_stream(client)
        assert caught.value is cancellation
        assert stream.closed is True
        assert response is not None
        assert response.is_closed is True
        assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_repeated_streams_preserve_client_after_every_iteration() -> None:
    """Repeated calls independently close responses and preserve the client."""
    streams: list[TrackingAsyncByteStream] = []
    responses: list[httpx.Response] = []

    def respond(request: httpx.Request) -> httpx.Response:
        stream = TrackingAsyncByteStream((_successful_sse(str(len(streams))),))
        response = httpx.Response(200, request=request, stream=stream)
        streams.append(stream)
        responses.append(response)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        for index in range(12):
            events = await _collect_stream(client)
            assert events[0] == AssistantDeltaEvent(text=str(index))
            assert streams[index].closed is True
            assert responses[index].is_closed is True
            assert client.is_closed is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_concurrent_probes_and_streams_share_one_open_client() -> None:
    """Mixed operations safely share one open injected client concurrently."""
    streams: list[TrackingAsyncByteStream] = []
    responses: list[httpx.Response] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)
        if request.url.path.endswith("/v1/capabilities"):
            return httpx.Response(200, request=request, json=_supported_capabilities())
        stream = TrackingAsyncByteStream((_successful_sse(request.url.path),))
        response = httpx.Response(200, request=request, stream=stream)
        streams.append(stream)
        responses.append(response)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))

    async def probe() -> object:
        result = await _probe(client, bearer_key="shared-bearer")
        assert client.is_closed is False
        return result

    async def stream() -> tuple[object, ...]:
        result = await _collect_stream(client, bearer_key="shared-bearer")
        assert client.is_closed is False
        return result

    operations = tuple(probe if index % 2 == 0 else stream for index in range(24))
    try:
        results = await asyncio.gather(*(operation() for operation in operations))
        assert len(results) == len(operations)
        assert len(streams) == len(responses) == _CONCURRENT_STREAM_COUNT
        assert all(item.closed for item in streams)
        assert all(item.is_closed for item in responses)
        assert client.is_closed is False
    finally:
        await client.aclose()
