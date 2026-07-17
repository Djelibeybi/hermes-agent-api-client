---
phase: 02-conversation-event-contract
reviewed: 2026-07-17T02:09:13Z
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
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 2: Code Review Report

**Reviewed:** 2026-07-17T02:09:13Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** clean

## Summary

The four findings from the prior deep report are closed by `865bf19`, and `9234be0` records the implemented behavior accurately. The new verifier helpers preserve finite diagnostics, validation-before-cleanup precedence, and cleanup ownership across failed fetch initialization, canonical/newer comparison, and both CLI scopes. No ordinary Python correctness regression was found in the new call chains.

All reviewed files meet quality standards. No issues found.

## Prior Finding Re-evaluation

- **Oversized numeric tags and legacy ranges — CLOSED.** Regex-valid 5,000-digit release components now produce `invalid-numeric-release-tag`; 5,000-digit legacy line anchors produce `invalid-source-line-anchor`. Conversion occurs inside guarded blocks, and failures are classified only after leaving the active handler.
- **Deep parser-valid matrix metadata — CLOSED.** `_contains_none` now uses an iterative exact-built-in `dict`/`list` traversal. Five-hundred-level metadata with and without null reaches the intended finite matrix result instead of consuming Python call frames.
- **Unicode subprocess output — CLOSED.** `_run_git` classifies `UnicodeError` with `OSError` as `latest-tag-verification-blocked`; direct errors have one closed argument and the CLI emits exit 3 with one closed stderr line.
- **Temporary-directory lifecycle — CLOSED.** Creation failure, fetch-initialization failure, cleanup-only failure, and validation-plus-cleanup failure all release ownership through the new helpers. An already-selected validation error is re-raised ahead of cleanup failure; cleanup alone maps to `latest-tag-verification-blocked`.

## RED/GREEN Verification

I replayed the six representative boundaries against `865bf19^`. The pre-fix implementation propagated raw `ValueError` for both oversized conversions, raw `RecursionError` for deep matrix traversal, raw `UnicodeDecodeError` for Git output, raw `OSError` for temporary creation, and cleanup `OSError` in place of an already-selected `ProvenanceError`. These are the intended RED failure modes introduced by `19cce6c`.

On the current implementation, the 19 focused totality regressions pass. Their direct and `main()` assertions cover exact finite codes, exit 1 versus exit 3, absent cause/context and canaries, cleanup execution, and validation-error precedence.

## Narrative Findings (AI reviewer)

No Critical, Warning, or Info findings remain in the reviewed scope.

## Regression Evidence

- Exact five-test-file scope: 577 passed without coverage instrumentation.
- Focused totality regressions: 19 passed, 64 deselected.
- Ruff formatting and lint for the changed verifier/test files: passed.
- Repository-configured basedpyright: 0 errors, 0 warnings, 0 notes.
- No package source, public export, immutable fixture, helper, or non-provenance test changed after `aeab137`; public SSE protocol classification and cleanup regressions remain green in the scoped suite.

---

_Reviewed: 2026-07-17T02:09:13Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
