---
phase: 2
reviewers: [claude, opencode]
reviewed_at: 2026-07-16T19:28:37Z
plans_reviewed:
  - 02-01-PLAN.md
  - 02-02-PLAN.md
  - 02-03-PLAN.md
  - 02-04-PLAN.md
---

# Cross-AI Plan Review — Phase 2

## Claude Review

**CLI:** Claude Code 2.1.211  
**Model:** `claude-opus-4-8`

# Cross-AI Plan Review — Phase 2: Conversation Event Contract

## 1. Summary

The four plans encode a genuinely strong design: evidence is frozen before mapping code exists, the duplicate-rejection policy is path-scoped rather than global, the exact-`str` validator correctly compensates for a real Pydantic strictness hole, and the delayed-terminal commit is enriched in place rather than relocated. Every claim I traced about the existing seams (`_pending_terminal`, `scrub()`, input-free sentinels, `extra="ignore"`) checks out against source. The plans are, however, undermined by one concrete sequencing defect and one mechanical defect. Plan 02-01 makes `ToolProgressEvent.tool_call_id` required and `status` a strict enum while excluding `sse.py` and `tests/test_sse.py` from its `files_modified` — the only construction site (`sse.py:106`) and two test assertions still use the old shape, so Wave 1 leaves the tree red and 02-01 cannot satisfy its own end-of-wave `pytest -q` gate. Separately, both of Plan 02-02's `<automated>` gates contain literal `&gt;` HTML entities and are unrunnable as written, which matters because they are the *only* machine enforcement of D-13 through D-16. Both are fixable without redesign.

## 2. Strengths

**Evidence gate precedes implementation, and derivation is enforced per-path, not per-plan.** Plan 02-02 sits in Wave 1 so that 02-03 and 02-04 consume hash-linked fixtures. Its Task 2 gate maps each path to an expected kind explicitly (`{"chat_completions/terminal_length.sse": "tag-source-derived", …, "terminal_design_matrix.json": "design-derived"}`) and asserts `set(entries)==set(expected)`, so a design-derived row cannot be laundered as a capture. This extends a pattern that already exists — `tests/fixtures/hermes/v2026.7.7.2/provenance.json:70` records `"evidence_kind": "synthetic-derived"` and line 83 records `"live_server_invoked": false` for the existing `complete.sse`.

**The plans target the actual leak seams, not plausible-looking ones.** Every integration point 02-03/02-04 names is real: `_load_json_safely` at `sse.py:73-78` is exactly where duplicate evidence dies (`json.loads(data)` with no hook); `_parse_tool_progress`/`_parse_chat_chunk` at `protocol.py:378-395` already reduce `ValidationError` to `None`; `_raise_protocol_failure` at `sse.py:46-48` already raises from a raw-record-free frame; and `_SSEDecoder.scrub()` at `sse.py:177-184` already clears `_pending_terminal`. The plans extend these rather than inventing parallel machinery.

**The delayed-terminal guarantee is enriched, not moved.** 02-04's instruction to "enrich only the TerminalEvent value stored by `_SSEDecoder._pending_terminal`; do not move finalization or the outer response cleanup gate" matches the real two-stage commit: `_accept_events` (`sse.py:203-216`) stores the terminal instead of yielding it, `finalize()` (`sse.py:308-320`) requires `_pending_terminal is not None`, and `async_decode_hermes_sse` yields it only after `source.aclose()` and the `finally` block (`sse.py:376-426`). The `key_links` pattern `terminal_is_delivered_only_after_response_cleanup` resolves to a real test at `tests/test_transport.py:906` — this is a verified anchor, not a placeholder.

**The Pydantic strict-string hole is correctly identified and centralised.** `models.py:12` sets `ConfigDict(frozen=True, strict=True)`, which per the research probe still accepts a `str` subclass. 02-01 requires one private `_require_lifecycle_text` that first checks `type(value) is str`, reused by 02-03's wire DTOs — the correct structural answer to D-08's public/wire parity requirement, rather than duplicating rules at two boundaries.

**Duplicate policy is scoped correctly.** 02-03's explicit "do not globally reject duplicate additive data" preserves D-12 and keeps the `extra="ignore"` forward-compatibility contract at `protocol.py:180` intact. A global reject-all-duplicates hook would have been the obvious wrong turn.

