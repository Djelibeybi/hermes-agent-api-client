---
phase: 02-conversation-event-contract
plan: 06
subsystem: testing
tags: [provenance, duplicate-json, malformed-json, totality, cleanup, evidence-roles, diagnostics, sse, tdd]

requires:
  - phase: 02-conversation-event-contract
    provides: release-bound immutable lifecycle evidence and production pair-aware event projection from Plans 02-03 through 02-05
provides:
  - production-faithful pair-preserving lifecycle normalization for provenance compatibility
  - exact release-agnostic evidence-role enforcement for every required lifecycle fixture
  - closed context-free provenance errors for recursive, oversized-integer, malformed-container, and invalid-path inputs
  - public SSE classification of JSON decoder ValueError as a non-retryable protocol failure
  - exception-total numeric, subprocess, recursive metadata, and temporary-tree verifier boundaries
affects: [phase-2-verification, phase-4-contract-verification]

tech-stack:
  added: []
  patterns:
    - internal provenance verification reuses production approved-path JSON projectors
    - lower-level failures are classified outside active exception handlers before closed errors are raised
    - editor-controlled values are exact-type validated before hash/set operations or filesystem resolution
    - temporary-tree cleanup preserves an already-selected validation failure and runs on every exit path

key-files:
  created: []
  modified:
    - scripts/check_phase2_provenance.py
    - src/hermes_agent_api_client/sse.py
    - tests/test_phase2_provenance.py
    - tests/test_sse.py
    - tests/test_transport.py

key-decisions:
  - "Lifecycle compatibility uses the production pair hook plus tool/chat projectors, so approved duplicates reject while ignored additive duplicates remain compatible."
  - "Every required lifecycle path must match its exact _EXPECTED_KINDS role before any fixture bytes are normalized."
  - "Provenance failures expose one finite constant code and translate lower-level exceptions only after leaving the active handler."
  - "RecursionError is classified at both JSON entry points as the existing boundary-specific closed parse code."
  - "Plain JSON decoder ValueError is malformed protocol/provenance input, never a retryable transport failure or raw verifier exception."
  - "Design-matrix citations and finish reasons must be exact built-in strings before membership or lookup operations."
  - "Invalid fixture paths, including NUL-bearing strings and resolve failures, map to invalid-fixture-path."
  - "Regex-valid decimal components are guarded before int conversion and map to their existing tag or source-line code."
  - "Metadata null detection uses an iterative exact built-in dict/list walk rather than recursive Python frames."
  - "Temporary creation and cleanup failures map to latest-tag-verification-blocked, but cleanup never replaces a selected validation code."

patterns-established:
  - "Pair-aware evidence normalization: project event-specific approved facts before computing compatibility tuples."
  - "Closed diagnostics: never interpolate editor-controlled fixture, source, range, or case values into provenance errors."
  - "Total parser boundaries: catch decoder-wide ValueError plus RecursionError, then classify outside the active handler."
  - "Validate-before-hash: reject non-string JSON members before set construction or dictionary lookup."
  - "Exception-total scalar conversion: guard every external decimal conversion outside its active handler."
  - "Selected-error cleanup: capture the first failure without traceback state, clean once, then raise the original before considering cleanup failure."

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
    description: "Fixture, source, range, tag, terminal-case, recursive/oversized JSON, deep matrix, Git decoding, invalid-path, and temporary-tree failures remain closed across exceptions, traceback state, and CLI stderr."
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
      - kind: unit
        ref: "tests/test_phase2_provenance.py#recursive JSON direct and CLI boundary tests"
        status: pass
      - kind: unit
        ref: "tests/test_phase2_provenance.py#oversized JSON, malformed matrix, and NUL path direct and CLI tests"
        status: pass
      - kind: integration
        ref: "tests/test_sse.py and tests/test_transport.py#oversized integer protocol taxonomy and cleanup"
        status: pass
      - kind: unit
        ref: "tests/test_phase2_provenance.py#numeric conversion, deep metadata, Git decoding, and temporary lifecycle direct and CLI tests"
        status: pass
    human_judgment: false

duration: 89min
completed: 2026-07-17
status: complete
---

# Phase 2 Plan 6: Provenance Trust-Boundary Closure Summary

**Newer-release provenance now shares production duplicate semantics, authenticates exact evidence roles, and emits only closed context-free diagnostics.**

## Performance

- **Duration:** 89 min
- **Started:** 2026-07-17T00:32:49Z
- **Completed:** 2026-07-17T02:01:30Z
- **Tasks:** 1 TDD feature
- **Files modified:** 5

