# Hermes Agent API Client Design

**Status:** Approved
**Date:** 2026-07-14
**Distribution:** `hermes-agent-api-client`
**Import package:** `hermes_agent_api_client`
**Initial version:** `0.1.0`

## Purpose

Extract the Hermes API contract, HTTP transport, and streaming decoder from
`hermes_conversation` into a small, reusable Python package. The package will
provide a typed client for the stable Hermes API Server surface used by Home
Assistant without depending on Home Assistant or the full `hermes-agent`
runtime.

The first release covers authenticated capability discovery and streaming
Chat Completions. It deliberately does not attempt to expose every Hermes API
Server endpoint or model the full OpenAI-compatible request schema.

## Goals

- Publish one typed `HermesAgentApiClient` suitable for Home Assistant and
  other async Python consumers.
- Preserve the Phase 1 capability, SSE, failure, timeout, resource ownership,
  cancellation, and redaction contracts.
- Accept a caller-provided `httpx.AsyncClient` while also supporting an
  internally owned client.
- Make client lifetime explicit and automatic through an async context
  manager.
- Validate untrusted Hermes JSON strictly while tolerating additive fields.
- Ship a complete PEP 561 type surface.
- Build reproducible wheel and source distributions suitable for PyPI.

## Non-goals for 0.1.0

- Home Assistant lifecycle, config flows, entities, diagnostics, or error UX.
- A dependency on or in-process embedding of the `hermes-agent` runtime.
- A wrapper around the OpenAI Python SDK.
- Responses, Runs, Jobs, Sessions, Skills, Toolsets, Models, or health APIs.
- Public models for the complete OpenAI-compatible chat request schema.
- Automatic retries, credential refresh, endpoint discovery, or profile
  management.
- PyPI publication as part of the local repository extraction.

## Repository and packaging

The repository uses `main` as its initial branch and a `src` layout:

```text
hermes-agent-api-client/
├── LICENSE
├── README.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── hermes_agent_api_client/
│       ├── __init__.py
│       ├── client.py
│       ├── models.py
│       ├── protocol.py
│       ├── sse.py
│       └── py.typed
└── tests/
    ├── fixtures/hermes/v2026.7.7.2/
    ├── helpers/
    ├── test_capabilities.py
    ├── test_client_lifecycle.py
    ├── test_http_ownership.py
    ├── test_package.py
    └── test_sse.py
```

Package metadata and dependencies:

- Python `>=3.13`.
- UPL-1.0 license, preserving the extracted code's existing license.
- `uv_build>=0.11.28,<0.12` as the PEP 517 backend.
- `httpx>=0.28.1,<1` as the async transport.
- `pydantic>=2.13.4,<3` as the wire-validation layer.
- `py.typed` included in the wheel.
- Static version metadata; `uv_build` dynamic metadata is not required.

Development tools are locked with uv. The initial implementation uses Ruff
0.15.21, pytest 9.1.1, pytest-asyncio 1.4.0, coverage 7.15.1, and Microsoft
Pyright 1.1.411. Dependency versions are rechecked before they are committed.

## Public API

The package exports these public categories from `hermes_agent_api_client`:

- `HermesAgentApiClient`
- `HermesCapabilities`
- `AssistantDeltaEvent`
- `ToolProgressEvent`
- `UsageEvent`
- `KeepaliveEvent`
- `TerminalEvent`
- `TerminalOutcome`
- `HermesEvent`
- `HermesContractError`
- `HermesProtocolError`
- `HermesAuthenticationError`
- `HermesHttpStatusError`
- `HermesTransportError`

The intended usage is:

```python
import httpx

from hermes_agent_api_client import HermesAgentApiClient


async def stream_turn(
    http_client: httpx.AsyncClient,
    base_url: str,
    bearer_key: str,
    request: dict[str, object],
) -> None:
    async with HermesAgentApiClient(
        base_url,
        bearer_key,
        http_client=http_client,
    ) as client:
        capabilities = await client.probe_capabilities()
        if not capabilities.chat_completions_streaming:
            raise RuntimeError("Hermes streaming is unavailable")

        async for event in client.stream_chat_events(request):
            handle_event(event)
```

