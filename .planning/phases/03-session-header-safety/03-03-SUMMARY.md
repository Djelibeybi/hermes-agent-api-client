---
phase: 03-session-header-safety
plan: 03
subsystem: testing
tags: [httpx, asyncio, session-headers, secrecy, pytest, mutation-red, async-generator]

requires:
  - phase: PR #7 (8843cfc, v0.3.1)
    provides: shipped stream_chat_events session scrubbing, delegated-stream close, metadata-only failure translation
  - phase: 03-02
    provides: _HasAsyncGeneratorFrame, _assert_no_sensitive_traceback_references, TrackingAsyncByteStream and _successful_transport reuse pattern; mutation bytecode-purge hygiene
provides:
  - D-08 SESS-05 completion row (ag_frame None, canary-free repr(stream) and repr(events), live headers proven)
  - D-08 SESS-05 early-close row (aclose completes, response closed, ag_frame None, canary-free repr)
  - Early close before first iteration pinned (no request, ag_frame None) without inspecting the unstarted frame
  - SESS-05 post-dispatch public-failure matrix (401, 503, protocol, transport ConnectError, request-stage cancellation)
  - D-08 request-stage cancellation repr cell closed
affects: [03-04 traceability, 03 verification]

actuals:
  tokens: 1824
  tasks: 2
  commits: 2
plan_head_before: 01e9f209b728e561a16b8342c627d076a055dbe3
plan_head_after: 64831d45291a869c8f391fa200f3047c7854a7e2

tech-stack:
  added: []
  patterns:
    - "Module-level case factory returning (handler, expected public failure type) keeps a parametrised failure matrix inside Ruff branch limits and strict basedpyright"
    - "Test-side negative control proves an ag_frame or no-dispatch assertion can observe a retained frame or a request when no realistic source mutation can"

key-files:
  created: []
  modified:
    - tests/test_client_lifecycle.py

key-decisions:
  - "Extracted one module-level helper, _post_dispatch_failure_case, so the five-case failure matrix needs no in-test branching on handler behaviour"
  - "Completion and before-first-iteration ag_frame cells are proven red by test-side negative controls; CPython clears a finished generator's frame, so no realistic source mutation turns them red"

patterns-established:
  - "Negative-control RED: temporarily weaken the test's own driving (stop early, add an anext), confirm the target assertion fails, restore from a byte-identical backup and cmp"

requirements-completed: [SESS-05]

coverage:
  - id: D1
    description: "Completion with both session values: events are delta then SUCCESS terminal, aclose() on the exhausted stream completes, ag_frame None, no canary in repr(stream) or repr(events), request carried both headers, injected client open"
    requirement: SESS-05
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[completion]"
        status: pass
      - kind: other
        ref: "negative control (stop after first event, no aclose) fails on ag_frame is None"
        status: pass
    human_judgment: false
  - id: D2
    description: "Early close after one delta: aclose() completes, response byte stream closed, ag_frame None, no canary in repr(stream), request carried both headers, injected client open"
    requirement: SESS-05
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]"
        status: pass
      - kind: other
        ref: "mutation T1a (delegated aclose replaced by pass) fails on response_stream.closed is True"
        status: pass
    human_judgment: false
  - id: D3
    description: "Early close before first iteration: aclose() completes, no request sent, ag_frame None; the unstarted frame is never inspected (Pitfall 1, input to the Plan 03-04 Q2 decision)"
    requirement: SESS-05
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-before-first-iteration]"
        status: pass
      - kind: other
        ref: "negative control (one anext before aclose) fails on requests == []"
        status: pass
    human_judgment: false
  - id: D4
    description: "Post-dispatch public failures (401 HermesAuthenticationError, 503 HermesHttpStatusError, malformed SSE HermesProtocolError, ConnectError embedding both session values HermesTransportError, request-stage CancelledError identity) carry no session canary in str, repr, rendered traceback or package frame locals; cause/context None; ag_frame None; injected client open"
    requirement: SESS-05
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values"
        status: pass
      - kind: other
        ref: "mutation T2 (session_id/session_key scrub deleted) fails all five cases on the package-frame canary check"
        status: pass
    human_judgment: false
  - id: D5
    description: "How the four exception-less cells (completion and early close x traceback chain and cause/context) are recorded"
    requirement: SESS-05
    verification: []
    human_judgment: true
    rationale: "Plan 03-04 Q1 is a user decision; this plan supplies the evidence (normal termination, clean aclose, ag_frame None, canary-free repr) but does not decide the cell wording"

