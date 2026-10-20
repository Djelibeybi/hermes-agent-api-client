---
phase: 03-session-header-safety
plan: 01
subsystem: testing
tags: [httpx, asyncio, cancellation, session-headers, pytest, mutation-red]

requires:
  - phase: PR #7 (8843cfc, v0.3.1)
    provides: shipped stream_chat_events session headers, local scrubbing, owns_active guard
provides:
  - GatedAsyncByteStream test double (yield one chunk, signal, block until cancelled)
  - HTTP-02 mid-iteration task-cancellation evidence through the public stream with an injected client
  - HTTP-02 early-close evidence with later stream and probe_capabilities reuse on the same client
  - D-08 SESS-05 mid-iteration cancellation and early-close matrix rows
  - SESS-04 evidence that no session header survives a cancelled or early-closed stream
affects: [03-04 traceability, 03 verification]

actuals:
  tokens: 1938
  tasks: 2
  commits: 2
plan_head_before: 431e51de7c98d968f2d81e567f3323d4fb90db18
plan_head_after: 247cbe03410a452a28efb49d7588ff52ae9e5774

tech-stack:
  added: []
  patterns:
    - "Gated byte stream: the gate is set only after the first chunk is consumed, so task.cancel() lands mid-iteration"
    - "Record the library-raised CancelledError inside the consumer task and re-raise, then inspect the recorded object"
    - "Serve the gated or tracked response for the first request only; later requests go to _successful_transport"

key-files:
  created: []
  modified:
    - tests/test_client_lifecycle.py

key-decisions:
  - "Consumer loop uses while True / anext instead of async for + append, because Ruff PERF401 rejects the append loop and an async comprehension would lose the event received before cancellation"
  - "No assertion helpers were extracted: both tests stay within Ruff's statement and branch limits"

patterns-established:
  - "Mutation-RED for already-shipped behaviour: exact-string edit of client.py, focused pytest run, git checkout -- src/, git diff --exit-code -- src/"

requirements-completed: [HTTP-02, SESS-05, SESS-04]

coverage:
  - id: D1
    description: "Mid-iteration task cancellation through the public stream closes only the response, propagates CancelledError (task.cancelled() True), leaves the injected client open and reusable, and leaks no session canary or header"
    requirement: HTTP-02
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation"
        status: pass
      - kind: other
        ref: "mutation G4b and session-local scrub each turn the test red (see RED entries)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Early aclose() after the first event closes the response, clears ag_frame, keeps the injected client open, and a later stream plus probe_capabilities succeed on the same client without session headers"
    requirement: HTTP-02
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close"
        status: pass
      - kind: other
        ref: "mutations G4 and G4b each turn the test red (see RED entries)"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-08 SESS-05 rows for mid-iteration cancellation (str/repr, traceback chain locals, __cause__/__context__, ag_frame) and early close (ag_frame, repr)"
    requirement: SESS-05
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation"
        status: pass
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close"
        status: pass
    human_judgment: false
  - id: D4
    description: "SESS-04 concurrency edge: a later stream without session arguments sends neither session header after a cancelled or early-closed stream that carried them"
    requirement: SESS-04
    verification:
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation"
        status: pass
      - kind: unit
        ref: "tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-10-20
status: complete
---

# Phase 3 Plan 01: Injected-client stream cancellation and early-close evidence Summary

**Two public-API characterisation tests prove that real mid-iteration `task.cancel()` and early `aclose()` close only the response, keep an injected `httpx.AsyncClient` open and reusable, scrub the propagated `CancelledError`, and leak no session value; each is shown red under the G4/G4b/scrub mutations with `src/` untouched.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-10-20T06:40:46Z
- **Completed:** 2026-10-20T06:44:01Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- `GatedAsyncByteStream` test double: yields one SSE chunk, sets `blocked` only after that chunk is consumed, then waits forever; `aclose()` records closure. No branches.
- Tracer test for mid-iteration task cancellation (HTTP-02, D-08 cancellation row, SESS-04 edge), passing on shipped code.
- Early-close reuse test (HTTP-02, D-08 early-close row, SESS-04 edge), including a later full stream and `probe_capabilities()` on the same wrapper.
- `src/` unchanged: `git diff --exit-code -- src/` exits 0 and `git log --oneline main..HEAD -- src/` is empty.

## Pytest node IDs (for the Plan 03-04 traceability table)

- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation`
- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`

## RED Evidence

