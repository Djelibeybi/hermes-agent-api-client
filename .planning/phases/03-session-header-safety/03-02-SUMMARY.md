---
phase: 03-session-header-safety
plan: 02
subsystem: testing
tags: [httpx, session-headers, validation, secrecy, pytest, mutation-red, inspect]

requires:
  - phase: PR #7 (8843cfc, v0.3.1)
    provides: shipped session header mapping, _is_valid_session_value, D-05 path-shape rule, local scrubbing
  - phase: 03-01
    provides: _HasAsyncGeneratorFrame, _assert_no_sensitive_traceback_references and _successful_transport reuse pattern
provides:
  - SESS-01 exact-header-only evidence (id-only, key-only, both) and a stream_chat_events signature lock
  - SESS-02 rejection evidence for empty, CR, tab and bytes on both arguments, plus embedded .., slash and drive prefix on session_id
  - SESS-02 positive boundaries (session_key 1 and 256 characters) and exact D-05 adjacency pins
  - SESS-03 exact local-input str, repr, args and metadata across 14 rejection cases (ordering edge)
  - D-08 SESS-05 rejection row (str/repr, traceback text and package frame locals, cause/context, ag_frame)
affects: [03-04 traceability, 03 verification]

actuals:
  tokens: 2600
  tasks: 2
  commits: 2
plan_head_before: 8ada3b1444e2fe0103fe441abe5ff7850a7e6461
plan_head_after: 1bb4d93dec1818772e14fee04bfd82cab37eec51

tech-stack:
  added: []
  patterns:
    - "Signature lock: inspect.signature(...).parameters compared as an exact ordered list plus kind/default checks"
    - "Visible-ASCII canary substrings so repr-escaped leaks (\\r, \\t, b'...') are still detected"
    - "Identity-forbid only supplied values of length >= _MIN_UNIQUE_CANARY_LENGTH; never None or the interned empty string"

key-files:
  created: []
  modified:
    - tests/test_client_lifecycle.py

key-decisions:
  - "Mutation runs purge src/ __pycache__ before and after each run: a same-length edit (isalpha -> isalnum) restored within one mtime second left a stale .pyc that contaminated the next mutation run"
  - "No helpers extracted: both Task 2 tests stay within Ruff statement and branch limits"

patterns-established:
  - "Mutation-RED hygiene: exact-string edit, purge bytecode cache, focused pytest, git checkout -- src/, purge again, git diff --exit-code -- src/"

requirements-completed: [SESS-01, SESS-02, SESS-03, SESS-04, SESS-05]

coverage:
  - id: D1
    description: "Each supplied session value appears exactly once, verbatim, only under its own header; never in other headers, the body or the URL; an omitted value's header is absent; bound headers unchanged"
    requirement: SESS-01
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers"
        status: pass
      - kind: other
        ref: "mutation T1a (extra X-Request-Trace header) turns [id-only] and [both] red"
        status: pass
    human_judgment: false
  - id: D2
    description: "stream_chat_events has exactly self, request, keyword-only session_id/session_key defaulting to None, and no *args/**kwargs (no arbitrary-header API)"
    requirement: SESS-01
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_stream_chat_events_accepts_no_arbitrary_headers"
        status: pass
      - kind: other
        ref: "mutation T1b (extra headers parameter) turns the test red"
        status: pass
    human_judgment: false
  - id: D3
    description: "14-case rejection matrix: exact HermesTransportError text, repr, args and metadata; no dispatch; no cause/context; ag_frame None; no canary in str, repr, rendered traceback or package frame locals"
    requirement: SESS-03
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state"
        status: pass
      - kind: other
        ref: "mutations T2a, T2b, T2c, T2f and T2g each turn their listed cases red"
        status: pass
    human_judgment: false
  - id: D4
    description: "Positive boundaries: session_key '!' and '~'*256 accepted; session_id single dots, inner colon and digit-colon prefix accepted and sent unchanged (exact D-05 rule)"
    requirement: SESS-02
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries"
        status: pass
      - kind: other
        ref: "mutations T2d (drive-prefix broadening) and T2e (256 bound) each turn their listed case red"
        status: pass
    human_judgment: false
  - id: D5
    description: "Byte-for-byte transport: sent header values equal the inputs exactly and the client's bound headers equal their pre-stream copy"
    requirement: SESS-04
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers"
        status: pass
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries"
        status: pass
    human_judgment: false
  - id: D6
    description: "D-08 SESS-05 rejection row: no session canary in str/repr, traceback.format_exception output or any package frame's locals; __cause__/__context__ None; ag_frame None"
    requirement: SESS-05
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state"
        status: pass
      - kind: other
        ref: "mutation T2g (session-local scrub removed) turns all 12 canary-bearing cases red"
        status: pass
    human_judgment: false
  - id: D7
    description: "SESS-01 edge classification was left unresolved by the edge probe (#1110); a reviewer should classify it manually"
    requirement: SESS-01
    verification: []
    human_judgment: true
    rationale: "The plan flags SESS-01 as unclassified by the edge probe; classification is a reviewer judgement, not something a test asserts"