The constructor binds one base URL, bearer key, and transport policy. Public
methods receive operation-specific input only:

- `probe_capabilities() -> HermesCapabilities`
- `stream_chat_events(request: Mapping[str, object]) -> AsyncIterator[HermesEvent]`

The exact OpenAI-compatible message schema remains a caller-owned mapping in
0.1.0. A later release may introduce request models after real consumers
establish the required text, image, transcript, and session shapes.

The constructor's TLS argument is `verify: ssl.SSLContext | bool | None = None`.
For an owned HTTP client, `None` selects httpx's verified default. Supplying an
HTTP client together with a non-`None` `verify` value is rejected because the
library cannot safely override or inspect an injected client's transport
configuration.

## Client lifetime and HTTP ownership

`HermesAgentApiClient` is an async context manager.

- When `http_client` is omitted, context entry creates an
  `httpx.AsyncClient`; context exit closes it on success, failure, or
  cancellation.
- When `http_client` is supplied, the caller retains ownership and context exit
  never closes it.
- TLS verification configuration applies when the library creates the HTTP
  client. A caller that injects a client is responsible for configuring that
  client's TLS policy.
- Public operations fail predictably before context entry and after context
  exit. The instance is single-use: double entry and re-entry after exit raise
  `RuntimeError` with constant, non-sensitive messages. Consumers create a new
  instance for a new lifetime.
- Response scopes are always closed independently of HTTP client ownership.
- Cancellation propagates unchanged after owned response and client resources
  are released.
- The client does not follow redirects implicitly across an authenticated
  request boundary.

This ownership model permits Home Assistant to inject its lifecycle-managed
HTTP client while giving standalone consumers safe automatic cleanup.

## Validation and models

Pydantic validates JSON application payloads at the untrusted wire boundary.
It does not replace byte framing, transport control, or exception types.

- Public capability and event value objects are frozen Pydantic models.
- Strict validation rejects coercion of required wire values.
- Internal wire models use `extra="ignore"` to tolerate additive Hermes fields.
- Discriminated unions or `TypeAdapter` validate distinct event payloads where
  they reduce ambiguity.
- Enums retain the closed set of supported terminal and failure categories.
- Pydantic Settings is not used.
- Chat request mappings are serialized only after type and JSON-encoding
  checks; secret-bearing invalid input is never copied into an exception.

The bounded SSE state machine remains responsible for:

- Incremental UTF-8 decoding.
- CRLF and LF record framing across arbitrary byte partitions.
- Record, line, event-name, and content bounds.
- Comments and keepalive records.
- Hermes `hermes.tool.progress` separation.
- Standard Chat Completions chunks.
- `[DONE]`, finish reasons, EOF, and terminal ordering.

## Errors and sensitive data

Public failures remain ordinary exception classes rather than Pydantic
models. They expose only safe structured metadata such as category,
retryability, and bounded status code.

Pydantic `ValidationError` objects are handled internally. Translation to a
sanitized `HermesProtocolError` occurs outside the active exception context so
raw Pydantic `input_value` data is not retained in `__cause__`, `__context__`,
tracebacks, attributes, `str`, or `repr`.

Bearer keys, request payloads, response bodies, transport exception messages,
and URL userinfo never appear in public exceptions. The tests use canary
values to prove this boundary on every failure category.

## Data flow

Capability discovery follows this path:

1. Resolve `/v1/capabilities` beneath the normalized base path.
2. Add bearer authentication and bounded timeouts.
3. Dispatch with the active HTTP client.
4. Enter and always close the response scope.
5. Reject redirects and classify non-success statuses.
6. Enforce declared and observed response-size bounds.
7. Parse JSON, validate the Pydantic wire model, and return frozen public
   capabilities.

