---
phase: 02-conversation-event-contract
reviewed: 2026-07-16T22:15:06Z
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
  critical: 3
  warning: 0
  info: 0
  total: 3
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-07-16T22:15:06Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found

## Summary

The externally expected release/commit now flows through detached-tree `HEAD`, manifest identity, entry identity, source references, and fixture hashes. That closes the original CR-01 identity-spoofing reproduction. The original CR-02 empty/self-attested evidence reproduction is also rejected, but CR-02 is not fully closed: the replacement byte normalizer collapses duplicate approved JSON members and can certify bytes that the public client rejects. Two additional provenance-contract gaps remain: newer evidence roles are not enforced, and several `ProvenanceError` messages interpolate editor-controlled values despite the input-independent error contract.

The focused provenance suite passes (14 tests) and Ruff is green, but neither result covers the three adversarial reproductions below.

## Prior Finding Re-evaluation

- **Prior CR-01 — CLOSED.** `_verify_release_manifest` supplies external identity, `_verify_fixture_entry` rejects release/commit mismatches, `_verify_source_tree_head` checks the exact Git `HEAD`, and source references receive the external commit rather than the entry's claim.
- **Prior CR-02 — NOT CLOSED.** Missing/empty/stale newer evidence and declaration-only equivalence are now rejected, but actual newer bytes with duplicate approved members are normalized differently from the public client and can still pass as identical.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Newer compatibility collapses duplicate approved JSON members that the client rejects

**File:** `scripts/check_phase2_provenance.py:462-469,700-747`
**Issue:** `_json_object` uses ordinary `json.loads`, so repeated JSON member names are collapsed before `_normalize_tool_events` and `_normalize_terminal_fixture` compute compatibility. The production decoder deliberately preserves object pairs and rejects duplicate `toolCallId`, `tool`, `status`, root `hermes`, choice `finish_reason`, and approved lifecycle fields in `protocol.py:149-259`. I reproduced the mismatch with a fully validated simulated newer release by changing the length fixture from `"partial": true` to `"partial": false, "partial": true`, updating its manifest SHA-256, and leaving all release, commit, source-anchor, and inventory checks valid. `_verify_newer_release` accepted the release as equivalent, while `async_decode_hermes_sse` rejected the same bytes with `HermesProtocolError`. Thus behaviorally incompatible evidence can still satisfy the D-15/D-16 gate, so the prior CR-02 remains blocking.

**Fix:** Parse lifecycle fixture JSON with duplicate-preserving pairs and apply the same approved-path duplicate rules as the public decoder before normalization. Prefer extracting/reusing one pure pair-aware projection/normalization boundary rather than maintaining a second permissive parser. Add adversarial tests for duplicate tool fields, root `hermes`, choice `finish_reason`, and each approved lifecycle field where the last value would otherwise preserve the canonical normalized event.

```python
value = json.loads(data, object_pairs_hook=_json_object_pairs_hook)
projected = _project_chat_chunk_object(value)
if projected is None:
    _fail("invalid-lifecycle-fixture")
```

### CR-02: Newer lifecycle evidence kinds are accepted without the required role mapping

**File:** `scripts/check_phase2_provenance.py:407,750-755,807-839`
**Issue:** `_verify_fixture_entry` only requires `evidence_kind` to be a non-empty string. `_normalize_lifecycle_events` requires the five paths but never compares their kinds with `_EXPECTED_KINDS`; `_verify_scope` checks those kinds only for canonical entries after newer-release verification. I reproduced a passing newer release after changing `chat_completions/tool_progress_pair.sse` from `tag-source-derived` to `editor-invented`. This violates D-14's truthful captured-versus-derived provenance and Plan 02-05's requirement that canonical and newer inventories cover the same required evidence roles. The aggregate `latest_evidence.evidence_kind` cannot authenticate each entry's evidence class.

**Fix:** Validate every required lifecycle path and its exact expected evidence kind inside the release-agnostic manifest/normalization path for both canonical and newer releases. Add negative tests for an unknown kind and for swapping `tag-source-derived` with `design-derived` while hashes, anchors, and bytes remain valid.

```python
for path, expected_kind in _EXPECTED_KINDS.items():
    entry = entries.get(path)
    if entry is None or entry.get("evidence_kind") != expected_kind:
        _fail("lifecycle-evidence-role-mismatch")
```

### CR-03: Provenance failures expose editor-controlled manifest values

**File:** `scripts/check_phase2_provenance.py:310-341,384-424,629-695`
**Issue:** `ProvenanceError` is documented and planned as input-independent, but multiple failure paths interpolate fixture paths, source paths/ranges, and design-matrix case IDs. I reproduced `missing-fixture:provenance-secret-canary.sse` by supplying that manifest path. A malicious or accidentally sensitive manifest value therefore reaches CLI stderr through `main`, and newline-bearing values can also forge multi-line diagnostics. Plan 02-05 explicitly required preserving input-independent errors, but `tests/test_phase2_provenance.py` checks only exception type and contains no canary/traceback assertions for this boundary.

**Fix:** Replace value-bearing failures with closed constant codes, clear cause/context when translating lower-level failures, and add parameterized canary tests over fixture path, source path, and case ID that inspect `str`, `repr`, args, formatted traceback, cause/context, and CLI stderr.

```python
except OSError:
    _fail("missing-fixture")
if entry.get("sha256") != hashlib.sha256(payload).hexdigest():
    _fail("fixture-hash-mismatch")
```

---

_Reviewed: 2026-07-16T22:15:06Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
