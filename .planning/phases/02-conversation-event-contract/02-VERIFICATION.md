---
phase: 02-conversation-event-contract
verified: 2026-07-17T03:09:07Z
status: passed
score: 22/22 must-haves verified
behavior_unverified: 0
overrides_applied: 0
freshness_refresh:
  previous_status: stale
  trigger: signed-history rewrite and summary task-hash refresh
  source_test_fixture_dependency_diff: none
  uat: 24/24 passed
  live_provenance_scopes: passed
re_verification:
  previous_status: gaps_found
  previous_score: 11/12
  gaps_closed:
    - "Newer-release normalization now preserves JSON pairs and reuses the production approved-path projectors before computing compatibility."
    - "Every required lifecycle path now enforces its exact tag-source-derived or design-derived evidence role in release-agnostic verification."
    - "Provenance failures now use closed constant diagnostics with no editor-controlled values, cause, or context across direct and CLI paths."
  gaps_remaining: []
  regressions: []
---

# Phase 2: Conversation Event Contract Verification Report

**Phase Goal:** Python consumers receive immutable, bounded tool-progress and terminal events whose wire mapping is ordered, strict, ambiguity-free, and secret-safe.
**Verified:** 2026-07-17T03:09:07Z
**Status:** passed
**Re-verification:** Yes - after Plans 02-05 and 02-06 gap closure and post-review hardening

**Freshness refresh:** The signed-history rewrite changed commit identities only, and the six summaries were mechanically updated to reference those rewritten task hashes. `git diff 2c622805..f0f4b39 -- src tests scripts pyproject.toml uv.lock` is empty. The completed UAT records 24/24 passes; its signed commit reran and passed lock validation, Ruff, basedpyright, verifytypes, the 635-test 100%-coverage suite, distribution build, and standalone distribution verification. Both live provenance scopes were rerun against the official tag gate and passed. Dependency currency was also rechecked: only the already-deferred Phase 4 updates for prek 0.4.10 and Ruff 0.15.22 remain.

## Goal Achievement

All five roadmap success criteria, every Phase 2 PLAN frontmatter truth, all eleven Phase 2 requirements, and the three prior provenance gaps are verified against the current implementation and tests. The later review-derived exception boundaries are also exercised: recursive and oversized JSON, malformed/deep matrices, oversized decimal conversion, Unicode Git output, invalid/NUL paths, public SSE failure taxonomy, and temporary-directory setup/cleanup precedence.

### Observable Truths

