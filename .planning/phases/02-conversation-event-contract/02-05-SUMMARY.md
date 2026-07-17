---
phase: 02-conversation-event-contract
plan: 05
subsystem: testing
tags: [provenance, release-identity, git, sha256, sse, tdd]

requires:
  - phase: 02-conversation-event-contract
    provides: immutable lifecycle evidence, structured source anchors, and strict public tool/terminal semantics from Plans 02-02 and 02-04
provides:
  - externally bound manifest and fixture release/commit identity
  - exact source-tree HEAD validation before source-anchor authentication
  - complete newer-release manifest, inventory, hash, byte, and source-anchor validation
  - deterministic canonical/newer lifecycle equivalence computed from immutable evidence bytes
affects: [phase-2-verification, phase-4-contract-verification]

tech-stack:
  added: []
  patterns:
    - external tag identity flows through source-tree HEAD, manifest, entries, anchors, hashes, and normalized lifecycle events
    - compatibility declarations remain audit metadata while immutable bytes determine public equivalence

key-files:
  created:
    - tests/test_phase2_provenance.py
  modified:
    - scripts/check_phase2_provenance.py

key-decisions:
  - "Release evidence is authenticated top-down from externally expected release and commit values; entry-owned identity fields never establish their own trust root."
  - "Newer-tag compatibility compares deterministic lifecycle events derived from validated fixture bytes; difference_summary declarations cannot produce a passing equivalence result."
  - "The historical evidence_scope.live_server_tested check remains canonical-only while the release-agnostic manifest path validates newer evidence without that legacy field."

patterns-established:
  - "Release-bound evidence: verify Git HEAD before manifest and entry identity, then verify source anchors and immutable fixture hashes."
  - "Computed compatibility: normalize required tool, terminal, contradiction, and design-matrix roles from validated bytes before comparing releases."

requirements-completed: [TOOL-02, TERM-02, TERM-03, TERM-04, TERM-05]

coverage:
  - id: D1
    description: "Every fixture entry is bound to independently expected release/commit identity and the exact checked-out source-tree HEAD."
    requirement: TOOL-02
    verification:
      - kind: unit
        ref: "tests/test_phase2_provenance.py#test_fixture_identity_is_bound_to_external_release_and_commit"
        status: pass
      - kind: unit
        ref: "tests/test_phase2_provenance.py#test_source_tree_head_must_equal_external_commit"
        status: pass
    human_judgment: false
  - id: D2
    description: "Newer evidence rejects missing manifests/inventory/bytes, stale hashes/anchors, and release or commit identity mismatches."
    requirement: TERM-05
    verification:
      - kind: unit
        ref: "tests/test_phase2_provenance.py#test_newer_release_rejects_unvalidated_or_different_evidence"
        status: pass
    human_judgment: false
  - id: D3
    description: "Canonical and newer public lifecycle behavior is compared from validated immutable bytes rather than self-attested declaration maps."
    requirement: TERM-04
    verification:
      - kind: unit
        ref: "tests/test_phase2_provenance.py#test_complete_newer_release_uses_bytes_not_declaration_maps"
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

# Phase 2 Plan 5: Release-Bound Provenance Integrity Summary

**External tag identity now authenticates every manifest, source tree, fixture entry, anchor, and byte-derived lifecycle event before canonical/newer compatibility can pass.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-16T21:53:29Z
- **Completed:** 2026-07-16T22:04:57Z
- **Tasks:** 1 TDD feature
- **Files modified:** 2

## Accomplishments

- Bound every manifest and fixture entry to independently expected release/commit values and verified the supplied Git source tree is at that exact HEAD before accepting anchors.
- Replaced newer-tag self-attestation with complete manifest, required inventory, immutable-byte hash, source-anchor, and checked-out-commit validation with guaranteed temporary-tree cleanup.
- Derived deterministic tool and terminal lifecycle sequences from validated SSE/design bytes, including explicit contradiction rejection, and ignored editor-controlled declaration-map equality when making the compatibility decision.
- Added isolated, network-free adversarial tests using real temporary Git repositories for every reproduced review/verifier failure and one complete positive newer-release case.

## Task Commits

The TDD feature was committed through its required gates:

