---
phase: 02-conversation-event-contract
plan: 02
subsystem: testing
tags: [provenance, fixtures, sse, git, sha256]

requires:
  - phase: 02-conversation-event-contract
    provides: strict correlated public tool events and safe terminal vocabulary from Plan 02-01
provides:
  - live canonical/latest Hermes numeric-tag verification with a distinct blocked disposition
  - detached-commit source-anchor and immutable fixture hash verification
  - correlated tool lifecycle and terminal evidence with truthful per-path origins
  - design-derived terminal omission, unknown-code, and explicit-null decision rows
affects: [02-03-duplicate-aware-tool-decoding, 02-04-terminal-mapping, phase-4-verification]

tech-stack:
  added: []
  patterns:
    - live tag identity followed by detached immutable source-anchor verification
    - per-fixture evidence kind, reproduction, semantic assertions, and SHA-256

key-files:
  created:
    - scripts/check_phase2_provenance.py
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/tool_progress_pair.sse
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_length.sse
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_agent_error.sse
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_task_exception_contradiction.sse
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_design_matrix.json
  modified:
    - tests/fixtures/hermes/v2026.7.7.2/provenance.json

key-decisions:
  - "Observed latest numeric Hermes tag v2026.7.7.2 remains the canonical tag, so D-16 records canonical-current and creates no alternate fixture root."
  - "Structured source references include detached-tree path, exact line range, commit-pinned URL, and SHA-256 of the anchored source lines."
  - "Historical evidence_scope.live_server_tested remains unchanged while new evidence uses reproduction.configuration.live_server_invoked as the authoritative field until Phase 4 normalization."

patterns-established:
  - "Evidence gate: live tag enumeration must succeed before pinned fixture evidence can pass."
  - "Origin honesty: tag-source-derived and design-derived bytes remain distinct and neither is described as a live capture."

requirements-completed: [TOOL-02, TOOL-03, TOOL-04, TERM-02, TERM-03, TERM-04, TERM-05, TERM-06]

coverage:
  - id: D1
    description: "The canonical annotated tag and latest numeric Hermes release are live-verified before evidence is accepted."
    verification:
      - kind: integration
        ref: "uv run --no-sync python scripts/check_phase2_provenance.py --scope release-and-tool"
        status: pass
    human_judgment: false
  - id: D2
    description: "Ordered running and completed tool records retain one correlated ID and hash-linked tagged-source provenance."
    requirement: TOOL-02
    verification:
      - kind: integration
        ref: "scripts/check_phase2_provenance.py --scope release-and-tool#tool fixture sequence and detached source anchors"
        status: pass
    human_judgment: false
  - id: D3
    description: "Length, agent-error, and tagged contradiction fixtures retain exact lifecycle facts without laundering raw errors into public evidence."
    requirement: TERM-03
    verification:
      - kind: integration
        ref: "uv run --no-sync python scripts/check_phase2_provenance.py --scope terminal"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every terminal design row carries applicable D-01 through D-04 citations and exact accept/reject semantics."
    requirement: TERM-05
    verification:
      - kind: integration
        ref: "scripts/check_phase2_provenance.py --scope terminal#terminal design matrix"
        status: pass
    human_judgment: false
  - id: D5
    description: "All declared evidence paths have exact hashes, source identities, reproduction procedures, semantic assertions, and live_server_invoked false."
    requirement: TERM-06
    verification:
      - kind: integration
        ref: "scripts/check_phase2_provenance.py#all manifest entries"
        status: pass
      - kind: unit
        ref: "uv run --no-sync pytest -q (410 passed, 100% branch coverage)"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-07-17
status: complete
---

# Phase 2 Plan 2: Immutable Conversation Evidence Summary

**Live release identity, detached source anchors, and exact SHA-256 checks now guard a truthfully classified tool and terminal evidence corpus before production mapping consumes it.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-16T20:11:45Z
- **Completed:** 2026-07-16T20:29:15Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added one committed verifier with `release-and-tool` and `terminal` scopes that live-enumerates numeric tags, proves the annotated canonical peel, fetches the exact detached tree, and checks source-anchor and fixture hashes.
- Froze an ordered running/completed tool pair plus valid length, valid agent-error, and tagged task-exception contradiction SSE evidence under the canonical version root.
- Added a design-derived matrix whose omission, bounded unknown-code, and explicit-null rows carry machine-checked per-row D-01 through D-04 citations.
- Preserved honest provenance: every new entry records `live_server_invoked: false`, and source-derived/design-derived bytes are never called live captures.

## Release and Compatibility Disposition

- **Canonical tag:** `v2026.7.7.2`
- **Canonical annotated tag object:** `b7751df34688835a108e0d630f3495fc11f3df79`
- **Canonical peeled commit:** `9de9c25f620ff7f1ce0fd5457d596052d5159596`
- **Observed latest numeric tag:** `v2026.7.7.2`
- **Observed latest peeled commit:** `9de9c25f620ff7f1ce0fd5457d596052d5159596`
- **Compatibility disposition:** `canonical-current`
- **D-16 conditional evidence paths:** inactive; no newer numeric tag exists, so no alternate version root was created.

