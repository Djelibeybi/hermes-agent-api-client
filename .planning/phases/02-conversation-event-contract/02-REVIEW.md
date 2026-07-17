---
phase: 02-conversation-event-contract
reviewed: 2026-07-17T01:12:04Z
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

**Reviewed:** 2026-07-17T01:12:04Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found

## Summary

The post-review recursion fix is correct: both lifecycle and object-file JSON now translate `RecursionError` outside the active handler to their exact closed codes, and the real CLI paths emit one line with no traceback or input canary. I also confirmed that the four new RED tests fail before `fe8d99a`: the `d389cdf` implementation propagates `RecursionError` through both direct entry points and through `main`. The current 51-test provenance suite and Ruff pass.

The broader malformed-input boundary is still not total. Python's JSON decoder also raises plain `ValueError` for a valid 5,000-digit JSON integer; the public SSE decoder misclassifies that protocol input as a retryable transport failure, while both verifier JSON entry points let it escape as a raw traceback. Two other valid JSON shapes likewise escape the verifier through unvalidated hash/set operations and a NUL-bearing fixture path. The reported 601 tests at 100% coverage do not exercise these exception variants.

## Prior Finding Re-evaluation

- **Release/commit identity — CLOSED.** Detached `HEAD`, manifest identity, entry identity, source references, and fixture hashes remain bound to externally supplied release identity.
- **Production-equivalent duplicate handling — CLOSED.** Compatibility normalization reuses the production pair hook and approved-path projectors, rejects all nine same/conflicting approved duplicate families, and still accepts ignored additive duplicates.
- **Exact lifecycle evidence roles — CLOSED.** `_normalize_lifecycle_events` checks every required path against `_EXPECTED_KINDS` for canonical and newer evidence.
- **Recursive JSON diagnostic CR-01 — CLOSED.** `_load_object` and `_json_pairs` now catch `RecursionError`, leave the handler, and raise `invalid-provenance-json` or `invalid-sse-json` with no cause/context. Direct tests check exception args and formatted traceback; CLI tests check exact single-line stderr and absence of canaries/tracebacks. Running the same direct and `main` call chains from `fe8d99a^` reproduced four raw `RecursionError` escapes, proving the RED tests genuinely cover the pre-fix defect.
- **General closed-diagnostic contract — NOT CLOSED.** The recursion variant is fixed, but CR-02 through CR-04 below prove remaining valid JSON/path inputs that bypass the finite-code boundary.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Oversized JSON integers are misclassified as retryable transport failures

**File:** `src/hermes_agent_api_client/sse.py:81-86,168-175,453-468,508-517`
**Issue:** `_load_json_safely` catches `JSONDecodeError`, `RecursionError`, and `UnicodeError`, but Python 3.13's `json.loads` raises plain `ValueError` when a JSON integer exceeds the interpreter's 4,300-digit conversion limit. A 5,000-digit integer is valid JSON and fits comfortably under `MAX_EVENT_DATA_CHARS`. I placed one in an otherwise valid terminal SSE chunk; `_load_json_safely` propagated `ValueError`, the broad iterator-body handler treated it as an opaque source exception, and the public decoder raised `HermesTransportError(transient=True)` instead of `HermesProtocolError`. Malformed wire data is therefore incorrectly advertised as a retryable network failure, which can drive inappropriate retries and violates the transport/protocol taxonomy.

**Fix:** Treat every decoder `ValueError` as a closed JSON parse failure inside `_load_json_safely` (with `JSONDecodeError` already a subclass), then add direct SSE and client streaming regressions using a 5,000-digit additive integer. Assert `HermesProtocolError`, no cause/context or canary retention, and response cleanup.

```python
try:
    return (True, json.loads(data, object_pairs_hook=_json_object_pairs_hook))
except (ValueError, RecursionError, UnicodeError):
    return (False, None)
```

### CR-02: Plain JSON `ValueError` still escapes both provenance parse boundaries

**File:** `scripts/check_phase2_provenance.py:102-110,502-510,995-1002`
**Issue:** The post-review fix adds `RecursionError` but still assumes all other JSON parse failures are `JSONDecodeError`. Passing either `_json_pairs` or `_load_object` a valid object containing a 5,000-digit integer raises the same uncaught plain `ValueError`. `main` catches only `ProvenanceError`, so lifecycle evidence, canonical/newer provenance, and the design matrix can still produce a raw multiline traceback instead of `invalid-sse-json` or `invalid-provenance-json`. This is the same closed-diagnostic trust boundary and is reachable with a roughly 5 KiB evidence value.

**Fix:** Catch `ValueError` at both JSON entry points, classify it outside the active handler, and extend the direct and real-CLI matrix to cover oversized integer values for lifecycle SSE, provenance JSON, and design-matrix JSON. Reuse `_assert_closed_error` and exact stderr assertions.

```python
except (ValueError, RecursionError, UnicodeError):
    failed = True
    value = None
```

### CR-03: Valid design-matrix containers can crash validation with `TypeError`

**File:** `scripts/check_phase2_provenance.py:709-740,995-1002`
**Issue:** `_verify_design_matrix` constructs sets and performs a dictionary lookup before validating that editor-controlled JSON members are strings. Each of these valid JSON mutations raises `TypeError: unhashable type: 'list'`: a nested list in root `decision_refs`, a nested list in a case's `decision_refs`, or a list-valued `wire.finish_reason`. The error bypasses `ProvenanceError` and `main`, yielding a raw traceback. Fixture hashing does not protect this boundary because a newer evidence root controls both the matrix bytes and its recorded digest.

**Fix:** Validate root refs as a list of exact strings before `set`, validate every case ref the same way, and require `finish_reason` to be a string before `required_by_finish.get`. Fail with the existing finite matrix codes. Add direct and CLI tests for list/dict values at all three positions, including closed exception state and exact stderr.

```python
refs = matrix.get("decision_refs")
if (
    not isinstance(refs, list)
    or any(type(ref) is not str for ref in refs)
    or set(refs) != _DECISIONS
):
    _fail("terminal-matrix-decision-set")
```

### CR-04: A NUL-bearing manifest path bypasses the closed fixture-path failure

**File:** `scripts/check_phase2_provenance.py:392-396,404-430,995-1002`
**Issue:** `_require_string` accepts a JSON path containing `\u0000`, after which `Path.resolve()` raises `ValueError: lstat: embedded null character in path`. That operation occurs before the guarded `read_bytes` block, so the value bypasses `missing-fixture`/`fixture-path-escape` and escapes `main` as a raw traceback. I reproduced both the direct `_safe_fixture_path` and CLI propagation paths. This leaves the earlier fixture-path diagnostic closure incomplete for a valid JSON string.

**Fix:** Reject NUL and other invalid path scalars before filesystem resolution, and translate `resolve()` failures outside the active handler to one constant fixture-path code. Add a manifest-level direct test and a real `main` test with `fixture-secret-canary\u0000.sse`, asserting exact one-line stderr, no canary, and no cause/context.

```python
if "\0" in relative:
    _fail("invalid-fixture-path")
failed = False
try:
    path = (version_root / relative).resolve()
except (OSError, RuntimeError, ValueError):
    failed = True
    path = version_root
if failed:
    _fail("invalid-fixture-path")
```

---

_Reviewed: 2026-07-17T01:12:04Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
