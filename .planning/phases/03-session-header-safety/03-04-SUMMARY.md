---
phase: 03-session-header-safety
plan: 04
subsystem: testing
tags: [traceability, mutation-check, session-headers, httpx, pytest, evidence]

requires:
  - phase: PR #7 (8843cfc, v0.3.1)
    provides: shipped session header behaviour and the PR #7 session tests that the record credits
  - phase: 03-01
    provides: HTTP-02 early-close and mid-iteration cancellation tests (G4b expected inclusions)
  - phase: 03-02
    provides: SESS-01 to SESS-03 rejection matrix, exact-header and boundary tests (G1, G2, G3 expected inclusions)
  - phase: 03-03
    provides: completion, early-close and post-dispatch failure secrecy tests (S1 expected inclusions, Q1 evidence)
provides:
  - "03-TRACEABILITY.md: plan-authored D-10/D-11 evidence record (D-10 table, SC1-SC5 table, D-08 matrix, D-09, D-11 results, D-07 upstream record, user decisions, known boundaries, provenance)"
  - "D-11 manual mutation check on the working tree: G1 37, G2 7, G3 17, G3b 1, G4 45, G4b 32, S1 49 failures, all expected inclusions present, every restore clean"
  - "User D-02 decisions recorded: q1-accept-na, q2-document-boundary"
affects: [03 verification, phase 4 VERI-02]

actuals:
  tokens: 16455
  tasks: 3
  commits: 2
plan_head_before: 231af246b66cd0d472417b59a67384d792dd8723
plan_head_after: 8f7d05a60096a84ed92792898361f55fc5b03923

tech-stack:
  added: []
  patterns:
    - "Mutation harness: assert the anchor occurs once, edit, purge src/**/__pycache__, run the two modules with -rf, git checkout, purge again, git diff --exit-code -- src/"
    - "Evidence record kept outside 03-VERIFICATION.md so an initial-mode verifier pass cannot overwrite it"

key-files:
  created:
    - .planning/phases/03-session-header-safety/03-TRACEABILITY.md
  modified: []

key-decisions:
  - "Q1 = q1-accept-na: the four exception-less D-08 cells read 'N/A: no exception escapes', backed by test_completed_and_closed_streams_retain_no_session_values[completion] and [early-close-after-event]"
  - "Q2 = q2-document-boundary: pre-iteration retention stays released v0.3.x behaviour and is a documented known boundary, not a SESS-05 gap; src/ unchanged"
  - "Criteria with no D-11 guard (signature lock, request-mapping copy, D-06 absence of a key path check) cite their supplementary Plan 03-02 RED proof or say plainly which assertion the D-11 mutation hits, rather than overstating coverage"

patterns-established:
  - "Generate the D-11 FAILED lists from captured pytest output, and check every cited node ID (including [case] suffixes) against --collect-only before committing"

requirements-completed: [SESS-01, SESS-02, SESS-03, SESS-04, SESS-05, HTTP-02]

coverage:
  - id: D1
    description: "D-11 mutation check: all seven guards mutated on the working tree, each turning named tests red with every expected inclusion present, each restored with src/ clean"
    verification:
      - kind: other
        ref: "uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q -rf under G1, G2, G3, G3b, G4, G4b, S1 (03-TRACEABILITY.md ## D-11 Mutation Check)"
        status: pass
      - kind: other
        ref: "git diff --exit-code -- src/ && test -z \"$(git log --oneline main..HEAD -- src/)\""
        status: pass
    human_judgment: false
  - id: D2
    description: "D-10 traceability for SESS-01 to SESS-05, HTTP-02 and SC1 to SC5; every cited node ID (42 functions, 80 [case] IDs) resolves in --collect-only"
    verification:
      - kind: other
        ref: "Task 3 verify commands: TRACE-ROWS-OK and CITED-TESTS-OK"
        status: pass
    human_judgment: false
  - id: D3
    description: "Provenance honesty and the wording of boundaries, D-07 record and edge-probe dispositions"
    verification: []
    human_judgment: true
    rationale: "The plan marks provenance honesty as a judgement prohibition, and the three unclassified edge-probe rows (SESS-01, SESS-05, HTTP-02) and the SESS-04 adjacency backstop truth need a reviewer"

duration: 8min
completed: 2026-10-20
status: complete
---

# Phase 3 Plan 04: D-11 mutation check and Phase 3 traceability record Summary

**`03-TRACEABILITY.md` records a working-tree D-11 mutation check in which all seven guards (G1, G2, G3, G3b, G4, G4b, S1) turned named tests red (37, 7, 17, 1, 45, 32 and 49 failures) and every restore left `src/` clean. It also holds a D-10 table mapping SESS-01 to SESS-05, HTTP-02 and SC1 to SC5 to 42 collected test functions, the D-08 matrix with the user's `q1-accept-na` wording, the `q2-document-boundary` known boundary and the PR #7 provenance. `## Gaps` reads None (`open_gaps: 0`).**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-20T07:37:19Z
- **Completed:** 2026-10-20T07:45:11Z
- **Tasks:** 3 (Task 1 decided by the user through the orchestrator; Tasks 2 and 3 executed here)
- **Files modified:** 1

## User Decisions (Task 1, D-02)

- **Q1: `q1-accept-na`.** The four exception-less D-08 cells read "N/A: no exception escapes".
- **Q2: `q2-document-boundary`.** Pre-iteration retention is a documented known boundary. No `src/` change.

The orchestrator presented both questions to the user verbatim, and these ids are the user's own answers. They are recorded word for word in `03-TRACEABILITY.md` under `## User Decisions (D-02)`.

## D-11 Mutation Results

Run one at a time on the working tree. Command: `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q -rf`. Clean baseline: 198 passed.