The behaviour already ships (PR #7, v0.3.1), so a committed failing test is impossible. RED was proven by temporary exact-string mutations of `src/hermes_agent_api_client/client.py`, each restored before any commit. Per the plan, the `tdd-red-evidence` classifier was not run (test-only tasks in a `type: execute` plan, no GREEN implementation step).

### Task 1: `test_injected_client_survives_public_stream_task_cancellation`

Command: `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "injected_client_survives_public_stream_task_cancellation"`

| Mutation | Edit | Exit | Failing assertion | FAILED line |
|----------|------|------|-------------------|-------------|
| G4b (stream-path close) | insert `await active.aclose()` before the `active = None` / `base_url = None` / `request = {}` / `event = None` block in `stream_chat_events` | 1 | `tests/test_client_lifecycle.py:782` `assert injected_http_client.is_closed is False` (`assert True is False`) | `FAILED tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` |
| Session-local scrub | delete `session_id = None` and `session_key = None` in `stream_chat_events` | 1 | test line 809 `_assert_no_sensitive_traceback_references(...)` → helper line 297 `assert all(canary not in rendered for canary in canaries)` (package frame locals hold the canary) | `FAILED tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` |

Both: `1 failed, 96 deselected`. After each run: `git checkout -- src/hermes_agent_api_client/client.py` then `git diff --exit-code -- src/` exit 0. Failures point into the test's own assertions; no collection, import or syntax error.

GREEN on restored code: `1 passed, 96 deselected`.

Semantic assessment: the target test executed and failed on the planned assertions for the intended reasons (client closed by the stream path; session canary retained in package frame locals).

### Task 2: `test_injected_client_survives_public_stream_early_close`

Command: `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "injected_client_survives_public_stream_early_close"`

| Mutation | Edit | Exit | Failing assertion | FAILED line |
|----------|------|------|-------------------|-------------|
| G4 (exit ownership) | `owns_active = active is not None and self._injected_http_client is None` → `owns_active = active is not None` | 1 | `tests/test_client_lifecycle.py:885` final `assert injected_http_client.is_closed is False` after the context exits | `FAILED tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close` |
| G4b (stream-path close) | insert `await active.aclose()` before the `active = None` block, as in Task 1 | 1 | `tests/test_client_lifecycle.py:860` `assert injected_http_client.is_closed is False` straight after `aclose()` | `FAILED tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close` |

Both: `1 failed, 97 deselected`. After each run: `git checkout -- src/hermes_agent_api_client/client.py` then `git diff --exit-code -- src/` exit 0.

GREEN on restored code: `2 passed, 96 deselected` for `-k "injected_client_survives_public_stream"`.

## Task Commits

1. **Task 1: Tracer: mid-iteration task cancellation through the public stream with an injected client** - `de5e53c` (test)
2. **Task 2: Early close keeps the injected client open and reusable for later requests** - `247cbe0` (test)

Tracer feedback gate (interactive, `end-of-phase`, automated-only verify): re-ran the Task 1 verify block green before expanding to Task 2.

## Files Created/Modified

- `tests/test_client_lifecycle.py` - adds `GatedAsyncByteStream` and the two tests (182 added lines, 0 removed; no PR #7 test or helper edited).

## Verification

- `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q` → `166 passed` (after Task 1).
- `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "injected_client_survives_public_stream"` → `2 passed`.
- `uv run pytest` → `643 passed`, `Required test coverage of 100.0% reached. Total coverage: 100.00%`.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run --no-sync basedpyright` (0 errors) all green.
- `uv run --no-sync prek run --all-files` → all hooks passed (uv lock, Ruff format and check, basedpyright, verifytypes, tests with coverage, build, verify distributions).
- `git diff --exit-code -- src/ && test -z "$(git log --oneline main..HEAD -- src/)"` succeeds.

## TDD Gate Compliance

`type: execute` plan with `tdd="true"` test-only tasks. Two `test(03-01)` commits exist; no `feat(03-01)` commit exists by design, because the behaviour already ships and D-01/D-03 forbid `src/` changes. RED was proven by the four mutation runs above and GREEN is the restored shipped code.

## Decisions Made

- The consumer coroutine iterates with `while True: received.append(await anext(public_stream))`. Ruff PERF401 rejected `async for` plus `append`, and the suggested async-comprehension `extend` would discard the delta received before cancellation, defeating the `received == [AssistantDeltaEvent(text="hello")]` check.
- No module-level assertion helpers were needed; Ruff's PLR0915/PLR0912/C901 limits did not trip.

## Deviations from Plan

None - plan executed exactly as written (the PERF401 loop shape above is an implementation detail within the task's action).

## Issues Encountered

None. The first attempt to capture the G4b exit code printed an empty value because the shell is zsh (`PIPESTATUS` unset); the run was repeated with output written to a file and `$?` captured directly, giving exit 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- HTTP-02 is evidenced for early close and real mid-iteration cancellation with later reuse; ready for the remaining Phase 3 gap-fill plans and the Plan 03-04 traceability record.
- No blockers.

---
*Phase: 03-session-header-safety*
*Completed: 2026-10-20*

## Self-Check: PASSED

- FOUND: tests/test_client_lifecycle.py
- FOUND: .planning/phases/03-session-header-safety/03-01-SUMMARY.md
- FOUND: de5e53c, 247cbe0 (ancestors of HEAD)
