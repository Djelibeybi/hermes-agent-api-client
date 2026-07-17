# Requirements: Hermes Agent API Client

**Defined:** 2026-07-17
**Core Value:** Python consumers can use a typed, bounded, secret-safe asynchronous client for the documented Hermes Agent API Server boundary without implementing protocol or transport behaviour themselves.

## v0.3.0 Requirements

Requirements for the Conversation Contract milestone. Each requirement maps to exactly one roadmap phase.

### Session Headers

- [ ] **SESS-01**: A Python consumer can independently provide `session_id`, `session_key`, both, or neither to `stream_chat_events`, with non-`None` values mapped only to `X-Hermes-Session-Id` and `X-Hermes-Session-Key`.
- [ ] **SESS-02**: A Python consumer receives local rejection unless each supplied session value is an exact built-in `str` containing 1-256 characters in the visible ASCII range `0x21..0x7e`, and `session_id` additionally rejects path-shaped values.
- [ ] **SESS-03**: An invalid session value fails before network dispatch as the existing safe, non-retryable local-input classification, without including the rejected value in text or metadata.
- [ ] **SESS-04**: Each stream constructs fresh request headers without mutating the caller's request mapping, the client's bound authorization headers, or another concurrent request's session values.
- [ ] **SESS-05**: Session values are absent from public failures, `str`, `repr`, tracebacks, causes, contexts, and retained generator locals after rejection, completion, early close, or cancellation.

### Stream Lifecycle

- [ ] **HTTP-02**: Closing or cancelling a stream closes only its response, never an injected caller-owned HTTP client, and `asyncio.CancelledError` propagates after cleanup.

### Tool Progress

- [x] **TOOL-01**: A Python consumer can import `ToolProgressStatus` and an immutable `ToolProgressEvent` carrying a 1-256 character `tool_call_id`, a 1-256 character `tool_name`, and exactly `RUNNING` or `COMPLETED` status.
- [x] **TOOL-02**: A Python consumer receives `toolCallId`, tool name, and status as ordered correlated progress events, including repeated lifecycle records needed to detect unmatched running calls after interruption.
- [x] **TOOL-03**: Missing, malformed, unknown, over-bound, or duplicate approved tool-lifecycle fields fail as `HermesProtocolError`; every duplicate singleton lifecycle key is invalid even when duplicate values agree.
- [x] **TOOL-04**: Tool emoji, labels, arguments, results, other additive fields, and the raw tool payload never enter public models or exceptions.

### Terminal Metadata

- [x] **TERM-01**: A Python consumer can import `TerminalFailureReason`, and immutable `TerminalEvent` values expose `partial: bool = False` plus an optional closed failure reason.
- [x] **TERM-02**: `finish_reason="stop"` produces `SUCCESS`, `partial=False`, and no failure reason only when no abnormal terminal metadata is present.
- [x] **TERM-03**: `finish_reason="length"` or compatible `output_truncated` metadata produces `LENGTH`, `partial=True`, and `OUTPUT_TRUNCATED`.
- [x] **TERM-04**: `finish_reason="error"` preserves a strict server `partial` boolean, maps `agent_error` to `AGENT_ERROR`, and maps any other valid 1-256 character visible-ASCII safe error code to `UNKNOWN`.
- [x] **TERM-05**: Duplicate approved terminal lifecycle fields or incompatible `completed`, `failed`, `partial`, `error_code`, and `finish_reason` combinations fail as `HermesProtocolError` instead of applying precedence guesses.
- [x] **TERM-06**: Raw Hermes error text, messages, exception types, and error objects never enter public events or exceptions; disconnects remain `HermesTransportError`, cancellation remains `CancelledError`, and the client synthesizes no terminal event.
- [x] **TERM-07**: A terminal event becomes observable only after the complete response and suffix validate and response cleanup succeeds, preserving the existing terminal-order guarantee.

### Verification and Distribution

- [ ] **SECU-02**: Canary tests prove session values, raw tool data, and raw terminal error details are absent from public values, failures, traceback chains, and retained generator state.
- [ ] **VERI-02**: Automated tests cover session omission/independence/together cases, exact bounds and strict types, duplicate and contradictory wire matrices, ordered tool correlation, unmatched-call detectability, cancellation, early close, cleanup precedence, and all v0.1.0 regression guarantees with 100% branch coverage.
- [ ] **PKG-02**: Package-root exports, `HermesEvent`, strict basedpyright and `--verifytypes`, Ruff, `py.typed`, wheel imports, sdist imports, and standalone distribution verification expose the complete v0.3.0 contract.
- [ ] **DEPS-01**: The lockfile is refreshed and reviewed against the latest compatible dependency versions at final verification without adding or broadening conversation-contract dependencies in `pyproject.toml`.

## Future Requirements

Deferred until a later evidence-backed client milestone.

### Protocol Extensions

- **TOOL-05**: A Python consumer can receive additional closed tool lifecycle statuses when an immutable Hermes release and consumer requirement define their semantics.
- **TERM-08**: A Python consumer can receive additional safe terminal failure reasons when consumers require a stable distinction that does not expose raw upstream details.
- **SESS-06**: A Python consumer can provide additional named request metadata after independent secrecy, ownership, and boundary review.
- **OPER-01**: A Python consumer can call additional Hermes API operations supported by captured upstream evidence.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Arbitrary per-request headers | Expands and weakens the bounded public transport and secrecy contract. |
| Home Assistant identity derivation, session lifecycle, or memory policy | Owned by `hermes-conversation`; this package accepts opaque values only. |
| Tool arguments, results, labels, emoji, or raw payloads | Unbounded and potentially secret-bearing data outside the approved progress contract. |
| Raw upstream error messages, exception types, or error objects | Violates the stable, secret-safe public failure boundary. |
| Client-owned unmatched-call tracking or synthetic tool outcomes | The client emits ordered facts; consumer policy belongs to the integration. |
| Synthetic terminal events for disconnects or cancellation | Would conflate transport/control-flow failures with server-reported outcomes. |
| Automatic replay of partially consumed streams | Risks duplicated text or tool side effects and belongs to consumer retry policy. |
| Additional API operations | Require separate immutable server evidence and an evidence-backed milestone. |

## Traceability

Each active requirement maps to exactly one v0.3.0 roadmap phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SESS-01 | Phase 3 | Pending |
| SESS-02 | Phase 3 | Pending |
| SESS-03 | Phase 3 | Pending |
| SESS-04 | Phase 3 | Pending |
| SESS-05 | Phase 3 | Pending |
| HTTP-02 | Phase 3 | Pending |
| TOOL-01 | Phase 2 | Complete |
| TOOL-02 | Phase 2 | Complete |
| TOOL-03 | Phase 2 | Complete |
| TOOL-04 | Phase 2 | Complete |
| TERM-01 | Phase 2 | Complete |
| TERM-02 | Phase 2 | Complete |
| TERM-03 | Phase 2 | Complete |
| TERM-04 | Phase 2 | Complete |
| TERM-05 | Phase 2 | Complete |
| TERM-06 | Phase 2 | Complete |
| TERM-07 | Phase 2 | Complete |
| SECU-02 | Phase 4 | Pending |
| VERI-02 | Phase 4 | Pending |
| PKG-02 | Phase 4 | Pending |
| DEPS-01 | Phase 4 | Pending |

**Coverage:**

- v0.3.0 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0

---
*Requirements defined: 2026-07-17*
*Last updated: 2026-07-17 after v0.3.0 roadmap creation*
