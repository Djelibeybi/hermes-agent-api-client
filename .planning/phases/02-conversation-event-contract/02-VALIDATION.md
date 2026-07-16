---
phase: 2
slug: conversation-event-contract
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-17
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --no-sync pytest tests/test_protocol.py tests/test_sse.py --no-cov -q` |
| **Full suite command** | `uv run --no-sync pytest -q` |
| **Estimated runtime** | Quick suite under 1 second; full suite under 10 seconds on the research host |

---

## Sampling Rate

- **After every task commit:** Run the narrow test command named by that task; default to `uv run --no-sync pytest tests/test_protocol.py tests/test_sse.py --no-cov -q`.
- **After every plan wave:** Run `uv run --no-sync pytest -q` so the 100% branch-coverage gate applies.
- **Before `$gsd-verify-work`:** The full pytest suite, Ruff, basedpyright, and package-root export tests must be green.
- **Max feedback latency:** 10 seconds for the full suite on the research host.

---

## Per-Task Verification Map

The planner assigns final task IDs. Every requirement below must remain attached to an automated task and its named command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| planner-assigned | TBD | TBD | TOOL-01 | T-02-01 | Exact immutable public enum/model contract | unit/static | `uv run --no-sync pytest tests/test_protocol.py tests/test_package.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TOOL-02 | T-02-02 | Ordered correlated records remain facts, without synthetic tracking | async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TOOL-03 | T-02-01 | Approved duplicate/malformed keys fail closed | async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TOOL-04 | T-02-03 | Raw/additive tool data never enters public state, errors, or frames | security unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TERM-01 | T-02-01 | Closed immutable terminal vocabulary | unit/static | `uv run --no-sync pytest tests/test_protocol.py tests/test_package.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TERM-02 | T-02-04 | Only the approved stop matrix maps to success | parameterized async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TERM-03 | T-02-04 | Only the approved length matrix maps to truncation | parameterized async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TERM-04 | T-02-04 | Exact partial and bounded safe error-code mapping | parameterized async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TERM-05 | T-02-01, T-02-04 | Duplicates, nulls, and contradictions are never normalized | property-style parameterized unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TERM-06 | T-02-03 | Raw errors remain private; transport and cancellation classifications remain exact | security/regression | `uv run --no-sync pytest tests/test_sse.py tests/test_transport.py --no-cov -q` | ✅ extend existing | ⬜ pending |
| planner-assigned | TBD | TBD | TERM-07 | T-02-05 | Terminal observation follows suffix validation and cleanup | async integration/regression | `uv run --no-sync pytest tests/test_sse.py tests/test_transport.py --no-cov -q` | ✅ extend existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Threat references:

- **T-02-01:** duplicate-key, exact-type, null, and bound bypass at the JSON/protocol boundary.
- **T-02-02:** lifecycle reordering or synthetic reconciliation hides interruption state.
- **T-02-03:** raw tool/error data leaks through values, exceptions, frames, or retained state.
- **T-02-04:** contradictory terminal facts are normalized by precedence instead of rejected.
- **T-02-05:** a terminal event becomes visible before suffix validation or cleanup completes.

---

## Wave 0 Requirements

- [ ] Add immutable running/completed and terminal evidence fixtures under `tests/fixtures/hermes/v2026.7.7.2/chat_completions/` with SHA-256 provenance entries distinguishing tag-source-derived from design-derived cases.
- [ ] Add raw duplicate-member inputs as bytes/text because Python dictionaries cannot represent duplicate JSON members.
- [ ] Extend `tests/test_protocol.py` and `tests/test_package.py` for direct-construction, exact-bound, enum, and export cases.
- [ ] Extend `tests/test_sse.py` for the exhaustive tool/terminal matrix, secrecy canaries, repetition, interruption, and ordering cases.
- [ ] Extend `tests/test_transport.py` only where the outer response-cleanup gate requires coverage.
- No framework installation or test configuration change is required.

---

## Manual-Only Verifications

All Phase 2 behaviors have automated verification. The implementation must repeat the latest Hermes numeric-tag check before coding; a newer incompatible tagged envelope is a blocking contract decision rather than a manual acceptance test.

---

## Validation Sign-Off

- [x] All planned requirement areas have automated verification commands.
- [x] Sampling continuity prevents three consecutive tasks without an automated check.
- [x] Wave 0 names every missing fixture/test extension.
- [x] No watch-mode flags are used.
- [x] Measured feedback latency is under 10 seconds.
- [x] `nyquist_compliant: true` is set in frontmatter.

**Approval:** approved for planning 2026-07-17