duration: 4min
completed: 2026-10-20
status: complete
---

# Phase 3 Plan 02: Session header exactness, rejection matrix and boundary evidence Summary

**Four characterisation tests (23 cases) on the shipped PR #7 session code prove that session values reach only their own headers verbatim, that `stream_chat_events` exposes no arbitrary-header API, and that 14 malformed inputs (CR, tab, bytes, empty, embedded `..`, slash, drive prefix and the pair orderings) fail with identical value-free error metadata and no retained state. Five boundary cases pin the exact D-05 rule. Every test is proven red under nine named mutations, and `src/` is unchanged.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-10-20T07:19:32Z
- **Completed:** 2026-10-20T07:23:09Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- G-01: `test_session_values_appear_only_in_their_exact_headers` checks `headers.get_list(name) == [value]` for each supplied value. It also checks that the value is absent from every other header value, the body and the URL, that an omitted value's header is absent, and that the bound client headers are unchanged.
- G-02: `test_stream_chat_events_accepts_no_arbitrary_headers` locks the signature to `(self, request, *, session_id=None, session_key=None)`.
- G-03/G-04/G-05: `test_rejected_session_values_leave_no_retained_state` covers 14 cases. Each asserts the exact `str`, `repr` and `args`, the category `TRANSPORT`, `status_code None` and `retryable False`, that `__cause__` and `__context__` are `None`, that no request is sent, that `ag_frame` is `None`, and that no canary appears in the error text or the package traceback locals.
- D-05/D-06 pins: `test_session_values_accept_exact_boundaries` covers the session_key bounds of 1 and 256 characters, and accepts single dots, an inner colon and a digit-colon prefix in session_id.
- Added `import inspect` and the module constants `_LOCAL_INPUT_FAILURE_TEXT` and `_LOCAL_INPUT_FAILURE_REPR`.
- `src/` unchanged: `git diff --exit-code -- src/` exits 0 and `git log --oneline main..HEAD -- src/` is empty.

## Pytest node IDs (for the Plan 03-04 traceability table)

