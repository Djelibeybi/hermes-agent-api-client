---
phase: 02-conversation-event-contract
reviewed: 2026-07-17T01:45:26Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - scripts/check_phase2_provenance.py
  - src/hermes_agent_api_client/__init__.py
  - src/hermes_agent_api_client/models.py
  - src/hermes_agent_api_client/protocol.py
  - src/hermes_agent_api_client/sse.py
  - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_agent_error.sse
  - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_design_matrix.json
  - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_length.sse
  - tests/fixtures/hermes/v2026.7.7.2/chat_completions/terminal_task_exception_contradiction.sse
  - tests/fixtures/hermes/v2026.7.7.2/chat_completions/tool_progress_pair.sse
  - tests/fixtures/hermes/v2026.7.7.2/provenance.json
  - tests/helpers/hermes.py
  - tests/test_package.py
  - tests/test_phase2_provenance.py
  - tests/test_protocol.py
  - tests/test_sse.py
  - tests/test_transport.py
findings:
  critical: 4
  warning: 0
  info: 0
  total: 4
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-07-17T01:45:26Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found

## Summary

The four reported malformed-input defects are fixed. Oversized JSON integers now become `HermesProtocolError` publicly and exact closed provenance codes internally; decoder-recursive JSON remains closed; matrix references and finish reasons are exact-type checked before hashing; and NUL/resolution failures become `invalid-fixture-path`. Commit `4cbeb93` records those `aeab137` fixes accurately. The exact five-test-file review scope passes all 558 tests without coverage instrumentation. Executing the pre-fix `aeab137^` implementation reproduced the intended RED outcomes (`HermesTransportError`, raw `ValueError`, raw `TypeError`, and raw path `ValueError`), while the earlier recursion implementation propagated raw `RecursionError` through both direct and `main` paths.

A systematic pass over the remaining parsing, validation, and verifier-setup operations found four ordinary-exception escapes. Oversized numeric release tags and legacy source ranges can trigger raw integer-conversion `ValueError`; recursive but parser-valid matrix metadata can trigger raw `RecursionError`; undecodable Git output can escape `_run_git` as `UnicodeDecodeError`; and temporary-directory creation can escape as raw `OSError`. Each bypasses `main`'s finite `ProvenanceError` boundary.

## Prior Finding Re-evaluation

- **Large JSON integers — CLOSED.** `ValueError` is caught at the public SSE and both provenance JSON boundaries. Direct SSE, HTTP client cleanup, provenance, design-matrix, lifecycle, and CLI regressions pass with the intended protocol/code taxonomy.
- **Recursive JSON — CLOSED at both decoders.** Lifecycle JSON maps to `invalid-sse-json`; provenance and matrix JSON map to `invalid-provenance-json`; direct exceptions have no cause/context and CLI stderr is a single closed line.
- **Non-string design-matrix members — CLOSED for the reported members.** Root refs, case refs, and `finish_reason` are validated before set/dict operations, and list/dict variants fail with finite matrix codes.
- **Invalid/NUL fixture paths — CLOSED.** NUL is rejected before resolution; `OSError`, `RuntimeError`, and `ValueError` from resolution are translated after leaving the handler; escapes retain their separate `fixture-path-escape` code.
- **RED validity — CONFIRMED.** Running `aeab137^` through the same direct boundaries produced raw `ValueError` for oversized JSON and NUL paths, raw `TypeError` for malformed matrix refs, and retryable `HermesTransportError` for public SSE. The recursion pre-fix source likewise produced raw `RecursionError` from both direct boundaries and both `main` call chains.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Numeric tags and legacy source ranges can escape as raw integer-conversion errors

**File:** `scripts/check_phase2_provenance.py:157-168,364-376,1020-1027`
**Issue:** `_version_key` and `_verify_legacy_source_ref` validate only regex shape before calling `int()` on externally controlled digit strings. A numeric release tag such as `v<5000 digits>.1`, or a valid manifest URL with a correct repository/ref/path and a 5,000-digit `L...-L...` range, matches its regex and then raises Python's integer-limit `ValueError`. `_latest_release`, direct legacy-reference validation, and `main` propagate that ordinary exception instead of a finite provenance code. This is the same `ValueError` class now handled at JSON parsing, but at later scalar-conversion boundaries.

