---
phase: 02-conversation-event-contract
plan: 04
subsystem: api
tags: [sse, terminal-metadata, duplicate-detection, secrecy, tdd]

requires:
  - phase: 02-conversation-event-contract
    provides: strict terminal vocabulary, immutable terminal evidence, and pair-aware JSON projection from Plans 02-01 through 02-03
provides:
  - omission-aware root-Hermes lifecycle projection with exact types and duplicate rejection
  - total stop, length, and upstream-error mapping for only the approved contract rows
  - safe unknown-code reduction and raw terminal-error scrubbing
  - enriched terminal withholding through suffix, source, and HTTP response cleanup
affects: [phase-3-session-header-safety, phase-4-contract-verification]

tech-stack:
  added: []
  patterns:
    - sanitized frozen DTO separates JSON omission from explicit null before terminal mapping
    - closed total mapper returns an input-independent failure sentinel for every unapproved row

key-files:
  created: []
  modified:
    - src/hermes_agent_api_client/protocol.py
    - src/hermes_agent_api_client/sse.py
    - tests/test_sse.py
    - tests/test_transport.py
    - scripts/check_phase2_provenance.py
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_length.sse
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_agent_error.sse
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_task_exception_contradiction.sse
    - tests/fixtures/hermes/v2026.7.7.2/provenance.json

key-decisions:
  - "Root hermes is projected into an omission-aware private DTO and excluded from ordinary chat-tree materialization so raw error members are discarded at the trust boundary."
  - "The terminal mapper accepts only D-01 through D-03; explicit null finish_reason is nonterminal only when no approved lifecycle fact is present."
  - "Unknown bounded safe error codes collapse to TerminalFailureReason.UNKNOWN and never enter public or retained state."

patterns-established:
  - "Terminal projection: validate approved root members before collapse, then materialize the remaining additive-compatible chat tree."
  - "Delayed enriched terminal: only the value stored in _pending_terminal changes; finalization and outer response cleanup remain the commit gates."

requirements-completed: [TERM-02, TERM-03, TERM-04, TERM-05, TERM-06, TERM-07]

coverage:
  - id: D1
    description: "Every approved stop row maps to exact SUCCESS metadata and every contradictory stop row fails closed."
    requirement: TERM-02
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_stop_terminal_accepts_only_the_total_success_rows"
        status: pass
      - kind: unit
        ref: "tests/test_sse.py#test_contradictory_terminal_rows_fail_without_precedence"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every approved length row maps to exact LENGTH, partial true, and OUTPUT_TRUNCATED metadata."
    requirement: TERM-03
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_length_terminal_accepts_only_the_total_truncation_rows"
        status: pass
      - kind: integration
        ref: "tests/test_sse.py#test_terminal_evidence_fixtures_map_to_exact_safe_public_events"
        status: pass
    human_judgment: false
  - id: D3
    description: "Agent and bounded unknown error rows map explicitly to UPSTREAM_ERROR with the server partial flag and closed safe reasons."
    requirement: TERM-04
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_error_terminal_accepts_only_the_total_upstream_error_rows"
        status: pass
      - kind: unit
        ref: "tests/test_sse.py#test_present_terminal_metadata_requires_exact_types_and_bounds"
        status: pass
    human_judgment: false
  - id: D4
    description: "Duplicate, null, coercible, omitted-required, and contradictory lifecycle combinations fail without precedence guesses."
    requirement: TERM-05
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_duplicate_approved_terminal_members_fail_before_collapse"
        status: pass
      - kind: unit
        ref: "tests/test_sse.py#test_design_terminal_matrix_is_executable_contract_evidence"
        status: pass
      - kind: integration
        ref: "scripts/check_phase2_provenance.py --scope terminal"
        status: pass
    human_judgment: false
  - id: D5
    description: "Raw terminal errors and unknown codes remain absent while disconnect and cancellation classifications stay unchanged."
    requirement: TERM-06
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_raw_terminal_errors_and_unknown_codes_are_never_retained"
        status: pass
      - kind: integration
        ref: "uv run --no-sync pytest tests/test_sse.py tests/test_transport.py --no-cov -q (307 passed)"
        status: pass
    human_judgment: false
  - id: D6
    description: "An enriched terminal is observable only after suffix validation and source plus HTTP response cleanup succeed."
    requirement: TERM-07
    verification:
      - kind: integration
        ref: "tests/test_transport.py#test_terminal_is_delivered_only_after_response_cleanup"
        status: pass
      - kind: unit
        ref: "tests/test_sse.py#test_second_done_confirmation_is_rejected_before_terminal_delivery"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-17
status: complete
---

# Phase 2 Plan 4: Total Safe Terminal Metadata Summary

**Omission-aware root-Hermes projection now maps only the locked terminal matrix into safe enriched values while preserving suffix, source, and HTTP cleanup as the terminal commit boundary.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-16T20:51:12Z
- **Completed:** 2026-07-16T21:00:08Z
- **Tasks:** 1 TDD feature
- **Files modified:** 9

## Accomplishments

- Executed all approved stop, length, and error combinations plus contradiction, omission, null, exact-type, bound, duplicate, and root-scope rejection cases as an executable total matrix.
- Added a frozen omission-aware terminal DTO that discards raw root-Hermes error members before chat materialization and collapses bounded unknown codes only to `UNKNOWN`.
- Enriched only the terminal stored by `_pending_terminal`, preserving DONE/suffix validation, source closure, HTTP response cleanup, transport failure, and cancellation precedence.
- Restored complete SSE record boundaries to all three terminal evidence streams and made the provenance verifier enforce that invariant.