The 22 rows below are the deduplicated union of ROADMAP success criteria and all six PLAN `must_haves.truths` blocks. Roadmap wording takes precedence where it overlaps a plan truth.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Consumers can import the closed tool-progress and terminal-failure enums from the package root. | VERIFIED | `models.py:32-45`; explicit imports and `__all__` in `__init__.py`; package tests pass; verifytypes reports 100% completeness. |
| 2 | Direct tool-event construction accepts only exact built-in 1-256 character visible-ASCII identifiers and strict running/completed enum values. | VERIFIED | Shared value-free validator at `models.py:47-58`, field use at `models.py:93-103`, and direct bounds/type/immutability tests in `test_protocol.py`. |
| 3 | Public tool events, private tool wire validation, SSE construction, and existing assertions transition coherently. | VERIFIED | `_ToolProgressWire` reuses `_require_lifecycle_text`; `sse.py:168-190` explicitly constructs `ToolProgressStatus`; artifact/key-link query passes all Plan 02-01 links. |
| 4 | `TerminalEvent` remains immutable with strict `partial=False` and `failure_reason=None` defaults. | VERIFIED | `models.py:118-123`; direct construction, exact-type, enum, default, and frozen-model tests pass. |
| 5 | Every lifecycle fixture has immutable source identity, truthful evidence kind, semantic assertions, reproduction metadata, and a matching SHA-256. | VERIFIED | Live verifier scopes pass; canonical manifest schema 3 contains exact release/commit and five exact lifecycle roles/hashes; source-anchor and hash checks are implemented in `check_phase2_provenance.py:381-529`. |
| 6 | Canonical `v2026.7.7.2` and the latest numeric Hermes tag are verified before evidence is accepted. | VERIFIED | Both live scopes re-enumerated official tags and passed; manifest records canonical/latest `v2026.7.7.2`, peeled commit `9de9c25f...`, and `canonical-current`. |
| 7 | Tag-source-derived and design-derived evidence are never represented as live captures. | VERIFIED | `_EXPECTED_KINDS` defines four `tag-source-derived` roles and one `design-derived` role; `live_server_invoked` must be false; manifest inspection and role-forgery tests pass. |
| 8 | Accepted tool progress records become ordered immutable events with exact call ID, name, and closed status, preserving repeats and interruption prefixes. | VERIFIED | `sse.py:168-190`; fixture/order/interleaving/repetition/interruption tests pass in the 635-test suite. |
| 9 | Missing, malformed, unknown, over-bound, and duplicate approved tool fields fail closed before dictionary collapse. | VERIFIED | Pair node and tool projection at `protocol.py:124-236`; raw duplicate-member, exact-bound, wrong-type, unknown-status, recursive, and oversized-JSON tests pass. |
| 10 | Repeated lifecycle facts remain observable, while additive/raw tool data never enters public values, failures, traceback locals, or retained decoder state. | VERIFIED | Projection copies only three approved fields; raw-payload secrecy, additive-duplicate compatibility, generator-state, and interruption tests pass. |
| 11 | Normal stop, truncation, agent error, and bounded unknown safe codes map only through the locked total terminal matrix. | VERIFIED | Total mapper at `sse.py:102-162`; exhaustive matrix and immutable-fixture tests pass. |
| 12 | `finish_reason=length` accepts only D-02 rows and always exposes `LENGTH`, `partial=true`, `OUTPUT_TRUNCATED`. | VERIFIED | `_map_terminal_event` length branch at `sse.py:125-140`; accepted/rejected D-02 matrix tests pass. |
| 13 | `finish_reason=error` requires exact server partial state and maps agent/unknown safe codes to closed failure reasons. | VERIFIED | `_map_terminal_event` error branch at `sse.py:142-162`; exact booleans, omissions, bounds, agent code, and unknown-code tests pass. |
| 14 | Explicit nulls, duplicate approved terminal keys, and every contradictory lifecycle combination fail without precedence guesses. | VERIFIED | Omission-aware `_TerminalMetadata` and pair projection at `protocol.py:130-269`; raw duplicate/null/contradiction and design-matrix tests pass. |
| 15 | Raw upstream error data stays private and terminal events remain pending until suffix validation and cleanup succeed. | VERIFIED | Root `hermes` is sanitized before materialization; `_pending_terminal` gate at `sse.py:253-413`; source/response cleanup integration and canary tests pass. |
| 16 | Disconnects remain transport errors, cancellation remains `CancelledError`, and neither path synthesizes a terminal. | VERIFIED | `async_decode_hermes_sse` cleanup/precedence paths at `sse.py:420-519`; focused transport, cancellation, and cleanup tests pass. |
| 17 | Fixture identity is bound to externally expected release/commit and the exact source-tree HEAD. | VERIFIED | `_verify_fixture_entry` and `_verify_source_tree_head` at `check_phase2_provenance.py:476-529`; identity rewrite and mismatched-HEAD regressions pass. |
| 18 | A newer tag requires a complete validated manifest, lifecycle inventory, bytes, hashes, anchors, and source tree at that tag. | VERIFIED | `_verify_newer_release` and release-manifest validation at `check_phase2_provenance.py:273-379, 970-1010`; missing/stale/mismatched evidence regressions and a complete positive simulated release pass. |
| 19 | Canonical/newer behavior is computed from validated bytes rather than declaration maps. | VERIFIED | Byte-derived normalization at `check_phase2_provenance.py:598-940`; declaration-map mutation and behavior-difference regressions pass. |
| 20 | Newer evidence is normalized only after production-equivalent approved-path duplicate checks accept the raw JSON. | VERIFIED | The verifier imports production `_json_object_pairs_hook` and tool/chat projectors, then uses them at `check_phase2_provenance.py:580-611`; all approved duplicate families reject and an ignored-additive duplicate passes. |
| 21 | Every required canonical/newer fixture path has exactly its D-14 evidence role. | VERIFIED | Exact role gate at `check_phase2_provenance.py:910-917`; unknown and swapped roles for every required path reject. |
| 22 | Provenance failures expose only closed diagnostics and remain exception-total across malformed inputs and temporary-resource failure. | VERIFIED | All `_fail` call sites use string literals; direct/CLI canary tests cover path/source/range/case values, recursive/oversized JSON, malformed/deep matrices, oversized decimals, Unicode Git output, and temporary setup/cleanup with no cause/context and correct validation-over-cleanup precedence. |

**Score:** 22/22 truths verified (0 present but behavior-unverified)

### Re-verification of Previous Gaps

| Previous Gap | Result | Current Evidence |
|--------------|--------|------------------|
| Duplicate approved members collapsed during newer-release normalization. | CLOSED | Production pair hook and exact tool/chat projectors are reused; all same/conflicting approved duplicate families reject, while ignored additive duplicates remain compatible. |
| Generic newer manifests did not enforce exact evidence roles. | CLOSED | `_normalize_lifecycle_events` checks every `_EXPECTED_KINDS` path before reading bytes; unknown and swapped role matrices pass as negative regressions. |
| Provenance diagnostics leaked editor values and retained exception context. | CLOSED | Closed-code direct and real-CLI tests inspect `str`, `repr`, `args`, formatted traceback, `__cause__`, `__context__`, and stderr. |