Streaming Chat Completions follows this path:

1. Validate and serialize the caller's request mapping.
2. Resolve `/v1/chat/completions` beneath the normalized base path.
3. Dispatch an authenticated streaming request with bounded connect/write and
   keepalive-aware read timeouts.
4. Feed response bytes to the bounded SSE decoder.
5. Validate JSON application records and yield typed public events in order.
6. Require an accepted terminal outcome; ordinary EOF is a protocol failure.
7. Close the response scope on completion, error, generator close, or
   cancellation.

## Testing and verification

The existing Phase 1 contract tests and versioned Hermes fixtures move to the
client repository and use normal package imports. They are extended with
class-level lifecycle tests.

Required behavior coverage includes:

- Owned-client creation and automatic closure.
- Injected-client preservation.
- Success, exception, generator close, and cancellation cleanup.
- Before-entry, double-entry, after-exit, and prohibited re-entry behavior.
- URL normalization, encoded base paths, userinfo rejection, and redirect
  rejection.
- Authentication, status classification, timeout policy, and response bounds.
- Bytewise, partitioned, concurrent, malformed, abnormal-terminal, and EOF SSE
  behavior.
- Additive-field compatibility and strict required-field validation.
- Secret, payload, traceback, cause, and context redaction.

Quality gates:

- `ruff check` and `ruff format --check` with Ruff 0.15.21.
- pytest 9.1.1 and pytest-asyncio 1.4.0 on Python 3.13 and 3.14.
- Enforced line and branch coverage for package source.
- Microsoft Pyright 1.1.411 in strict mode for `src` and `tests`.
- `pyright --verifytypes hermes_agent_api_client --ignoreexternal` for public
  type completeness.
- `uv build` for wheel and source distribution.
- Archive inspection for license, metadata, and `py.typed`, while excluding
  tests and secret-like fixtures from distributions.
- Clean-environment wheel installation and public-import smoke tests.
- GitHub Actions pinned to reviewed full commit SHAs after the repository is
  pushed.

Pyright is invoked from Microsoft's official npm distribution rather than the
unofficial PyPI wrapper.

## Migration and release sequence

1. Initialize the local repository on `main` and commit this design plus the
   inherited UPL license with a GPG signature and DCO signoff.
2. The user pushes the initial commit to GitHub and provides the public remote
   URL.
3. Create and execute the package implementation plan in the new repository.
4. Commit the package, fixtures, tests, documentation, and local verification
   evidence in signed, DCO-compliant conventional commits.
5. Pin the public Git commit from `hermes_conversation` development metadata
   and `manifest.json`.
6. Replace local `client.py`, `protocol.py`, and `sse.py` imports with
   `hermes_agent_api_client` and remove the duplicated modules.
7. Move protocol/transport tests to the client repository. Retain Home
   Assistant adapter tests that verify injection, context lifetime, error
   translation, and framework behavior.
8. Verify both repositories independently and together from clean
   environments.
9. Publish `hermes-agent-api-client==0.1.0` to PyPI in a separately authorized
   release step.
10. Replace the temporary Git requirement with the exact PyPI requirement and
    regenerate the integration lock.

The integration is not cut over before the GitHub dependency is publicly
fetchable. No external repository creation, push, or package publication is
performed without explicit authorization.

## Success criteria

- The new repository contains no Home Assistant imports.
- `HermesAgentApiClient` owns and closes only HTTP clients it creates.
- Capability and stream contracts retain all Phase 1 behavior and security
  guarantees.
- Public models and methods are complete under Pyright `--verifytypes`.
- Python 3.13 and 3.14 pass lint, type, test, coverage, build, archive, and
  clean-wheel gates.
- The Home Assistant integration has no duplicate Hermes protocol, SSE, or
  HTTP transport implementation after cutover.
- The temporary Git dependency is commit-pinned and later replaced by exact
  `0.1.0` from PyPI.
- The package can be understood and used without reading Home Assistant code.
