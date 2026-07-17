# Hermes Agent API Client

## What This Is

Hermes Agent API Client is the reusable Python package for the typed Hermes
Agent API boundary described by this project.

## Core Value

Python consumers can use a typed, bounded, secret-safe asynchronous client for the documented Hermes Agent API Server boundary without implementing protocol or transport behaviour themselves.

## Current Milestone: v0.3.0 Conversation Contract

**Goal:** Extend the typed client with the conversation-specific contracts required by the Hermes Conversation integration while preserving existing safety, ownership, and transport guarantees.

**Target features:**
- Strict, secret-safe per-request session headers
- Correlated and bounded tool-progress events
- Safe terminal partial-state and failure metadata
- Complete package exports, tests, strict typing, linting, and distribution verification

## Scope

- Public immutable capability and stream-event models
- Typed public authentication, HTTP status, transport, and protocol failures
- Authenticated `GET /v1/capabilities`
- Streaming `POST /v1/chat/completions`
- Validated per-request Hermes session headers
- Correlated tool-progress lifecycle events
- Safe terminal partial-state and failure metadata
- Bounded SSE framing and application-event decoding
- URL, timeout, cancellation, cleanup, and HTTP client ownership behaviour
- Typed package distribution, CI, and release operation

## Boundaries

- Home Assistant lifecycle, profiles, entities, sessions, memory policy, and Assist behaviour belong to `hermes-conversation`.
- Home Assistant derives session and durable-memory identifiers; this package validates and transports opaque values only.
- Arbitrary per-request headers, raw tool payloads, and raw upstream error details are not public API.
- Future API operations require a new evidence-backed milestone.

## Requirements

### Validated

- ✓ Typed immutable capability and stream-event models — v0.1.0
- ✓ Secret-safe typed failures and bounded authenticated transport — v0.1.0
- ✓ Capability discovery and streaming Chat Completions — v0.1.0
- ✓ Caller-owned HTTP lifecycle, cancellation, and cleanup guarantees — v0.1.0
- ✓ Typed distribution and locked verification gates — v0.1.0
- ✓ Correlated, bounded tool-progress events — validated in Phase 2: Conversation Event Contract
- ✓ Safe terminal partial-state and failure metadata — validated in Phase 2: Conversation Event Contract

### Active

- [ ] Consumers can send independently optional, strictly validated session ID and session key headers without mutating caller or client state.
- [ ] Existing authentication, retryability, protocol ordering, resource ownership, typing, coverage, and distribution guarantees remain green.

### Out of Scope

- Home Assistant identity derivation and memory policy — owned by `hermes-conversation`.
- Arbitrary per-request headers — would expand the public transport surface beyond the approved contract.
- Tool arguments, results, labels, raw payloads, and raw upstream error text — excluded to preserve the bounded, secret-safe public boundary.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-17 after completing Phase 2: Conversation Event Contract*
