---
phase: 03-session-header-safety
verified: 2026-10-20T08:18:27Z
status: passed
score: 42/42 must-haves verified
covered_files:
  - ".planning/phases/03-session-header-safety/03-01-PLAN.md"
  - ".planning/phases/03-session-header-safety/03-01-SUMMARY.md"
  - ".planning/phases/03-session-header-safety/03-02-PLAN.md"
  - ".planning/phases/03-session-header-safety/03-02-SUMMARY.md"
  - ".planning/phases/03-session-header-safety/03-03-PLAN.md"
  - ".planning/phases/03-session-header-safety/03-03-SUMMARY.md"
  - ".planning/phases/03-session-header-safety/03-04-PLAN.md"
  - ".planning/phases/03-session-header-safety/03-04-SUMMARY.md"
  - "src/hermes_agent_api_client/client.py"
  - "src/hermes_agent_api_client/models.py"
  - "tests/test_client_lifecycle.py"
  - "tests/test_transport.py"
covered_digest: "v3:sha256:f5bf3d4aa742e9a6f9cf640deb906d1f8cfa67fbf85e6db8eb18c1c7476e4364"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Judgement-tier prohibition (Plans 03-01, 03-02, 03-03): 'MUST NOT present the PR #7 (8843cfc, v0.3.1) session implementation as built by this phase, or edit or re-parametrise the PR #7 session tests; new evidence is added beside them.' Read the Provenance section of 03-TRACEABILITY.md and the one-line summaries of 03-01/02/03-SUMMARY.md, and confirm that none of them claims Phase 3 built the session behaviour."
    expected: "All phase artefacts credit PR #7 (8843cfc) for the implementation and describe Phase 3 as characterisation tests and evidence only. The mechanical half is already verified: `git diff main -- tests/test_client_lifecycle.py` has 0 removed lines, so no PR #7 test was edited or re-parametrised."
    why_human: "Provenance honesty is a judgement-tier prohibition. The verifier's verdict (satisfied) is a non-authoritative LLM judgement and cannot be passed silently."
  - test: "Judgement-tier prohibition (Plan 03-04): 'MUST NOT ... overstate coverage: every claim in 03-TRACEABILITY.md cites a collected test node ID or a recorded command result.' Skim the D-10 table, the D-08 matrix and the Post-Review Strengthening section of 03-TRACEABILITY.md."
    expected: "No row claims more than its cited test proves. The verifier found that all 116 cited node IDs (42 functions) resolve in `--collect-only`. It also reproduced 15 of the recorded mutations or negative controls independently, in scratch copies. The record already relabels the post-exit `ag_frame is None` assertions as lifecycle checks (CR-01) and names the supplementary RED proofs where no D-11 guard applies."
    why_human: "Whether wording overstates coverage is a judgement call. The verifier's verdict (satisfied) is non-authoritative."
---

# Phase 3: Session Header Safety Verification Report

**Phase Goal:** Python consumers can attach opaque conversation and durable-memory identifiers to a stream without leakage, shared-state mutation, or transport ownership changes.
**Verified:** 2026-10-20T08:18:27Z
**Status:** human_needed (complete, with 2 flagged judgement-tier prohibitions; every truth is verified)
**Re-verification:** No (initial verification)
**Mode:** standard (ROADMAP `mode: null`)

## Scope and Provenance Check

This is an audit phase (D-01, D-03). PR #7 (`8843cfc fix: complete conversation contract (#7)`, v0.3.1) implemented the session behaviour, and this phase adds characterisation tests and evidence only. The verifier confirmed this independently:

- `git diff --stat main -- src/` is empty, and `git log --oneline main..HEAD -- src/` prints nothing.
- `git diff --stat main -- tests/ src/ docs/ README.md CHANGELOG.md pyproject.toml uv.lock` reports a single file, `tests/test_client_lifecycle.py`, with 678 insertions and **0 deletions** (no PR #7 test was edited).
- `git log --oneline 8843cfc..main -- src/hermes_agent_api_client/client.py tests/test_client_lifecycle.py tests/test_transport.py` is empty, so the audited code is the PR #7 code.
- All 30 branch commits are GPG-signed (`%G?` = `G`) and carry a `Signed-off-by` trailer.

## Goal Achievement

### Observable Truths

Roadmap success criteria (the contract) come first, then the plan must-haves. Every truth marked "mutation-proven" was independently turned red by the verifier, using scratch copies of `src/` (or of the test tree for negative controls) and leaving the working tree untouched (see Behavioural Spot-Checks).

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | **SC1:** Consumers can independently omit or provide `session_id` and `session_key`; non-`None` values map only to their exact Hermes headers; there is no arbitrary-header API | ✓ VERIFIED | `client.py:176-198` `_chat_request_headers` adds only `X-Hermes-Session-Id`/`-Key` for non-`None` values; the signature at `client.py:653-659` is `(self, request, *, session_id=None, session_key=None)`. Tests: `test_stream_session_headers_are_independent_and_request_scoped`, `test_session_values_appear_only_in_their_exact_headers[id-only,key-only,both]`, `test_stream_chat_events_accepts_no_arbitrary_headers`, all passing. Mutation-proven: an extra `X-Request-Trace` header turned `[id-only]` and `[both]` red, and an extra `headers` parameter turned the signature test red. A verifier probe also showed that a request document with `headers`/`extra_headers` keys puts no extra header on the wire (IN-04 concern) |
| 2 | **SC2:** Only exact built-in `str` of 1-256 visible ASCII characters is accepted; path-shaped IDs are rejected; invalid pairs fail atomically before dispatch as safe non-retryable local errors | ✓ VERIFIED | `models.py:51-58` `_require_lifecycle_text` (`type(value) is not str`, `1 <= len <= 256`, `"!" <= c <= "~"`); `client.py:153-173` path shape; `client.py:676-681` raises `_raise_transport_failure(transient=False)` before `aiter(_stream_chat_events(...))`. The 14-case `test_rejected_session_values_leave_no_retained_state` and 5-case `test_session_values_accept_exact_boundaries` pass. Mutation-proven: G1, G2, the D-05 narrowing, the D-05 broadening and the 256-bound mutation each turned their named cases red |
| 3 | **SC3:** Concurrent streams use fresh headers and leave the request mapping, bound authorisation headers and every other stream's session values unchanged | ✓ VERIFIED | `client.py:193` `request_headers = dict(headers)` per stream, plus the inner copy at `client.py:435`. Tests `test_concurrent_streams_isolate_session_headers` (8 gathered streams), `test_stream_session_headers_are_independent_and_request_scoped` (`request_document == original_document`, `client._headers == bound_headers`) and the two Plan 03-01 later-stream tests all pass. Mutation-proven: under G3, 3 of 3 named tests went red and the `[neither]` control stayed green |
| 4 | **SC4:** Session canaries are absent from public failures, text representations, traceback chains and retained generator locals after rejection, completion, early close or cancellation | ✓ VERIFIED | Scrub at `client.py:674-676`, `operation_headers = {}` at `:687`, `_reraise_scrubbed_failure` at `:83-89`. Rejection, post-dispatch and cancellation: `_assert_no_sensitive_traceback_references` deep-walks package traceback frame locals, plus `__cause__`/`__context__` None. Suspended or completed streams: `_assert_suspended_stream_retains_no_secrets` reads live `ag_frame.f_locals` at every yield (CR-01 fix `19f7631`). Mutation-proven: S1 turned 6 of 6 named tests red; CR-01 mutant A (scrub moved) turned 4 of 4 red and mutant B (`operation_headers` retained) turned 4 of 4 red, failing at the suspended-frame canary assertion (`tests/test_client_lifecycle.py:285`) |
| 5 | **SC5:** Closing or cancelling a stream closes its response but never an injected caller-owned client, and `asyncio.CancelledError` propagates after cleanup | ✓ VERIFIED | `client.py:601` `owns_active = active is not None and self._injected_http_client is None`; the stream path never closes `active`; the `finally` block at `:700-707` closes the delegated stream before `_reraise_scrubbed_failure`. Behavioural tests `test_injected_client_survives_public_stream_task_cancellation` (real `task.cancel()` mid-iteration, `task.cancelled() is True`, `gated.closed is True`, `is_closed is False`) and `..._early_close` pass. Mutation-proven: G4 and G4b turned both tests red |
| 6 | (03-01) A consumer task cancelled after exactly one `AssistantDeltaEvent` ends with `task.cancelled()` True; the response closes; the injected client stays open | ✓ VERIFIED | Test body asserts `received == [AssistantDeltaEvent(text="hello")]`, `task.cancelled() is True`, `gated.closed is True` and `injected_http_client.is_closed is False`. The gate wait is bounded (WR-01, `wait_until_blocked`, 5 s), so the test fails rather than hangs |
| 7 | (03-01) After cancellation and after early close, a later stream on the same injected client completes with a `TerminalEvent`, `probe_capabilities()` succeeds, and the client is open after context exit | ✓ VERIFIED | Both tests iterate a later stream to `(delta, TerminalEvent(SUCCESS))`; the early-close test calls `probe_capabilities()` and checks that the last request path ends with `/v1/capabilities`; both assert `is_closed is False` after `async with` |
| 8 | (03-01) The recorded `CancelledError` has `__cause__`/`__context__` None, no canary in `str`/`repr`/`format_exception`/package frame locals, and `ag_frame` None | ✓ VERIFIED | Assertions on `recorded[0]` plus `_assert_no_sensitive_traceback_references`. Mutation-proven by S1 (red). The suspended-frame check also runs at the gate before cancellation |
| 9 | (03-01) After early `aclose()`, `ag_frame` is None and no canary appears in `repr()` of the stream | ✓ VERIFIED | `ag_frame is None` is asserted (a lifecycle check). The `repr` assertion was removed under WR-02 because a generator's `repr` never shows locals. A verifier probe directly observed that `repr` carries no canary while suspended or closed. Stronger replacement: the suspended-frame `f_locals` check before `aclose()` |
| 10 | (03-01) A later stream without session arguments, after a cancelled or early-closed stream that carried session values, sends neither session header | ✓ VERIFIED | `"X-Hermes-Session-Id" not in requests[-1].headers` (and `-Key`) in both tests. G3 turned both red (03-TRACEABILITY observation, consistent with the verifier's G3 run) |
| 11 | (03-01) Each new test fails under its named mutation (G4b, the scrub, G4) and passes once restored | ✓ VERIFIED | Verifier reproduction: G4b turned 2 of 2 red, G4 2 of 2 red and S1 the cancellation test red; the unmutated scratch baseline passed all 22 named tests |
| 12 | (03-02) For id-only, key-only and both, each value appears exactly once, only under its own header, never in another header, the body or the URL; an omitted value's header is absent | ✓ VERIFIED | `get_list(name) == [value]`, a `multi_items()` scan, `sent.content.decode()` and `str(sent.url)` assertions in `test_session_values_appear_only_in_their_exact_headers` |
| 13 | (03-02) `inspect.signature(stream_chat_events)` has exactly `self, request, session_id, session_key`; both session parameters are keyword-only with default None; no `*args`/`**kwargs` | ✓ VERIFIED | `test_stream_chat_events_accepts_no_arbitrary_headers` passes; mutation-proven (an extra `headers` parameter turned it red) |
| 14 | (03-02) Values are sent byte-for-byte, and the bound headers equal their pre-stream copy | ✓ VERIFIED | `get_list == [value]` plus `client._headers == bound_headers` in both Plan 03-02 positive tests |
| 15 | (03-02) Embedded `..` is rejected; single dots, an inner colon and a digit-colon prefix are accepted unchanged (D-05 exactly) | ✓ VERIFIED | `[session-id-embedded-parent]` rejection plus the three adjacency positives. Mutation-proven: the narrowing (`== ".."`) turned `[session-id-embedded-parent]` red and the broadening (`isalnum`) turned `[session-id-digit-colon-prefix]` red |
| 16 | (03-02) The empty string is rejected for either argument, `!` is accepted, and `None` omits only that header | ✓ VERIFIED | `[session-id-empty]`, `[session-key-empty]`, `[session-key-minimum]` and the id-only/key-only absence assertions |
| 17 | (03-02) `bytes`, CR and tab are rejected for both arguments; `"~" * 256` is accepted as `session_key` | ✓ VERIFIED | Six rejection cases plus `[session-key-maximum]`. Mutation-proven: G1 (CR/tab/bytes red) and the 256-bound mutation (`[session-key-maximum]` red) |
| 18 | (03-02) Rejection is atomic and order-independent, with identical text and metadata for invalid id, invalid key or both, and no request sent | ✓ VERIFIED | `[pair-invalid-id]`, `[pair-invalid-key]` and `[pair-both-invalid]` assert the same exact constants and `requests == []` |
| 19 | (03-02) Every rejection raises exactly `HermesTransportError`, `TRANSPORT`, `status_code None`, `retryable False`, with exact `str`/`repr`/`args` | ✓ VERIFIED | `_LOCAL_INPUT_FAILURE_TEXT`/`_REPR` constants asserted in all 14 cases; `type(error) is HermesTransportError` |
| 20 | (03-02) Canary checks use the visible-ASCII substring of each rejected value | ✓ VERIFIED | Parametrisation uses `"return-session-id-canary"`, `"separated-..."` and `"bytes-..."` substrings, so `\r`/`\t`/`b'...'` escapes cannot hide a leak |
| 21 | (03-02, backstop) Validation and the local-input raise happen inside the first `anext()` with no intervening `await`, so a rejected stream can neither dispatch nor interleave | ✓ VERIFIED | Directly observed: verifier probe `rejected.__anext__().send(None)` raised `HermesTransportError` on the first coroutine step, so no suspension point precedes the raise, and `requests == []`. Code at `client.py:661-681` contains no `await` |
| 22 | (03-02) After every rejection, `__cause__`/`__context__` are None, `ag_frame` is None, and no canary appears in `str`/`repr`/traceback/package frame locals | ✓ VERIFIED | Assertions in `test_rejected_session_values_leave_no_retained_state`; S1 turned the canary-bearing cases red (03-TRACEABILITY S1 list, consistent with the verifier's S1 run) |
| 23 | (03-02) Each new test fails under its named mutation | ✓ VERIFIED | Verifier reproduced G1, G2, the narrowing, the broadening, the 256 bound, the extra header and the signature mutations (all red) |
| 24 | (03-03) After a session-bearing stream completes, `ag_frame` is None and no canary is retained; the request carried both headers | ✓ VERIFIED | `[completion]` runs the suspended-frame check at every yield and asserts both request headers. `repr(stream)`/`repr(events)` were removed under WR-02 as unfalsifiable; the verifier probe observed that `repr` is canary-free |
| 25 | (03-03) After one event and `aclose()`, `aclose()` does not raise, the response closes and `ag_frame` is None | ✓ VERIFIED | `[early-close-after-event]` asserts `response_stream.closed is True`. Mutation-proven: delegated `aclose()` changed to `pass` turned it red at line 1297 (`assert False is True`) |
| 26 | (03-03) A stream closed before its first `anext()` sends no request and has `ag_frame` None; the unstarted frame is never inspected | ✓ VERIFIED | `[early-close-before-first-iteration]`; verifier negative control (`anext` before `aclose`) turned it red at `requests == []` |
| 27 | (03-03) For 401, 503, malformed SSE, a `ConnectError` embedding both values, and request-stage cancellation (identity preserved), the failure has no cause/context and no canary anywhere, and `ag_frame` is None | ✓ VERIFIED | `test_post_dispatch_failures_carry_no_session_values` (5 cases) passes; the connect handler deliberately embeds both canaries; `error is cancellation` is asserted. Mutation-proven: S1 turned all 5 red |
| 28 | (03-03) The early-close case fails without the delegated `aclose()`; completion and before-first-iteration fail their negative controls; post-dispatch cases fail under the scrub | ✓ VERIFIED | Verifier reproduced the delegated-close mutation, the before-first-iteration negative control and S1. The completion `ag_frame` control is superseded by the stronger CR-01 mutants A and B, which the verifier also reproduced |
| 29 | (03-04) 03-TRACEABILITY.md maps SESS-01 to SESS-05, HTTP-02 and SC1 to SC5 to node IDs that all exist in `--collect-only` | ✓ VERIFIED | Rows for all 11 keys are present; the verifier extracted 116 distinct cited node IDs (42 functions) and all resolve against `198 tests collected` |
| 30 | (03-04) The D-11 record gives G1, G2, G3, G3b, G4, G4b and S1 with location, mutation, count, FAILED IDs and a clean restore | ✓ VERIFIED | `## D-11 Mutation Check` table plus `<details>` lists (37/7/17/1/45/32/49). The verifier independently reproduced every listed guard except G3b in focused runs (all red), and `git diff --exit-code -- src/` is clean |
| 31 | (03-04) G4b includes both Plan 03-01 tests; G1 includes CR/tab/bytes; S1 includes every post-dispatch case | ✓ VERIFIED | Present in the record's FAILED lists and reproduced by the verifier |
| 32 | (03-04) Every D-08 cell cites evidence, and only the four exception-less cells read "N/A: no exception escapes" (`q1-accept-na`) | ✓ VERIFIED | `## D-08 Canary Exit-Path Matrix`; the Post-Review note redirects the completion and early-close `ag_frame` cells to the suspended-frame check |
| 33 | (03-04) Pre-iteration retention is recorded as a documented boundary (`q2-document-boundary`); `src/` is not changed | ✓ VERIFIED | Known Boundaries (b) and AR-03-01 in 03-SECURITY.md; `src/` diff is empty |
| 34 | (03-04) The record states that PR #7 implemented the behaviour and Phase 3 added tests and evidence only, backed by an empty `git log main..HEAD -- src/` | ✓ VERIFIED | `## Provenance` section; the verifier re-ran the commands with the same results |
| 35 | (03-04) The D-07 upstream record at `v2026.7.7.2` (`9de9c25f…`): same rule set as D-05, no decoding, no D-02 conflict, glob observation out of scope | ✓ VERIFIED | `## D-07 Upstream Hermes Record` is present with all five points. The upstream source itself was not re-read by the verifier; it is a research record, not a codebase claim |
| 36 | (03-04) `## Gaps` reads "None" and `open_gaps: 0` | ✓ VERIFIED | Confirmed in the file. The verifier's own analysis found no unmet truth that would contradict it |
| 37 | (03-04) The 256-character `session_id` is sent intact with the bound headers unchanged, and G3 turns `[maximum-session-id]` red | ✓ VERIFIED | Passing test, plus reproduction under G3 |
| 38 | (03-04) With neither value, no session header is sent and bound headers are unchanged; `[neither]` stays green under G3 | ✓ VERIFIED | The verifier's G3 run kept `[neither]` green (control) |
| 39 | (03-04) Concurrent isolation is asserted as the exact set of (id, key) pairs across 8 gathered streams, and G3 turns it red | ✓ VERIFIED | `test_concurrent_streams_isolate_session_headers` passes and was red under the verifier's G3 run |
| 40 | (03-04, backstop) Two streams with identical values each build their own header dict through `dict(headers)`; equal values never share or merge a mapping | ✓ VERIFIED | Directly observed: a verifier probe ran two in-flight concurrent streams with identical values (gated until both requests arrived). Each sent `get_list == [value]` for both headers, and `_chat_request_headers` returns distinct, equal dicts that are not the bound mapping; bound headers were unchanged |
| 41 | (03-04) The prek gate is green and `src/` is clean at commit | ✓ VERIFIED | The verifier ran each hook it could run without writing state: `uv lock --check`, `ruff format --check`, `ruff check`, `basedpyright` (0 errors), `--verifytypes` (100%) and `uv run pytest` (674 passed, 100.00% coverage). Build and verify-dist were not re-run (they write `dist/`); their inputs (`src/`, `pyproject.toml`, `uv.lock`) are byte-identical to `main` |
| 42 | (all plans) `git diff --exit-code -- src/` exits 0 and `git log main..HEAD -- src/` is empty (D-01, D-03) | ✓ VERIFIED | Re-run by the verifier, before and after every scratch mutation run |

**Score:** 42/42 truths verified (0 present but behaviour-unverified). Every behaviour-dependent truth (cancellation, cleanup and ownership invariants) is backed by a passing behavioural test and a reproduced mutation.

### Prohibitions (must-NOT)

| Prohibition | Tier | Disposition | Evidence |
|-------------|------|-------------|----------|
| MUST NOT change shipped behaviour in `src/` (03-01 to 03-04) | test | ✓ verified (enforced) | `git diff --exit-code main -- src/` exits 0; `git log main..HEAD -- src/` is empty |
| MUST NOT derive, default, generate or transform a session identifier (03-02) | test | ✓ verified (enforced) | `[id-only]`/`[key-only]` assert the omitted header is absent; `get_list == [value]` verbatim; the extra-header mutation turned them red |
| MUST NOT create or edit `03-VERIFICATION.md` (03-04) | test | ✓ verified (enforced) | The file did not exist when this verifier started (directory listing); only the verifier wrote it |
| MUST NOT present PR #7 as built by this phase, or edit or re-parametrise PR #7 tests (03-01 to 03-03) | judgement | ⚠️ flagged: unverified prohibition, human review recommended | Non-authoritative LLM judgement: **satisfied**. 0 removed lines in the test diff; Provenance and summaries credit PR #7 |
| MUST NOT present PR #7 as built by this phase, or overstate coverage (03-04) | judgement | ⚠️ flagged: unverified prohibition, human review recommended | Non-authoritative LLM judgement: **satisfied**. All cited IDs resolve; mutation results reproduced; CR-01 relabelling is honest |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/phases/03-session-header-safety/03-TRACEABILITY.md` | **Plan-authored D-10/D-11 evidence record** (D-10 table, SC1-SC5 table, D-08 matrix, D-09, D-11 mutation results, D-07 record, user decisions Q1/Q2, known boundaries, PR #7 provenance, Post-Review Strengthening). Linked here as required by amended D-10/D-11, not duplicated. Phase 4 VERI-02 starts from its `## D-10 Traceability` table | ✓ VERIFIED | 460 lines; every required heading present; frontmatter keys `phase`, `plan_authored_by`, `recorded`, `open_gaps: 0`; `verify.artifacts` 1/1 |
| `tests/test_client_lifecycle.py` › `class GatedAsyncByteStream` | Gated byte-stream test double | ✓ VERIFIED | Used by the cancellation test; bounded wait (WR-01) |
| `tests/test_client_lifecycle.py` › `test_injected_client_survives_public_stream_task_cancellation` | HTTP-02 mid-iteration cancellation | ✓ VERIFIED | Passes; red under G4b and S1 |
| `tests/test_client_lifecycle.py` › `test_injected_client_survives_public_stream_early_close` | HTTP-02 early-close reuse | ✓ VERIFIED | Passes; red under G4 and G4b |
| `tests/test_client_lifecycle.py` › `test_session_values_appear_only_in_their_exact_headers` | SESS-01 exact-header evidence | ✓ VERIFIED | 3 cases pass |
| `tests/test_client_lifecycle.py` › `test_stream_chat_events_accepts_no_arbitrary_headers` | No arbitrary-header API lock | ✓ VERIFIED | Passes; red under the signature mutation |
| `tests/test_client_lifecycle.py` › `test_rejected_session_values_leave_no_retained_state` | SESS-02/03 rejection matrix plus D-08 rejection row | ✓ VERIFIED | 14 cases pass |
| `tests/test_client_lifecycle.py` › `test_session_values_accept_exact_boundaries` | Positive bounds plus D-05 adjacency pins | ✓ VERIFIED | 5 cases pass |
| `tests/test_client_lifecycle.py` › `test_completed_and_closed_streams_retain_no_session_values` | D-08 completion and early-close rows | ✓ VERIFIED | 3 cases pass; suspended-frame helper (CR-01) |
| `tests/test_client_lifecycle.py` › `test_post_dispatch_failures_carry_no_session_values` | SESS-05 post-dispatch matrix | ✓ VERIFIED | 5 cases pass |
| `tests/test_client_lifecycle.py` › `_assert_suspended_stream_retains_no_secrets` | CR-01 retention evidence | ✓ VERIFIED | Wired into 4 tests; catches mutants A and B |
| 03-SECURITY.md, 03-VALIDATION.md, 03-REVIEW*.md | Phase evidence | ✓ present | T-03-11 already updated for CR-01; `threats_open: 0`; `nyquist_compliant: true` |

`verify.artifacts`: 03-01 3/3, 03-02 4/4, 03-03 2/2 and 03-04 1/1, all passed.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_client_lifecycle.py` | `client.py` | public `stream_chat_events(...)` with an injected `httpx.AsyncClient` | ✓ WIRED | `verify.key-links` passed (03-01, 03-02, 03-03) |
| `tests/test_client_lifecycle.py` | `protocol.py` | exact `retryable=false` text | ✓ WIRED | `verify.key-links` 03-02 passed |
| new tests | existing helpers | `_assert_no_sensitive_traceback_references(` reused, not duplicated | ✓ WIRED | `verify.key-links` passed |
| `GatedAsyncByteStream` | `httpx.MockTransport` | first chat request only; later requests use `_successful_transport` | ✓ WIRED (manual) | The tool reported "Source file not found" because `from:` is a class name, not a path. Manual check: `respond` returns `stream=gated` only when `requests` is empty, otherwise `later(request)` |
| `03-TRACEABILITY.md` | `tests/test_client_lifecycle.py` | every cited node ID resolves | ✓ WIRED | 116 of 116 resolve |
| `03-TRACEABILITY.md` | `client.py` | guard lines 158, 185, 193, 435, 601, 674-675, 708 | ✓ WIRED | Line anchors match the current `client.py` |

### Data-Flow Trace (Level 4)

Not applicable: no rendered UI or data source. The equivalent wire-level flow (session argument → `_chat_request_headers` → `operation_headers` → `_stream_chat_events` request headers → `httpx.Request.headers`) is traced by tests that inspect the recorded `httpx.Request` objects: ✓ FLOWING.

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
|-----------|---------|--------|--------|
| Full suite with the coverage gate (run once) | `uv run --no-sync pytest -p no:cacheprovider` | `674 passed`; `Total coverage: 100.00%` | ✓ PASS |
| Lint, format, types, public typing, lock | `ruff check .`; `ruff format --check .`; `basedpyright`; `basedpyright --verifytypes hermes_agent_api_client --ignoreexternal`; `uv lock --check` | All checks passed; 15 files formatted; 0 errors, 0 warnings, 0 notes; 100%; resolved | ✓ PASS |
| Cited node IDs resolve | `pytest tests/test_client_lifecycle.py tests/test_transport.py --collect-only -q --no-cov` vs `grep` of 03-TRACEABILITY.md | 198 collected; 116 of 116 cited IDs present | ✓ PASS |
| Independent mutation sensitivity (scratch copy of `src/`, `PYTHONPATH` override confirmed) | named tests per mutation | baseline 22 passed; G1 3/3 red; G2 2/2; D-05 narrow 1/1; D-05 broaden 1/1; G3 3/3 (`[neither]` control green); extra header 2/2; signature 1/1; G4 2/2; G4b 2/2; S1 6/6; CR-01 mutant A 4/4; mutant B 4/4 (at `:285`, the suspended-frame canary assertion); 256-bound 1/1; delegated close → `pass` 1/3 (`[early-close-after-event]`) | ✓ PASS |
| Negative control (scratch copy of the test tree) | `anext` before `aclose` in `[early-close-before-first-iteration]` | red at `requests == []` | ✓ PASS |
| SESS-03 backstop (no `await` before the rejection raise) | probe: `rejected.__anext__().send(None)` | raised `HermesTransportError` synchronously; no request | ✓ PASS |
| SESS-04 adjacency backstop | probe: two gated in-flight streams with identical values | one copy per header per request; distinct dicts; bound headers unchanged | ✓ PASS |
| Generator `repr` holds no canary (WR-02-removed assertions) | probe | `<async_generator object HermesAgentApiClient.stream_chat_events …>` while suspended and closed | ✓ PASS |
| Request-document keys cannot add headers (IN-04 concern) | probe with `headers`/`extra_headers` keys | 1 request, no `X-Injected` header | ✓ PASS |
| Working tree untouched | `git status --short`; `git diff --exit-code -- src/ tests/` | clean | ✓ PASS |

Probe scripts are in the verifier scratchpad (`mutate.py`, `backstop_probe.py`, `in04_probe.py`) and are not committed.

### Probe Execution

No `scripts/*/tests/probe-*.sh` was declared or implied by the phase. Step 7c: not applicable.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| SESS-01 | 03-02, 03-04 | Independent `session_id`/`session_key`, mapped only to the exact headers | ✓ SATISFIED | Truths 1, 12-14 |
| SESS-02 | 03-02, 03-04 | Exact `str`, 1-256, visible ASCII; `session_id` path-shape rejection | ✓ SATISFIED | Truths 2, 15-17, 20 |
| SESS-03 | 03-02, 03-04 | Fails before dispatch, non-retryable, value-free | ✓ SATISFIED | Truths 2, 18, 19, 21 |
| SESS-04 | 03-01, 03-02, 03-04 | Fresh headers; no mutation of the request mapping, bound auth or other streams | ✓ SATISFIED | Truths 3, 10, 14, 37-40 |
| SESS-05 | 03-01, 03-02, 03-03, 03-04 | Absent from failures, `str`, `repr`, tracebacks, causes, contexts and retained locals after every exit path | ✓ SATISFIED | Truths 4, 8, 9, 22, 24-28 |
| HTTP-02 | 03-01, 03-04 | Close or cancel closes only the response, never an injected client; `CancelledError` propagates | ✓ SATISFIED | Truths 5-7, 11 |

Orphaned requirements: none. REQUIREMENTS.md maps exactly SESS-01 to SESS-05 and HTTP-02 to Phase 3, and Plan 03-04 claims all six. Out-of-scope items (SECU-02, VERI-02, PKG-02, DEPS-01, SESS-06) are correctly left to Phase 4 or later.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_client_lifecycle.py` (added lines) | none | No TBD/FIXME/XXX/TODO/HACK, no `noqa`, no skip/xfail | none | Two `pyright: ignore[reportPrivateUsage]` comments for `client._headers` follow the existing PR #7 test pattern |
| `tests/test_client_lifecycle.py` | 1019-1048 | IN-01: rejection ids duplicate older parametrisations | ℹ️ Info | Redundant, not wrong; open in 03-REVIEW-DISPOSITION.md |
| `tests/test_client_lifecycle.py` | various | IN-02: SSE literal and gated-handler duplication | ℹ️ Info | Drift risk only |
| `tests/test_client_lifecycle.py` | completion branch | IN-03: `[completion]` does not assert `response_stream.closed` | ℹ️ Info | Success-path closure is covered by `tests/test_transport.py::test_stream_success_closes_response_and_refuses_redirects` and is not part of HTTP-02 (close/cancel) |
| `tests/test_client_lifecycle.py` | signature test | IN-04: name suggests more than the signature check proves | ℹ️ Info | The verifier probe showed that request-document keys cannot add headers, so the property holds |
| 03-TRACEABILITY.md D-08 matrix | rejection, request-stage and post-dispatch rows | `ag_frame` cells cite post-exit `ag_frame is None` (CPython-guaranteed) | ℹ️ Info | For those exception rows, the falsifiable retention evidence is the traceback deep walk (S1-proven), and the tests already label the `ag_frame` lines as lifecycle checks. Not a gap |

### Human Verification Required

Both items are judgement-tier prohibitions. The verifier's non-authoritative verdict on each is **satisfied**, but policy requires a human sign-off rather than a silent pass.

#### 1. Provenance honesty (Plans 03-01 to 03-03)

**Test:** Read `## Provenance` in `03-TRACEABILITY.md` and the one-line summaries of `03-01-SUMMARY.md`, `03-02-SUMMARY.md` and `03-03-SUMMARY.md`.
**Expected:** Each credits PR #7 (`8843cfc`, v0.3.1) for the session implementation and describes Phase 3 as characterisation tests only. The mechanical half (no PR #7 test edited) is already proven: 0 removed lines in the test diff.
**Why human:** This is a judgement-tier prohibition, so the LLM verdict is non-authoritative.

#### 2. No overstated coverage in the evidence record (Plan 03-04)

**Test:** Skim the D-10 table, the D-08 matrix and `## Post-Review Strengthening` in `03-TRACEABILITY.md`.
**Expected:** No row claims more than its cited test proves. Cited IDs all resolve (116 of 116), the mutation directions were independently reproduced, and the CR-01 relabelling of post-exit `ag_frame` checks is explicit.
**Why human:** Whether wording overstates coverage is a judgement call.

### Non-Blocking Notes

- **Edge-probe classification:** 3 edge-probe rows (SESS-01, SESS-05, HTTP-02) are unclassified, a planning-tool limitation (#1110). Their criteria have test evidence, so this is not a behaviour gap.
- **Release gate not re-run:** build and verify-dist were not re-run by the verifier (they write `dist/`). The phase changes no packaged input, and Phase 4 owns installed-distribution closure.
- **Upstream observation:** the `_remove_session_files` glob observation is server-side and out of scope; you may want to report it upstream.

### Gaps Summary

There are no gaps. Phase 3 achieves its goal through the shipped PR #7 implementation, which is unchanged in `src/`, now locked by 8 new test functions (33 cases; 198 collected in the two session modules, up from 165). Every roadmap success criterion and plan truth has passing behavioural evidence. The verifier independently reproduced the sensitivity of each key guard: value validation, path shape, fresh header copy, injected-client ownership (exit and stream path), and session scrubbing, including the CR-01 suspended-frame mutants that slipped past the pre-review suite.

The status is `human_needed` only because policy never lets the two judgement-tier provenance and coverage prohibitions pass silently. With those signed off, the phase is ready for `/gsd-ship` (D-04).

---

_Verified: 2026-10-20T08:18:27Z_
_Verifier: Claude (gsd-verifier)_