No previously verified consumer-facing truth regressed.

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/hermes_agent_api_client/models.py` | Strict immutable public Phase 2 vocabulary | VERIFIED | 132 substantive lines; exact enums, shared validator, frozen event shapes; directly tested and exported. |
| `src/hermes_agent_api_client/__init__.py` | Exact package facade | VERIFIED | Both enums and existing event types are explicitly imported and listed in `__all__`; package tests and verifytypes pass. |
| `src/hermes_agent_api_client/protocol.py` | Pair-preserving approved-path projection and strict DTOs | VERIFIED | 569 substantive lines; pair nodes, exact duplicate paths, omission-aware terminal metadata, recursive materialization, strict private DTOs; wired into SSE and provenance verifier. |
| `src/hermes_agent_api_client/sse.py` | Ordered tool mapping, total terminal mapping, and delayed delivery | VERIFIED | 519 substantive lines; pair-aware load, safe parser taxonomy, explicit mappings, scrubbed state, suffix/source cleanup gate; behavioral tests pass. |
| `scripts/check_phase2_provenance.py` | Release-bound, production-faithful, secret-safe evidence gate | VERIFIED | 1,107 substantive lines; live tag/source verification, manifest/role/hash/anchor checks, byte normalization, finite diagnostics, and temporary ownership are exercised independently. |
| `tests/test_protocol.py` / `tests/test_package.py` | Direct public contract and exact exports | VERIFIED | Substantive direct-construction, enum, strictness, frozen, union, export, and installed metadata coverage. |
| `tests/test_sse.py` / `tests/test_transport.py` | Wire matrix, secrecy, ordering, taxonomy, and cleanup integration | VERIFIED | Substantive raw-byte duplicate, matrix, lifecycle, canary, cancellation, transport, response cleanup, recursive/oversized input coverage. |
| `tests/test_phase2_provenance.py` | Adversarial evidence-boundary regressions | VERIFIED | 1,580 substantive lines using isolated roots and real temporary Git repositories; covers all prior and post-review gaps. |
| Canonical lifecycle fixtures and `provenance.json` | Immutable current-tag evidence with exact roles and hashes | VERIFIED | All five required fixtures exist; live release/tool and terminal scopes validate them against the official tag/source tree. |
| `tests/fixtures/hermes/{observed-latest-tag}/...` | Conditional D-16 alternate evidence root | NOT APPLICABLE | Live verification confirms the latest numeric tag is the canonical tag; Plan 02-02 explicitly makes this artifact conditional. |

Automated artifact queries passed 23/24 declared paths. The sole mechanical miss is the literal conditional placeholder above and is not a gap under the plan's activation rule.

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Public models | Package root | Explicit imports and `__all__` | WIRED | Export and star-import tests pass. |
| Public lifecycle validator | Private tool DTO | Shared `_require_lifecycle_text` | WIRED | One exact boundary serves direct and wire construction. |
| SSE decoder | Protocol pair/projector seam | `object_pairs_hook` plus event-specific projectors | WIRED | Duplicate evidence is checked before ordinary containers reach DTO validation. |
| Protocol terminal metadata | SSE total mapper | Sanitized omission-aware `_TerminalMetadata` | WIRED | Only bounded lifecycle facts reach public mapping. |
| Pending terminal | Source/HTTP cleanup | Decoder finalization plus outer response scope | WIRED | Terminal-after-cleanup integration test passes. |
| Canonical manifest | Detached source tree and fixture bytes | External identity, HEAD, source anchors, SHA-256 | WIRED | Live scopes and adversarial identity tests pass. |
| Newer evidence | Canonical behavior | Validated byte-derived normalized lifecycle tuples | WIRED | Complete positive and all negative future-tag simulations pass. |
| Provenance normalizer | Production ambiguity contract | Private pair hook and exact tool/chat projectors | WIRED | All approved duplicate families and additive control pass. |
| Provenance failures | CLI and traceback boundary | Closed literal codes and context-free translation | WIRED | Direct and executable canary/totality matrices pass. |

The GSD key-link query independently reports all 19 declared links verified across Plans 02-01 through 02-06.

## Data-Flow Trace (Level 4)

No Phase 2 artifact renders dynamic UI data, so the UI-specific Level 4 trace is not applicable. The equivalent protocol flow was traced end to end:

`untrusted SSE bytes -> bounded framing -> pair-preserving JSON -> approved-path projection -> strict private DTO -> explicit immutable public event -> pending terminal -> suffix/source/HTTP cleanup -> consumer`.

The provenance flow is:

`live tag/peeled commit -> detached source HEAD -> manifest identity -> entry role/identity -> source anchors and fixture hashes -> pair-aware byte normalization -> canonical/newer event comparison`.

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full contract and regression suite | `uv run --no-sync pytest -q` | Completed successfully; coverage database reports 1,168/1,168 statements and 348/348 branches; 635 tests collected | PASS |
| Focused provenance plus public lifecycle boundaries | `pytest tests/test_phase2_provenance.py` plus named SSE/transport duplicate, secrecy, oversized-integer, cleanup, and cancellation tests | Completed successfully | PASS |
| Canonical release/tool evidence | `uv run --no-sync python scripts/check_phase2_provenance.py --scope release-and-tool` | `phase2-provenance-ok:release-and-tool` | PASS |
| Canonical terminal evidence | `uv run --no-sync python scripts/check_phase2_provenance.py --scope terminal` | `phase2-provenance-ok:terminal` | PASS |
| Formatting and lint | `ruff format --check .`; `ruff check .` | 16 files formatted; all checks passed | PASS |
| Static typing | `basedpyright`; `basedpyright --verifytypes hermes_agent_api_client --ignoreexternal` | 0 diagnostics; 100% type completeness | PASS |
| Compilation | `python -m compileall -q src scripts tests` | Exit 0 | PASS |
| Isolated build/distribution | `uv build --out-dir <temporary>` then `scripts/verify_dist.py` | Wheel and sdist built; distribution verification passed | PASS |

## Probe Execution

No `probe-*.sh` file is declared by this phase. The two committed executable evidence gates required by the plans were run directly and both passed, as recorded above.

## Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| TOOL-01 | 02-01 | SATISFIED | Closed imports, strict immutable model construction, exact bounds/types, and package facade pass. |
| TOOL-02 | 02-01, 02-02, 02-03, 02-05, 02-06 | SATISFIED | Exact correlation, order, repeats, interruption observability, evidence identity, and live fixture gate pass. |
| TOOL-03 | 02-03, 02-06 | SATISFIED | Missing/malformed/unknown/bounds and every approved duplicate family fail as protocol/provenance input; additive duplicate control passes. |
| TOOL-04 | 02-03, 02-06 | SATISFIED | Raw/additive data and malformed-input canaries are absent from values, failures, traceback state, and retained decoder state. |
| TERM-01 | 02-01 | SATISFIED | Closed failure enum and strict immutable terminal defaults pass. |
| TERM-02 | 02-02, 02-04, 02-05, 02-06 | SATISFIED | Total normal-stop matrix and evidence normalization pass. |
| TERM-03 | 02-02, 02-04, 02-05, 02-06 | SATISFIED | Total truncation matrix maps exact public metadata. |
| TERM-04 | 02-02, 02-04, 02-05, 02-06 | SATISFIED | Exact server partial and agent/unknown safe-code mapping pass. |
| TERM-05 | 02-02, 02-04, 02-05, 02-06 | SATISFIED | Explicit null, duplicate, contradiction, exact evidence-role, and production-equivalent normalization matrices pass. |
| TERM-06 | 02-02, 02-04 | SATISFIED | Raw errors remain private; disconnect/cancellation taxonomy and no-synthetic-terminal behavior pass. |
| TERM-07 | 02-04 | SATISFIED | Terminal remains withheld through suffix validation and source/response cleanup. |

No Phase 2 requirement is orphaned. Phase 3 session-header requirements and Phase 4 combined distribution/dependency requirements remain correctly deferred and do not conceal a Phase 2 gap.

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| Phase-owned source and tests | TODO/FIXME/XXX/HACK/PLACEHOLDER or unimplemented marker | None | No matches. |
| `scripts/check_phase2_provenance.py` | Dynamic/value-bearing `_fail(...)` argument | None | Every call site supplies a finite string literal. |
| Phase-owned dependency/fixture contract | Unexpected dependency, lock, immutable fixture, or public-export drift during re-verification | None | `git diff` is empty for protected files; verification changed only this report. |

## Human Verification Required

None. All roadmap and plan truths are programmatically observable, and every behavior-dependent ordering, cancellation, cleanup, and failure-boundary invariant has passing behavioral tests.

## Gaps Summary

No gaps remain. The original release-evidence trust defects and all later review-derived malformed-input/cleanup defects have permanent regressions. Phase 2 achieves its goal and is ready to proceed.

---

_Verified: 2026-07-17T02:20:46Z_
_Verifier: the agent (gsd-verifier)_
