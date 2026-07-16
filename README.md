# Hermes Agent API Client

Hermes Agent API Client is a typed async Python client for authenticated
capability discovery and streaming Chat Completions from the Hermes Agent API
Server. The package requires Python 3.13 or later.

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

Capability discovery can distinguish a non-Hermes endpoint from a Hermes Agent
that lacks required Chat Completions support using package-root imports only:

```python
from hermes_agent_api_client import (
    HermesAgentApiClient,
    HermesCapabilityError,
    HermesIdentityError,
)


async def discover_hermes(base_url: str, bearer_key: str) -> str:
    try:
        async with HermesAgentApiClient(base_url, bearer_key) as client:
            capabilities = await client.probe_capabilities()
    except HermesIdentityError:
        return "not a Hermes Agent endpoint"
    except HermesCapabilityError:
        return "Hermes Agent lacks Chat Completions support"
    return capabilities.model
```

## Supported contract

The package supports only these Hermes operations:

- `GET /v1/capabilities` through `probe_capabilities()`.
- Streaming `POST /v1/chat/completions` through `stream_chat_events()`.

The exact OpenAI-compatible request document remains a caller-owned mapping;
the client does not define additional request-model semantics.

A successful capability probe returns an immutable `HermesCapabilities` value
with this supported shape:

- `object`: exactly `hermes.api_server.capabilities`.
- `platform`: exactly `hermes-agent`.
- `model`: the advertised API/profile name.
- `auth_type`: exactly `bearer`.
- `auth_required`: the literal boolean `True`.
- `chat_completions`: the literal boolean `True`.
- `chat_completions_streaming`: the literal boolean `True`.

At the immutable upstream compatibility target, `model` is resolved in order
from an explicit API-server model override, a non-default active profile, or
the `hermes-agent` fallback. The client preserves the advertised string exactly:
it does not trim, normalize, replace, or truncate leading, trailing, or internal
whitespace. Strict validation requires an actual string containing 1 through
255 Unicode code points and at least one non-whitespace code point; empty,
whitespace-only, non-string, and over-limit values are rejected.

The stream yields immutable `AssistantDeltaEvent`, `ToolProgressEvent`,
`UsageEvent`, `KeepaliveEvent`, and `TerminalEvent` values. Terminal outcomes
are `success`, `length`, or `upstream_error`.

Public failures derive from `HermesContractError` and expose only safe
`category`, `status_code`, and `retryable` metadata. `HermesIdentityError` and
`HermesCapabilityError` both inherit `HermesProtocolError`, so existing callers
that catch `HermesProtocolError` or `HermesContractError` continue to catch
them. Both subclasses have protocol category, no status code, and
`retryable=False`, with no additional instance state.

Capability-probe classification is staged and deterministic:

| Wire condition | Public exception |
| --- | --- |
| Top-level document is not a mapping | `HermesProtocolError` |
| Missing or non-exact `object` discriminator | `HermesIdentityError` |
| Missing or non-exact `platform` discriminator | `HermesIdentityError` |
| Valid identity, but `features` is missing or not a mapping | `HermesCapabilityError` |
| Valid identity, but `features.chat_completions` is missing, false, or not the literal boolean `True` | `HermesCapabilityError` |
| Invalid or missing `model` | `HermesProtocolError` |
| Invalid or missing bearer authentication contract | `HermesProtocolError` |
| Missing, false, or invalid `chat_completions_streaming` | `HermesProtocolError` |
| Malformed JSON, oversized body, or another unrelated schema failure | `HermesProtocolError` |
| Existing authentication HTTP status | `HermesAuthenticationError` |
| Existing non-authentication HTTP status | `HermesHttpStatusError` |
| Existing request, timeout, read, or cleanup transport failure | `HermesTransportError` |

Identity failures take precedence over required-feature failures. Capability
failures are classified only after both identity discriminators are valid, and
all remaining wire failures use the generic `HermesProtocolError` fallback.
Authentication HTTP status, other HTTP status, and transport failures remain
`HermesAuthenticationError`, `HermesHttpStatusError`, and
`HermesTransportError`, respectively. Callers should not expect upstream
response bodies, bearer credentials, request payloads, URLs, or raw validation
details in public error text.

Compatibility targets the immutable Hermes Agent tag `v2026.7.7.2` at commit
`9de9c25f620ff7f1ce0fd5457d596052d5159596`. Evidence is derived from a
capability fixture captured from that tagged handler and local
protocol/transport tests; it is not evidence from a live Hermes server or a
moving upstream branch.

> **Security:** Hermes API access exposes the configured agent toolset. Protect
> the bearer key, restrict network access, and grant the Hermes agent only the
> tools appropriate for the calling application.

## Development

Install the exact locked development environment and the commit hook:

```console
uv sync --locked --all-groups
prek install
```

`prek` runs the complete quality gate automatically before every Git commit and
blocks the commit when any check fails.

## License

Licensed under the Universal Permissive License 1.0 (UPL-1.0). See `LICENSE`.
