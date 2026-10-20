---
phase: "3"
slug: "session-header-safety"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-20"
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`), pytest-cov 7.1.0 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) |
| **Quick run command** | `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q` |
| **Full suite command** | `uv run pytest` (enforces `fail_under = 100` branch coverage) |
| **Full gate** | `uv run --no-sync prek run --all-files` |
| **Estimated runtime** | ~1 second (quick); ~10 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** `uv run --no-sync prek run --all-files` must be green, and the D-11 mutation results must be recorded in `03-TRACEABILITY.md` (the plan-authored D-10/D-11 evidence record that `gsd-verifier` lists under Required Artifacts in `03-VERIFICATION.md`)
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

Task IDs filled by the planner (2026-10-20). The requirement-to-test mapping comes from `03-RESEARCH.md` § Validation Architecture. Every new test is proven red under a named temporary mutation and green on the restored shipped code; `git diff --exit-code -- src/` must be clean after every task.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-T1 (tracer) | 03-01 | 1 | HTTP-02, SESS-05, SESS-04 | T-03-01, T-03-02, T-03-03 | Mid-iteration task cancellation closes only the response; `CancelledError` propagates after cleanup; no session canary in str/repr/traceback/frames; `ag_frame` None; later stream carries no session header | unit (asyncio task) | `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "injected_client_survives_public_stream_task_cancellation"` | ✅ G-08 | ✅ green |
| 03-01-T2 | 03-01 | 1 | HTTP-02, SESS-05 | T-03-01 | Early close keeps the injected client open and reusable (later stream + capability probe); open after context exit | unit | `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "injected_client_survives_public_stream"` | ✅ G-08 | ✅ green |
| 03-02-T1 | 03-02 | 2 | SESS-01, SESS-04 | T-03-08 | Values appear only in their exact headers, exactly once, byte-for-byte; no arbitrary-header API | unit | `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "appear_only_in_their_exact_headers or accepts_no_arbitrary_headers"` | ✅ G-01, G-02 | ✅ green |
| 03-02-T2 | 03-02 | 2 | SESS-02, SESS-03, SESS-05 | T-03-04, T-03-05, T-03-06, T-03-07, T-03-09 | CR/TAB/bytes/empty/path-shaped/pair rejection before dispatch with exact value-free text, repr and args; `ag_frame` None; positive key bounds and D-05 adjacency pins | unit | `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "rejected_session_values_leave_no_retained_state or session_values_accept_exact_boundaries"` | ✅ G-03 to G-05 | ✅ green |
| 03-03-T1 | 03-03 | 3 | SESS-05 | T-03-11, T-03-12 | Completion and early close (after event and before first iteration) retain no session values | unit | `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "completed_and_closed_streams_retain_no_session_values"` | ✅ G-06 | ✅ green |
| 03-03-T2 | 03-03 | 3 | SESS-05 | T-03-10, T-03-12 | 401, 503, protocol, connect-error and request-stage cancellation failures carry no session values | unit | `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "post_dispatch_failures_carry_no_session_values"` | ✅ G-07 | ✅ green |
| 03-04-T1 | 03-04 | 4 | SESS-05 | T-03-13 | User decides Q1 (exception-less D-08 cells) and Q2 (pre-iteration retention) under D-02 | checkpoint:decision | n/a (blocking-human decision) | n/a | ✅ decided (q1-accept-na, q2-document-boundary) |
| 03-04-T2 | 03-04 | 4 | SESS-02, SESS-04, HTTP-02 | T-03-15 | D-11 mutation check: G1, G2, G3, G3b, G4, G4b, S1 each turn named tests red and are restored | manual (D-11) + automated restore gate | `git diff --exit-code -- src/` then `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q` | ✅ (guards and tests exist after Plans 03-01 to 03-03) | ✅ recorded in 03-TRACEABILITY.md |
| 03-04-T3 | 03-04 | 4 | SESS-01, SESS-02, SESS-03, SESS-04, SESS-05, HTTP-02 | T-03-16, T-03-17 | D-10 traceability: every cited node ID resolves in `--collect-only`; full gate green | doc check + full gate | `uv run --no-sync prek run --all-files` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The only new shared helper, `GatedAsyncByteStream` in `tests/test_client_lifecycle.py`, is created by the HTTP-02 (G-08) plan itself.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Guard sensitivity (D-11 mutation check) | SESS-02, SESS-04, HTTP-02 | No mutation-testing tooling by decision (D-11) | Break each guard in turn (value validation, path-shape rejection, fresh header copy, injected-client non-closure), run the two session test modules, confirm at least one named test fails, restore, and record in `03-TRACEABILITY.md` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-10-20 (validate-phase audit: 0 gaps)

## Validation Audit 2026-10-20

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