## Accomplishments

- Reused the production pair-preserving JSON hook and event-specific tool/chat projectors so all same-value and conflicting approved duplicates reject without globally rejecting ignored additive data.
- Enforced the exact `_EXPECTED_KINDS` mapping for all five lifecycle paths in the release-agnostic canonical/newer normalization path.
- Replaced value-bearing verifier failures with finite constant codes and translated JSON, Unicode, filesystem, and Git failures without retained cause or context.
- Classified Python's oversized-integer JSON `ValueError` as malformed protocol data in both direct and HTTP client streaming paths, preserving cleanup and non-retryable taxonomy.
- Made remaining scalar conversion, recursive metadata, subprocess decoding, and temporary lifecycle operations exception-total without changing public package source.
- Added 73 network-free adversarial provenance cases over complete temporary release roots and real temporary Git source trees, plus direct/streaming public SSE regressions.

## Task Commits

1. **RED: Expose provenance boundary gaps** - `21d45e9` (test)
2. **GREEN: Close provenance trust boundaries** - `313e7f9` (feat)
3. **Post-review RED: Cover recursive provenance JSON failures** - `b9378c7` (test)
4. **Post-review GREEN: Close recursive JSON error boundary** - `33ef55d` (fix)
5. **Post-review RED: Expose malformed JSON boundary escapes** - `487e7e2` (test)
6. **Post-review GREEN: Close malformed JSON input boundaries** - `ddfff89` (fix)
7. **Post-review RED: Expose remaining provenance exception escapes** - `a0aa8af` (test)
8. **Post-review GREEN: Make provenance validation exception-total** - `e58dd53` (fix)

No separate refactor commit was needed; the GREEN implementation already centralizes fixture reading, pair decoding, event-specific projection, and closed translation.

## Files Created/Modified

- `scripts/check_phase2_provenance.py` - Production-faithful lifecycle projection, exact evidence roles, and closed diagnostics.
- `src/hermes_agent_api_client/sse.py` - Decoder-wide malformed JSON classification as protocol failure.
- `tests/test_phase2_provenance.py` - Duplicate-family, additive-control, evidence-role, malformed-input, exception-state, traceback, and CLI regressions.
- `tests/test_sse.py` - Direct oversized-integer protocol taxonomy and cleanup regression.
- `tests/test_transport.py` - HTTP streaming oversized-integer taxonomy, secrecy, and response cleanup regression.

## Decisions Made

- Reused intentional package-private production projectors with narrow static-analysis suppressions instead of copying approved member lists into the verifier.
- Consumed only sanitized approved Hermes terminal metadata during normalization; additive raw fields remain outside compatibility state.
- Preserved `latest-tag-verification-blocked` as the sole exit-3 diagnostic; every other provenance failure remains exit 1.
- Reused existing finite matrix codes for malformed reference and finish-reason values rather than expanding diagnostic vocabulary.
- Used `invalid-fixture-path` for invalid path scalars/resolution failures while preserving `fixture-path-escape` for successfully resolved escapes.
- Preserved `invalid-numeric-release-tag` and `invalid-source-line-anchor` for integer-limit decimal conversions.
- Used iterative exact built-in container traversal so subclasses cannot expand the accepted matrix metadata surface.
- Preserved the first selected failure across cleanup; cleanup-only failure remains the existing exit-3 blocked code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug / Rule 2 - Missing Critical] Closed recursive JSON decoder failures discovered by deep post-execution review**

- **Found during:** Deep post-execution code review CR-01
- **Issue:** Valid deeply nested lifecycle or object-file JSON raised raw `RecursionError`; `main()` propagated a traceback instead of the closed provenance code promised by the plan.
- **Fix:** Added direct and real-CLI RED regressions for both JSON entry points, then translated `RecursionError` through the existing outside-active-handler classification pattern.
- **Files modified:** `scripts/check_phase2_provenance.py`, `tests/test_phase2_provenance.py`
- **Verification:** 51 focused tests, both live scopes, and the 601-test 100%-coverage suite pass; recursive CLI failures emit exactly one closed line.
- **Committed in:** `b9378c7` (RED), `33ef55d` (GREEN)

**2. [Rule 1 - Bug] Classified oversized JSON integers as protocol failures**

