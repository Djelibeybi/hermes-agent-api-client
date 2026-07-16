---
phase: 02-conversation-event-contract
plan: 03
subsystem: api
tags: [json, sse, duplicate-detection, pydantic, tdd]

requires:
  - phase: 02-conversation-event-contract
    provides: strict public tool vocabulary and immutable correlated lifecycle evidence from Plans 02-01 and 02-02
provides:
  - pair-preserving JSON intake for every SSE application object
  - exact-path duplicate rejection for tool progress, root hermes, and choice finish reason members
  - recursive ordinary-container materialization before existing strict chat DTO validation
  - ordered repeat-preserving correlated tool event decoding with raw-payload scrubbing
affects: [02-04-terminal-mapping, phase-4-verification]

tech-stack:
  added: []
  patterns:
    - private frozen pair nodes retain duplicate evidence until approved-path checks finish
    - ignored additive JSON is discarded for tools or recursively materialized for compatible chat DTO validation

key-files:
  created: []
  modified:
    - src/hermes_agent_api_client/protocol.py
    - src/hermes_agent_api_client/sse.py
    - tests/test_sse.py
    - tests/helpers/hermes.py
    - tests/fixtures/hermes/v2026.7.7.2/chat_completions/tool_progress_pair.sse
    - tests/fixtures/hermes/v2026.7.7.2/provenance.json

key-decisions:
  - "Every JSON object remains a private _JsonObjectPairs node until event-specific duplicate checks complete."
  - "Tool projection copies only toolCallId, tool, and status, while chat projection recursively materializes the complete additive-compatible tree before Pydantic validation."
  - "Duplicate root hermes and choice finish_reason members fail closed now so Plan 02-04 can extend the same seam to terminal lifecycle members."

patterns-established:
  - "Pair-aware intake: json.loads object_pairs_hook preserves ambiguity evidence without replacing the bounded SSE state machine."
  - "Path-scoped duplicates: approved singleton paths fail closed while duplicates inside ignored additive objects retain last-value-wins compatibility."

requirements-completed: [TOOL-02, TOOL-03, TOOL-04]

coverage:
  - id: D1
    description: "Immutable and derived tool lifecycle records preserve exact IDs, names, statuses, repeats, and wire order through interruption."
    requirement: TOOL-02
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_tool_progress_pair_fixture_preserves_exact_correlation_and_order"
        status: pass
      - kind: unit
        ref: "tests/test_sse.py#test_tool_progress_preserves_punctuation_case_repeats_and_interleaving"
        status: pass
    human_judgment: false
  - id: D2
    description: "Same-value and conflicting duplicates at every approved Phase-2 tool/chat singleton path fail before dictionary collapse while ignored nested duplicates remain compatible."
    requirement: TOOL-03
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_duplicate_approved_tool_members_fail_before_dictionary_collapse"
        status: pass
      - kind: unit
        ref: "tests/test_sse.py#test_duplicate_approved_chat_members_fail_before_materialization"
        status: pass
      - kind: unit
        ref: "tests/test_sse.py#test_additive_application_fields_are_ignored_at_every_wire_level"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tool emoji, labels, arguments, results, raw nested payloads, and private pair trees never enter public values, failures, traceback frames, or retained generator state."
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_tool_raw_payloads_and_pair_tree_are_scrubbed_on_failure"
        status: pass
      - kind: integration
        ref: "uv run --no-sync pytest -q (428 passed, 100% branch coverage)"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-07-17
status: complete
---

# Phase 2 Plan 3: Pair-Aware Correlated Tool Decoding Summary

**Pair-preserving JSON intake now rejects duplicate approved lifecycle facts before collapse, emits exact ordered correlated tool events, and recursively restores additive chat trees without retaining raw payloads.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-16T20:35:18Z
- **Completed:** 2026-07-16T20:45:17Z
- **Tasks:** 1 TDD feature
- **Files modified:** 6

## Accomplishments

- Added a frozen slotted `_JsonObjectPairs` intake node and event-specific projections so same-value and conflicting duplicate lifecycle members remain observable until they fail closed.
- Preserved one-record-to-one-event ordering, exact correlation, repetitions, interleaving, and already-yielded interruption prefixes without adding a tool registry or synthetic event.
- Recursively materialized every remaining chat pair node into ordinary dictionaries/lists before strict DTO validation, keeping the named additive-fields regression green.
- Proved raw/additive tool data and private pair evidence are absent from public values, exception graphs, package traceback locals, and closed generator state.

## Task Commits

The TDD feature was committed through its required gates:

1. **RED: Define duplicate-aware tool decoding contract** - `ed6c0bb` (test)
2. **RED: Cover approved chat duplicate paths** - `c984e27` (test)
3. **GREEN: Implement duplicate-aware tool decoding** - `762abda` (feat)