- `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[id-only]`
- `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[key-only]`
- `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[both]`
- `tests/test_client_lifecycle.py::test_stream_chat_events_accepts_no_arbitrary_headers`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-empty]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-empty]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-carriage-return]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-carriage-return]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-tab]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-tab]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-bytes]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-bytes]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-embedded-parent]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-slash]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-drive-prefix]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-invalid-id]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-invalid-key]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-both-invalid]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-key-minimum]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-key-maximum]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-single-dots]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-inner-colon]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-digit-colon-prefix]`

## Task Commits

1. **Task 1: SESS-01 exact headers and no arbitrary-header API**: `6ef46ef` (test)
2. **Task 2: SESS-02/SESS-03 rejection matrix, D-08 rejection row, positive boundaries**: `1bb4d93` (test)

## RED evidence

Each mutation was an exact-string edit applied alone. The focused pytest run was followed by `git checkout -- src/`, a bytecode-cache purge and `git diff --exit-code -- src/` (exit 0 in every case). The Task 2 runs below are the clean re-runs with the cache purge (see Issues Encountered).

**Task 1** (`-k "appear_only_in_their_exact_headers or accepts_no_arbitrary_headers"`):

| Mutation | Edit | pytest exit | FAILED | Restore |
|---|---|---|---|---|
| T1a | client.py: add `request_headers["X-Request-Trace"] = session_id` after the session-id header line | 1 | `[id-only]`, `[both]` (2 failed, 2 passed) | diff exit 0 |
| T1b | client.py: add `headers: Mapping[str, str] \| None = None,` to the `stream_chat_events` signature | 1 | `test_stream_chat_events_accepts_no_arbitrary_headers` (1 failed, 3 passed) | diff exit 0 |

**Task 2** (`-k "rejected_session_values_leave_no_retained_state or session_values_accept_exact_boundaries"`):

| Mutation | Edit | pytest exit | FAILED | Restore |
|---|---|---|---|---|
| T2a (G1) | `validated = _require_lifecycle_text(value)` → `validated = str(value)` | 1 | the empty, CR and tab cases for both arguments, the bytes cases for both arguments, and all three pair cases (11 failed, 8 passed) | diff exit 0 |
| T2b (G2) | session_id `reject_path_shape=True` → `False` | 1 | `[session-id-embedded-parent]`, `[session-id-slash]`, `[session-id-drive-prefix]` (3 failed, 16 passed) | diff exit 0 |
| T2c (narrowing) | `".." in validated` → `validated == ".."` (run also selected `test_path_shaped_session_ids_fail_before_dispatch`) | 1 | `[session-id-embedded-parent]` only; PR #7 `[parent]` still passes (1 failed, 22 passed) | diff exit 0 |
| T2d (broadening) | `validated[0].isalpha()` → `validated[0].isalnum()` | 1 | `[session-id-digit-colon-prefix]` (1 failed, 18 passed) | diff exit 0 |
| T2e (bound) | models.py `<= _LIFECYCLE_TEXT_MAX` → `< _LIFECYCLE_TEXT_MAX` | 1 | `[session-key-maximum]` (1 failed, 18 passed) | diff exit 0 |
| T2f (classification) | `_raise_transport_failure(transient=False)` after `request = {}` → `transient=True` | 1 | all 14 rejection cases (14 failed, 5 passed) | diff exit 0 |
| T2g (scrub) | delete `session_id = None` / `session_key = None` after `_chat_request_headers` | 1 | all 12 canary-bearing rejection cases; the two empty cases have no canary and pass (12 failed, 7 passed) | diff exit 0 |

**GREEN** on restored code: the focused run gives 23 passed. `tests/test_client_lifecycle.py` plus `tests/test_transport.py` give 190 passed. `uv run pytest` gives 666 passed at 100.00% coverage. `uv run --no-sync prek run --all-files` passes every hook.

**Semantic assessment:** each failure is on the planned assertion for the planned reason. The T1a cases fail on the "not in other header values" assertion. T1b fails on the exact parameter list. In Task 2, the rejection cases fail because no `HermesTransportError` is raised (T2a, T2b, T2c), because the exact `retryable=false` text no longer matches (T2f), or because a canary appears in a package frame's locals (T2g). The boundary cases fail because a valid value was rejected (T2d, T2e). There are no collection, import or fixture faults.

## TDD Gate Compliance

This is a `type: execute` plan with test-only `tdd="true"` tasks. Under D-01/D-03 a `feat(03-02)` commit is impossible by design: the shipped `src/` is the GREEN state, and RED is proven against named temporary mutations rather than a missing implementation. The `test(03-02)` commits are `6ef46ef` and `1bb4d93`. There is no `feat`, and no `refactor` was needed.

## Files Created/Modified

- `tests/test_client_lifecycle.py`: adds `import inspect`, two module constants and four tests (23 cases). Additions only; the PR #7 tests are untouched.

## Decisions Made

- The `supplied` identity-forbidden tuple keeps only `str`/`bytes` inputs of at least `_MIN_UNIQUE_CANARY_LENGTH`. This excludes `None` and the interned empty string, as the plan requires.
- No helpers were extracted, because Ruff complexity limits were not tripped.

## Deviations from Plan

None to the shipped code or the test design. The only addition is to RED-proof hygiene (see Issues Encountered).

**Total deviations:** 0 to plan scope.

## Issues Encountered

- **Stale bytecode during mutation runs.** In the first pass, T2e also failed `[session-id-digit-colon-prefix]`, which the 256-bound mutation cannot cause. Root cause: T2d swaps `isalpha` for `isalnum`, which has the same byte length. The restore landed within the same mtime second, so Python's `.pyc` freshness check (mtime in seconds plus size) treated the mutated `client.py` bytecode as current, and the T2e run executed the T2d mutation. Isolated re-runs of T2e showed only `[session-key-maximum]` failing. Fix: the mutation harness now purges `src/**/__pycache__` after applying each mutation and again after restoring. All seven Task 2 mutations were re-run cleanly, and those results are the ones recorded above. Before the final GREEN runs, all `__pycache__` directories under `src/` and `tests/` were purged. Task 1's mutations change the file size, so they were not affected.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Ready for 03-03. SESS-01 to SESS-03 and the D-08 rejection row now have direct, mutation-proven evidence for the 03-04 traceability table.
- SESS-01 edge classification is still unresolved (#1110 probe note). A reviewer should classify it manually.

## Self-Check: PASSED

- FOUND: tests/test_client_lifecycle.py (4 new test functions, `import inspect`, `_LOCAL_INPUT_FAILURE_TEXT`)
- FOUND: 6ef46ef (ancestor of HEAD)
- FOUND: 1bb4d93 (ancestor of HEAD)
- `git rev-list --count 8ada3b1..HEAD` = 2

---
*Phase: 03-session-header-safety*
*Completed: 2026-10-20*