duration: 4min
completed: 2026-10-20
status: complete
---

# Phase 3 Plan 03: Completion, early-close and post-dispatch failure secrecy evidence Summary

**Two characterisation tests (8 cases) on the shipped PR #7 code prove that completed and early-closed streams keep no session values in `ag_frame` or `repr`, and that every post-dispatch public failure (401, 503, malformed SSE, a `ConnectError` that embeds both session values, and request-stage cancellation) leaks no session value through `str`, `repr`, traceback text, package frame locals, `__cause__`/`__context__` or `ag_frame`. Each case is proven red by a named source mutation or a test-side negative control. `src/` is unchanged.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-10-20T07:26:46Z
- **Completed:** 2026-10-20T07:30:33Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- G-06: `test_completed_and_closed_streams_retain_no_session_values` fills the D-08 completion and early-close rows and pins early close before the first iteration. It never reads the unstarted frame (Pitfall 1).
- G-07: `test_post_dispatch_failures_carry_no_session_values` covers the SESS-05 "absent from public failures" clause for every post-dispatch failure type. It also closes the request-stage cancellation `repr` cell, which earlier tests did not assert.
- Added `HermesAuthenticationError` to the package import tuple and the module constant `_AUTHENTICATION_STATUS_CODE = 401`.
- Added one module-level helper, `_post_dispatch_failure_case(case, requests, cancellation)`, which returns the recording handler and the exact expected public failure type.
- `src/` is unchanged: `git diff --exit-code -- src/` exits 0, and `git log --oneline main..HEAD -- src/` prints nothing.

## Pytest node IDs (for the Plan 03-04 traceability table)

- `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[completion]`
- `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]`
- `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-before-first-iteration]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[authentication-401]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[status-503]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[protocol-malformed-sse]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[transport-connect-error]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]`

## Task Commits

1. **Task 1: D-08 completion and early-close rows retain no session values**: `0c9f36c` (test)
2. **Task 2: Post-dispatch public failures carry no session values**: `64831d4` (test)

## RED evidence

Each source mutation was an exact-string edit, applied alone. The `src/` bytecode cache was purged after the edit and again after `git checkout -- src/`. Each negative control was a temporary test edit, restored from a byte-identical backup and confirmed with `cmp`.

**Task 1** (`-k "completed_and_closed_streams_retain_no_session_values"`):

| Proof | Edit | pytest exit | FAILED | Failing assertion | Restore |
|---|---|---|---|---|---|
| T1a source mutation | client.py `stream_chat_events` finally block: `await delegated_stream.aclose()` → `pass` | 1 | `[early-close-after-event]` (1 failed, 2 passed) | `assert response_stream.closed is True` (False) | `git diff --exit-code -- src/` exit 0 |
| T1b negative control, completion | completion branch reduced to `events = (await anext(stream),)`: no further iteration and no `aclose()` | 1 | `[completion]` (1 failed, 2 passed) | `assert cast("_HasAsyncGeneratorFrame", stream).ag_frame is None` (live frame at client.py:695) | test file `cmp` identical; src clean |
| T1c negative control, before first iteration | `await anext(stream)` inserted before `aclose()` | 1 | `[early-close-before-first-iteration]` (1 failed, 2 passed) | `assert requests == []` (one POST /v1/chat/completions) | test file `cmp` identical; src clean |

**Limitation:** no realistic source mutation can turn the completion or before-first-iteration `ag_frame` cell red. CPython sets `ag_frame` to `None` once a generator finishes or is closed. The negative controls show only that the assertion can observe a retained frame or a dispatch when one exists.

**Task 2** (`-k "post_dispatch_failures_carry_no_session_values"`):