## Task Commits

The TDD feature was committed through its required gates:

1. **RED: Define the total terminal metadata contract** - `81d3667` (test)
2. **GREEN: Implement total safe terminal metadata mapping** - `560f588` (feat)

No separate refactor commit was needed; the GREEN implementation is compact, named by contract role, and passed every quality gate.

## Files Created/Modified

- `src/hermes_agent_api_client/protocol.py` - Omission-aware lifecycle DTO, exact root-Hermes projection, and raw-member discard boundary.
- `src/hermes_agent_api_client/sse.py` - Total terminal mapper integrated with the existing pending-terminal state machine.
- `tests/test_sse.py` - Exhaustive accepted/rejected matrix, immutable evidence, duplicate, secrecy, suffix, cleanup, transport, and cancellation coverage.
- `tests/test_transport.py` - Enriched outer response-cleanup-before-terminal integration proof.
- `scripts/check_phase2_provenance.py` - Complete terminal fixture record-boundary verification.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_length.sse` - Complete valid length evidence stream.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_agent_error.sse` - Complete valid agent-error evidence stream.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_task_exception_contradiction.sse` - Complete contradictory rejection evidence stream.
- `tests/fixtures/hermes/v2026.7.7.2/provenance.json` - Updated immutable terminal fixture hashes.

## Decisions Made

- Removed root `hermes` from ordinary materialization after projecting only `completed`, `failed`, `partial`, and `error_code`; this preserves additive chat compatibility without traversing or retaining raw Hermes error objects.
- Treated explicit `finish_reason: null` as a valid nonterminal only when approved lifecycle metadata is absent; any lifecycle fact paired with null is an unlisted row and fails closed.
- Preserved the canonical-current `v2026.7.7.2` disposition from Plan 02-02; no alternate version root or generic alias was activated.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repaired unterminated terminal evidence records**

- **Found during:** GREEN immutable fixture execution
- **Issue:** All three terminal SSE fixtures ended with one LF after `data: [DONE]`, so the decoder correctly treated the final record as unterminated even though the provenance verifier accepted it.
- **Fix:** Added the required blank-line record boundary, updated all three immutable SHA-256 values, and taught the terminal provenance gate to reject an incomplete final record.
- **Files modified:** `terminal_length.sse`, `terminal_agent_error.sse`, `terminal_task_exception_contradiction.sse`, `provenance.json`, `scripts/check_phase2_provenance.py`
- **Verification:** Terminal provenance passes and both whole/bytewise fixture decoding paths are green.
- **Committed in:** `560f588`

**2. [Rule 1 - Test Bug] Isolated finish-reason omission from empty-delta validation**

- **Found during:** GREEN explicit-null behavior
- **Issue:** The new test builder used an empty delta, so a `finish_reason: null` row failed the pre-existing empty-semantic rule instead of isolating omission versus explicit null.
- **Fix:** Made derived terminal candidates carry the accepted assistant role without changing terminal behavior or fixture bytes.
- **Files modified:** `tests/test_sse.py`
- **Verification:** Missing `finish_reason` fails, explicit null emits no terminal itself, and a later DONE establishes default success.
- **Committed in:** `560f588`

---

**Total deviations:** 2 auto-fixed issues (one blocking evidence defect, one test-isolation bug).
**Impact on plan:** Both fixes were required to make the approved evidence executable and the omission/null test semantically precise; no public contract or dependency scope changed.

## Issues Encountered

- The RED commit intentionally skipped only the coverage-test hook because 112 contract failures were required before implementation. Lock, Ruff, basedpyright, verifytypes, build, and distribution hooks still passed.
- No release, network, authentication, dependency, transport, cancellation, or cleanup blocker occurred.

## TDD Gate Compliance

- RED commit `81d3667` precedes GREEN commit `560f588`.
- The 185-test targeted baseline passed before RED; RED failed on the missing total terminal contract, then GREEN passed 307 targeted tests.
- The full suite passes 550 tests with 100% statement and branch coverage.
- No behavior-preserving refactor commit was necessary.

## Verification Results

- `uv run --no-sync python scripts/check_phase2_provenance.py --scope terminal` - passed against the live canonical/latest tag gate.
- `uv run --no-sync pytest tests/test_sse.py tests/test_transport.py --no-cov -q` - 307 passed.
- `uv run --no-sync pytest -q` - 550 passed with 100% statement and branch coverage.
- `uv run --no-sync ruff check .` - passed.
- `uv run --no-sync basedpyright` - 0 errors, warnings, or notes.
- Commit hooks also passed verifytypes, wheel/sdist build, and standalone distribution verification.
- `git diff -- pyproject.toml uv.lock` - empty; Phase 4 dependency currency remains deferred exactly as planned.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2's correlated progress and safe terminal event contract is complete and ready for phase-level verification.
- Phase 3 can add strict per-request session headers without changing terminal projection or delivery ordering.
- Phase 4 still owns dependency refresh, combined secrecy/regression closure, and installed-distribution verification.

## Self-Check: PASSED

- All nine modified implementation, test, verifier, fixture, and provenance files exist.
- RED commit `81d3667` and GREEN commit `560f588` exist in order.
- Terminal provenance, targeted tests, full 100% coverage, Ruff, basedpyright, verifytypes, build, and distribution gates pass.
- No TODO, FIXME, placeholder, known stub, uncommitted dependency, or lockfile change remains.

---
*Phase: 02-conversation-event-contract*
*Completed: 2026-07-17*