No separate refactor commit was needed; the GREEN implementation was already compact and passed every quality gate.

## Files Created/Modified

- `src/hermes_agent_api_client/protocol.py` - Pair node, hook, approved-path duplicate checks, projection, and recursive materialization.
- `src/hermes_agent_api_client/sse.py` - Pair-aware JSON loading and sanitized event-specific projection before private DTO parsing.
- `tests/test_sse.py` - Immutable-pair, bounds, punctuation, repetition, interleaving, interruption, duplicate-path, materialization, recursion, and secrecy coverage.
- `tests/helpers/hermes.py` - Raw ordered JSON-member SSE builder that can represent duplicate names without dictionaries.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/tool_progress_pair.sse` - Correct complete SSE record boundary after DONE.
- `tests/fixtures/hermes/v2026.7.7.2/provenance.json` - Updated immutable SHA-256 for the corrected complete fixture bytes.

## Decisions Made

- Kept duplicate policy event- and path-specific: tool root `toolCallId`, `tool`, and `status`; chat root `hermes`; and the single choice's `finish_reason`.
- Discarded tool additive values before mapping, while preserving existing chat forward compatibility by recursively materializing all remaining nested objects and arrays.
- Reduced projection, recursion, JSON, and DTO failures to input-independent sentinels before the existing raw-record-free `HermesProtocolError` frame.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repaired the immutable tool-pair fixture's final SSE record boundary**

- **Found during:** RED immutable fixture decoding
- **Issue:** `tool_progress_pair.sse` ended with one newline after `data: [DONE]`, leaving the final record unterminated under the repository's established SSE framing contract.
- **Fix:** Added the required second LF and updated the manifest SHA-256 without changing the fixture's lifecycle facts or provenance classification.
- **Files modified:** `tests/fixtures/hermes/v2026.7.7.2/chat_completions/tool_progress_pair.sse`, `tests/fixtures/hermes/v2026.7.7.2/provenance.json`
- **Verification:** `scripts/check_phase2_provenance.py --scope release-and-tool` passes, and whole/bytewise immutable fixture decoding is green.
- **Committed in:** `ed6c0bb`

**2. [Rule 1 - Tracking Bug] Corrected progress values not persisted by the GSD handlers**

- **Found during:** Plan metadata update
- **Issue:** `state.update-progress` reported three of four plans and 75% but persisted `percent: 0` and left the prose bar at 50%; `roadmap.update-plan-progress` also omitted spacing in the in-progress status cell.
- **Fix:** Applied the handler's reported 75% values to both STATE representations, updated the last-activity description, and normalized the roadmap row.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** STATE records three of four plans and 75% in machine-readable and prose fields; ROADMAP renders a valid five-column 3/4 in-progress row.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 2 auto-fixed issues (one blocking fixture defect, one tracking bug).
**Impact on plan:** The corrections make the approved evidence executable and the planning state truthful; no public contract, dependency, or lifecycle semantics changed.

## Issues Encountered

- The initial coverage run reached 99.44%; explicit sanitized recursion-failure and non-object progress cases closed every new projection branch, restoring the mandatory 100% branch gate.
- The intentionally failing RED commits skipped only the coverage-test hook. Ruff, basedpyright, verifytypes, build, and distribution verification still ran; the GREEN commit ran every installed hook normally and passed.

## TDD Gate Compliance

- RED commits `ed6c0bb` and `c984e27` precede GREEN commit `762abda`.
- Baseline `tests/test_sse.py` was 100/100 green before RED; RED then failed specifically on approved duplicate collapse and private-pair secrecy behavior.
- GREEN passed 118 targeted SSE tests and the full 428-test suite with 100% branch coverage.
- No behavior-preserving refactor change was necessary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-04 can extend `_project_chat_chunk_object` while duplicate evidence still exists to validate root `hermes` lifecycle members and map the total terminal matrix.
- Existing delayed-terminal, source cleanup, cancellation, transport classification, SSE bounds, and additive chat behavior remain green.
- No dependency or lock metadata changed; the Phase 4 currency obligation remains intact.

## Self-Check: PASSED

- All six modified source, test, helper, fixture, and provenance files exist.
- RED commits `ed6c0bb`/`c984e27` and GREEN commit `762abda` exist in order.
- Release/tool provenance, targeted SSE tests, full branch coverage, Ruff, basedpyright, verifytypes, build, and distribution verification pass.
- No TODO, FIXME, placeholder, or goal-blocking stub was introduced.

---
*Phase: 02-conversation-event-contract*
*Completed: 2026-07-17*
