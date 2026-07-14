# Hermes Agent API Client

Hermes Agent API Client is a typed async Python client for authenticated
capability discovery and streaming Chat Completions from the Hermes Agent API
Server. Version 0.1.0 requires Python 3.13 or later.

## Installation

Install the package from PyPI:

```console
uv add hermes-agent-api-client
```

## Usage

`HermesAgentApiClient` is a single-use async context manager. Without an
injected HTTP client, it creates and closes its own `httpx.AsyncClient`:

```python
from hermes_agent_api_client import HermesAgentApiClient, TerminalEvent


async def ask_hermes(request: dict[str, object]) -> None:
    async with HermesAgentApiClient(
        "https://hermes.example",
        "bearer-key",
    ) as client:
        capabilities = await client.probe_capabilities()
        assert capabilities.chat_completions_streaming

        async for event in client.stream_chat_events(request):
            if isinstance(event, TerminalEvent):
                print(event.outcome)
```

The default `verify=None` uses httpx's verified TLS default. An owned client may
instead receive `verify=False` or an `ssl.SSLContext`. Disabling certificate
verification weakens transport security and should be limited to controlled
environments.

To share a caller-managed client, inject it explicitly:

```python
import httpx

from hermes_agent_api_client import HermesAgentApiClient


async def probe_with_shared_transport() -> None:
    async with httpx.AsyncClient(verify=True) as http_client:
        async with HermesAgentApiClient(
            "https://hermes.example",
            "bearer-key",
            http_client=http_client,
        ) as client:
            await client.probe_capabilities()
```

The caller owns an injected client, so exiting `HermesAgentApiClient` does not
close it. TLS verification must be configured on the injected client; passing
both `http_client` and a non-`None` `verify` value is rejected.

## Supported contract

Version 0.1.0 supports only these Hermes operations:

- `GET /v1/capabilities` through `probe_capabilities()`.
- Streaming `POST /v1/chat/completions` through `stream_chat_events()`.

The exact OpenAI-compatible request document remains a caller-owned mapping;
version 0.1.0 does not define additional request-model semantics.

The stream yields immutable `AssistantDeltaEvent`, `ToolProgressEvent`,
`UsageEvent`, `KeepaliveEvent`, and `TerminalEvent` values. Terminal outcomes
are `success`, `length`, or `upstream_error`.

Public failures derive from `HermesContractError` and expose only safe
`category`, `status_code`, and `retryable` metadata. Authentication, HTTP
status, transport, and protocol failures are represented by distinct public
exception types. Callers should not expect upstream response bodies, bearer
credentials, request payloads, or URLs in public error text.

Compatibility targets Hermes v2026.7.7.2. Evidence is derived from captured
Hermes fixtures for that version and local protocol/transport tests; it is not
evidence from a live Hermes server.

> **Security:** Hermes API access exposes the configured agent toolset. Protect
> the bearer key, restrict network access, and grant the Hermes agent only the
> tools appropriate for the calling application.

## Development

Install the exact locked development environment, install the commit hook, and
run the complete quality gate:

```console
uv sync --locked --all-groups
uv run prek install --prepare-hooks
uv run prek run --all-files
```

## License

Licensed under the Universal Permissive License 1.0 (UPL-1.0). See `LICENSE`.