**Fix:** Parse release components and both range components inside guarded classification blocks, translate `ValueError` after leaving the handler, and pass only validated integers onward. Add direct and real-CLI tests for both an oversized numeric tag and an oversized line range, asserting exact codes, no cause/context or canary retention, and single-line stderr.

```python
failed = False
try:
    parts = tuple(int(part) for part in digit_parts)
except ValueError:
    failed = True
    parts = ()
if failed:
    _fail(closed_code)
```

### CR-02: Recursive matrix metadata bypasses the JSON recursion fix

**File:** `scripts/check_phase2_provenance.py:608-615,722-767,1020-1027`
**Issue:** `_load_object` correctly closes decoder recursion, but `_contains_none` recursively walks `wire.hermes` afterward without a guard or depth bound. Python's JSON decoder accepts a 500-level nested array in this environment; `_contains_none` then raises `RecursionError`. I reproduced both direct `_verify_design_matrix` and `main` escapes with an otherwise structurally valid matrix case. Thus parser-valid recursive metadata still yields a raw traceback even though decoder-recursive JSON is covered.

**Fix:** Replace `_contains_none` with an iterative traversal over built-in dict/list containers, or catch and classify traversal recursion outside the active handler. Add direct and real-CLI matrix tests whose `wire.hermes` contains a deeply nested array both with and without `null`, asserting a finite matrix code and closed exception state.

```python
def _contains_none(value: object) -> bool:
    pending = [value]
    while pending:
        item = pending.pop()
        if item is None:
            return True
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return False
```

### CR-03: Git output decoding errors bypass the subprocess failure boundary

**File:** `scripts/check_phase2_provenance.py:78-99,129-154,1020-1027`
**Issue:** `_run_git` uses `text=True`, so `subprocess.run` decodes captured stdout and stderr before returning. The function translates `OSError` only. If Git or a remote ref/error response contains bytes invalid under the process encoding, `subprocess.run` raises `UnicodeDecodeError`; direct `_run_git` and `main` both propagate the raw exception and its retained byte payload instead of `latest-tag-verification-blocked`. I reproduced the call chain with `subprocess.run` raising the exact decoder exception. This contradicts `_run_git`'s stated value-free failure boundary and makes tag/source verification non-total over subprocess output.

**Fix:** Treat `UnicodeError` like `OSError` in `_run_git`, preserving the existing outside-handler `latest-tag-verification-blocked` classification. Add direct and CLI tests that inject undecodable subprocess output and inspect args, formatted traceback, cause/context, canary retention, exact stderr, and exit code 3.

```python
try:
    completed = subprocess.run(..., text=True)
except (OSError, UnicodeError):
    failed = True
```

### CR-04: Temporary-directory failures escape verifier setup and cleanup

**File:** `scripts/check_phase2_provenance.py:267-323,943-1007,1020-1027`
**Issue:** `_fetch_source_tree` constructs `tempfile.TemporaryDirectory` outside any failure-classification boundary, and all three cleanup sites call `TemporaryDirectory.cleanup()` directly. If the system temporary directory is unavailable, full, or denied, creation raises raw `OSError`; cleanup can likewise raise and replace an otherwise closed validation result. I reproduced the creation path with an `OSError("temporary-secret-canary")`: the exception and its value-bearing args escaped unchanged rather than becoming `latest-tag-verification-blocked`. This also breaks the plan's guarantee that temporary-tree failures remain closed and cleanup is guaranteed on every path.

**Fix:** Wrap temporary-directory creation and cleanup in small helpers that capture `OSError` outside the active handler and translate it to `latest-tag-verification-blocked`; ensure a cleanup failure cannot overwrite an already-selected closed provenance failure. Add direct and `main` tests for creation and cleanup failures, including exact exit 3, single-line stderr, no canary, and no cause/context.

```python
failed = False
try:
    temporary = tempfile.TemporaryDirectory(prefix="phase2-provenance-")
except OSError:
    failed = True
    temporary = None
if failed:
    _fail("latest-tag-verification-blocked")
```

---

_Reviewed: 2026-07-17T01:45:26Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
