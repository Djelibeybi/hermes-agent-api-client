---
phase: 02-conversation-event-contract
plan: 01
subsystem: api
tags: [pydantic, sse, enums, validation, tdd]

requires:
  - phase: 01-typed-hermes-api-client
    provides: strict frozen public models, safe private wire DTOs, and ordered SSE decoding
provides:
  - closed public tool-progress and terminal-failure enums
  - exact bounded lifecycle-text validation shared by public and wire models
  - correlated toolCallId mapping into immutable public progress events
affects: [02-03-duplicate-aware-tool-decoding, 02-04-terminal-mapping, phase-4-verification]

tech-stack:
  added: []
  patterns:
    - exact built-in visible-ASCII lifecycle validation before Pydantic coercion
    - private wire Literal mapped explicitly into a strict public StrEnum

key-files:
  created: []
  modified:
    - src/hermes_agent_api_client/models.py
    - src/hermes_agent_api_client/__init__.py
    - src/hermes_agent_api_client/protocol.py
    - src/hermes_agent_api_client/sse.py
    - tests/test_protocol.py
    - tests/test_package.py
    - tests/test_sse.py

key-decisions:
  - "One input-value-free validator enforces exact built-in str, 1-256 characters, and visible ASCII for both public and private tool identifiers."
  - "Wire statuses remain closed string literals and are converted explicitly into strict public ToolProgressStatus members."
  - "Terminal metadata extends the existing frozen event without adding a new HermesEvent union variant."

patterns-established:
  - "Lifecycle text parity: public construction and wire decoding call the same private validator."
  - "Atomic event transition: model, wire DTO, SSE mapper, exports, and existing assertions change together."

requirements-completed: [TOOL-01, TOOL-02, TERM-01]

coverage:
  - id: D1
    description: "Consumers can import and directly construct only the approved immutable correlated tool-progress vocabulary."
    requirement: TOOL-01
    verification:
      - kind: unit
        ref: "tests/test_protocol.py#test_conversation_event_enums_are_closed_and_stable"
        status: pass
      - kind: unit
        ref: "tests/test_protocol.py#test_tool_progress_identifiers_reject_non_contract_values"
        status: pass
      - kind: unit
        ref: "tests/test_package.py#test_conversation_event_enums_are_available_through_star_import"
        status: pass
    human_judgment: false
  - id: D2
    description: "Current Hermes progress records preserve toolCallId, tool name, and the closed status in existing event order."
    requirement: TOOL-02
    verification:
      - kind: unit
        ref: "tests/test_sse.py#test_tool_progress_record_is_isolated_metadata"
        status: pass
      - kind: unit
        ref: "tests/test_sse.py#test_composite_golden_emits_one_success_in_closed_event_order"
        status: pass
    human_judgment: false
  - id: D3
    description: "Consumers can import immutable terminal metadata with strict safe defaults and closed failure reasons."
    requirement: TERM-01
    verification:
      - kind: unit
        ref: "tests/test_protocol.py#test_terminal_event_defaults_and_strict_metadata_contract"
        status: pass
      - kind: unit
        ref: "tests/test_package.py#test_public_exports_are_exact"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-07-17
status: complete
---

# Phase 2 Plan 1: Strict Conversation Event Vocabulary Summary

**Strict correlated tool-progress events and safe terminal metadata now share one exact visible-ASCII validation boundary across direct construction and current SSE decoding.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-16T20:03:03Z
- **Completed:** 2026-07-16T20:09:46Z
- **Tasks:** 1 TDD feature
- **Files modified:** 7

## Accomplishments

- Added exact package-root `ToolProgressStatus` and `TerminalFailureReason` enums and enriched the existing frozen events without widening `HermesEvent`.
- Enforced exact built-in strings of 1-256 visible-ASCII characters for both tool identifiers with one value-free validator shared by public and private models.
- Mapped required wire `toolCallId`, bounded tool name, and closed wire status atomically through the existing ordered SSE construction path.
- Preserved the full baseline while expanding the suite to 410 tests at 100% branch coverage.

## Task Commits