1. **RED: Expose provenance trust defects** - `ef0e681` (test)
2. **GREEN: Bind provenance to validated evidence** - `bc65601` (feat)

No separate refactor commit was needed; the GREEN implementation is factored into identity, manifest, normalization, and comparison helpers and passes every quality gate.

## Files Created/Modified

- `tests/test_phase2_provenance.py` - Isolated release builders, real Git source trees, identity/HEAD regressions, adversarial newer-evidence matrix, cleanup probes, and positive byte-derived equivalence proof.
- `scripts/check_phase2_provenance.py` - External identity binding, release-agnostic manifest verification, byte-derived lifecycle normalization, and validated newer-release comparison.

## Decisions Made

- Kept the latest-evidence declaration and structured difference summary as required audit metadata, but removed declaration-map equality from the pass condition.
- Required the same five lifecycle evidence roles for canonical/newer comparison and normalized tool facts, accepted terminals, explicit contradiction rejection, and design-derived rows in deterministic order.
- Kept canonical-current CLI scope behavior and the exact `latest-tag-verification-blocked` result; dependency and fixture contents remain unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Tracking Bug] Corrected stale current-plan and progress prose after GSD state handlers**

- **Found during:** Plan metadata update
- **Issue:** `state.advance-plan` advanced the reset execution position from Plan 1 to Plan 2 even though five summaries exist, and `state.update-progress` reported 100% without updating the prose progress bar.
- **Fix:** Set the current position to Plan 5 of 5, retained executing status pending phase verification, and synchronized the prose activity/progress values to the completed gap plan.
- **Files modified:** `.planning/STATE.md`
- **Verification:** STATE now records Plan 5 of 5 and a 100% plan progress bar while preserving the five-summary and phase-verification workflow.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 1 auto-fixed tracking bug.
**Impact on plan:** Planning metadata only; production, test, fixture, and dependency scope are unchanged.

## Issues Encountered

- The RED commit intentionally skipped only the full coverage-test hook because the committed suite had to remain failing before implementation; lock, Ruff, basedpyright, verifytypes, build, and distribution hooks passed. The GREEN commit ran and passed every installed hook normally.
- The repository's existing case-insensitive `/Scripts/` ignore rule reported the tracked lowercase verifier during staging; Git still staged the tracked modification, and the feature commit contains both planned files only.

## TDD Gate Compliance

- RED commit `ef0e681` precedes GREEN commit `bc65601`.
- RED produced 13 intended trust-boundary failures and one control pass against the prior verifier.
- GREEN passes all 14 focused adversarial cases.
- No behavior-preserving refactor commit was necessary.

## Verification Results

- `uv run --no-sync pytest tests/test_phase2_provenance.py --no-cov -q` - 14 passed.
- `uv run --no-sync python scripts/check_phase2_provenance.py --scope release-and-tool` - passed against the live official tag gate.
- `uv run --no-sync python scripts/check_phase2_provenance.py --scope terminal` - passed against the live official tag gate.
- `uv run --no-sync pytest -q` - 564 passed with 100% statement and branch coverage.
- `uv run --no-sync ruff format --check .` and `uv run --no-sync ruff check .` - passed.
- `uv run --no-sync basedpyright` and `--verifytypes` - passed with 100% type completeness.
- `uv run --no-sync python -m compileall -q src scripts tests` - passed.
- The GREEN commit hook also passed lock validation, distribution build, and standalone distribution verification.
- `git diff 01a88e9..HEAD -- pyproject.toml uv.lock tests/fixtures src` - empty.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both blocking Phase 2 review/verifier findings now have permanent adversarial regressions and byte-derived positive evidence.
- Phase-level code review and re-verification can independently confirm the gap closure.
- Phase 4 retains the existing obligation to re-check and refresh latest compatible dependencies.

## Self-Check: PASSED

- Both planned implementation/test files exist and no fixture, source package, dependency declaration, or lockfile changed.
- RED commit `ef0e681` and GREEN commit `bc65601` exist in the required order.
- Both live provenance scopes, the 564-test 100%-coverage suite, Ruff, basedpyright, verifytypes, compile/build, and distribution verification pass.
- No TODO, FIXME, placeholder, known stub, untracked generated artifact, or undeclared threat surface remains.

---
*Phase: 02-conversation-event-contract*
*Completed: 2026-07-17*
