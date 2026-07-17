---
phase: 2
slug: conversation-event-contract
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-17
audited: 2026-07-17
---

# Phase 2 — Validation Strategy

> Retrospective Nyquist audit of all executed conversation-event contract plans.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0 |
| **Config file** | `pyproject.toml` |
| **Task test command** | Use the exact `<automated>` command from each PLAN; pytest selections include `--no-cov` so partial suites do not misrepresent the repository-wide threshold. |
| **Full suite command** | `uv run --no-sync pytest -q` |
| **Static gates** | `uv lock --check`, Ruff, basedpyright, and `basedpyright --verifytypes hermes_agent_api_client --ignoreexternal` |
| **Measured runtime** | Full suite approximately 49 seconds on the audit host; narrower commands range from seconds to the distribution-heavy package selection. |

---

## Sampling Rate

- **After every task commit:** Run the task's exact PLAN `<automated>` command.
- **After every wave:** Run `uv run --no-sync pytest -q` so the 100% statement/branch gate applies.
- **Before phase closeout:** Run the full suite, lock check, Ruff, basedpyright, verifytypes, both live provenance scopes, and isolated distribution hooks.
- **Continuity:** Every one of the seven executed tasks has an automated command; there is no three-task validation gap.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirements | Automated Command | Current Evidence | Status |
|---------|------|------|--------------|-------------------|------------------|--------|
| 02-01-task-1 | 02-01 | 1 | TOOL-01, TOOL-02, TERM-01 | `uv run --no-sync pytest tests/test_protocol.py tests/test_package.py tests/test_sse.py --no-cov -q` | Public vocabulary, exact bounds/types, immutable models, exports, and SSE construction tests pass. | ✅ green |
| 02-02-task-1 | 02-02 | 1 | TOOL-02, TOOL-03, TOOL-04 | `uv run --no-sync python scripts/check_phase2_provenance.py --scope release-and-tool` | Live canonical/latest identity, immutable tool fixture, hashes, anchors, and ordered correlation pass. | ✅ green |
| 02-02-task-2 | 02-02 | 1 | TERM-02, TERM-03, TERM-04, TERM-05, TERM-06 | `uv run --no-sync python scripts/check_phase2_provenance.py --scope terminal` | Live terminal fixtures, evidence roles, design rows, citations, and hashes pass. | ✅ green |
| 02-03-task-1 | 02-03 | 2 | TOOL-02, TOOL-03, TOOL-04 | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | Pair preservation, duplicate rejection, correlation/order, repetition, interruption, recursion, and secrecy tests pass. | ✅ green |
| 02-04-task-1 | 02-04 | 3 | TERM-02, TERM-03, TERM-04, TERM-05, TERM-06, TERM-07 | `uv run --no-sync pytest tests/test_sse.py tests/test_transport.py --no-cov -q` | Total terminal matrix, contradiction, raw-error secrecy, cancellation, cleanup precedence, and delayed delivery tests pass. | ✅ green |
| 02-05-task-1 | 02-05 | 4 | TOOL-02, TERM-02, TERM-03, TERM-04, TERM-05 | `uv run --no-sync pytest tests/test_phase2_provenance.py --no-cov -q` | External identity, source-tree HEAD, complete newer evidence, hashes/anchors, and byte-derived equivalence tests pass. | ✅ green |
| 02-06-task-1 | 02-06 | 5 | TOOL-02, TOOL-03, TOOL-04, TERM-02, TERM-03, TERM-04, TERM-05 | `uv run --no-sync pytest tests/test_phase2_provenance.py --no-cov -q` | Production duplicate rules, exact evidence roles, closed diagnostics, parser totality, and temporary-resource tests pass. | ✅ green |

---

## Requirement Coverage