## 3. Concerns

### HIGH — Plan 02-01 leaves Wave 1 red; its own verification gate cannot pass

`src/hermes_agent_api_client/models.py:64-68` currently declares:

```python
class ToolProgressEvent(_FrozenModel):
    tool_name: str
    status: str
```

Plan 02-01 makes `tool_call_id` required and `status: ToolProgressStatus` under `strict=True`. Its `files_modified` lists only `models.py`, `__init__.py`, `tests/test_protocol.py`, `tests/test_package.py`. But three construction sites outside that set use the old shape:

- `src/hermes_agent_api_client/sse.py:106` — `return (ToolProgressEvent(tool_name=progress.tool, status=progress.status),)`, where `progress.status` is a plain `str` from `_ToolProgressWire` (`protocol.py:232-235`). Under strict mode a raw string is rejected for an enum field, and `tool_call_id` is simply absent. This call is **not** inside a `try`, so the `ValidationError` escapes `_decode_application_record` as an unhandled exception rather than reducing to the safe `None` sentinel.
- `tests/test_sse.py:492` and `tests/test_sse.py:567` — both assert `ToolProgressEvent(tool_name="home_assistant", status="running")`, including the canonical golden-order test `test_composite_golden_emits_one_success_in_closed_event_order`.

Plan 02-01's `<verify>` runs only `pytest tests/test_protocol.py tests/test_package.py`, which passes and masks the breakage. Its `<verification>` block then says "Run `uv run --no-sync pytest -q` at the end of Wave 1 so the 100% branch gate covers the new public paths" — that run will fail, and no plan owns the fix until 02-03 in Wave 2. This directly contradicts 02-01's own acceptance criterion, "Existing direct model construction, union membership, frozen-model, and package export tests remain green."

A knock-on effect: 02-03's RED gate says `pytest tests/test_sse.py` "must fail for contract behavior." With the suite already red from Wave 1, RED is unfalsifiable — the executor cannot distinguish "my new test failed correctly" from "the tree was already broken."

### HIGH — Plan 02-02's only machine gates are unrunnable as written

Both `<automated>` commands contain literal HTML entities. From `.planning/phases/02-conversation-event-contract/02-02-PLAN.md:94` and `:119`:

```
len(latest_evidence["source_refs"])&gt;0
len(entry["semantic_assertions"])&gt;0
```

Passed to `python -c`, `&gt;` is a `SyntaxError`; passed through zsh unquoted, `&` would background the command. These two commands are the sole enforcement of the entire D-13/D-14/D-15/D-16 evidence contract. An autonomous executor hitting a `SyntaxError` on a ~3,000-character one-liner is likely to hand-repair it under time pressure — silently weakening the gate it was meant to be blocked by. The one-liner's length is itself the root cause; it should be a committed script.

### MEDIUM — Plan 02-03 under-specifies what happens to non-lifecycle chat paths under the pairs hook

`sse.py:110` feeds the whole parsed document to `_parse_chat_chunk`, which validates a nested tree: `_ChatChunkWire.choices: list[_ChoiceWire]` → `_ChoiceWire.delta: _DeltaWire` → `_DeltaWire.role/content`, plus `_UsageWire` (`protocol.py:237-255`). If `object_pairs_hook` returns `_JsonObjectPairs` for *every* object, then `delta`, `usage`, and each choice stop being mappings and Pydantic rejects them — breaking every currently-green chat test, including `test_additive_application_fields_are_ignored_at_every_wire_level` (`tests/test_sse.py:576-600`).