| Proof | Edit | pytest exit | FAILED | Failing assertion | Restore |
|---|---|---|---|---|---|
| T2 scrub mutation | client.py `stream_chat_events`: delete `session_id = None` and `session_key = None` after `_chat_request_headers` | 1 | all five: `[authentication-401]`, `[status-503]`, `[protocol-malformed-sse]`, `[transport-connect-error]`, `[request-stage-cancellation]` (5 failed) | `_assert_no_sensitive_traceback_references`: `assert all(canary not in rendered ...)`, because the public wrapper frame still holds the values | `git diff --exit-code -- src/` exit 0 |

**GREEN** on the restored code, with all `__pycache__` directories under `src/` and `tests/` purged first. The focused run gives 3 passed and 5 passed, and the combined plan filter gives 8 passed. `tests/test_client_lifecycle.py` plus `tests/test_transport.py` give 198 passed. `uv run pytest` gives 674 passed at 100.00% coverage. `uv run ruff check .`, `ruff format --check .` and `basedpyright` (0 errors, 0 warnings) are clean. `uv run --no-sync prek run --all-files` exits 0, and both commits passed the pre-commit hooks.

**Semantic assessment:** each failure is on the planned assertion for the planned reason. T1a leaves the response open because the delegated close never runs. T1b leaves a suspended generator, so its frame is live. T1c dispatches a request. T2 leaves both canaries in the `stream_chat_events` frame locals of every public failure's traceback. There were no collection, import or fixture faults, and no case failed for an unrelated reason.

## TDD Gate Compliance

This is a `type: execute` plan with test-only `tdd="true"` tasks. The MVP+TDD runtime gate does not apply, because no task's `<files>` list contains a source file. Under D-01 and D-03, a `feat(03-03)` commit cannot exist by design. The shipped `src/` is the GREEN state, and RED was shown by the named mutations and negative controls above. The `test(03-03)` commits are `0c9f36c` and `64831d4`. There is no `feat` commit and no `refactor` was needed.

## Files Created/Modified

- `tests/test_client_lifecycle.py`: adds the `HermesAuthenticationError` import, `_AUTHENTICATION_STATUS_CODE`, `_post_dispatch_failure_case` and two tests (8 cases). Additions only; the PR #7 tests are untouched.

## Decisions Made

- One helper was extracted for the Task 2 matrix: a module-level factory that returns the handler and the expected type. With it, the test body has only the status-code and identity checks as conditionals. Task 1 needed no helper.
- In the completion case, `response_stream.closed` is not asserted, so that the T1b negative control fails on `ag_frame` as the plan intends. Response closure is covered by the early-close case and by Plan 03-01.

## Deviations from Plan

None. The plan was executed exactly as written.

**Total deviations:** 0.

## Issues Encountered

None. Following the Plan 03-02 lesson, the bytecode-cache purge ran around every mutation.

## Known Stubs

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Ready for 03-04. With Plans 03-01 to 03-03, every D-08 row now has direct evidence, and so does the SESS-05 public-failure clause.
- Plan 03-04 needs two user decisions. Q1 is how to record the four exception-less cells; D5 above holds the evidence for that choice. Q2 is about pre-iteration retention (Pitfall 1), which this plan deliberately left uninspected.
- SESS-05 is also declared by Plan 03-04, so `requirements.ready-ids` blocks marking it complete until that plan finishes.
- The SESS-05 edge classification is still unresolved (#1110 probe note). A reviewer should classify it manually.

## Self-Check: PASSED

- FOUND: tests/test_client_lifecycle.py (`def test_completed_and_closed_streams_retain_no_session_values`, `def test_post_dispatch_failures_carry_no_session_values`, `_AUTHENTICATION_STATUS_CODE = 401`, `HermesAuthenticationError,` import line: one match each)
- FOUND: 0c9f36c (ancestor of HEAD)
- FOUND: 64831d4 (ancestor of HEAD)
- `git rev-list --count 01e9f20..HEAD` = 2; `check evaluation-scope --plan 03-03 --commits-only` resolves both commits on this branch

---
*Phase: 03-session-header-safety*
*Completed: 2026-10-20*