| Requirement | Primary Automated Evidence | Classification |
|-------------|----------------------------|----------------|
| TOOL-01 | `test_protocol.py` direct enum/model strictness and `test_package.py` exact exports | COVERED |
| TOOL-02 | `test_sse.py` correlation/order/repetition/interruption plus release-bound provenance tests | COVERED |
| TOOL-03 | Raw approved-member duplicate matrices in `test_sse.py` and production-faithful duplicate-family provenance tests | COVERED |
| TOOL-04 | Raw/additive payload scrub assertions, traceback/generator canaries, and closed provenance diagnostics | COVERED |
| TERM-01 | Direct immutable/default/strict metadata tests and package-root enum export tests | COVERED |
| TERM-02 | Exhaustive stop rows and canonical terminal fixture execution | COVERED |
| TERM-03 | Exhaustive length rows, output-truncated mapping, and canonical fixture execution | COVERED |
| TERM-04 | Exhaustive error rows, exact partial handling, bounded unknown-code mapping, and byte-derived equivalence | COVERED |
| TERM-05 | Duplicate/null/contradiction matrices, design evidence execution, and exact lifecycle evidence-role checks | COVERED |
| TERM-06 | Raw terminal secrecy, transport/disconnect taxonomy, cancellation identity, and retained-state checks | COVERED |
| TERM-07 | Suffix/source/response cleanup ordering, early close, failure precedence, and delayed terminal delivery | COVERED |

**Coverage result:** 11/11 Phase 2 requirements are covered by automated tests. No partial or missing requirement was found, so no new test file or Nyquist auditor was required.

---

## Wave 0 Completion

- [x] Immutable correlated tool and terminal fixtures exist with exact provenance, SHA-256, source/design roles, and semantic assertions.
- [x] `scripts/check_phase2_provenance.py` enforces tag identity, conditional newer-tag compatibility, hashes, source anchors, evidence roles, and closed failures.
- [x] `tests/helpers/hermes.py` provides raw ordered JSON-member SSE construction for duplicate-name cases.
- [x] `tests/test_protocol.py` and `tests/test_package.py` cover direct construction, exact bounds/types, immutability, and exports.
- [x] `tests/test_sse.py` covers the exhaustive tool/terminal matrices, ordering, repetition, interruption, secrecy, and parser boundaries.
- [x] `tests/test_transport.py` covers response ownership, cancellation, cleanup precedence, and delayed terminal observation.
- [x] `tests/test_phase2_provenance.py` covers release identity, immutable evidence, duplicate/role integrity, exception totality, and cleanup.
- [x] No framework installation or test-configuration change was required.

---

## Current Audit Evidence

| Gate | Result |
|------|--------|
| Combined Phase 2 test files with `--no-cov` | Green; all plan-owned test modules pass. |
| Full suite | 635 passed with 100% statement and branch coverage. |
| Live provenance | `release-and-tool` and `terminal` scopes both emitted success markers. |
| Lock and static analysis | Lock check, Ruff, basedpyright, and verifytypes pass; type completeness is 100%. |
| Distribution hooks | Build and standalone wheel/sdist verification pass in the repository commit gate. |
| Security and goal verification | `02-SECURITY.md` has 18/18 threats closed; `02-VERIFICATION.md` passes 22/22 must-haves. |

---

## Manual-Only Verifications

None. All Phase 2 requirements have automated verification. A future incompatible or ambiguous Hermes tag remains a blocking contract-decision checkpoint rather than a current manual-only validation gap.

---

## Validation Audit 2026-07-17

| Metric | Count |
|--------|-------|
| Requirements audited | 11 |
| Executed tasks audited | 7 |
| Gaps found | 0 |
| Resolved by new tests | 0 |
| Escalated/manual-only | 0 |

---

## Validation Sign-Off

- [x] All executed tasks have current automated verification commands.
- [x] All 11 Phase 2 requirements have green automated evidence.
- [x] Wave 0 fixtures, helpers, tests, and provenance gates exist and pass.
- [x] No watch-mode flags are used.
- [x] `wave_0_complete: true` is set in frontmatter.
- [x] `nyquist_compliant: true` is set in frontmatter.
- [x] `status: verified` is set in frontmatter.

**Approval:** verified 2026-07-17