02-03 names the approved projections (`toolCallId`/`tool`/`status`; root `hermes`; the single choice's `finish_reason`) but never states how unapproved subtrees get materialised back into ordinary `dict`/`list` (last-wins) for DTO validation. The plan's `contains` check for `protocol.py` is just `_JsonObjectPairs`, which doesn't force the executor to confront this.

### MEDIUM — the D-16 newer-tag branch is accepted by the gate but has no implementation plan

The gate permits a compatible newer tag correctly — `assert (latest==canonical and disposition=="canonical-current") or (latest!=canonical and newer_ok)`, where `newer_ok` demands `identical-public-semantics`, `evidence_kind: immutable-tag-capture`, commit-pinned `source_refs`, non-empty reproduction/semantic assertions, `live_server_invoked is False`, and per-path SHA-256 under that tag's own root. Ambiguous or incompatible shapes fail the assert and block. That logic is sound.

But two gaps follow:

1. **`public_semantics: identical` is an unvalidated self-assertion.** No field requires the executor to record *what* differed, and nothing cross-checks the claim against the tagged handler. A careless executor writes `"identical"` and the gate passes.
2. **Plan 02-04 has no tasks for the newer-tag branch.** It says only "proceed only with its exact version-specific evidence-backed projection under D-16" — no tasks, no design for dual-envelope decoding, and no newer-tag fixture root in `files_modified`. If a newer tag lands during implementation, 02-04 is unexecutable as written, and an `autonomous: true` plan is the wrong place to improvise a contract decision.

### MEDIUM — Plan 02-02 has no offline disposition despite depending on the network

Task 1's gate shells out to `git ls-remote`. `02-RESEARCH.md` ("Environment Availability") explicitly states the correct behaviour: "If network later fails, use the pinned local fixture/commit only and report latest-tag verification blocked; do not guess." The plan carries no such branch — a network failure surfaces as a bare `CalledProcessError` with no instruction. For an `autonomous: true` plan, the blocked outcome should be named.

### LOW — `source_refs` validation is weaker than it reads

The check is `ref.startswith(source_repo+"/blob/") and commit in ref`. That pins the commit but accepts any path and any (or no) line anchor, and never fetches the URL. `.../blob/<commit>/nonexistent.py` passes. This is acceptable for an offline gate, but the plans' language ("machine-verifies canonical release/source identities") overstates what is actually proven.

### LOW — Plan 02-02 writes outside its declared `files_modified` on the newer-tag path

The gate requires `path.startswith("tests/fixtures/hermes/" + latest + "/")`, but `files_modified` and the "New fixture paths" section list only `v2026.7.7.2` paths.

### LOW — Plan 02-04's D-03 RED row never names the outcome

The RED text says an absent or `agent_error` code "maps AGENT_ERROR" and another bounded code "maps UNKNOWN", but never states `TerminalOutcome.UPSTREAM_ERROR`. Both the design spec (`docs/superpowers/specs/2026-07-17-conversation-contract-design.md:106-107`) and the current mapping (`sse.py:137`) say `UPSTREAM_ERROR`. The acceptance criteria demand "the exact outcome/partial/failure_reason triple", so leaving one leg of the triple implicit in the only place the rows are enumerated is an avoidable ambiguity.

### LOW — D-04 coverage omits `finish_reason`'s own presence semantics

`_ChoiceWire.finish_reason: Literal["stop","length","error"] | None` (`protocol.py:244`) has no default, so an absent `finish_reason` is already a `ValidationError` while explicit `null` is a legal "no terminal yet". 02-04 exhaustively covers null/omission for the approved *metadata* fields but never pins that `finish_reason` itself keeps this asymmetry — the one field where omission and null genuinely differ today.

### LOW — `key_links` target inconsistency

02-03's entry `from: "src/hermes_agent_api_client/sse.py"` / `to: "ToolProgressEvent"` uses a symbol where every other entry across all four plans uses a path.

## 4. Suggestions

1. **Fix the Wave 1 break (choose one):** (a) add `src/hermes_agent_api_client/sse.py` and `tests/test_sse.py` to 02-01's `files_modified`, with a GREEN step that updates `sse.py:106` to `ToolProgressEvent(tool_call_id=progress.tool_call_id, tool_name=progress.tool, status=ToolProgressStatus(progress.status))` and adds `toolCallId` to `_ToolProgressWire` — this pulls a slice of 02-03 forward but makes Wave 1 self-consistent; (b) merge 02-01 into 02-03; or (c) declare Wave 1 intentionally red, delete 02-01's `pytest -q` gate, and move the branch-coverage gate to the end of Wave 2 — but then 02-03's RED gate needs a per-test-name check, not a per-file pass/fail.
2. **Replace both 02-02 one-liners with a committed script.** Add `scripts/check_provenance.py` (or a `tests/test_provenance.py` parameterised over path → expected `evidence_kind`), invoked as `uv run --no-sync python scripts/check_provenance.py`. This removes the entity-escaping failure mode entirely, makes the gate reviewable, and lets Phase 4 re-run it. Fix `&gt;` → `>` regardless.
3. **Add an explicit materialisation step to 02-03's GREEN:** "after duplicate rejection at approved paths, convert every remaining `_JsonObjectPairs` node back to an ordinary `dict` (last-value-wins) and each array to a `list` before `_ChatChunkWire.model_validate`." Add `test_additive_application_fields_are_ignored_at_every_wire_level` (`tests/test_sse.py:576`) to 02-03's `<read_first>` as the named regression anchor.
4. **Harden the D-16 branch:** require a non-empty `release_verification.latest_evidence.difference_summary` recording exactly what changed versus the canonical handler, and convert 02-04's newer-tag path from an inline autonomous decision into a `checkpoint:decision` that stops for a human. A blocking contract decision should not be resolvable by an autonomous executor.
5. **Name the offline outcome in 02-02:** on `git ls-remote` failure, stop and record `compatibility_disposition: latest-tag-verification-blocked`; do not fall back to the pinned commit alone and proceed.
6. **Spell out `TerminalOutcome.UPSTREAM_ERROR`** in 02-04's D-03 RED row, and add one regression row asserting that absent `finish_reason` fails while explicit `null` yields no terminal.

## 5. Risk Assessment

**MEDIUM.**

The contract design is correct and the plans are unusually well-grounded — every mechanism I traced (delayed-terminal two-stage commit, input-free sentinels, scrub paths, `extra="ignore"` tolerance, the Pydantic strict-string hole) exists in source exactly as described, and the D-16 gate genuinely does permit a compatible newer tag while rejecting ambiguous shapes. Phase 3 session headers and Phase 4 dependency work are consistently and explicitly excluded, with `git diff -- pyproject.toml uv.lock` empty enforced as a gate.

The risk is not design risk; it is execution risk from two defects that both fail loudly rather than silently. The Wave 1 break (HIGH-1) will surface immediately as red tests, and the entity-escaped gates (HIGH-2) will surface as a `SyntaxError` — neither can ship undetected. What keeps this at MEDIUM rather than LOW is that both defects arrive at the moment an autonomous executor is most likely to improvise: HIGH-1 gives it a broken tree with no owning plan, and HIGH-2 gives it a broken gate guarding the phase's entire evidence contract. The remaining MEDIUMs (pairs-hook materialisation, the unplanned D-16 branch, the missing offline disposition) are gaps that would each force a mid-execution design decision inside a plan marked `autonomous: true`. Fixing HIGH-1 and HIGH-2 and adding the materialisation step would move this to LOW.

---

## OpenCode Review

**CLI:** OpenCode 1.17.15  
**Model:** `openrouter/z-ai/glm-5.2`

I'll review these plans against the actual repository state. Let me start by exploring the codebase to verify claims.
Now I have sufficient evidence to write the review. Let me verify one more critical claim about the `sse.py` construction path.
# Cross-AI Plan Review: Phase 2 — Conversation Event Contract

## Summary

The four-plan series is well-researched, tightly scoped to D-01–D-16 / TOOL-01–TOOL-04 / TERM-01–TERM-07, and correctly preserves Phase 3 (session headers) and Phase 4 (dependency refresh) as out of scope. Provenance, evidence-gate, and TDD structures are mostly sound. However, **Plan 02-01 has a critical wave-ordering defect**: it changes the `ToolProgressEvent` public contract (adds required `tool_call_id`, switches `status` to a strict enum) without updating `src/hermes_agent_api_client/sse.py:106` or `tests/test_sse.py:492,567`, both of which directly construct the old shape. This makes the Wave 1 full-suite gate (`uv run --no-sync pytest -q`) unachievable as written. Plan 02-02 additionally ships verification commands containing literal HTML entities (`&gt;`) that produce `SyntaxError` when executed. These two defects must be fixed before execution.

---

## Strengths

1. **Evidence gate is faithful to D-15/D-16.** Plan 02-02 Task 1 verification (`02-02-PLAN.md:94`) enumerates numeric tags via `git ls-remote`, peels the canonical tag, records `observed_latest_numeric_tag`/`observed_latest_peeled_commit`, and enforces the exact branch logic: `canonical-current` when latest==canonical, or `identical-public-semantics` with version-specific fixture root + immutable evidence when a newer tag exists. This correctly permits a compatible newer tag while blocking ambiguous shapes.

2. **Provenance per-path evidence kinds are enforced.** Plan 02-02 Task 2 verification (`02-02-PLAN.md:119`) asserts the exact path-to-kind mapping: three SSE paths are `tag-source-derived`, the matrix is `design-derived`. Tag-source entries must carry commit-pinned `source_refs` under `source_repo+"/blob/"` containing the pinned commit; the design-derived entry must carry `decision_refs == {"D-01","D-02","D-03","D-04"}`. `reproduction.configuration.live_server_invoked is False`, non-empty `semantic_assertions`, and matching SHA-256 are all checked per entry.

3. **One shared lifecycle-text validator prevents D-08 drift.** Plan 02-01 `must_haves.key_links` ties `models.py` to `protocol.py` via `_require_lifecycle_text`, and Plan 02-03 reuses it for `_ToolProgressWire`. The existing repository confirms the need: `src/hermes_agent_api_client/protocol.py:232-234` currently has unbounded `_NonEmptyString` for `tool`/`status` with no visible-ASCII or 256-char cap, and `models.py:64-68` has no `tool_call_id` at all.

4. **Pair-aware projection is correctly scoped.** Plan 02-03 `implementation` cites `json.loads(object_pairs_hook=...)` and the `_JsonObjectPairs` wrapper, matching CPython 3.13 semantics. The plan explicitly avoids the anti-pattern of globally rejecting all duplicate names (which would violate D-12 for ignored additive data) and instead projects only approved paths: `toolCallId`/`tool`/`status` for tool records, root `hermes`/`finish_reason` for chat chunks.

5. **Terminal matrix is total, not precedence-based.** Plan 02-04 `behavior` enumerates every D-01/D-02/D-03 combination as parameterized RED rows and rejects every unlisted combination, including the tagged task-exception contradiction (`completed=true` + `failed=true`). This directly satisfies TERM-05 and avoids the Pitfall 5 normalization hazard identified in `02-RESEARCH.md`.

6. **Delayed-terminal commit is preserved.** Plan 02-04 `implementation` says "Enrich only the `TerminalEvent` value stored by `_SSEDecoder._pending_terminal`; do not move finalization or the outer response cleanup gate." The existing `src/hermes_agent_api_client/sse.py:160, 308-320, 376-426` confirms `_pending_terminal`, `finalize()`, and the outer `aclose()`/response-scope gate are the right seam.

7. **TDD plans provide executable RED/GREEN/REFACTOR.** Plans 02-01, 02-03, 02-04 each have explicit RED/GREEN/REFACTOR sections and `verify.automated` commands targeting the touched test files. Plan 02-02 (type `execute`) correctly separates immutable evidence freezing from TDD.

8. **Phase 3/4 boundaries respected.** All four plans explicitly disclaim session headers, dependency pin/lock edits, and distribution changes. Plan 02-02 records the Ruff 0.15.22 / prek 0.4.10 / coverage 7.15.2 / GitPython 3.1.52 currency drift as a Phase 4 obligation only.

---

## Concerns

### HIGH — Plan 02-01 breaks `sse.py` and `tests/test_sse.py` without updating them

**Evidence:**
- `src/hermes_agent_api_client/models.py:64-68` currently defines `ToolProgressEvent(tool_name: str, status: str)` — no `tool_call_id`, `status` is open `str`.
- `src/hermes_agent_api_client/sse.py:106` constructs `ToolProgressEvent(tool_name=progress.tool, status=progress.status)` — no `tool_call_id`, raw string `status`.
- `tests/test_sse.py:492` and `tests/test_sse.py:567` both assert `ToolProgressEvent(tool_name="home_assistant", status="running")`.
- `tests/test_protocol.py:732` also constructs `ToolProgressEvent(tool_name="home_assistant", status="running")`.

**Plan 02-01 `must_haves.truths`** requires: "Direct `ToolProgressEvent` construction accepts only exact built-in 1-256 character visible-ASCII identifiers and the closed running/completed status enum." The `implementation` section adds `tool_call_id` and makes `status` a strict `ToolProgressStatus` enum.

**Mechanism of breakage:** After Plan 02-01 GREEN, `sse.py:106` will raise `ValidationError` when decoding the existing `complete.sse` fixture (which has `toolCallId` in the wire but the wire DTO still lacks the alias — that comes in Plan 02-03). The `ValidationError` propagates from `_decode_application_record` through `_dispatch_record`/`consume_chunk` to `async_decode_hermes_sse`, where it is caught by the broad `except Exception` at `sse.py:374` and misclassified as `HermesTransportError(transient=True)` — the wrong exception type.

**Scope mismatch:** Plan 02-01 `files_modified` lists only `models.py`, `__init__.py`, `tests/test_protocol.py`, `tests/test_package.py`. It does NOT list `sse.py` or `tests/test_sse.py`. Yet Plan 02-01 `verification` says "Run `uv run --no-sync pytest -q` at the end of Wave 1 so the 100% branch gate covers the new public paths." That command will fail because at least `test_sse.py:492`, `test_sse.py:567`, and the composite-golden test at `test_sse.py:562-572` will be RED.

**Fix:** Either (a) merge Plan 02-01's public-model change with Plan 02-03's wire-DTO/mapper change into the same wave so `sse.py:106` is updated synchronously, or (b) add `src/hermes_agent_api_client/sse.py` and `tests/test_sse.py` to Plan 02-01 `files_modified` and include a minimal pass-through (`tool_call_id=progress.tool_call_id` after adding the alias to `_ToolProgressWire`, `status=ToolProgressStatus(progress.status)`) in the GREEN step. Option (a) is cleaner because the alias and the public field are contract-coupled.

---

### HIGH — Plan 02-02 verification commands contain literal HTML entities

**Evidence:** `02-02-PLAN.md:94` and `02-02-PLAN.md:119` contain `&gt;` instead of `>` in the inline Python verification scripts. Confirmed by `grep -n '&gt;' 02-02-PLAN.md` and by executing `uv run --no-sync python -c 'print(1 &gt; 0)'` which produces `SyntaxError: invalid syntax`.

**Impact:** Both `<automated>` verification commands for Plan 02-02 are non-executable as written. An autonomous executor following the plan verbatim will fail at the verify step with a Python syntax error, blocking the plan regardless of whether the actual fixtures are correct.

**Fix:** Replace all `&gt;` with `>` in both verification commands. There are at least 6 occurrences across the two commands (e.g., `len(latest_evidence["source_refs"])&gt;0`, `len(latest_reproduction["procedure"])&gt;0`, `len(latest_paths)&gt;0`, etc.).

---

### MEDIUM — Plan 02-01 acceptance criterion is internally contradictory

**Evidence:** Plan 02-01 `acceptance_criteria` states: "Existing direct model construction, union membership, frozen-model, and package export tests remain green." But `tests/test_protocol.py:732` constructs `ToolProgressEvent(tool_name="home_assistant", status="running")` — this will fail after GREEN because `tool_call_id` is now required and `status` must be a `ToolProgressStatus` enum.

The `02-PATTERNS.md:254` acknowledges the needed update: "Extend this expectation with `tool_call_id` and `ToolProgressStatus`." But Plan 02-01's RED behavior does not call out updating `test_stream_vocabulary_is_closed_immutable_and_text_safe`, and the acceptance criterion explicitly claims existing construction tests "remain green" rather than "are updated."

**Fix:** Reword the acceptance criterion to acknowledge that existing direct-construction tests must be updated to supply `tool_call_id` and `ToolProgressStatus.*`, and list `test_stream_vocabulary_is_closed_immutable_and_text_safe` explicitly in the RED section.

---

### MEDIUM — Plan 02-02 requires network access with no offline fallback

**Evidence:** `02-02-PLAN.md:94` verification calls `subprocess.check_output(["git","ls-remote","--tags",repo,"v[0-9]*"],text=True)`. If the network is unavailable, `subprocess.check_output` raises and the verification fails hard. The research notes this risk ("If network later fails, use the pinned local fixture/commit only and report latest-tag verification blocked") but the plan's verification command has no fallback path.

**Impact:** CI environments without network egress (air-gapped, restricted firewall) cannot verify Plan 02-02. Since the existing test suite has no network dependency, this introduces a new environmental requirement.

**Fix:** Add an offline fallback that verifies the canonical pinned commit against the existing fixture/provenance when `git ls-remote` fails, and records `latest_tag_verification: blocked-offline` in the provenance summary rather than hard-failing.

---

### MEDIUM — Plan 02-02 `files_modified` is incomplete for the newer-tag branch

**Evidence:** Plan 02-02 `files_modified` lists only paths under `tests/fixtures/hermes/v2026.7.7.2/`. But the Task 1 `action` says: "If a newer tag exists... continue only after storing immutable version-specific captured evidence under that tag's own fixture root." The verification command (`02-02-PLAN.md:94`) enforces `path.startswith("tests/fixtures/hermes/"+latest+"/")` for latest-evidence paths. If a newer tag exists at execution time, new fixture files under `tests/fixtures/hermes/<latest_tag>/` must be created, but they are not listed in `files_modified`.

**Mitigating factor:** Research confirms `v2026.7.7.2` is currently the latest numeric tag, so this branch is likely inactive. But D-15/D-16 require the plan to handle it.

**Fix:** Add a conditional note in `files_modified` (e.g., "plus `tests/fixtures/hermes/<latest>/...` if D-16 activates") or restructure the plan so the newer-tag branch is a separate conditional task with its own file list.

---

### LOW — Provenance schema drift between existing and new entries

**Evidence:** Existing `provenance.json:18` uses `evidence_scope.live_server_tested: false` at the top level. New entries in Plan 02-02 use `reproduction.configuration.live_server_invoked: false` per-fixture. The verification commands only check `live_server_invoked` for new entries, so this is functionally correct, but the two schemas coexist without reconciliation.

**Fix:** No action required for Phase 2, but Phase 4 should consider migrating the existing entries to the `reproduction.configuration.live_server_invoked` convention or documenting the dual schema.

---

### LOW — Plan 02-02 verification does not check per-row decision citations

**Evidence:** Plan 02-02 Task 2 `action` says "each row must state expected accept/reject semantics and cite D-01, D-02, D-03, or D-04." But the verification command (`02-02-PLAN.md:119`) only checks `set(design.get("decision_refs",[]))=={"D-01","D-02","D-03","D-04"}` at the entry level. Per-row citations inside `terminal_design_matrix.json` are not verified.

**Impact:** A matrix file with no per-row citations but a top-level `decision_refs` list would pass verification despite violating the acceptance criterion.

**Fix:** Add a verification assertion that walks the matrix rows and checks each row cites at least one D-0[1-4] decision.

---

## Suggestions

1. **Merge Plan 02-01 and Plan 02-03 into a single wave** (or make 02-03 not depend on 02-01). The public `ToolProgressEvent` contract change and the wire `_ToolProgressWire` alias/mapping change are tightly coupled — the existing `sse.py:106` construction site must be updated atomically with the model change. Splitting them across waves creates an unrunnable intermediate state.

2. **Add `sse.py` and `test_sse.py` to Plan 02-01 `files_modified`** if the merge is not feasible. At minimum, Plan 02-01 GREEN must update `sse.py:106` to `ToolProgressEvent(tool_call_id=..., tool_name=..., status=ToolProgressStatus(...))` and update the three existing test assertions at `test_sse.py:492`, `test_sse.py:567`, and `test_protocol.py:732`.

3. **Fix the HTML entities in Plan 02-02 verification commands** before execution. Run `sed -i 's/&gt;/>/g' 02-02-PLAN.md` or equivalent.

4. **Add a `terminal_design_matrix.json` schema check** to Plan 02-02 Task 2 verification that validates per-row `decision_ref` fields, not just the top-level `decision_refs` set.

5. **Consider a raw-bytes duplicate-member helper** in `tests/helpers/hermes.py` as Plan 02-03 RED will need it. The `02-VALIDATION.md:70` Wave 0 list already calls for "raw duplicate-member inputs as bytes/text." Adding it as a tracked artifact avoids ad-hoc inline construction.

6. **Clarify the `live_server_invoked` vs `live_server_tested` field naming** in the provenance schema. The existing top-level `evidence_scope.live_server_tested` and the new per-fixture `reproduction.configuration.live_server_invoked` serve the same purpose; document which is authoritative.

---

## Risk Assessment

**HIGH** — The plan set cannot be executed as written due to two blocking defects:

1. Plan 02-01's wave isolation leaves `sse.py` and `test_sse.py` in a broken state after Wave 1, making the "100% branch gate" verification unachievable. This is a structural ordering defect, not a content defect — the plan's technical approach is correct, but the wave boundary is drawn in the wrong place.

2. Plan 02-02's verification commands are syntactically invalid Python due to HTML-entity encoding, making the plan unverifiable as written.

Both defects are fixable without re-planning: merge 02-01/02-03 waves (or expand 02-01 scope), and replace `&gt;` with `>`. Once fixed, the plan set is technically sound, well-evidenced, and faithfully implements D-01–D-16, TOOL-01–TOOL-04, and TERM-01–TERM-07 within the declared Phase 2 boundary.

---

## Consensus Summary

### Agreed Strengths

- The phase boundary is disciplined: both reviewers confirmed that session-header work remains in Phase 3 and dependency/lock refresh remains in Phase 4.
- The evidence-first ordering, per-path provenance classifications, immutable source identities, semantic assertions, and SHA-256 checks are strong foundations for D-13 through D-16.
- The shared exact lifecycle-text validator, approved-path duplicate projection, total terminal matrix, input-free sentinels, scrubbing, and delayed-terminal gate all target real existing seams in the repository.
- The TDD plans are concrete and source-grounded, with the public model, wire parser, mapper, and terminal state-machine boundaries identified accurately.

### Agreed Concerns

1. **HIGH — Wave 1 is not executable as written.** Plan 02-01 makes `ToolProgressEvent.tool_call_id` required and `status` a strict enum, but the existing construction path in `src/hermes_agent_api_client/sse.py:106` and assertions in `tests/test_sse.py:492,567` retain the old shape until Plan 02-03. The full Wave 1 suite therefore cannot remain green, and Plan 02-03's RED signal becomes ambiguous.
2. **HIGH — Plan 02-02's automated Python gates are syntactically invalid.** Both reviewers found literal `&gt;` entities in the commands. These are the only machine gates for the provenance contract and must be replaced or corrected before execution.
3. **MEDIUM — The network/newer-tag path is underspecified operationally.** Both reviewers want an explicit blocked-offline disposition and declared conditional fixture ownership when a newer tag activates D-16, rather than autonomous improvisation.

### Divergent Views

- Claude additionally flagged pair-tree materialization for ignored chat subtrees: after approved-path duplicate checks, nested `_JsonObjectPairs` must be converted back to ordinary dictionaries/lists before the existing Pydantic DTO path, with the additive-fields regression test named explicitly.
- Claude considered the compatible-newer-tag evidence claim insufficiently self-verifying and recommended a recorded difference summary plus a human decision checkpoint; OpenCode accepted the existing compatibility branch logic but still flagged its conditional file ownership.
- OpenCode specifically flagged Plan 02-01's claim that existing construction tests remain green, missing per-row decision citations in the design matrix gate, and dual provenance schema terminology.
- Claude rated the current plan set **MEDIUM** risk because the blockers fail loudly; OpenCode rated it **HIGH** because the plans cannot execute as written. Consensus disposition: treat both shared HIGH findings as actionable blockers and replan before execution.

### Recommended Incorporation Order

1. Repair Wave 1 ownership/order so public model changes, wire aliases/mapping, and all existing construction tests transition atomically or explicitly defer the full-suite gate until the tree is coherent.
2. Replace the long inline provenance one-liners with a committed, reviewable verification script/test and remove all entity escaping; preserve every per-path provenance assertion.
3. Specify pair-tree materialization and regression coverage for ignored nested chat data.
4. Make offline/latest-tag outcomes and conditional newer-tag fixture ownership explicit, and strengthen the compatibility evidence with a concrete difference summary or decision checkpoint.
5. Tighten lower-risk acceptance details: D-03's `TerminalOutcome.UPSTREAM_ERROR`, finish-reason omission/null behavior, and per-row design-decision citations.

