# Phase 3: Session Header Safety - Context

**Gathered:** 2026-10-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Python consumers can attach opaque conversation (`session_id`) and durable-memory (`session_key`) identifiers to `stream_chat_events` without leakage, shared-state mutation, or transport ownership changes (SESS-01 to SESS-05, HTTP-02).

**Starting state:** this behaviour was implemented outside GSD in PR #7 (`8843cfc fix: complete conversation contract`, released in v0.3.1). The code is `_is_valid_session_value`, `_chat_request_headers` and `HermesClient.stream_chat_events` in `src/hermes_agent_api_client/client.py`. The tests are in `tests/test_client_lifecycle.py` and `tests/test_transport.py`. This phase audits the shipped implementation against the requirements and closes proven gaps. It is not a greenfield build.

Installed-distribution closure, the milestone-wide canary sweep (SECU-02), the full regression matrix (VERI-02), package exports (PKG-02) and the dependency review (DEPS-01) remain Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Phase Approach

- **D-01:** Audit and close gaps. Plans must check each SESS-01 to SESS-05 and HTTP-02 criterion against the shipped code and tests. Add tests or fixes only where the audit proves something missing. Do not rewrite the PR #7 implementation.
- **D-02:** If shipped v0.3.x behaviour conflicts with `.planning/REQUIREMENTS.md` or the design spec, stop and raise it to the user before planning a change. Neither source wins automatically. — **Reversibility:** one-way — any change is to released v0.3.x public behaviour that `hermes-conversation` consumes.
- **D-03:** Change code only to fix a proven gap. No refactoring, renaming or deduplication (for example, with `_require_lifecycle_text`), even where the existing code is correct but awkward.
- **D-04:** Ship fixes through the normal flow: phase branch, PR and merge. PSR releases from the commit types as usual. Don't hold the release for Phase 4.

### Path-Shaped ID Rules