The TDD feature was committed through its required gates:

1. **RED: Define conversation event vocabulary contract** - `46414f2` (test)
2. **GREEN: Implement strict conversation event vocabulary** - `69f4680` (feat)

No separate refactor commit was needed; the GREEN implementation was already compact and passed all quality gates.

## Files Created/Modified

- `src/hermes_agent_api_client/models.py` - Closed enums, enriched frozen events, and the shared lifecycle-text validator.
- `src/hermes_agent_api_client/__init__.py` - Exact package-root imports and `__all__` entries.
- `src/hermes_agent_api_client/protocol.py` - Required aliased `toolCallId`, bounded tool name, and closed wire statuses.
- `src/hermes_agent_api_client/sse.py` - Explicit correlated public-event construction with `ToolProgressStatus`.
- `tests/test_protocol.py` - Exact bounds, types, enum strictness, defaults, immutability, and safe validator failures.
- `tests/test_package.py` - Exact and star-import export coverage.
- `tests/test_sse.py` - Updated current construction/order assertions and public/private wire-bound parity coverage.

## Decisions Made

- Reused a single private lifecycle-text validator across modules so D-05 through D-08 cannot drift.
- Kept wire statuses as `Literal["running", "completed"]` and constructed the strict public enum explicitly rather than weakening public model strictness.
- Kept pair-aware JSON intake, duplicate detection, terminal matrix mapping, dependencies, and session transport outside this plan as assigned to Plans 02-03, 02-04, Phase 4, and Phase 3 respectively.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Replaced a valid visible-ASCII secrecy canary with an invalid value**

- **Found during:** GREEN implementation
- **Issue:** The RED helper test used `lifecycle-secret-canary`, which is itself a valid lifecycle identifier and therefore should not raise.
- **Fix:** Changed the rejected canary to `lifecycle secret canary`, whose space is outside the approved `0x21..0x7e` range, while retaining the input-free exception assertion.
- **Files modified:** `tests/test_protocol.py`
- **Verification:** Targeted suite passes all validator acceptance/rejection cases.
- **Committed in:** `69f4680`

**2. [Rule 1 - Tracking Bug] Corrected progress values not persisted by the state handler**

- **Found during:** Plan metadata update
- **Issue:** `state.update-progress` returned 25% and a one-of-four completion count but left the persisted STATE percentage/progress bar at 0%; the roadmap handler also emitted a malformed in-progress table row.
- **Fix:** Applied the handler's reported 25% result to STATE and normalized the roadmap row while preserving all other handler-owned updates.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** STATE now records one of four plans and 25% in both machine-readable and prose fields; ROADMAP renders a five-column 1/4 in-progress row.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 2 auto-fixed bugs (one test input, one tracking persistence issue).
**Impact on plan:** Both corrections preserve the locked contract and truthful execution state; production scope and behavior are unchanged.

## Issues Encountered

- The repository's commit hook runs the complete green suite and strict typing. For the intentionally failing RED commit, only the `tests` and `basedpyright` hook IDs were skipped; the hook still ran lock, Ruff, verifytypes, build, and distribution verification. The GREEN commit ran every hook normally and passed.

## TDD Gate Compliance

- RED `46414f2` preceded GREEN `69f4680`.
- RED was proven after a 229-test green baseline and failed for the missing contract.
- GREEN passed 285 targeted tests and the full 410-test suite with 100% branch coverage.
- No refactor change was necessary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-02 can freeze evidence and provenance independently on the same Wave 1 baseline.
- Plan 02-03 can begin duplicate-aware decoding from a fully green tree whose public and current wire construction paths already agree.
- Dependency drift remains recorded for the Phase 4 recheck and refresh; no dependency metadata changed here.

## Self-Check: PASSED

- Required source and test files exist.
- RED commit `46414f2` and GREEN commit `69f4680` exist in order.
- Targeted, full coverage, Ruff, strict basedpyright, verifytypes, build, and distribution gates passed.
- No plan-owned uncommitted source or test changes remain.

---
*Phase: 02-conversation-event-contract*
*Completed: 2026-07-17*
