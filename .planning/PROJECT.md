# Hermes Agent API Client

## Core Value

Python consumers can use a typed, bounded, secret-safe asynchronous client for the documented Hermes Agent API Server boundary without implementing protocol or transport behavior themselves.

## Scope

- Public immutable capability and stream-event models
- Typed public authentication, HTTP status, transport, and protocol failures
- Authenticated `GET /v1/capabilities`
- Streaming `POST /v1/chat/completions`
- Bounded SSE framing and application-event decoding
- URL, timeout, cancellation, cleanup, and HTTP client ownership behavior
- Typed package distribution, CI, and release operation

## Boundaries

- Home Assistant lifecycle, profiles, entities, sessions, memory policy, and Assist behavior belong to `hermes-conversation`.
- v0.1.0 supports capability discovery and streaming Chat Completions only.
- Future API operations require a new evidence-backed milestone.
