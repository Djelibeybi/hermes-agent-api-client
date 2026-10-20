---
phase: 03-session-header-safety
reviewed: 2026-10-20T07:53:42Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - tests/test_client_lifecycle.py
findings:
  critical: 1
  warning: 2
  info: 4
  total: 7
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-10-20T07:53:42Z
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Scope: the lines added to `tests/test_client_lifecycle.py` since `8f28e23` (new helpers at lines 60-66, 160-177 and 397-431, and nine new tests at lines 772-1326). `src/` is unchanged. The 71 session, post-dispatch and survival tests pass, `ruff check`, `ruff format --check` and basedpyright are clean, and the task-cancellation test passed five repeated runs.

I mutated a scratch copy of `src/` (the real tree was not touched) to check whether the tests catch regressions. The traceback-based secrecy checks are sound. Deleting the `session_id = None` / `session_key = None` scrub at `client.py:674-675` turns 48 tests red. The generator-retention claim is the weak spot. Two mutants pass the whole suite (628 passed, `test_package.py` excluded because the scratch copy has no README):

- Keep `session_id`/`session_key` live in the public generator frame while it is suspended, and clear them only before any raise.
- Keep `operation_headers`, which holds the bearer and both session headers, live until the generator ends.

The test named for this property cannot detect either mutant, because every `ag_frame` assertion it makes runs after the generator has finished.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: "Retain no session values" test checks only CPython-guaranteed state; suspended-frame retention passes the whole suite

**File:** `tests/test_client_lifecycle.py:1191-1253` (also `:827`, `:905`, `:1108`, `:1317`)
**Issue:** `test_completed_and_closed_streams_retain_no_session_values` is the evidence for T-03-11 in `03-SECURITY.md`, and D-08 asks for an `ag_frame` check in every exit-path cell. All of its frame assertions run after `aclose()` or after the generator is exhausted. At that point CPython always sets `ag_frame` to `None`, whatever the library code does, so the assertion at line 1243 can never fail. The other new tests use the same post-exit `ag_frame is None` check (lines 827, 905, 1108, 1317). `03-TRACEABILITY.md:69` already records that this test went red under G4b only through its `is_closed` assertion, never through a retention check.

The window that matters is the one where a consumer holds an open stream suspended at a `yield`. In that window the frame is live and readable through `ag_frame.f_locals`. AR-03-01 accepts the never-iterated case and AR-03-02 accepts httpx's own request object, but neither covers the public generator's own locals. I checked this by mutation:

- Mutant A: move the `session_id = None` / `session_key = None` scrub from `client.py:674-675` into the invalid branch and to just before `_reraise_scrubbed_failure`. The suite gives `628 passed`, and `ag_frame.f_locals` after the first event shows `{'session_id': 'SID-canary', 'session_key': 'SKEY-canary'}`.
- Mutant B: drop `operation_headers = {}` at `client.py:687` and clear it only at the end. The suite gives `628 passed`, with the bearer and both session headers held in the suspended frame.

So a session-retention regression of the kind this phase exists to stop would ship green.
**Fix:** Add a suspended-frame cell. Read the public generator's frame after the first event and before close:
```python
assert await anext(stream) == AssistantDeltaEvent(text="hello")
frame = cast("_HasAsyncGeneratorFrame", stream).ag_frame
assert frame is not None
rendered = repr(frame.f_locals)
assert all(canary not in rendered for canary in (session_id, session_key))
assert frame.f_locals["session_id"] is None
assert frame.f_locals["session_key"] is None
assert frame.f_locals["operation_headers"] == {}
await stream.aclose()
```
Either add a `"suspended-after-first-event"` mode to the parametrised test, or put this check before `aclose()` in the `early-close-after-event` branch. Keep the post-close `ag_frame is None` assertions if you like, but label them as lifecycle checks, not secrecy evidence, and update T-03-11 to cite the new assertion.

## Warnings

### WR-01: Unbounded gate wait makes the cancellation test hang instead of failing

