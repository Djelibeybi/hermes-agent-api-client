---
phase: 02-conversation-event-contract
plan: 06
subsystem: testing
tags: [provenance, duplicate-json, evidence-roles, diagnostics, tdd]

requires:
  - phase: 02-conversation-event-contract
    provides: release-bound immutable lifecycle evidence and production pair-aware event projection from Plans 02-03 through 02-05
provides:
  - production-faithful pair-preserving lifecycle normalization for provenance compatibility
  - exact release-agnostic evidence-role enforcement for every required lifecycle fixture
  - closed context-free provenance errors and single-line CLI diagnostics
affects: [phase-2-verification, phase-4-contract-verification]

tech-stack:
  added: []
  patterns:
    - internal provenance verification reuses production approved-path JSON projectors
    - lower-level failures are classified outside active exception handlers before closed errors are raised

key-files:
  created: []
  modified:
    - scripts/check_phase2_provenance.py
    - tests/test_phase2_provenance.py

key-decisions:
  - "Lifecycle compatibility uses the production pair hook plus tool/chat projectors, so approved duplicates reject while ignored additive duplicates remain compatible."
  - "Every required lifecycle path must match its exact _EXPECTED_KINDS role before any fixture bytes are normalized."
  - "Provenance failures expose one finite constant code and translate lower-level exceptions only after leaving the active handler."

patterns-established:
  - "Pair-aware evidence normalization: project event-specific approved facts before computing compatibility tuples."
  - "Closed diagnostics: never interpolate editor-controlled fixture, source, range, or case values into provenance errors."

requirements-completed: [TOOL-02, TOOL-03, TOOL-04, TERM-02, TERM-03, TERM-04, TERM-05]

coverage:
  - id: D1
    description: "Newer-release lifecycle evidence obeys production duplicate ambiguity rules for all nine approved member families while ignored additive duplicates remain compatible."
    requirement: TOOL-03
    verification:
      - kind: unit
        ref: "tests/test_phase2_provenance.py#test_newer_release_rejects_every_approved_duplicate_family"
        status: pass
      - kind: unit
        ref: "tests/test_phase2_provenance.py#test_newer_release_accepts_duplicate_inside_ignored_additive_data"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every canonical or newer required lifecycle entry has its exact source-derived or design-derived evidence role."
    requirement: TERM-05
    verification:
      - kind: unit
        ref: "tests/test_phase2_provenance.py#test_lifecycle_evidence_roles_are_exact_for_every_required_path"
        status: pass
    human_judgment: false
  - id: D3
    description: "Fixture, source, range, and terminal-case canaries are absent from exceptions, traceback state, and CLI stderr."
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: "tests/test_phase2_provenance.py#closed diagnostic and CLI canary tests"
        status: pass
      - kind: integration
        ref: "uv run --no-sync python scripts/check_phase2_provenance.py --scope release-and-tool"
        status: pass
      - kind: integration
        ref: "uv run --no-sync python scripts/check_phase2_provenance.py --scope terminal"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-17
status: complete
---

# Phase 2 Plan 6: Provenance Trust-Boundary Closure Summary

**Newer-release provenance now shares production duplicate semantics, authenticates exact evidence roles, and emits only closed context-free diagnostics.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-17T00:32:49Z
- **Completed:** 2026-07-17T00:44:31Z
- **Tasks:** 1 TDD feature
- **Files modified:** 2

## Accomplishments

- Reused the production pair-preserving JSON hook and event-specific tool/chat projectors so all same-value and conflicting approved duplicates reject without globally rejecting ignored additive data.
- Enforced the exact `_EXPECTED_KINDS` mapping for all five lifecycle paths in the release-agnostic canonical/newer normalization path.
- Replaced value-bearing verifier failures with finite constant codes and translated JSON, Unicode, filesystem, and Git failures without retained cause or context.
- Added 33 network-free adversarial cases over complete temporary release roots and real temporary Git source trees.

## Task Commits

1. **RED: Expose provenance boundary gaps** - `0d421a9` (test)
2. **GREEN: Close provenance trust boundaries** - `22c5744` (feat)

No separate refactor commit was needed; the GREEN implementation already centralizes fixture reading, pair decoding, event-specific projection, and closed translation.

## Files Created/Modified

- `scripts/check_phase2_provenance.py` - Production-faithful lifecycle projection, exact evidence roles, and closed diagnostics.
- `tests/test_phase2_provenance.py` - Duplicate-family, additive-control, evidence-role, exception-state, traceback, and CLI regressions.

## Decisions Made

- Reused intentional package-private production projectors with narrow static-analysis suppressions instead of copying approved member lists into the verifier.
- Consumed only sanitized approved Hermes terminal metadata during normalization; additive raw fields remain outside compatibility state.
- Preserved `latest-tag-verification-blocked` as the sole exit-3 diagnostic; every other provenance failure remains exit 1.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The repository's case-insensitive `/Scripts/` ignore rule returned a non-zero staging status for the tracked lowercase verifier; Git had staged the tracked modification correctly, and the normal commit then passed every hook.
- The plan's abbreviated verifytypes command reports third-party incompleteness without the repository's established `--ignoreexternal` flag. The installed project gate with `--ignoreexternal` passed at 100% type completeness.

## TDD Gate Compliance

- RED commit `0d421a9` precedes GREEN commit `22c5744`.
- RED failed on approved duplicate acceptance, evidence-role forgery, and value-bearing/context-retaining diagnostics while the additive duplicate control passed.
- GREEN passes all 47 focused tests. No behavior-preserving refactor commit was necessary.

## Verification Results

- Focused provenance matrix - 47 passed across bounded invocations.
- Live `release-and-tool` and `terminal` provenance scopes - passed against the official tag gate.
- `uv run --no-sync pytest -q` - 597 passed with 100% statement and branch coverage.
- Ruff format/check and full basedpyright - passed.
- `basedpyright --verifytypes hermes_agent_api_client --ignoreexternal` - 100% type completeness.
- Isolated wheel/sdist build and `scripts/verify_dist.py` - passed.
- Public package source, immutable fixtures, `pyproject.toml`, and `uv.lock` - unchanged.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three Phase 2 verifier/review gaps now have permanent adversarial regressions and production-faithful fixes.
- Phase 2 is ready for re-verification and milestone progression into Phase 3.
- Phase 4 retains dependency currency and installed-distribution closure ownership.

## Self-Check: PASSED

- Both planned implementation/test files exist and contain no stub markers.
- RED `0d421a9` and GREEN `22c5744` exist in the required order.
- Focused, live, full-coverage, lint, typing, build, and distribution gates pass.
- No public source, fixture, dependency declaration, lockfile, new endpoint, or new external trust surface changed.

---
*Phase: 02-conversation-event-contract*
*Completed: 2026-07-17*
