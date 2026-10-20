---
phase: "3"
slug: "session-header-safety"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-20"
---

# Phase 3 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Phase 3 is an audit phase. It adds tests and documentation only, and `src/` is unchanged (`git diff main -- src/` is empty and `git log main..HEAD -- src/` prints nothing). Each mitigation below is the control that shipped in PR #7 (v0.3.1), now locked by phase 3 tests whose sensitivity is recorded in `03-TRACEABILITY.md` (D-11 mutation check).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Caller to `stream_chat_events` | Caller-supplied `session_id` and `session_key` enter the library | Opaque conversation and memory identifiers (sensitive) |
| Library to Hermes server (HTTP headers) | Session values leave the process as `X-Hermes-Session-Id` and `X-Hermes-Session-Key` | Identifiers that the server may use in filenames |
| Caller-owned `httpx.AsyncClient` to library stream | The library may own the response only; the injected client and its pool belong to the caller | Connection lifecycle |
| Library exception and frame state to consumer | Exceptions, tracebacks and retained generator frames return to the consumer and may be logged | Error text, frame locals (must not carry session values) |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-01 | Denial of Service | Stream close and cancel paths plus `__aexit__` against an injected client | high | mitigate | `owns_active` guard (`client.py:601`), with no client close on the stream path; `test_injected_client_survives_public_stream_task_cancellation` and `..._early_close`, red under G4 and G4b | closed |
| T-03-02 | Information Disclosure | `CancelledError` traceback, chain and frames after mid-iteration cancellation | high | mitigate | `_reraise_scrubbed_failure` (`client.py:83`) and local scrubbing (`client.py:674-675`); tracer test, red under scrub mutation S1 | closed |
| T-03-03 | Tampering | RED-proof mutations of `client.py` in plan 03-01 | medium | mitigate | Restored after every run; `git diff main -- src/` empty and no `src/` commits on the branch | closed |
| T-03-04 | Tampering | CR/LF/TAB/NUL header injection through session values | high | mitigate | Visible-ASCII allowlist through `_require_lifecycle_text` (`client.py:158`); `test_rejected_session_values_leave_no_retained_state`, red under G1 | closed |
| T-03-05 | Elevation of Privilege | Literal `session_id` traversal (`..`, `/`, `\`, drive prefix) | high | mitigate | D-05 path-shape rule (`client.py:153-185`); rejection and adjacency cases, red under G2 | closed |
| T-03-06 | Elevation of Privilege | Percent-encoded traversal in `session_id` | medium | transfer | Hermes server responsibility (D-05); research D-07 confirms the server never percent-decodes either header and applies `_is_path_unsafe` (`03-TRACEABILITY.md` D-07 record) | closed |
| T-03-07 | Information Disclosure | Local-input `HermesTransportError` text, repr, args, traceback and frame | high | mitigate | Metadata-only error and local scrubbing; exact text, repr and args, canary and `ag_frame` checks in plan 03-02, red under mutation | closed |
| T-03-08 | Elevation of Privilege | An arbitrary per-request header API | medium | mitigate | Signature lock test `..._accepts_no_arbitrary_headers`, red when a `headers` parameter is added | closed |
| T-03-09 | Tampering | RED-proof mutations of `client.py` and `models.py` in plan 03-02 | medium | mitigate | Restored after every run, with stale bytecode cleared; `src/` unchanged on the branch | closed |
| T-03-10 | Information Disclosure | Post-dispatch failures (401, 503, protocol, connect error, request-stage cancellation) | high | mitigate | Fresh metadata-only errors raised outside handlers; `test_post_dispatch_failures_carry_no_session_values` (5 cases), red under S1 | closed |
| T-03-11 | Information Disclosure | Retained generator frames after completion and early close | medium | mitigate | The wrapper closes the delegated stream and finishes, and scrubs session values before the first yield. `_assert_suspended_stream_retains_no_secrets` reads `ag_frame.f_locals` while the stream is suspended (every yield in `[completion]`, before `aclose()` on early close, and at the cancellation gate). It is red under review mutants A (session values retained while suspended) and B (`operation_headers` retained until the end): 4 failures each (code review CR-01, `19f7631`). The post-exit `ag_frame is None` checks are lifecycle checks only, because CPython clears the frame itself. | closed |
| T-03-12 | Tampering | RED-proof mutations and negative-control edits in plan 03-03 | medium | mitigate | Restored and reverted before each commit; `src/` unchanged on the branch | closed |
| T-03-13 | Information Disclosure | A created but never iterated generator retains session arguments in `ag_frame` | low | accept | See Accepted Risks Log AR-03-01 | closed |
| T-03-14 | Information Disclosure | Live `httpx.Response.request.headers` while a consumer holds a suspended stream | low | accept | See Accepted Risks Log AR-03-02 | closed |
| T-03-15 | Tampering | D-11 mutation residue in `client.py` | high | mitigate | One mutation at a time, restored and checked with `git diff --exit-code -- src/`; final `git log main..HEAD -- src/` empty | closed |
| T-03-16 | Repudiation | Evidence record overstating coverage or misattributing provenance | medium | mitigate | Every cited node ID was checked against `--collect-only` (42 functions and 80 case IDs matched); PR #7 provenance statement in `03-TRACEABILITY.md` | closed |
| T-03-17 | Tampering | Glob metacharacters in `session_id` reaching upstream `_remove_session_files` `Path.glob` | low | transfer | Server-side and operator-initiated, not traversal; recorded in `03-TRACEABILITY.md` for the user to report upstream | closed |
| T-03-18 | Repudiation | D-10 and D-11 evidence lost when the verifier writes `03-VERIFICATION.md` | medium | mitigate | Evidence lives only in `03-TRACEABILITY.md`, which no verifier pass writes; `03-VERIFICATION.md` did not exist when plan 03-04 finished | closed |
| T-03-SC | Tampering | Package dependencies | low | accept | See Accepted Risks Log AR-03-03 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-13 | The values are the caller's own in-process objects and cross no trust boundary. Closing before iteration clears the frame without dispatch (plan 03-03). Changing this would alter released v0.3.x behaviour (D-02 one-way door). Documented as Known Boundary (b) in `03-TRACEABILITY.md`. | User decision `q2-document-boundary` (plan 03-04, Task 1) | 2026-10-20 |
| AR-03-02 | T-03-14 | httpx needs the in-flight request; SESS-05 scopes secrecy to the exit paths; `request_headers` is cleared before the first yield (`test_stream_discards_temporary_request_headers_before_yield`). Recorded as a known boundary. | Plan 03-04 threat model | 2026-10-20 |
| AR-03-03 | T-03-SC | No package was installed or added; `uv.lock` and `pyproject.toml` are unchanged against `main`, and `uv lock --check` runs in prek on every commit. | Phase 3 threat models | 2026-10-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-20 | 19 | 19 | 0 | secure-phase (orchestrator, ASVS L1 short-circuit; register authored at plan time) |
| 2026-10-20 | 19 | 19 | 0 | orchestrator, after code review CR-01: T-03-11 evidence replaced with suspended-frame checks, re-verified against mutants A and B |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-20
