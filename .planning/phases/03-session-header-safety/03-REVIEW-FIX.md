---
phase: 03-session-header-safety
fixed_at: 2026-10-20T08:07:32Z
review_path: .planning/phases/03-session-header-safety/03-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-10-20T08:07:32Z
**Source review:** .planning/phases/03-session-header-safety/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (CR-01, WR-01, WR-02; fix scope `critical_warning`, so IN-01 to IN-04 were not attempted)
- Fixed: 3
- Skipped: 0

All changes are confined to `tests/test_client_lifecycle.py` and touch only the phase 3 additions. `src/` is unchanged: `git diff --exit-code e4e2aa1 -- src/` exits 0.

## Fixed Issues

### CR-01: "Retain no session values" test checks only CPython-guaranteed state; suspended-frame retention passes the whole suite

**Files modified:** `tests/test_client_lifecycle.py`
**Commit:** 19f7631
**Applied fix:** Added the `_assert_suspended_stream_retains_no_secrets(stream, *, canaries)` helper. It reads the public generator's live `ag_frame.f_locals` while the generator is suspended and checks that the rendered locals contain none of the session id, session key or bearer canaries. The check runs at these points:
- `test_completed_and_closed_streams_retain_no_session_values[completion]`: at every yield, inside the `async for` body.
- `test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]`: after the first event and before `aclose()`.
- `test_injected_client_survives_public_stream_early_close`: after the first event and before `aclose()`.
- `test_injected_client_survives_public_stream_task_cancellation`: while the consumer is blocked mid-stream at the gate, before cancellation.

The post-exit `ag_frame is None` assertions in all five phase 3 tests now have a comment saying they are lifecycle checks, not retention evidence. The retention test's docstring now names the suspended-frame check as the evidence.

The helper checks rendered locals for canaries. It does not assert particular local names (`session_id`, `operation_headers`), so a rename in `client.py` will not break the test, and a retained value is caught under any name. Adding the bearer canary also catches retained `operation_headers` through the `Authorization` value.

**Mutant verification** (run in the isolated worktree, with each mutation applied to `src/hermes_agent_api_client/client.py`, `src/**/__pycache__` deleted after every mutation and every restore, and `git checkout -- src/` followed by `git diff --exit-code -- src/` exiting 0 each time):

| Code under test | Pre-fix tests (HEAD `e4e2aa1`) | Fixed tests |
|---|---|---|
| Shipped code | 5 passed | 5 passed (focused); full suite 674 passed |
| Mutant A: `session_id = None` / `session_key = None` scrub moved into the invalid branch and to just before `_reraise_scrubbed_failure` | 5 passed (mutant survives) | 4 failed (full suite: 4 failed, 670 passed) |
| Mutant B: `operation_headers = {}` moved from before the `try` to the end of the generator | 5 passed (mutant survives) | 4 failed (full suite: 4 failed, 670 passed) |

The four failures under each mutant are `test_injected_client_survives_public_stream_task_cancellation`, `test_injected_client_survives_public_stream_early_close`, and `test_completed_and_closed_streams_retain_no_session_values[completion]` and `[early-close-after-event]`. In each case the failure is the `_assert_suspended_stream_retains_no_secrets` canary assertion. `[early-close-before-first-iteration]` still passes under both mutants, as expected: the generator has not started, and AR-03-01 accepts that case.

**Follow-up outside this fixer's scope:** T-03-11 in `03-SECURITY.md` still cites only the delegated-close mutation as evidence. It should now cite the suspended-frame assertion (`_assert_suspended_stream_retains_no_secrets`) and the mutant A/B results above. This fix was limited to tests, so that file was not edited.

### WR-01: Unbounded gate wait makes the cancellation test hang instead of failing

**Files modified:** `tests/test_client_lifecycle.py`
**Commit:** 9a6d07b
**Applied fix:** Added `GatedAsyncByteStream.wait_until_blocked(consumer)` and the `_GATE_TIMEOUT_SECONDS = 5` constant. The method runs the gate as a task and uses `asyncio.wait(..., FIRST_COMPLETED)` inside `asyncio.timeout(5)` to wait for either the gate or the consumer task. On timeout, it cancels the consumer and re-raises `TimeoutError`. The leftover gate task is always cancelled. If the consumer finishes first, the method awaits it, so the consumer's own exception shows up as the test failure. It then asserts that the gate was reached. The logic is in a method because putting it inline pushed the test over Ruff `PLR0915` (too many statements). Checked with two temporary copies of the test file, both deleted afterwards:
- First chunk replaced with `b"data: {malformed}\n\n"` (the reviewer's experiment): fails in 0.17 s with `HermesProtocolError` and a node ID, where it used to hang.
- `self.blocked.set()` removed, so the gate is never reached: fails with `TimeoutError` after 5.2 s.
- Shipped code: passed in 5 repeated runs before the refactor into a method and 3 repeated runs after it.

### WR-02: `repr()` canary assertions on generators and events cannot fail

**Files modified:** `tests/test_client_lifecycle.py`
**Commit:** 5c64a5c
**Applied fix:** Deleted the three assertions that could never fail: `repr(public_stream)` in `test_injected_client_survives_public_stream_early_close`, and `repr(stream)` and `repr(events)` in `test_completed_and_closed_streams_retain_no_session_values`. The suspended-frame locals check from CR-01 replaces them. Also removed the `events` pre-declaration in the retention test, which nothing used any more. The test now asserts the events directly.

## Verification

Every gate ran in the isolated worktree (`.claude/worktrees/rf-03-...`, which had its own `uv sync` environment), not in the main checkout. The worktree's editable install pointed at the worktree's `src/`, which was confirmed with `hermes_agent_api_client.__file__`. The worktree was removed after the fast-forward, but the commits are identical in the main checkout, so the results can be reproduced there.

- Each commit ran the full prek hook set through `git commit -s`: uv lock, Ruff format, Ruff check (ALL), basedpyright (strict), basedpyright verifytypes, tests with 100% branch coverage, build and verify-dist. All passed, with no `noqa` added and no `--no-verify`.
- `uv run --no-sync prek run --all-files` passed on the final tree (`5c64a5c`), first in the worktree and again in the main checkout after the fast-forward. The main-checkout run can be reproduced directly.
- All three commits are GPG-signed (`%G?` = `G`) and carry `Signed-off-by: Avi Miller <me@dje.li>`.

**Cleanup incident (resolved):** while the worktree was in use, something set `core.worktree` in the shared `.git/config` to the temporary worktree path. The most likely cause is a tool run by the commit hooks. The setting made git in the main checkout read files from the worktree, so the first `merge --ff-only` failed with a false "local changes would be overwritten" error. A check with an explicit `--work-tree` showed that the main checkout's files had not changed. After the worktree was removed, I unset `core.worktree`, retried the fast-forward (`e4e2aa1..5c64a5c`, which succeeded), deleted the temporary branch and removed the recovery sentinel. `git config --get core.worktree` now returns nothing. Later worktree-based review-fix runs may hit the same problem.

---

_Fixed: 2026-10-20T08:07:32Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