- **Found during:** Deep post-execution code review CR-01
- **Issue:** Python raises plain `ValueError` for a valid 5,000-digit JSON integer; the public SSE decoder translated it to retryable `HermesTransportError`.
- **Fix:** Caught decoder-wide `ValueError` in `_load_json_safely` and added direct plus HTTP streaming regressions for exact `HermesProtocolError`, closed exception state, and response/source cleanup.
- **Files modified:** `src/hermes_agent_api_client/sse.py`, `tests/test_sse.py`, `tests/test_transport.py`
- **Verification:** Both new public regressions and the complete 373-test affected-file suite pass.
- **Committed in:** `487e7e2` (RED), `ddfff89` (GREEN)

**3. [Rule 1 - Bug / Rule 2 - Missing Critical] Closed plain ValueError at both provenance JSON boundaries**

- **Found during:** Deep post-execution code review CR-02
- **Issue:** Oversized integers escaped `_json_pairs`, `_load_object`, and real CLI lifecycle/provenance/design-matrix paths as raw multiline tracebacks.
- **Fix:** Classified `ValueError` outside active handlers as `invalid-sse-json` or `invalid-provenance-json` and covered all three evidence inputs directly and through `main()`.
- **Files modified:** `scripts/check_phase2_provenance.py`, `tests/test_phase2_provenance.py`
- **Verification:** Exact one-line stderr, no traceback/canary, and no cause/context pass for every boundary.
- **Committed in:** `487e7e2` (RED), `ddfff89` (GREEN)

**4. [Rule 1 - Bug / Rule 2 - Missing Critical] Validated design-matrix values before hashing**

- **Found during:** Deep post-execution code review CR-03
- **Issue:** List/dict values at root citations, case citations, or `finish_reason` reached set/lookup operations and raised raw `TypeError`.
- **Fix:** Required lists of exact built-in strings before set operations and an exact built-in string before finish-reason lookup, preserving the existing finite codes.
- **Files modified:** `scripts/check_phase2_provenance.py`, `tests/test_phase2_provenance.py`
- **Verification:** Six list/dict variants pass both direct and real-CLI closed-code assertions.
- **Committed in:** `487e7e2` (RED), `ddfff89` (GREEN)

**5. [Rule 1 - Bug / Rule 2 - Missing Critical] Closed invalid fixture-path resolution**

- **Found during:** Deep post-execution code review CR-04
- **Issue:** A valid JSON string containing NUL reached `Path.resolve()` and escaped as raw `ValueError` with an editor-controlled path.
- **Fix:** Rejected NUL before resolution and translated `OSError`, `RuntimeError`, and `ValueError` from resolution outside the active handler to `invalid-fixture-path`.
- **Files modified:** `scripts/check_phase2_provenance.py`, `tests/test_phase2_provenance.py`
- **Verification:** Manifest-level direct and real-CLI tests prove exact code, single-line stderr, and no canary/cause/context.
- **Committed in:** `487e7e2` (RED), `ddfff89` (GREEN)

**6. [Rule 1 - Bug / Rule 2 - Missing Critical] Closed integer-limit tag and source-range conversion**

- **Found during:** Final deep post-execution review CR-01
- **Issue:** Regex-valid 5,000-digit release components and legacy line anchors raised raw integer-conversion `ValueError`.
- **Fix:** Guarded every external decimal conversion, cleared value-bearing conversion state, and mapped failures to `invalid-numeric-release-tag` or `invalid-source-line-anchor` after leaving the handler.
- **Files modified:** `scripts/check_phase2_provenance.py`, `tests/test_phase2_provenance.py`
- **Verification:** Direct and real-CLI oversized tag/range tests emit exact one-line codes with no canary, cause, context, or traceback.
- **Committed in:** `a0aa8af` (RED), `e58dd53` (GREEN)

**7. [Rule 1 - Bug / Rule 2 - Missing Critical] Removed recursive matrix metadata traversal**

- **Found during:** Final deep post-execution review CR-02
- **Issue:** Parser-valid 500-level matrix metadata raised raw `RecursionError` in recursive null detection.
- **Fix:** Replaced recursion with an iterative walk over exact built-in dictionaries/lists while preserving null detection semantics.
- **Files modified:** `scripts/check_phase2_provenance.py`, `tests/test_phase2_provenance.py`
- **Verification:** Deep metadata with and without null reaches its intended finite matrix result through direct and real-CLI paths.
- **Committed in:** `a0aa8af` (RED), `e58dd53` (GREEN)

**8. [Rule 1 - Bug / Rule 2 - Missing Critical] Closed Git output decoding failures**

- **Found during:** Final deep post-execution review CR-03
- **Issue:** `UnicodeDecodeError` from text-mode subprocess output escaped `_run_git` with retained bytes.
- **Fix:** Classified `UnicodeError` with `OSError` outside the active subprocess handler as `latest-tag-verification-blocked`.
- **Files modified:** `scripts/check_phase2_provenance.py`, `tests/test_phase2_provenance.py`
- **Verification:** Direct and executable tests prove one closed arg, no payload/cause/context, exact stderr, and exit 3.
- **Committed in:** `a0aa8af` (RED), `e58dd53` (GREEN)

