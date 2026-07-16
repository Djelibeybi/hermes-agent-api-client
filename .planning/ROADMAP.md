# Roadmap: Hermes Agent API Client

## Milestones

- ✅ **v0.1.0 Typed Hermes API Client Baseline** — Phase 1 (shipped 2026-07-15; archived in `.planning/milestones/`)
- 📋 **v0.3.0 Conversation Contract** — Phases 2-4 (planned)

## Overview

v0.3.0 extends the published typed client in three consumer-visible steps: first
define and decode a strict correlated event contract, then add secret-safe
per-request session transport, and finally prove the complete contract through
the installed distributions while preserving every v0.1.0 guarantee. The
client continues to transport bounded facts only; Home Assistant identity and
policy remain owned by `hermes-conversation`.

## Phases

- [ ] **Phase 2: Conversation Event Contract** — Expose bounded correlated tool progress and strict safe terminal metadata without raw upstream data.
- [ ] **Phase 3: Session Header Safety** — Transport independently optional opaque session values with exact validation, secrecy, isolation, and response ownership.
- [ ] **Phase 4: Contract and Distribution Verification** — Prove the complete v0.3.0 contract from source and built artifacts against current compatible dependencies.

## Phase Details

### Phase 2: Conversation Event Contract

**Goal:** Python consumers receive immutable, bounded tool-progress and terminal events whose wire mapping is ordered, strict, ambiguity-free, and secret-safe.
**Depends on:** Phase 1 (completed historical baseline)
**Requirements:** TOOL-01, TOOL-02, TOOL-03, TOOL-04, TERM-01, TERM-02, TERM-03, TERM-04, TERM-05, TERM-06, TERM-07
**Success Criteria** (what must be TRUE):

  1. Consumers can import the immutable tool status/event types and receive ordered `running` and `completed` events with correlated 1-256 character call IDs and names, including repeated records that preserve unmatched-call detectability after interruption.
  2. Missing, malformed, unknown, over-256-character, or duplicate approved tool lifecycle keys fail as `HermesProtocolError`, while emoji, labels, arguments, results, additive fields, and raw tool payloads never enter public state.
  3. Consumers can import the terminal failure-reason type and receive exact normal-stop, truncation, agent-error, and bounded unknown-safe-code mappings with the correct outcome and partial state.
  4. Every duplicate approved terminal key or contradictory `completed`, `failed`, `partial`, `error_code`, and `finish_reason` combination fails as `HermesProtocolError` instead of being resolved by precedence.
  5. Terminal events remain withheld until the response and suffix validate and cleanup succeeds; raw upstream error details stay private, transport disconnects remain transport errors, and cancellation produces no synthetic terminal event.

**Plans:** 2/4 plans executed

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Define the strict immutable public tool-progress and terminal vocabulary.
- [x] 02-02-PLAN.md — Freeze versioned tool and terminal evidence with truthful provenance.

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 02-03-PLAN.md — Decode duplicate-aware correlated tool-progress facts in order.

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 02-04-PLAN.md — Map strict safe terminal metadata through the delayed-delivery gate.

### Phase 3: Session Header Safety

**Goal:** Python consumers can attach opaque conversation and durable-memory identifiers to a stream without leakage, shared-state mutation, or transport ownership changes.
**Depends on:** Phase 2
**Requirements:** SESS-01, SESS-02, SESS-03, SESS-04, SESS-05, HTTP-02
**Success Criteria** (what must be TRUE):

  1. Consumers can independently omit or provide `session_id` and `session_key`, with non-`None` values mapped only to their exact Hermes headers and no arbitrary-header API.
  2. Only exact built-in strings of 1-256 visible ASCII characters (`0x21..0x7e`) are accepted, path-shaped session IDs are rejected, and invalid pairs fail atomically before dispatch as safe non-retryable local input errors.
  3. Concurrent streams use fresh headers and leave the request mapping, bound authorization headers, and every other stream's session values unchanged.
  4. Session canaries are absent from public failures, text representations, traceback chains, and retained generator locals after rejection, completion, early close, or cancellation.
  5. Closing or cancelling a stream closes its response but never an injected caller-owned HTTP client, and `asyncio.CancelledError` propagates after cleanup.

**Plans:** TBD

### Phase 4: Contract and Distribution Verification

**Goal:** Consumers can rely on the complete v0.3.0 contract from installed wheel and source distributions with all safety, lifecycle, typing, and regression gates proven together.
**Depends on:** Phase 3
**Requirements:** SECU-02, VERI-02, PKG-02, DEPS-01
**Success Criteria** (what must be TRUE):

  1. Canary and lifecycle matrices prove no session value, raw tool data, or raw terminal error detail survives in public values, failures, traceback chains, or retained generator state across normal and abnormal exits.
  2. The full session, duplicate/contradiction, ordered-correlation, unmatched-call, cancellation, cleanup-precedence, and v0.1.0 regression matrix passes with 100% branch coverage.
  3. Package-root imports and `HermesEvent` expose the complete v0.3.0 contract from source, wheel, and sdist with `py.typed`, strict basedpyright and `--verifytypes`, Ruff, and standalone distribution verification green.
  4. The lockfile uses the latest compatible dependency versions verified at execution time, with no new or broadened conversation-contract runtime dependency in `pyproject.toml`.

**Plans:** TBD

## Progress

**Execution Order:** Phase 2 → Phase 3 → Phase 4

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Typed Hermes API Client | v0.1.0 | 1/1 | Complete | 2026-07-15 |
| 2. Conversation Event Contract | v0.3.0 | 2/4 | In Progress | - |
| 3. Session Header Safety | v0.3.0 | 0/TBD | Not started | - |
| 4. Contract and Distribution Verification | v0.3.0 | 0/TBD | Not started | - |
