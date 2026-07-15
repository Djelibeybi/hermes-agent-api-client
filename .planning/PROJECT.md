# Hermes Agent API Client

## What This Is

Hermes Agent API Client is the reusable Python package for the typed Hermes
Agent API boundary described by this project.

## Core Value

Python consumers can use a typed, bounded, secret-safe asynchronous client for the documented Hermes Agent API Server boundary without implementing protocol or transport behaviour themselves.

## Scope

- Public immutable capability and stream-event models
- Typed public authentication, HTTP status, transport, and protocol failures
- Authenticated `GET /v1/capabilities`
- Streaming `POST /v1/chat/completions`
- Bounded SSE framing and application-event decoding
- URL, timeout, cancellation, cleanup, and HTTP client ownership behaviour
- Typed package distribution, CI, and release operation

## Boundaries

- Home Assistant lifecycle, profiles, entities, sessions, memory policy, and Assist behaviour belong to `hermes-conversation`.
- v0.1.0 supports capability discovery and streaming Chat Completions only.
- Future API operations require a new evidence-backed milestone.

## Requirements

The completed v0.1.0 baseline requirements and their status are recorded in
`REQUIREMENTS.md`.
