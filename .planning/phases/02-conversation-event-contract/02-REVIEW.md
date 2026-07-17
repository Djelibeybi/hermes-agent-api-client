---
phase: 02-conversation-event-contract
reviewed: 2026-07-17T00:54:10Z
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
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-07-17T00:54:10Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found

## Summary

The 02-06 gap work closes all three concrete defects from the prior review: compatibility normalization now reuses the production duplicate-preserving projectors without globally rejecting additive duplicates, lifecycle evidence roles are exact in the release-agnostic path, and the previously value-bearing manifest/path/case failures now emit constant, context-free codes. The focused 539-test suite and Ruff both pass.

One critical closed-diagnostic gap remains. Recursive JSON can raise `RecursionError` outside the verifier's translated failure boundary, producing a raw traceback instead of one stable `ProvenanceError` code. Phase 2 is therefore not clean yet.

## Prior Finding Re-evaluation

- **Prior CR-01 — CLOSED.** `_json_pairs`, `_tool_json_object`, and `_chat_json_object` reuse the production pair hook and approved-path projectors. The new matrix covers same-value and conflicting duplicates for all nine approved member families, while the additive `emoji` duplicate remains accepted.
- **Prior CR-02 — CLOSED.** `_normalize_lifecycle_events` checks every required path against `_EXPECTED_KINDS` before reading or comparing lifecycle bytes, and tests reject unknown and swapped roles on every path.
- **Prior CR-03 — CLOSED for the reported canaries.** Fixture paths, source paths/ranges, and matrix case IDs now fail with constant codes; the new assertions cover `str`, `repr`, args, formatted traceback, cause/context, and CLI stderr. The finding below is a distinct unhandled parser-exception path through the same broader diagnostic contract.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Recursive JSON escapes the verifier's closed error boundary

**File:** `scripts/check_phase2_provenance.py:102-110,502-510,994-1005`
**Issue:** Both JSON entry points translate `JSONDecodeError`, but neither translates `RecursionError`: `_load_object` catches `(OSError, UnicodeError, json.JSONDecodeError)` and `_json_pairs` catches only `json.JSONDecodeError`. The production decoder already treats `RecursionError` as an ordinary closed parse failure in `src/hermes_agent_api_client/sse.py:81-86`, but the evidence verifier does not. I reproduced the gap by passing `_json_pairs` a valid JSON array nested 20,000 levels deep; it raised `RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string`. Because `main` catches only `ProvenanceError`, the CLI emits a raw traceback with implementation and filesystem details instead of the required single input-independent code. A deeply nested provenance/design-matrix object reaches the analogous `_load_object` gap. Fixture hashes and detached-source identity do not mitigate this because the verifier must parse the externally sourced evidence before it can certify it.

**Fix:** Include `RecursionError` in both translation boundaries, discard the caught exception before calling `_fail`, and add direct plus CLI regression tests using deeply nested JSON. Assert the same closed properties as `_assert_closed_error` and exact stderr (`invalid-sse-json` for lifecycle records and `invalid-provenance-json` for object files). Keeping the exception handling aligned with `_load_json_safely` avoids a verifier/runtime parser mismatch.

```python
try:
    value = json.loads(data, object_pairs_hook=_json_object_pairs_hook)
except (json.JSONDecodeError, RecursionError, UnicodeError):
    failed = True
    value = None
if failed:
    _fail("invalid-sse-json")
```

---

_Reviewed: 2026-07-17T00:54:10Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