Any future network/DNS/auth failure exits with the exact `latest-tag-verification-blocked` disposition. A future newer tag cannot pass without its declared version root, immutable evidence, structured difference summary, and identical normalized public events; incompatible or ambiguous semantics remain a blocking contract decision.

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify the immutable release target and freeze correlated tool evidence** - `1c9b52d` (test)
2. **Task 2: Freeze terminal acceptance, unknown-code, and contradiction evidence** - `e5e608c` (test)

## Files Created/Modified

- `scripts/check_phase2_provenance.py` - Live tag, detached source, provenance, hash, evidence-kind, compatibility, and per-row decision gate.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/tool_progress_pair.sse` - Correlated running/completed records followed by valid stop and DONE.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_length.sse` - Valid canonical length lifecycle facts with raw ignored canaries.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_agent_error.sse` - Valid canonical agent-error facts with exact server partial state.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_task_exception_contradiction.sse` - Tagged `completed=true` plus `failed=true` contradiction retained for rejection.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_design_matrix.json` - Approved design-derived omission, unknown-code, and explicit-null rows.
- `tests/fixtures/hermes/v2026.7.7.2/provenance.json` - Schema 3 release verification and per-path immutable evidence metadata.

## Decisions Made

- Kept the canonical/latest disposition at `canonical-current`; D-16's conditional newer-tag ownership is implemented in the verifier but inactive in the evidence tree.
- Required structured source references to prove exact allowed paths and line anchors in a detached tree, not merely a commit-looking URL.
- Kept the historical top-level `evidence_scope.live_server_tested` field unchanged. New per-entry `reproduction.configuration.live_server_invoked` values are authoritative until the Phase 4 schema-normalization review.
- Retained Ruff 0.15.22, prek 0.4.10, coverage 7.15.2, and GitPython 3.1.52 as active Phase 4 currency constraints. No Phase 2 dependency pin, lock, or installation change was made.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Explicitly tracked the planned verifier despite a case-insensitive ignore collision**

- **Found during:** Task 1 commit
- **Issue:** The repository's root `/Scripts/` virtual-environment ignore pattern also matches lowercase `scripts/` on this case-insensitive filesystem, so the new planned verifier did not appear as an untracked file.
- **Fix:** Force-added only the explicitly planned `scripts/check_phase2_provenance.py` source artifact, matching the already tracked `scripts/verify_dist.py` convention; the ignore rule and generated files were not changed.
- **Files modified:** None beyond the planned verifier.
- **Verification:** The verifier is present in commit `1c9b52d`, and both commit hooks ran every configured gate normally.
- **Committed in:** `1c9b52d`

**2. [Rule 1 - Tracking Bug] Corrected progress values and roadmap cells not persisted by GSD handlers**

- **Found during:** Plan metadata update
- **Issue:** `state.update-progress` reported two of four plans and 50% but persisted `percent: 0` and left the prose bar at 25%; `roadmap.update-plan-progress` also emitted a malformed in-progress table row.
- **Fix:** Applied the handlers' reported 50% values to both STATE representations, normalized the roadmap row, and removed the now-resolved evidence-freezing blocker.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** STATE records two of four plans and 50% in machine-readable and prose fields; ROADMAP renders a valid five-column 2/4 in-progress row.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 2 auto-fixed issues (one blocking tracking collision, one state/roadmap persistence bug).
**Impact on plan:** Tracking behavior only; evidence semantics, dependencies, and scope are unchanged.

## Issues Encountered

- No network, authentication, source-identity, verifier, or hook blocker occurred.
- Both task commits passed the installed hook's lock, Ruff, basedpyright, verifytypes, full coverage, build, and distribution checks.

## Verification Results

- `uv run --no-sync python scripts/check_phase2_provenance.py --scope release-and-tool` — passed.
- `uv run --no-sync python scripts/check_phase2_provenance.py --scope terminal` — passed.
- `uv run --no-sync pytest -q` — 410 passed with 100% branch coverage.
- `uv run --no-sync ruff check .` — passed.
- `uv run --no-sync basedpyright` — 0 errors, warnings, or notes.
- `git diff -- pyproject.toml uv.lock` — empty.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-03 can consume the immutable correlated tool evidence while implementing pair-aware duplicate rejection.
- Plan 02-04 can execute the exact tag/design terminal matrix while preserving the delayed-terminal gate.
- A newer numeric tag, incompatible shape, or inability to live-verify tags remains a hard pre-production checkpoint rather than a permissive fallback.
- Phase 4 must re-check dependency currency and decide whether to normalize the historical/new provenance field names.

## Self-Check: PASSED

- All six created evidence/verifier files and the modified provenance manifest exist.
- Task commits `1c9b52d` and `e5e608c` exist in order.
- Both provenance scopes, the full coverage suite, Ruff, and basedpyright pass.
- Every new fixture hash and every structured source-anchor hash is machine-verified.
- No plan-owned source, fixture, dependency, or lock changes remain uncommitted before metadata closeout.

---
*Phase: 02-conversation-event-contract*
*Completed: 2026-07-17*