**9. [Rule 1 - Bug / Rule 2 - Missing Critical] Made temporary-tree ownership exception-total**

- **Found during:** Final deep post-execution review CR-04
- **Issue:** Temporary creation/cleanup `OSError` escaped raw, cleanup could overwrite validation, and fetch initialization did not explicitly clean on failure.
- **Fix:** Added closed creation/cleanup/finalization helpers, cleaned failed fetch initialization, applied them to all three owners, and preserved any already-selected failure ahead of cleanup failure.
- **Files modified:** `scripts/check_phase2_provenance.py`, `tests/test_phase2_provenance.py`
- **Verification:** Creation, initialization, cleanup-only, and validation-plus-cleanup direct/CLI cases pass with correct precedence and exit taxonomy.
- **Committed in:** `a0aa8af` (RED), `e58dd53` (GREEN)

---

**Total deviations:** 9 auto-fixed review-discovered correctness/security boundary issues (Rule 1 / Rule 2).
**Impact on plan:** The fixes complete the already-promised malformed-input, lifecycle-cleanup, and closed-diagnostic boundary without expanding public API exports, fixtures, dependencies, lock state, or distribution scope. The only public source change remains the earlier authorized SSE parser classification fix.

## Issues Encountered

- The repository's case-insensitive `/Scripts/` ignore rule returned a non-zero staging status for the tracked lowercase verifier; Git had staged the tracked modification correctly, and the normal commit then passed every hook.
- The plan's abbreviated verifytypes command reports third-party incompleteness without the repository's established `--ignoreexternal` flag. The installed project gate with `--ignoreexternal` passed at 100% type completeness.

## TDD Gate Compliance

- RED commit `21d45e9` precedes GREEN commit `313e7f9`.
- Post-review RED commit `b9378c7` precedes post-review GREEN fix `33ef55d`.
- Malformed-input RED commit `487e7e2` precedes GREEN fix `ddfff89`.
- Totality RED commit `a0aa8af` precedes GREEN fix `e58dd53`.
- RED failed on approved duplicate acceptance, evidence-role forgery, and value-bearing/context-retaining diagnostics while the additive duplicate control passed.
- The first continuation RED proved raw direct and CLI `RecursionError` failures.
- The second continuation RED proved 15 wrong-taxonomy or raw `ValueError`/`TypeError` failures; GREEN passes all 64 provenance tests and all 373 tests in the affected files. No behavior-preserving refactor commit was necessary.
- The final continuation RED proved 19 raw conversion/recursion/decoding/temporary exceptions or cleanup-precedence failures; GREEN passes all 83 provenance tests. No separate refactor commit was necessary.

## Verification Results

- Focused provenance matrix - 83 passed.
- Complete affected-file suite (`test_sse.py`, `test_transport.py`, `test_phase2_provenance.py`) - 373 passed.
- Live `release-and-tool` and `terminal` provenance scopes - passed against the official tag gate.
- `uv run --no-sync pytest -q` - 635 passed with 100% statement and branch coverage.
- Ruff format/check and full basedpyright - passed.
- `basedpyright --verifytypes hermes_agent_api_client --ignoreexternal` - 100% type completeness.
- Fresh wheel/sdist build in an isolated temporary output directory and `scripts/verify_dist.py` - passed.
- Public API exports, immutable fixtures, `pyproject.toml`, and `uv.lock` - unchanged; `sse.py` changed only to close the authorized parser taxonomy defect.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All Phase 2 verifier/review exception-totality gaps now have permanent adversarial regressions and production-faithful fixes.
- Phase 2 is ready for re-verification and milestone progression into Phase 3.
- Phase 4 retains dependency currency and installed-distribution closure ownership.

## Self-Check: PASSED

- All five modified implementation/test files exist and contain no stub markers.
- Original RED/GREEN `21d45e9` → `313e7f9`, recursion continuation `b9378c7` → `33ef55d`, malformed-input continuation `487e7e2` → `ddfff89`, and totality continuation `a0aa8af` → `e58dd53` exist in the required order.
- Focused, live, full-coverage, lint, typing, build, and distribution gates pass.
- No public API export, fixture, dependency declaration, lockfile, new endpoint, or new external trust surface changed.

---
*Phase: 02-conversation-event-contract*
*Completed: 2026-07-17*