- **D-05:** Keep the shipped `session_id` path-shape rejection exactly as it is: reject values containing `..`, `/` or `\`, and values that start with a letter followed by `:` (a Windows drive prefix). Don't add `%`, percent-encoding detection or a narrower character allowlist. Encoded traversal is the Hermes server's responsibility, and the client check is defence in depth.
- **D-06:** `session_key` gets no path-shape checks, only the exact-`str`, 1-256 character, visible-ASCII (`0x21..0x7e`) rules, as SESS-02 states and as shipped.
- **D-07:** Research must read the tagged upstream Hermes source and record how the server uses `X-Hermes-Session-Id` and `X-Hermes-Session-Key`: whether either value becomes a file or path component, and whether the server decodes either value. If the server's handling makes D-05 insufficient, raise it as a conflict under D-02. Don't change the rules silently.

### Evidence Standard

- **D-08:** SESS-05 needs a complete exit-path matrix of explicit session-value canary tests for rejection, successful completion, early close and cancellation. Each cell checks `str`/`repr`, the traceback chain (`tb_frame.f_locals`), `__cause__`/`__context__`, and the async generator's retained frame (`ag_frame`). Reuse the existing canary helpers in `tests/test_client_lifecycle.py`, and add only the cells the audit finds missing.
- **D-09:** HTTP-02 needs stream-specific tests with an injected `httpx.AsyncClient`, covering both early close and cancellation mid-iteration. Each test asserts that the response closed, the injected client is still open and usable for a later request, and `asyncio.CancelledError` propagated after cleanup in the cancellation case. The generic `test_injected_client_is_never_closed` alone doesn't count.
- **D-10:** `03-TRACEABILITY.md` must include a traceability table mapping each SESS-01 to SESS-05 and HTTP-02 criterion, and each roadmap success criterion, to the exact test names that prove it. `03-VERIFICATION.md` references it as a Required Artifact. Gaps in the table drive the gap-fill plans. Phase 4 reuses the table from `03-TRACEABILITY.md` for VERI-02. *(Amended 2026-10-20 during planning, from "VERIFICATION.md must include": `gsd-verifier` rewrites `03-VERIFICATION.md` in initial mode, so plan-authored evidence there would be overwritten.)*
- **D-11:** Verification must include a manual mutation check of the key guards. Temporarily break each one, confirm at least one named test fails, restore it, and record the result in `03-TRACEABILITY.md` (amended 2026-10-20 from VERIFICATION.md, for the same reason as D-10). The guards are value validation, path-shape rejection, the fresh copy of the request headers (no mutation of bound or caller headers), and not closing the injected client. Add no new mutation-testing tooling.

### Claude's Discretion

- Test naming, parameterisation and placement within the existing test modules.
- How to phrase the audit and traceability findings, provided D-10's mapping is complete.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Approved Contract

- `docs/superpowers/specs/2026-07-17-conversation-contract-design.md` §1 — Authoritative session header signature, wire mapping, validation rules, secrecy and ownership requirements, and acceptance tests.
- `.planning/REQUIREMENTS.md` — SESS-01 to SESS-05 and HTTP-02 wording, the Phase 4 requirements that stay out of scope, and the milestone exclusions (no arbitrary headers, no identity derivation).
- `.planning/ROADMAP.md` § Phase 3 — Phase goal and the five success criteria to trace in `03-TRACEABILITY.md`.
- `.planning/PROJECT.md` — Boundaries: Home Assistant derives identifiers; this package validates and transports opaque values only.

### Prior Phase

- `.planning/phases/02-conversation-event-contract/02-CONTEXT.md` — D-05/D-07 visible-ASCII text rules reused by `_require_lifecycle_text`, and the scrubbing and safe-sentinel patterns.

### Shipped Implementation (audit targets)

- `src/hermes_agent_api_client/client.py` — `_is_valid_session_value`, `_chat_request_headers`, `HermesClient.stream_chat_events`, `_raise_transport_failure`, `_reraise_scrubbed_failure`.
- `tests/test_client_lifecycle.py` — Existing session tests (`test_stream_session_headers_are_independent_and_request_scoped`, `test_invalid_session_arguments_fail_locally_without_dispatch`, `test_path_shaped_session_ids_fail_before_dispatch`, `test_invalid_session_pair_is_atomic_and_secret_free`, `test_concurrent_streams_isolate_session_headers`, `test_injected_client_is_never_closed`), plus the canary and frame-inspection helpers.
- `tests/test_transport.py` — Stream cancellation and response-cleanup tests.
- Git commit `8843cfc` (PR #7) — The change that introduced the session implementation.

### External

- https://owasp.org/www-community/attacks/Path_Traversal — Background for D-05/D-07: encoded traversal forms, and why the server is responsible for resolving paths.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `_require_lifecycle_text` (shared with Phase 2 tool-text validation): the exact-`str`, 1-256 visible-ASCII check that `_is_valid_session_value` delegates to.
- Canary and frame helpers in `tests/test_client_lifecycle.py`: an `ag_frame` accessor, traceback-frame `f_locals` collection, and canary absence assertions over `str`/`repr`/cause/context. Reuse them for the D-08 matrix.
- `respx` mocks and an injected `httpx.AsyncClient` fixture pattern, already used by the lifecycle and transport tests.

### Established Patterns

- Invalid local input reduces to `HermesTransportError(transient=False)` through `_raise_transport_failure`, without carrying the rejected value.
- Sensitive locals are overwritten with `None` or `{}` before raising or yielding (`session_id = None`, `headers = {}`, `request_headers.clear()`). Tests assert this through frame inspection.
- Failures are re-raised through `_reraise_scrubbed_failure` with tracebacks stripped. Cancellation and close errors follow documented precedence rules.

### Integration Points

- Any gap fixes are confined to `client.py` (`_chat_request_headers` / `stream_chat_events`) and to `tests/test_client_lifecycle.py` and `tests/test_transport.py`. There are no public API surface changes, which is consistent with D-03.

</code_context>

<specifics>
## Specific Ideas

- The audit should state the PR #7 provenance explicitly in the research and verification artefacts, so this phase doesn't claim to have implemented the shipped behaviour (the same honesty pattern as the v0.1.0 historical baseline).

</specifics>

<deferred>
## Deferred Ideas

- Milestone or version re-scoping: the package is already at v0.3.3 while milestone v0.3.0 still has Phases 3 and 4 open. This is a roadmap and milestone housekeeping question, not Phase 3 scope.

</deferred>

---

*Phase: 03-session-header-safety*
*Context gathered: 2026-10-20*
