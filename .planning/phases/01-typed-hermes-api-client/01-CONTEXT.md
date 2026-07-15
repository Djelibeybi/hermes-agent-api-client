# Phase 1 Context: Typed Hermes API Client

## Import Status

This phase is a historical import of work already implemented, tested, tagged,
and published as `hermes-agent-api-client` v0.1.0. GSD records the completed
baseline from repository and release evidence; GSD did not execute the
historical implementation.

## Public v0.1.0 Surface

The immutable public surface at tag `v0.1.0` is defined by
`src/hermes_agent_api_client/__init__.py` and consists of:

- `HermesAgentApiClient`, a single-use async context manager with
  `probe_capabilities()` and `stream_chat_events()` operations.
- Immutable `HermesCapabilities`, `AssistantDeltaEvent`, `ToolProgressEvent`,
  `UsageEvent`, `KeepaliveEvent`, and `TerminalEvent` models.
- The `HermesEvent` closed event union and `TerminalOutcome` enum.
- Typed `HermesAuthenticationError`, `HermesHttpStatusError`,
  `HermesTransportError`, `HermesProtocolError`, and `HermesContractError`
  failures.
- The static `__version__` value and the `py.typed` package marker.

The v0.1.0 transport boundary is limited to authenticated
`GET /v1/capabilities` and streaming `POST /v1/chat/completions`, including
bounded capability bodies and SSE records, timeout and cancellation handling,
secret-safe failures, and explicit ownership of injected or package-created
HTTP clients.

## Boundary

This package phase excludes Home Assistant lifecycle, profiles, entities,
sessions, memory policy, Assist behaviour, and integration configuration. Those
behaviours belong to `hermes-conversation`, not this reusable client milestone.