| ID | Location | Mutation | Failures | Expected inclusions | Restored |
|----|----------|----------|----------|---------------------|----------|
| G1 | `client.py:158` | `_require_lifecycle_text(value)` → `str(value)` | 37 | yes (CR, tab and bytes cases; all 24 invalid-argument cases) | yes |
| G2 | `client.py:185` | `reject_path_shape=True` → `False` | 7 | yes (`[parent]`, `[session-id-embedded-parent]`) | yes |
| G3 | `client.py:193` | `dict(headers)` → `headers` | 17 | yes; `[neither]` stayed green | yes |
| G3b | `client.py:435` | `dict(headers)` → `headers` | 1 | yes (`test_stream_success_closes_response_and_refuses_redirects`) | yes |
| G4 | `client.py:601` | drop the `_injected_http_client is None` check | 45 | yes | yes |
| G4b | `client.py:708` | insert `await active.aclose()` | 32 | yes (both Plan 03-01 tests) | yes |
| S1 | `client.py:674-675` | delete the session scrub | 49 | yes (all five post-dispatch cases, request-stage identity) | yes |

The full FAILED node-ID lists are in `03-TRACEABILITY.md`.

## Accomplishments

- Ran the D-11 mutation check on the real working tree. The harness asserted that each anchor occurred exactly once, purged the bytecode cache around every edit and restore (the Plan 03-02 lesson), and confirmed that `git diff --exit-code -- src/` exited 0 after each restore.
- Wrote `03-TRACEABILITY.md` with the 14 sections the plan specifies: 29 D-10 criterion rows, 5 SC rows, the D-08 matrix (6 rows × 4 columns, with 4 N/A cells), the D-09 table, the D-07 upstream record, dispositions, spot-checks and requirements coverage.
- Provenance: `git log --oneline main..HEAD -- src/` is empty. `client.py` and both session test modules were unchanged from `8843cfc` to `main`.
- Did not create `03-VERIFICATION.md`. `gsd-verifier` writes it after this plan.

## Task Commits

1. **Task 1: Decide the two D-02 evidence questions**: no commit (the user decided; the ids are recorded in the Task 3 commit and in this SUMMARY)
2. **Task 2: Run the D-11 manual mutation check and record it**: `db1f09c` (docs)
3. **Task 3: Write the D-10 table, D-08 matrix, decisions and boundaries**: `8f7d05a` (docs)

## Files Created/Modified

- `.planning/phases/03-session-header-safety/03-TRACEABILITY.md`: the plan-authored D-10/D-11 evidence record. Phase 4 VERI-02 starts from its `## D-10 Traceability` table.

## Verification

- Task 2: `git diff --exit-code -- src/` plus an empty `main..HEAD -- src/` log; `MUTATION-ROWS-OK`; `VERIFIER-FILE-UNTOUCHED`; two-module run `198 passed`.
- Task 3: `TRACE-ROWS-OK`; `CITED-TESTS-OK` (42 distinct functions). A stricter check found that all 80 cited `[case]` node IDs match `--collect-only` exactly.
- `uv run pytest`: `674 passed`, 100.00% coverage. `ruff check`, `ruff format --check`, `basedpyright` (0 errors), `--verifytypes` (100%) and `uv run --no-sync prek run --all-files` all pass. Both commits passed the pre-commit hooks.

## Decisions Made

- Some criteria have no D-11 guard: the signature lock, the request-mapping copy, the absence of a `session_key` path check under D-06, and the completion `ag_frame` cell. For these the record names the supplementary Plan 03-0x RED proof, or says which assertion the D-11 mutation actually hits. The record does not claim a guard-specific red it did not observe.
- Under G3, `test_injected_client_survives_public_stream_early_close` failed at its later-stream assertion (`'X-Hermes-Session-Id' not in ...headers`, `tests/test_client_lifecycle.py:923`). The record cites this as direct evidence for the SESS-04 "no leak into a later stream" row.

## Deviations from Plan

None. The plan was executed exactly as written. Mutation hygiene went beyond the plan: an anchor-uniqueness assertion, the bytecode purge, `-p no:cacheprovider` and a case-suffix node-ID check.

**Total deviations:** 0.

## Issues Encountered

None.

## Known Stubs

None.

## TDD Gate Compliance

This is a `type: execute` plan whose two auto tasks are documentation-only. No task carries `tdd="true"`, and the MVP+TDD gate does not apply because no task's `<files>` lists a source file. No `test` or `feat` commit is expected. The shipped `src/` is unchanged.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Phase 3 plans are complete. Next: phase verification (`gsd-verifier` writes `03-VERIFICATION.md` and lists `03-TRACEABILITY.md` under Required Artifacts), then `/gsd-ship` per D-04. These test- and docs-only commits cut no release.
- These items are left for a reviewer, and none is a phase gap: the three unclassified edge-probe rows (SESS-01, SESS-05, HTTP-02), and the SESS-04 adjacency backstop truth, which the verifier confirms from `client.py:193` or records as `human_needed`.
- For the user's awareness, outside this phase's scope: upstream Hermes `hermes_state.py:5090` builds a raw `Path.glob` pattern from the session ID. You may wish to report it upstream.

## Self-Check: PASSED

- FOUND: .planning/phases/03-session-header-safety/03-TRACEABILITY.md (`open_gaps: 0`, `## Gaps` reads None)
- FOUND: db1f09c and 8f7d05a (ancestors of HEAD; `git rev-list --count 231af24..HEAD` = 2 before this SUMMARY)
- NOT PRESENT (as required): .planning/phases/03-session-header-safety/03-VERIFICATION.md

---
*Phase: 03-session-header-safety*
*Completed: 2026-10-20*
