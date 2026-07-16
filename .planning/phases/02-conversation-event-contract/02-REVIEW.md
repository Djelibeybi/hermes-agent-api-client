---
phase: 02-conversation-event-contract
reviewed: 2026-07-16T21:11:00Z
depth: deep
files_reviewed: 16
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
  - tests/test_protocol.py
  - tests/test_sse.py
  - tests/test_transport.py
findings:
  critical: 2
  warning: 0
  info: 0
  total: 2
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-07-16T21:11:00Z
**Depth:** deep
**Files Reviewed:** 16
**Status:** issues_found

## Summary

The public event vocabulary, duplicate-aware projections, total terminal matrix, and delayed-terminal call chain are internally consistent with D-01 through D-12. The targeted protocol, SSE, and transport suite passes (446 tests), and Ruff reports no findings. However, the new provenance verifier does not establish the source identities it claims to verify. Both defects can let edited or future evidence assert compatibility with a release that was never actually checked, defeating the D-14 through D-16 evidence boundary.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Fixture source identity is not bound to the source tree being verified

**File:** `scripts/check_phase2_provenance.py:313-340`
**Issue:** `_verify_fixture_entry` reads each fixture's `hermes_release` and `source_commit`, but never requires them to equal the canonical release/commit or the commit checked out in `source_root`. `_verify_structured_source_ref` only checks that a source reference repeats the entry's claimed commit, while `_verify_scope` always supplies a tree fetched from `_CANONICAL_COMMIT` (lines 567-574). As a result, an entry can replace its release, commit, source-reference commits, and URLs with an arbitrary value while retaining hashes of lines from the canonical tree, and the verifier accepts it. This was reproduced in-memory with the terminal-length entry: changing its identity to `v9999.0` / forty zeroes still produced `accepted-mismatched-fixture-identity`. The gate therefore permits false provenance, contrary to D-14.
**Fix:** Pass the expected release and checked-out commit explicitly into `_verify_fixture_entry`, reject any entry identity that differs, and verify `git rev-parse HEAD` for the supplied source tree before validating anchors. Add a negative test that mutates all mutually reinforcing identity fields together and proves rejection.

```python
def _verify_fixture_entry(
    entry: Mapping[str, Any],
    version_root: Path,
    source_root: Path,
    *,
    expected_release: str,
    expected_commit: str,
) -> None:
    release = _require_string(entry.get("hermes_release"), "fixture-release")
    commit = _require_string(entry.get("source_commit"), "fixture-commit")
    if release != expected_release:
        _fail("fixture-release-mismatch")
    if commit != expected_commit:
        _fail("fixture-commit-mismatch")
    if _run_git("rev-parse", "HEAD", cwd=source_root).strip() != expected_commit:
        _fail("fixture-source-tree-mismatch")
```

### CR-02: Newer-release compatibility is accepted from self-attested JSON

**File:** `scripts/check_phase2_provenance.py:175-228`
**Issue:** `_verify_newer_release` validates declarations inside `latest_evidence`, then only checks that `{fixture_root}/provenance.json` exists. It never loads that manifest, checks its hashes, validates its fixture entries/source anchors against `latest_commit`, or derives normalized public events from the actual newer fixture bytes. The `normalized_public_events` comparison is merely equality between two editor-controlled mappings in the canonical manifest. When a newer tag appears, a manifest can therefore claim `public_semantics: identical` and provide two identical invented mappings while the actual newer evidence is missing, stale, or behaviorally incompatible. That makes the D-15/D-16 compatibility checkpoint non-verifying on the exact branch where it matters.
**Fix:** Fetch and detach the newer source tree at `latest_commit`; load the newer provenance manifest; bind every fixture entry to `latest` and `latest_commit`; validate fixture hashes and source anchors against that tree; and compute the normalized public event sequence from the validated fixture bytes. Compare those computed events to the canonical computed events instead of trusting declared mappings. Add a negative test where the declarations say `identical` but a newer fixture or hash differs.

```python
newer_provenance = _load_object(newer_manifest)
if newer_provenance.get("hermes_release") != latest:
    _fail("newer-manifest-release-mismatch")
if newer_provenance.get("source_commit") != latest_commit:
    _fail("newer-manifest-commit-mismatch")

source_root, temporary = _fetch_source_tree(latest_commit)
try:
    entries = _verify_all_entries_for_release(
        newer_provenance,
        source_root,
        expected_release=latest,
        expected_commit=latest_commit,
    )
    newer_events = _normalize_verified_fixtures(entries)
finally:
    temporary.cleanup()
if newer_events != canonical_events:
    _fail("newer-tag-public-events-differ")
```

---

_Reviewed: 2026-07-16T21:11:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