**File:** `tests/test_client_lifecycle.py:169-173, 817-818`
**Issue:** `await gated.blocked.wait()` has no timeout, and the project has no `pytest-timeout`. `blocked` is set only when the client asks the byte stream for a second chunk. If a regression makes the consume task fail first (an SSE or parser change that rejects the first event, an early `raise`, a header-building error), `blocked` is never set and the test waits forever. The task's exception is never observed. I checked this by swapping the first chunk for `b"data: {malformed}\n\n"` in a scratch copy: the test had to be killed by `timeout 10` (exit 124) and printed no pytest output. In CI this shows up as a job timeout with no failing node ID.
**Fix:** Race the gate against the task and bound the wait:
```python
task = asyncio.create_task(consume())
gate = asyncio.create_task(gated.blocked.wait())
async with asyncio.timeout(5):
    done, _ = await asyncio.wait({task, gate}, return_when=asyncio.FIRST_COMPLETED)
assert gate in done, "stream ended before reaching the gate"
assert not task.done()
task.cancel()
```

### WR-02: `repr()` canary assertions on generators and events cannot fail

**File:** `tests/test_client_lifecycle.py:906-909, 1244-1246, 1251-1253`
**Issue:** `repr()` of an async generator is always `<async_generator object HermesAgentApiClient.stream_chat_events at 0x...>`, and it never includes locals. `repr(events)` renders `AssistantDeltaEvent(text='hello')` and `TerminalEvent(...)` built from fixed mock bytes that never contain the session values. Neither assertion can detect a regression, yet both read as secrecy evidence. Together with CR-01 they make the test look much stronger than it is.
**Fix:** Delete these assertions, or replace them with the suspended `ag_frame.f_locals` check in CR-01. If an event-level check is wanted, make the mock server echo the request's session headers into the SSE `content`, so a leak through events becomes observable.

## Info

### IN-01: Rejected-value cases duplicate existing parametrisations

**File:** `tests/test_client_lifecycle.py:1019-1048`
**Issue:** `pair-invalid-id` and `pair-invalid-key` reuse the exact values of `test_invalid_session_pair_is_atomic_and_secret_free` (lines 669-670). `session-id-empty`, `session-key-empty`, `session-id-slash` and `session-id-drive-prefix` repeat cases in `test_invalid_session_arguments_fail_locally_without_dispatch` and `test_path_shaped_session_ids_fail_before_dispatch`. The new test asserts more (exact `str`/`repr`/`args`), so the older tests are now strict subsets.
**Fix:** Fold the older tests' value lists into `test_rejected_session_values_leave_no_retained_state` and delete the subsets, or drop the duplicated ids from the new matrix.

### IN-02: "First request gated, later requests succeed" handler and SSE literal duplicated

**File:** `tests/test_client_lifecycle.py:782-788, 874-880` (literal also at `:389-390, 778-779, 869-870, 1199-1200`)
**Issue:** The same `if not requests: ... return later(request)` closure is written twice, and the `hello` SSE delta bytes appear four times. If one copy drifts, the expected `AssistantDeltaEvent(text="hello")` assertions will fail in confusing ways.
**Fix:** Add a `_first_stream_then_success(requests, first_stream)` helper and a `_HELLO_DELTA_SSE` module constant.

### IN-03: Completion mode does not assert the response scope closed

**File:** `tests/test_client_lifecycle.py:1227-1233`
**Issue:** `early-close-after-event` asserts `response_stream.closed is True`, but `completion` does not. A regression that leaks the response on normal completion would still pass this test.
**Fix:** Add `assert response_stream.closed is True` after the completion branch.

### IN-04: Signature test name overclaims

**File:** `tests/test_client_lifecycle.py:999-1012`
**Issue:** `test_stream_chat_events_accepts_no_arbitrary_headers` checks only the parameter list. It does not show that a `request` mapping key (for example `{"headers": {...}}`) cannot influence outgoing headers. The name suggests it does.
**Fix:** Rename it to `test_stream_chat_events_signature_has_only_typed_session_arguments`, or add a case that sends a request document with a `headers` key and asserts no extra header was sent.

---

_Reviewed: 2026-10-20T07:53:42Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
