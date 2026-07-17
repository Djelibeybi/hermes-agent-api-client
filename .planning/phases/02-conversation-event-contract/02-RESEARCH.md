# Phase 2: Conversation Event Contract - Research

**Researched:** 2026-07-17
**Domain:** Strict, bounded, secret-safe JSON/SSE lifecycle decoding for a typed Python client
**Confidence:** HIGH for repository architecture and the locked contract; MEDIUM for upstream-release currency under the GSD source classifier

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Terminal Consistency Matrix

- **D-01:** For `finish_reason="stop"`, accept `completed` absent or `true`, `failed` absent or `false`, `partial` absent or `false`, and require `error_code` to be absent. Expose `SUCCESS`, `partial=False`, and no failure reason.
- **D-02:** For `finish_reason="length"`, accept `completed` absent or `false`, `failed` absent or `false`, `partial` absent or `true`, and `error_code` absent or `output_truncated`. Always expose `LENGTH`, `partial=True`, and `OUTPUT_TRUNCATED`.
- **D-03:** For `finish_reason="error"`, require an exact server `partial` boolean; accept `completed` absent or `false` and `failed` absent or `true`. An absent or `agent_error` code maps to `AGENT_ERROR`; another valid bounded safe code maps to `UNKNOWN`.
- **D-04:** Omission and `null` are different. When an approved metadata field is present, it must have its exact valid type and value; `null`, integers used as booleans, strings used as booleans, and other coercible lookalikes fail as `HermesProtocolError`.

#### Tool Identifier and Name Text

- **D-05:** `tool_call_id` must be an exact built-in `str` containing 1-256 characters, each in the inclusive visible ASCII range `0x21..0x7e`.
- **D-06:** `tool_name` uses the same exact built-in `str`, 1-256 visible ASCII contract.
- **D-07:** Accepted tool IDs and names are preserved exactly. Do not trim, case-fold, normalize Unicode, apply path-shaped checks, or rewrite punctuation.
- **D-08:** Direct public `ToolProgressEvent` construction and private wire decoding enforce identical type, character, and length rules.

#### Terminal Envelope Compatibility

- **D-09:** For the canonical `v2026.7.7.2` shape, read lifecycle metadata only from the root `hermes` object. Same-named fields elsewhere are unapproved additive data and are ignored rather than treated as aliases.
- **D-10:** The `hermes` object may be absent for `stop` and `length`; it is required for `error` because the exact server `partial` boolean is mandatory.
- **D-11:** Unknown fields inside `hermes`, including raw error objects and text, are ignored and discarded without entering public values, exceptions, or retained decoder state.
- **D-12:** Pair-aware duplicate rejection covers the root `hermes` member, choice-level `finish_reason`, and approved lifecycle members inside `hermes`. Duplicates confined to ignored additive data remain ignored.

#### Fixture and Evidence Gate

- **D-13:** When tagged upstream source confirms the field schema but no captured fixture demonstrates an approved combination, an immutable design-derived fixture may define that approved combination. Combinations not explicitly approved remain rejected.
- **D-14:** Store versioned immutable fixture files with provenance that states whether each case is captured or design-derived and cites its exact source. Never represent derived data as captured upstream output.
- **D-15:** Phase 2 must verify both canonical Hermes `v2026.7.7.2` and the latest tagged Hermes release available during implementation.
- **D-16:** `v2026.7.7.2` root `hermes` remains the canonical envelope. An alternate latest-tag shape may also be accepted only when captured versioned evidence maps it unambiguously to the identical public event. Do not guess generic aliases; a behavioral difference that cannot preserve identical public semantics is a blocking contract decision.

### the agent's Discretion

No product-level behavior was delegated. Downstream planning may choose helper names, parser factoring, constant placement, and test parameterization while preserving every decision above and the established safe-sentinel, scrubbing, and delayed-terminal patterns.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 2 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

The descriptions below are copied from `.planning/REQUIREMENTS.md`. [VERIFIED: `.planning/REQUIREMENTS.md`]

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | A Python consumer can import `ToolProgressStatus` and an immutable `ToolProgressEvent` carrying a 1-256 character `tool_call_id`, a 1-256 character `tool_name`, and exactly `RUNNING` or `COMPLETED` status. | Extend the existing strict frozen public-model seam with one shared exact-visible-ASCII alias/validator and a strict `StrEnum`; export it from the package root. [VERIFIED: repository source + Context7 `/pydantic/pydantic`] |
| TOOL-02 | A Python consumer receives `toolCallId`, tool name, and status as ordered correlated progress events, including repeated lifecycle records needed to detect unmatched running calls after interruption. | Tagged source and tagged tests prove a running/completed pair with the same ID; the current decoder already preserves record order and must not add a tracker. [VERIFIED: Hermes `v2026.7.7.2` source and tests] |
| TOOL-03 | Missing, malformed, unknown, over-bound, or duplicate approved tool-lifecycle fields fail as `HermesProtocolError`; every duplicate singleton lifecycle key is invalid even when duplicate values agree. | Preserve JSON object pairs before dict construction, reject duplicates only at approved paths, and feed a sanitized projection into strict wire DTOs. [VERIFIED: CPython 3.13 Context7 docs + repository decoder] |
| TOOL-04 | Tool emoji, labels, arguments, results, other additive fields, and the raw tool payload never enter public models or exceptions. | Project only `toolCallId`, `tool`, and `status`; retain `extra="ignore"`, input-free failure sentinels, decoder scrubbing, and traceback-local canary tests. [VERIFIED: repository source/tests] |
| TERM-01 | A Python consumer can import `TerminalFailureReason`, and immutable `TerminalEvent` values expose `partial: bool = False` plus an optional closed failure reason. | Extend the existing strict frozen `TerminalEvent` and package-root export set without adding a union variant. [VERIFIED: repository source] |
| TERM-02 | `finish_reason="stop"` produces `SUCCESS`, `partial=False`, and no failure reason only when no abnormal terminal metadata is present. | Implement the locked stop row as an explicit matrix, preserving the existing `[DONE]`-only success behavior and delayed terminal commit. [VERIFIED: `02-CONTEXT.md` + repository tests] |
| TERM-03 | `finish_reason="length"` or compatible `output_truncated` metadata produces `LENGTH`, `partial=True`, and `OUTPUT_TRUNCATED`. | The tag-derived length shape is `completed=false`, `partial=true`, `failed=false`, `error_code=output_truncated`; approved omitted fields require truthfully design-derived fixtures. [VERIFIED: Hermes tagged source/tests + `02-CONTEXT.md`] |
| TERM-04 | `finish_reason="error"` preserves a strict server `partial` boolean, maps `agent_error` to `AGENT_ERROR`, and maps any other valid 1-256 character visible-ASCII safe error code to `UNKNOWN`. | The current tag emits `agent_error`; the open-but-bounded unknown-code branch is a contract extension and needs a design-derived fixture. [VERIFIED: Hermes tagged source + approved design] |
| TERM-05 | Duplicate approved terminal lifecycle fields or incompatible `completed`, `failed`, `partial`, `error_code`, and `finish_reason` combinations fail as `HermesProtocolError` instead of applying precedence guesses. | Pair-aware path projection plus a total terminal matrix can reject nulls, duplicates, and every unlisted combination before public construction. [VERIFIED: `02-CONTEXT.md` + CPython JSON docs] |
| TERM-06 | Raw Hermes error text, messages, exception types, and error objects never enter public events or exceptions; disconnects remain `HermesTransportError`, cancellation remains `CancelledError`, and the client synthesizes no terminal event. | Ignore root/raw `error` fields during projection, reuse sanitized parser sentinels, and preserve existing transport/cancellation branches. [VERIFIED: repository source/tests] |
| TERM-07 | A terminal event becomes observable only after the complete response and suffix validate and response cleanup succeeds, preserving the existing terminal-order guarantee. | Keep `_SSEDecoder._pending_terminal`, `finalize()`, decoder-source closure, and the outer client's terminal list/response-scope gate unchanged except for the richer value. [VERIFIED: repository source/tests] |
</phase_requirements>

## Summary

Phase 2 should be implemented as an in-place extension of the existing public-model, private-protocol, and SSE state-machine seams. No runtime or development package is needed: Python 3.13's pair-aware JSON hook, Pydantic 2.13.4's strict/frozen validation, and the existing decoder already supply the required primitives. [VERIFIED: repository source, Context7 `/python/cpython/v3.13.9`, Context7 `/pydantic/pydantic`]

The upstream evidence gate is currently favorable: `v2026.7.7.2` is both the canonical tag and the latest numeric Hermes release tag visible on 2026-07-17, and it peels to commit `9de9c25f620ff7f1ce0fd5457d596052d5159596`. There is therefore no alternate latest-tag envelope to support today. [VERIFIED: official `git ls-remote` and detached tagged checkout]

The important nuance is that the tagged handler can also generate contradictory metadata. In particular, an agent-task exception leaves `result=None`, defaults `completed` to `true`, then sets `failed=true`; the locked error row does not accept that pair, so the client must reject it as `HermesProtocolError` rather than normalize it. Valid tag-derived length and error rows, plus explicitly approved design-derived omission/unknown-code rows, must be distinguished in fixture provenance. [VERIFIED: Hermes `v2026.7.7.2` `gateway/platforms/api_server.py`; locked D-02/D-03/D-13]

**Primary recommendation:** Plan evidence and matrix tests first, then implement one pair-aware projection boundary, shared exact text validation, explicit public mapping, and finally the enriched delayed-terminal integration. [VERIFIED: repository architecture + locked decisions]

## Project Constraints (from AGENTS.md instructions supplied with the task)

- Check current dependency versions rather than relying on remembered versions. This research queried official PyPI metadata on 2026-07-17. [VERIFIED: user-supplied AGENTS instructions + PyPI JSON metadata]
- Do not ignore discovered problems merely because they pre-exist. The dependency drift found below is recorded as an active Phase 4 obligation because the approved roadmap assigns lock refresh and combined verification to Phase 4; it is not silently discarded. [VERIFIED: user-supplied AGENTS instructions + `.planning/ROADMAP.md`]
- For library, framework, SDK, API, or CLI documentation, resolve with `npx ctx7@latest library` before `npx ctx7@latest docs`, use no more than three commands per question, and do not include secrets in queries. The Hermes, Pydantic, and CPython lookups followed that sequence. [VERIFIED: user-supplied AGENTS instructions + command results]
- A Context7 quota failure must be reported rather than silently replaced with training knowledge. No quota failure occurred in this research. [VERIFIED: command results]
- No on-disk `AGENTS.md`, `.codex/skills/`, or `.agents/skills/` was present in this checkout during discovery; the instructions embedded in the task remain authoritative. [VERIFIED: repository file discovery]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Public event vocabulary and direct construction | Client library / Public API (`models.py`, `__init__.py`) | Type-verification tests | Consumers import frozen enums/models here; wire aliases must not escape this tier. [VERIFIED: repository source] |
| Duplicate-aware JSON lifecycle intake | Client library / Protocol boundary (`protocol.py` or a private helper adjacent to it) | SSE record dispatch | Duplicate evidence exists only before dict construction, while approved-path interpretation belongs with private validation. [VERIFIED: CPython docs + repository architecture] |
| Tool and terminal wire-to-public mapping | Client library / SSE application mapper (`sse.py`) | Private protocol DTOs | `_decode_application_record` already owns ordered event construction from sanitized wire values. [VERIFIED: repository source] |
| Terminal withholding and cleanup ordering | Client library / SSE and transport state machines | Outer client response scope | `_pending_terminal` withholds at the decoder boundary; `_stream_chat_events` withholds again until HTTP response cleanup. [VERIFIED: repository source/tests] |
| Upstream/version provenance | Evidence fixtures and `provenance.json` | Tests | Accepted combinations must be traceable to captured/tag-derived or explicitly design-derived evidence. [VERIFIED: locked D-13-D-16 + existing provenance] |
| Unmatched tool-call policy | Consumer integration (`hermes-conversation`) | Client emits ordered facts only | This package must not synthesize or reconcile lifecycle state; repeated records remain observable facts. [VERIFIED: requirements and approved design] |

## Upstream Evidence and Compatibility Gate

### Release identity

| Item | Result | Planning consequence |
|------|--------|----------------------|
| Canonical tag | Annotated tag `v2026.7.7.2`, tag object `b7751df...`, peeled commit `9de9c25f...`, commit timestamp 2026-07-07. [VERIFIED: official Git remote + detached checkout] | Keep the existing version root and commit identity in provenance. |
| Latest numeric release tag on 2026-07-17 | `v2026.7.7.2`. [VERIFIED: official `git ls-remote --tags --refs`, version-sorted] | D-16's alternate-shape branch is inactive today; implementation must still repeat this check before coding. |
| Context7 index | `/nousresearch/hermes-agent` is the exact high-reputation match; its source excerpts agree with the detached tag for the relevant handler. [VERIFIED: Context7 resolution/docs + detached source] | Context7 supports discovery, but immutable tag/commit URLs remain the evidence authority. |
| Untagged `main` | `main` is ahead of the tag and is not an approved compatibility target. [VERIFIED: official Git remote + D-15/D-16] | Do not add permissive aliases based on `main`; only a newer immutable tag can activate version-aware support. |

### Exact tagged tool-progress shapes

| Lifecycle | Approved fields emitted by the tag | Additive/raw fields | Evidence |
|-----------|------------------------------------|---------------------|----------|
| Running | `tool`, `toolCallId`, `status="running"` | `emoji` and `label` are also emitted and must be discarded. | Tagged source lines 2220-2244 and tagged test `test_stream_emits_tool_lifecycle_with_call_id`. [VERIFIED: official tagged source/tests] |
| Completed | `tool`, the same `toolCallId`, `status="completed"` | No result or arguments are emitted by this callback, but hostile/additive payload fields must still be ignored. | Tagged source lines 2246-2260 and the same tagged test. [VERIFIED: official tagged source/tests] |
| Ordering | The upstream tagged test observes exactly running then completed with the same ID. | Internal tools and orphan completions are filtered upstream, but this client must preserve any valid records it actually receives rather than reproduce server tracking. | Tagged tests lines 1397-1477. [VERIFIED: official tagged tests + TOOL-02 ownership boundary] |

### Exact tagged terminal envelope

The streaming finish chunk contains choice-level `finish_reason`. For non-stop finishes it may also contain a raw root `error` object and always contains root `hermes` with `completed`, `partial`, `failed`, raw `error`, and `error_code`; the raw fields are not public contract inputs. [VERIFIED: official tagged source lines 2524-2564]

| Tagged/generated condition | Root `hermes` lifecycle facts | Contract disposition |
|----------------------------|-------------------------------|----------------------|
| Normal completion | `finish_reason="stop"`; `hermes` absent. [VERIFIED: tagged source and upstream normal-completion test] | Accept as `SUCCESS`, `partial=False`, no reason. |
| Truncation result (`completed=false`, `partial=true`, `failed=false`, truncation error text) | `error_code="output_truncated"`; upstream test confirms `completed=false` and `partial=true`. [VERIFIED: tagged source and `test_truncation_with_partial_text_uses_length_finish_reason`] | Accept as `LENGTH`, `partial=True`, `OUTPUT_TRUNCATED`; discard all raw error text. |
| Explicit failed result (`completed=false`, `failed=true`) | `finish_reason="error"`, exact `partial` boolean, `error_code="agent_error"`. [VERIFIED: tagged handler construction; approved source-derived combination] | Accept as `UPSTREAM_ERROR`, preserve `partial`, reason `AGENT_ERROR`. |
| Agent task raises before returning a result | Handler defaults `completed=true`, then sets `failed=true`, uses `finish_reason="error"` and `agent_error`. [VERIFIED: tagged source lines 2504-2562] | Reject as contradictory under D-03/TERM-05; do not guess that `failed` wins. |
| Other incomplete result combinations | The handler can mechanically serialize booleans that do not satisfy the locked matrix if its result dict is internally inconsistent. [VERIFIED: tagged source control flow] | Reject every unlisted combination; do not broaden the matrix to mirror upstream bugs. |
| Unknown bounded safe error code | Not emitted by this tag. [VERIFIED: tagged source has only `output_truncated` and `agent_error`] | Accept only because TERM-04/D-03 explicitly define it; fixture must be labeled design-derived and map to `UNKNOWN`. |

### Fixture plan implications

- Preserve `tests/fixtures/hermes/v2026.7.7.2/chat_completions/complete.sse` as its existing `synthetic-derived` evidence; it currently proves one running record and a normal stop, not a completed tool event or abnormal terminal combinations. [VERIFIED: fixture and provenance]
- Add immutable tag-source-derived fixtures for the running/completed pair and canonical valid non-stop field layout, citing the exact tag, peeled commit, source lines, and tagged test where applicable. [VERIFIED: locked D-13/D-14 + official tagged source]
- Add explicitly `design-derived` fixtures for approved omissions and an unknown bounded error code; do not label them captures. [VERIFIED: locked D-13/D-14]
- Add one contradictory tag-source-derived fixture for the task-exception `completed=true`/`failed=true` shape and assert rejection. [VERIFIED: tagged source + locked D-03]
- At implementation start, repeat latest-tag enumeration. If a later tag exists, inspect the exact handler and fixture shapes; support it only with a version-specific, evidence-backed mapping that yields identical public events, otherwise stop as blocked under D-16. [VERIFIED: locked D-15/D-16]

## Standard Stack

### Core

| Library/Runtime | Phase-2 version | Purpose | Why standard |
|-----------------|-----------------|---------|--------------|
| Python | Project `>=3.13`; local 3.13.11 | `StrEnum`, async generators, `json.loads(object_pairs_hook=...)`, exact type checks | Already supported; the standard JSON hook preserves ordered duplicate members without a new dependency. [VERIFIED: `pyproject.toml`, local runtime, Context7 `/python/cpython/v3.13.9`] |
| Pydantic | Locked and latest direct release `2.13.4` | Frozen strict public models and private DTO validation | Existing `_FrozenModel`/`_WireModel` patterns are correct; pre-validation is still required for exact built-in strings and omission-vs-null. [VERIFIED: `uv.lock`, PyPI, Context7, local probe] |
| HTTPX | Locked and latest `0.28.1` | Existing response stream and cleanup boundary | No transport API change is required, but TERM-07 regression tests cross this boundary. [VERIFIED: `uv.lock`, PyPI, repository source] |
| Repository SSE decoder | Current source | Bounded framing, event order, scrubbing, delayed terminal | Extending the established state machine minimizes ordering and leakage risk. [VERIFIED: repository source/tests] |

### Supporting test/tool stack

| Tool | Locked | Latest on 2026-07-17 | Use in this phase |
|------|--------|----------------------|-------------------|
| pytest | 9.1.1 | 9.1.1 | Parameterized matrices and async decoder/lifecycle tests. [VERIFIED: `uv.lock` + PyPI] |
| pytest-asyncio | 1.4.0 | 1.4.0 | Async stream and cancellation tests. [VERIFIED: `uv.lock` + PyPI] |
| pytest-cov | 7.1.0 | 7.1.0 | Existing 100% branch gate; use the pytest plugin, not a separate coverage CLI workflow. [VERIFIED: `pyproject.toml`, `uv.lock`, PyPI] |
| basedpyright | 1.39.9 | 1.39.9 | Strict public typing and union/export validation. [VERIFIED: `uv.lock` + PyPI] |
| Ruff | 0.15.21 | 0.15.22 | Existing lint/format gate; exact pin is stale and belongs in the Phase 4 dependency refresh. [VERIFIED: `pyproject.toml`, `uv.lock`, PyPI] |
| prek | 0.4.9 | 0.4.10 | Existing installed pre-commit hook workflow; exact pin is stale and belongs in Phase 4. [VERIFIED: `pyproject.toml`, `uv.lock`, PyPI] |
| RESPX | 0.23.1 | 0.23.1 | Existing HTTPX behavior tests if TERM-07 needs outer transport coverage. [VERIFIED: `uv.lock` + PyPI] |
| uv_build | Declared `>=0.11.28,<0.12` | 0.11.29 | Existing build backend; no Phase-2 build change. [VERIFIED: `pyproject.toml` + PyPI] |
| python-semantic-release | 10.6.1 | 10.6.1 | Release group only; not used by Phase-2 implementation. [VERIFIED: `uv.lock` + PyPI] |

### Relevant transitive currency

| Package | Locked | Latest | Disposition |
|---------|--------|--------|-------------|
| pydantic-core | 2.46.4 | 2.47.0 | Pydantic 2.13.4 requires exactly 2.46.4; do not override the parent dependency's compatibility pin. [VERIFIED: installed Pydantic metadata + PyPI] |
| httpcore | 1.0.9 | 1.0.9 | Current; no action. [VERIFIED: `uv.lock` + PyPI] |
| coverage | 7.15.1 | 7.15.2 | Active Phase 4 lock-refresh item; no Phase-2 package change. [VERIFIED: `uv.lock` + PyPI] |
| GitPython | 3.1.51 | 3.1.52 | Active Phase 4 lock-refresh item through python-semantic-release. [VERIFIED: `uv.lock` + PyPI] |

### Direct dependency currency result

Official PyPI metadata shows that `prek` 0.4.10 (uploaded 2026-07-16) and Ruff 0.15.22 (uploaded 2026-07-16) now exceed the repository's exact direct dev pins. The runtime dependencies remain current. This does not justify mixing a lock/pin migration into Phase 2 because `.planning/ROADMAP.md` and DEPS-01 assign the reviewed refresh to Phase 4, but the later plan must update the direct pins as well as compatible transitive locks and re-check currency at execution time. [VERIFIED: PyPI JSON metadata + `pyproject.toml` + roadmap]

### Package Legitimacy Audit

Not applicable: Phase 2 installs and recommends no new external package. Existing packages were verified against the correct PyPI ecosystem and official project metadata. [VERIFIED: phase scope + PyPI]

**Installation:** none. Use the existing locked environment with `uv run --no-sync`; do not add or broaden a dependency for duplicate detection or validation. [VERIFIED: project workflow + phase scope]

## Architecture Patterns

### System Architecture Diagram

```text
untrusted bounded SSE record
          |
          v
Python json.loads(object_pairs_hook=pair-node)
          |
          v
path-aware projection
  | reject duplicate approved keys
  | discard ignored/additive values
  | preserve omission distinctly from null
          |
          v
strict frozen private DTOs (protocol.py)
          |
          +-------------------+
          |                   |
          v                   v
tool mapper              terminal matrix
(one record -> one event) (finish_reason + root hermes)
          |                   |
          +---------+---------+
                    v
          immutable public events
                    |
                    v
        _SSEDecoder pending-terminal gate
                    |
          validate suffix / DONE / EOF
                    |
          close source and HTTP response
                    |
                    v
             terminal observable
```

This flow retains the current two-stage terminal commit and introduces duplicate awareness before ordinary mappings can erase evidence. [VERIFIED: repository source + CPython docs]

### Recommended Project Structure

```text
src/hermes_agent_api_client/
├── models.py       # public enums, shared bounded text contract, frozen events
├── protocol.py     # pair nodes/projection, strict private DTOs, safe sentinels
├── sse.py          # explicit event mapping and existing delayed terminal state
└── __init__.py     # package-root public vocabulary

tests/
├── fixtures/hermes/v2026.7.7.2/
│   ├── chat_completions/     # existing + tag/design-derived lifecycle fixtures
│   └── provenance.json       # exact evidence kind, commit, source, hash
├── helpers/hermes.py         # immutable fixture loading; duplicate raw JSON helper if useful
├── test_protocol.py          # public model parity and private strict parsing
├── test_sse.py               # pair duplicates, ordering, matrix, secrecy, terminal gate
├── test_transport.py         # response-cleanup-before-terminal regression
└── test_package.py           # package-root export expectations
```

No new source module is necessary; helper factoring among these established seams is agent discretion. [VERIFIED: repository structure + `02-CONTEXT.md`]

### Pattern 1: Evidence-first executable matrices

Write fixture/provenance and parameterized acceptance/rejection rows before production mapping. Each accepted row must cite either immutable tagged evidence or the explicit design decision authorizing a derived case; every row not listed is rejected. [VERIFIED: locked D-01-D-16]

### Pattern 2: Pair-aware approved-field projection

Use `object_pairs_hook` to return a distinct private pair node for every JSON object. Walk only the schema locations relevant to the selected event: tool root keys for `hermes.tool.progress`; root `hermes`, the single choice's `finish_reason`, and lifecycle members within `hermes` for chat chunks. Reject same-value and conflicting duplicates of approved keys, but collapse/discard duplicates wholly inside ignored additive data. [VERIFIED: CPython JSON docs + locked D-12]

Do not use a global “reject every duplicate key” hook: that would contradict D-12's additive-data policy and could fail on duplicated raw error members the client intentionally ignores. [VERIFIED: locked D-12]

### Pattern 3: One exact visible-ASCII contract at both boundaries

Define one reusable validator/annotation for exact built-in `str`, length 1-256, and each code point between `0x21` and `0x7e`. Apply it to public `tool_call_id`/`tool_name`, private `toolCallId`/`tool`, and safe `error_code` where applicable. Do not strip or normalize. [VERIFIED: locked D-04-D-08 + TERM-04]

Pydantic strict string validation alone is insufficient: a local Pydantic 2.13.4 probe accepted a `str` subclass and normalized it to `str`; a pre-validator checking `type(value) is str` is required for D-08. Strict `StrEnum` fields accept enum instances but reject raw wire strings, so private wire status should remain a closed `Literal` and mapping should explicitly construct `ToolProgressStatus`. [VERIFIED: Context7 `/pydantic/pydantic` + local 2.13.4 probe]

### Pattern 4: Omission-aware terminal projection followed by a total mapper

Preserve “missing” separately from explicit JSON `null` before DTO construction. A nullable default alone is not enough because it conflates those states; either carry field-presence metadata or use a private omission sentinel that cannot be supplied by wire input. Reject explicit null before the matrix. [VERIFIED: locked D-04]

Feed only validated optional booleans/code into a pure terminal mapping helper whose accepted rows exactly match D-01-D-03. This helper should return a safe public `TerminalEvent` or an input-independent failure sentinel; it must not retain raw `error` data or a Pydantic `ValidationError`. [VERIFIED: repository safe-sentinel pattern + locked matrix]

### Pattern 5: Fact preservation without lifecycle policy

Emit one `ToolProgressEvent` for every accepted progress record in wire order, including repeated records. Do not deduplicate IDs, require local running-before-completed state, or synthesize a completion on interruption. The consumer can retain unmatched running IDs from events already yielded before a later transport failure. [VERIFIED: TOOL-02 + approved design]

### Pattern 6: Preserve the delayed-terminal commit

Keep `TerminalEvent` pending inside `_SSEDecoder`; reject post-terminal records and duplicate completion before `finalize()`, close the byte source, let the outer client exit the HTTP response context, then expose exactly the enriched terminal. Raw disconnects and cancellation do not enter the terminal mapper. [VERIFIED: repository source/tests + TERM-06/TERM-07]

### Anti-Patterns to Avoid

- **Ordinary `json.loads` into dict:** duplicate approved members have already collapsed to last-value-wins. [VERIFIED: CPython JSON docs]
- **Rejecting all duplicate JSON names globally:** violates the locked policy for ignored additive data. [VERIFIED: D-12]
- **Nullable DTO defaults without presence tracking:** accepts explicit null as omission. [VERIFIED: D-04]
- **Pydantic strict strings as exact-type proof:** strict mode still accepts a `str` subclass in the tested version. [VERIFIED: local Pydantic 2.13.4 probe]
- **Terminal precedence rules:** choosing `failed` or `error_code` over an incompatible `finish_reason` violates TERM-05. [VERIFIED: requirements]
- **Public raw error codes/messages:** unknown valid code maps to `UNKNOWN`; raw values and prose are discarded. [VERIFIED: TERM-04/TERM-06]
- **Client-owned tool registry:** would collapse repeated facts and move Home Assistant policy into the transport client. [VERIFIED: approved design]
- **Immediate terminal yield:** breaks the existing suffix and cleanup guarantee. [VERIFIED: TERM-07 + repository tests]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Duplicate-preserving JSON lexer | A second JSON parser or regex key scanner | Python `json.loads(object_pairs_hook=...)` plus narrow path projection | The standard parser preserves ordered pairs while still enforcing JSON syntax; regex cannot safely parse nesting/escaping. [VERIFIED: CPython docs] |
| Event schema framework | A new validation dependency | Existing frozen strict Pydantic models and small pre-validators | The package already centralizes model strictness and validation failure reduction. [VERIFIED: repository source] |
| SSE lifecycle engine | A replacement parser/state machine | Existing `_SSEDecoder` | It already enforces byte/event bounds, cleanup, cancellation, and terminal ordering with 100% branch coverage. [VERIFIED: repository source/tests] |
| Tool correlation policy | A client-side map of running/completed IDs | Ordered immutable events | Consumer policy must remain in `hermes-conversation`; repeated records are required facts. [VERIFIED: TOOL-02 and out-of-scope table] |
| Error taxonomy from upstream prose | Regex/classification over `error.message` | Closed `TerminalFailureReason` mapping from bounded safe code | Raw prose is unstable and potentially secret-bearing. [VERIFIED: TERM-04/TERM-06] |
| Alternate latest-tag aliases | Generic searches for `partial`, `failed`, or `error_code` anywhere | Exact versioned envelope mapping | Same-named additive fields are explicitly not aliases. [VERIFIED: D-09/D-16] |

**Key insight:** The hard part is not parsing more fields; it is retaining just enough structural evidence to reject ambiguity, then destroying everything outside the bounded public contract before any public failure is raised. [VERIFIED: requirements + repository secrecy tests]

## Common Pitfalls

### Pitfall 1: Duplicate evidence is lost before validation
**What goes wrong:** Pydantic receives a dict and cannot tell whether an approved member appeared twice. [VERIFIED: CPython docs + repository source]
**Avoidance:** pair-aware load, path-aware projection, raw same/conflicting duplicate tests. [VERIFIED: D-12]

### Pitfall 2: Duplicate detection is too broad
**What goes wrong:** ignored additive/raw objects become compatibility hazards. [VERIFIED: D-11/D-12]
**Avoidance:** duplicate policy must be keyed by event kind and exact object path, not member spelling anywhere in the tree. [VERIFIED: D-09/D-12]

### Pitfall 3: Explicit null silently becomes omission
**What goes wrong:** `bool | None = None` accepts both missing and null, weakening the matrix. [VERIFIED: D-04]
**Avoidance:** preserve field presence before nullable/defaulted validation and test every lifecycle field with null. [VERIFIED: D-04]

### Pitfall 4: Tag-derived and design-derived fixtures are conflated
**What goes wrong:** tests claim upstream support for omissions or unknown codes the current tag never emits. [VERIFIED: tagged source + existing provenance]
**Avoidance:** evidence kind, exact source URL/commit, reproduction mode, semantic assertions, and immutable hash per fixture. [VERIFIED: D-13/D-14]

### Pitfall 5: Tagged contradictions are normalized
**What goes wrong:** task-exception metadata (`completed=true`, `failed=true`) is mapped to a plausible agent error. [VERIFIED: tagged source]
**Avoidance:** include it as a tag-source-derived rejection row; no field wins. [VERIFIED: D-03/TERM-05]

### Pitfall 6: Public/wire bounds drift
**What goes wrong:** direct construction and decoded events accept different types, characters, or lengths. [VERIFIED: D-08]
**Avoidance:** one validator/constant, exact 0/1/256/257 tests, Unicode/control/space tests, `str` subclass tests, and preservation assertions. [VERIFIED: D-05-D-08]

### Pitfall 7: Strict enum construction is weakened for wire convenience
**What goes wrong:** public `status` remains an open string or public model strictness is disabled so JSON strings coerce into enums. [VERIFIED: current model + local Pydantic probe]
**Avoidance:** private `Literal`, explicit `ToolProgressStatus(...)`, strict public enum field. [VERIFIED: Context7 + approved design]

### Pitfall 8: Raw ignored data survives in exception frames
**What goes wrong:** a caught `ValidationError`, pair tree, raw record, or nested error object remains in `HermesProtocolError` traceback locals/cause/context. [VERIFIED: repository secrecy test patterns]
**Avoidance:** return input-free sentinels, clear raw locals/state, raise from raw-record-free helpers, and inspect package-owned traceback frames with canaries. [VERIFIED: repository source/tests]

### Pitfall 9: Ordered facts are “helpfully” reconciled
**What goes wrong:** repeated running/completed records are dropped or reordered, preventing consumer-side unmatched-call detection. [VERIFIED: TOOL-02]
**Avoidance:** one valid record in, one public event out; no registry. [VERIFIED: approved design]

### Pitfall 10: The enriched terminal bypasses existing cleanup precedence
**What goes wrong:** a correct-looking terminal is observed before malformed suffix, source close failure, or HTTP response cleanup failure. [VERIFIED: repository tests]
**Avoidance:** enrich only the value stored in `_pending_terminal`; do not relocate when it is committed. [VERIFIED: TERM-07]

### Pitfall 11: Dependency research goes stale between planning and verification
**What goes wrong:** exact versions recorded today are treated as permanent latest versions. [VERIFIED: PyPI drift found during this research]
**Avoidance:** Phase 4 re-queries all direct and relevant transitive versions immediately before the reviewed lock/pin refresh. [VERIFIED: DEPS-01 + roadmap]

## Code Examples

### Preserve object pairs without confusing objects and arrays

```python
from dataclasses import dataclass
import json

@dataclass(frozen=True, slots=True)
class _JsonObjectPairs:
    pairs: tuple[tuple[str, object], ...]

def _object_pairs(pairs: list[tuple[str, object]]) -> _JsonObjectPairs:
    return _JsonObjectPairs(tuple(pairs))

document = json.loads(data, object_pairs_hook=_object_pairs)
```

Source pattern: CPython 3.13 documents that normal decoding keeps only the last repeated name and that `object_pairs_hook` can preserve the member sequence; the private wrapper keeps JSON arrays distinguishable from objects. [VERIFIED: Context7 `/python/cpython/v3.13.9`; wrapper is repository-specific design]

### Require exact visible-ASCII text before ordinary Pydantic validation

```python
_LIFECYCLE_TEXT_MAX = 256

def _require_lifecycle_text(value: object) -> object:
    if type(value) is not str:
        raise ValueError
    if not 1 <= len(value) <= _LIFECYCLE_TEXT_MAX:
        raise ValueError
    if any(not "!" <= char <= "~" for char in value):
        raise ValueError
    return value
```

Use this as a `mode="before"` validator or `BeforeValidator`-backed annotation at both private and public boundaries; do not interpolate `value` into errors. [VERIFIED: D-05-D-08 + Context7 `/pydantic/pydantic` + local probe]

### Keep wire literals separate from strict public enums

```python
class _ToolProgressWire(_WireModel):
    tool_call_id: _LifecycleText = Field(alias="toolCallId")
    tool: _LifecycleText
    status: Literal["running", "completed"]

return ToolProgressEvent(
    tool_call_id=progress.tool_call_id,
    tool_name=progress.tool,
    status=ToolProgressStatus(progress.status),
)
```

This preserves strict public enum construction while accepting the exact closed JSON literals at the wire boundary. [VERIFIED: Context7 `/pydantic/pydantic`, local probe, approved design]

### Express terminal mapping as data, not precedence

```text
stop   -> completed {missing,true};  failed {missing,false};
          partial {missing,false};    error_code {missing}
length -> completed {missing,false}; failed {missing,false};
          partial {missing,true};     error_code {missing,output_truncated}
error  -> completed {missing,false}; failed {missing,true};
          partial {false,true};       error_code {missing,agent_error,other-safe}
```

Every field present as null or with a coercible lookalike, and every combination outside these sets, is failure. `error` additionally requires the root `hermes` object and exact `partial` presence. [VERIFIED: D-01-D-04/D-10]

## State of the Art

| Old/current baseline | Phase-2 approach | Impact |
|----------------------|------------------|--------|
| `json.loads(data)` returns dicts and silently collapses repeated names. [VERIFIED: repository source + CPython docs] | Pair-aware object nodes followed by approved-path projection. | Same-value and conflicting lifecycle duplicates become rejectable without rejecting ignored additive duplicates. |
| `_ToolProgressWire` has only unbounded `tool` and open `status`; public event discards `toolCallId`. [VERIFIED: repository source] | Shared exact bound, closed literal/enum, explicit ID mapping. | Correlated repeated lifecycle facts remain ordered and bounded. |
| `TerminalEvent` exposes only outcome; `finish_reason` maps directly. [VERIFIED: repository source] | Omission-aware metadata DTO plus total consistency matrix and safe failure enum. | Consumers receive stable partial/failure facts without raw errors or precedence guesses. |
| Existing fixture proves one running event and normal stop only. [VERIFIED: fixture/provenance] | Truthfully separated tag-source-derived and design-derived lifecycle fixtures. | Test claims become auditable against immutable upstream evidence and locked decisions. |
| Earlier milestone research found only transitive patch drift. [VERIFIED: `.planning/research/STACK.md`] | Current PyPI check also finds direct dev-pin drift in prek and Ruff. [VERIFIED: PyPI 2026-07-17] | Phase 4 must update exact pins and compatible locks after rechecking currency. |

**Deprecated/outdated:** treating Pydantic `strict=True` as sufficient for exact built-in `str` is disproved for the locked Pydantic version; treating the earlier dependency snapshot as current is also outdated. [VERIFIED: local probe + PyPI]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 + pytest-cov 7.1.0. [VERIFIED: `uv.lock`] |
| Config file | `pyproject.toml`; strict markers/config, branch coverage, `fail_under=100`. [VERIFIED: `pyproject.toml`] |
| Quick run command | `uv run --no-sync pytest tests/test_protocol.py tests/test_sse.py --no-cov -q` (184 existing tests passed in 0.44s during research). [VERIFIED: local test run] |
| Full suite command | `uv run --no-sync pytest -q` (354 tests passed with 100% branch coverage in 6.45s during research). [VERIFIED: local test run] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-01 | Public enum/model import, strict frozen fields, exact bounds/type/characters | unit/static | `uv run --no-sync pytest tests/test_protocol.py tests/test_package.py --no-cov -q` | Yes; Phase-2 cases are Wave 0. [VERIFIED: repository tests] |
| TOOL-02 | Running/completed correlation, interleaving, repetition, interruption prefix | async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | Yes; Phase-2 cases are Wave 0. [VERIFIED: repository tests] |
| TOOL-03 | Missing/malformed/unknown/over-bound fields and raw same/conflicting duplicate keys | async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | Yes; duplicate-key cases are Wave 0. [VERIFIED: repository tests] |
| TOOL-04 | Additive/raw tool fields absent from values, errors, traceback frames, decoder state | async security unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | Yes; new canary cases are Wave 0. [VERIFIED: repository test helpers] |
| TERM-01 | Public failure enum and defaulted strict frozen terminal fields | unit/static | `uv run --no-sync pytest tests/test_protocol.py tests/test_package.py --no-cov -q` | Yes; Phase-2 cases are Wave 0. [VERIFIED: repository tests] |
| TERM-02 | Complete stop acceptance/rejection matrix | parameterized async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | Yes; matrix rows are Wave 0. [VERIFIED: repository tests] |
| TERM-03 | Length/output-truncated matrix and public mapping | parameterized async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | Yes; matrix rows/fixtures are Wave 0. [VERIFIED: repository tests] |
| TERM-04 | Error partial booleans, agent/unknown code mapping, code bounds | parameterized async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | Yes; matrix rows/fixtures are Wave 0. [VERIFIED: repository tests] |
| TERM-05 | Duplicate approved paths, explicit null, every contradiction | property-style parameterized async unit | `uv run --no-sync pytest tests/test_sse.py --no-cov -q` | Yes; pair-aware cases are Wave 0. [VERIFIED: repository tests] |
| TERM-06 | Raw error canaries absent; transport/cancel classifications unchanged; no synthetic terminal | async security/regression | `uv run --no-sync pytest tests/test_sse.py tests/test_transport.py --no-cov -q` | Yes; enriched canaries are Wave 0. [VERIFIED: repository tests] |
| TERM-07 | Suffix/source/HTTP cleanup precedes terminal observability | async integration/regression | `uv run --no-sync pytest tests/test_sse.py tests/test_transport.py --no-cov -q` | Yes; enrich existing terminal-order assertions. [VERIFIED: repository tests] |

### Sampling Rate

- **Per task commit:** run the touched file without coverage, normally `uv run --no-sync pytest tests/test_protocol.py tests/test_sse.py --no-cov -q`. [VERIFIED: measured quick suite]
- **Per wave merge:** run `uv run --no-sync pytest -q` so the 100% branch gate applies. [VERIFIED: project config]
- **Phase gate:** full pytest/coverage, Ruff, basedpyright, and package-root export tests green; Phase 4 remains responsible for built wheel/sdist and final dependency refresh. [VERIFIED: roadmap boundary]

### Wave 0 Gaps

- [ ] Add versioned running/completed and terminal evidence fixtures under `tests/fixtures/hermes/v2026.7.7.2/chat_completions/`, with explicit tag-source-derived/design-derived evidence kinds and SHA-256 entries in `provenance.json`. [VERIFIED: D-13-D-16]
- [ ] Add a raw duplicate-member test helper only if it improves readability; it must produce bytes/text because Python dicts cannot represent duplicates. [VERIFIED: CPython object behavior]
- [ ] Add public exact-construction/bounds cases in `tests/test_protocol.py` and package-root names in `tests/test_package.py`. [VERIFIED: repository test organization]
- [ ] Add exhaustive tool and terminal pair/matrix/secrecy/order cases in `tests/test_sse.py`; extend `tests/test_transport.py` only for the outer cleanup gate. [VERIFIED: repository test responsibilities]
- No framework install or config change is required. [VERIFIED: baseline test runs]

## Security Domain

Security enforcement is enabled at ASVS Level 1 and blocks high-severity findings. The current official OWASP ASVS release tag is `v5.0.0_release`; ASVS 5 renumbered categories, so this research uses current category names rather than the older template labels. [VERIFIED: `.planning/config.json` + official OWASP ASVS tag/source]

### Applicable ASVS 5.0 Categories

| ASVS Category/Control | Applies | Standard control for this phase |
|-----------------------|---------|---------------------------------|
| V2 Validation and Business Logic, 2.1.1 | Yes, L1 | The locked document defines exact type, range, character, presence, duplicate, and cross-field consistency rules. [VERIFIED: ASVS 5.0.0 + `02-CONTEXT.md`] |
| V2, 2.2.1 | Yes, L1 | Positive validation against closed statuses/reasons, exact visible-ASCII bounds, and total accepted terminal rows. [VERIFIED: ASVS 5.0.0 + requirements] |
| V2, 2.2.2 | Yes, L1 | Enforce at the package's trusted protocol boundary; do not rely on upstream validation. [VERIFIED: ASVS 5.0.0 + repository boundary] |
| V15 Secure Coding and Architecture, 15.1.1/15.2.1 | Yes, L1 | Track and remediate dependency drift under the Phase 4 currency gate; no new component enters Phase 2. [VERIFIED: ASVS 5.0.0 + DEPS-01] |
| V15, 15.3.1 | Yes, L1 | Return only the bounded public subset; raw tool/error object fields never leave the protocol layer. [VERIFIED: ASVS 5.0.0 + TOOL-04/TERM-06] |
| V16 Error Handling | Project-required beyond L1 | ASVS 16.5 controls are L2, but the project contract independently requires generic metadata-only failures, no raw traceback/cause/context leakage, and fail-closed contradictions. [VERIFIED: ASVS 5.0.0 + project requirements] |
| Authentication, session management, access control, cryptography | No Phase-2 change | Existing transport behavior is regression-tested; session headers belong to Phase 3 and no cryptographic primitive is introduced. [VERIFIED: roadmap] |

### Known Threat Patterns for the Python JSON/SSE Boundary

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Duplicate-key ambiguity changes lifecycle meaning | Tampering | Preserve pairs; reject duplicate approved singleton keys at exact paths before dict construction. [VERIFIED: D-12]
| Coercible/null metadata bypasses the consistency matrix | Tampering | Exact types, presence tracking, closed literals, total matrix. [VERIFIED: D-01-D-04]
| Oversized identifiers/error codes consume state or escape semantic bounds | Denial of Service | 256-character semantic caps plus existing 64-KiB event and 256-KiB pending-line bounds. [VERIFIED: requirements + repository constants]
| Raw tool arguments/results or terminal error data leaks through values/exceptions/frames | Information Disclosure | Approved-field projection, input-free sentinels, raw-state scrub, traceback-local canaries. [VERIFIED: TOOL-04/TERM-06 + repository tests]
| Contradictory terminal fields are normalized into success/failure | Tampering / Spoofing | No precedence; reject every unlisted combination. [VERIFIED: TERM-05]
| Premature terminal is observed before malformed suffix or cleanup failure | Tampering | Existing delayed-terminal two-stage commit. [VERIFIED: TERM-07]

### Security gate for the plan

Any implementation that globally accepts duplicate approved keys, exposes raw ignored fields, retains canaries in package-owned failure frames/state, or yields a terminal before suffix and cleanup validation is a high-severity contract failure and must block completion. [VERIFIED: security config + phase requirements]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Tests/implementation | Yes | 3.13.11 | Project also supports Python 3.14; no fallback needed. [VERIFIED: local command + `pyproject.toml`] |
| uv | Locked execution | Yes | 0.11.29 | None needed. [VERIFIED: local command] |
| Git/network | Tagged evidence check | Yes | Git 2.50.1; official remote reachable | If network later fails, use the pinned local fixture/commit only and report latest-tag verification blocked; do not guess. [VERIFIED: local command + successful remote queries] |
| Node/npm/npx | Required Context7 CLI | Yes | Node 26.5.0; npm/npx 11.17.0 | Context7 quota failure must be surfaced per AGENTS instructions. [VERIFIED: local command] |
| Context7 CLI | Current API/library docs | Yes | `npx ctx7@latest` completed Hermes, Pydantic, CPython queries | Official immutable source is the evidence cross-check, not a training-data fallback. [VERIFIED: command results] |
| pytest stack | Nyquist validation | Yes | Versions in Standard Stack | No install needed. [VERIFIED: baseline tests] |
| ripgrep/jq | Evidence and metadata inspection | Yes | ripgrep 15.1.0; jq 1.8.2 | Standard Python parsing is available if jq is absent elsewhere. [VERIFIED: local commands] |

**Missing dependencies with no fallback:** none. [VERIFIED: environment probes]

**Missing dependencies with fallback:** none. [VERIFIED: environment probes]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | None. All implementation-shaping claims are locked project decisions, current repository observations, local behavior probes, or official current/tagged sources. | — | — |

## Open Questions

No product or wire-contract question remains open for planning. [VERIFIED: `02-CONTEXT.md`]

Two execution-time revalidation gates remain mandatory rather than unresolved design questions:

1. Re-enumerate Hermes numeric tags immediately before implementation; if a later tag appears, apply D-16 and block on incompatible semantics. [VERIFIED: D-15/D-16]
2. Re-query PyPI immediately before Phase 4's pin/lock refresh; today's versions are evidence, not permanent latest values. [VERIFIED: DEPS-01 + observed drift]

## Sources

### Primary (authoritative)

- Context7 `/nousresearch/hermes-agent` plus [Hermes Agent API server at `v2026.7.7.2`](https://github.com/NousResearch/hermes-agent/blob/v2026.7.7.2/gateway/platforms/api_server.py) — exact tool callbacks, event framing, finish-reason selection, root `hermes` envelope, and contradictory task-exception shape. [VERIFIED: Context7 + detached tag]
- [Hermes tagged API-server tests](https://github.com/NousResearch/hermes-agent/blob/v2026.7.7.2/tests/gateway/test_api_server.py) — correlated running/completed records, canonical truncation fields, and normal-stop absence of `hermes`. [VERIFIED: detached tag]
- Context7 `/python/cpython/v3.13.9` and [Python 3.13 JSON documentation](https://docs.python.org/3.13/library/json.html) — default duplicate-name collapse and `object_pairs_hook`. [VERIFIED: Context7]
- Context7 `/pydantic/pydantic` and the local installed Pydantic 2.13.4 — strict boolean/enum behavior, frozen/strict model patterns, exact-string-subclass probe. [VERIFIED: Context7 + local probe]
- [OWASP ASVS `v5.0.0_release`](https://github.com/OWASP/ASVS/tree/v5.0.0_release/5.0/en) — current categories and Level 1 controls V2.1.1, V2.2.1, V2.2.2, V15.1.1, V15.2.1, and V15.3.1. [VERIFIED: official tagged source]
- Official PyPI JSON metadata for all direct and selected transitive packages — current versions and upload timestamps on 2026-07-17. [VERIFIED: PyPI]
- Local `.planning`, source, tests, fixtures, `pyproject.toml`, and `uv.lock` — locked decisions, architecture, test commands, package versions, and provenance. [VERIFIED: repository]

### Secondary

- GSD research-plan confidence classification rates Context7 and verified websearch inputs as MEDIUM; upstream release-currency claims are therefore reported as MEDIUM even though they were cross-checked against immutable official source. [VERIFIED: GSD `classify-confidence` seam]

### Tertiary

- None. No training-only claim is used to shape the plan.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — exact local lock/runtime, current PyPI metadata, Context7, and local probes agree. [VERIFIED: cited sources]
- Architecture: HIGH — the extension seams and lifecycle guarantees are directly exercised by the current 100%-covered repository. [VERIFIED: source + baseline tests]
- Upstream tag shape: MEDIUM — immutable official source and tests are exact, but the mandated GSD provider classifier assigns MEDIUM to the Context7/verified-web research route. [VERIFIED: classifier result]
- Pitfalls: HIGH — each maps to a locked decision, tagged contradiction, or existing regression/security test pattern. [VERIFIED: cited sources]
- Validation: HIGH — the existing quick/full suites ran successfully and every Phase-2 requirement has a fast automated path. [VERIFIED: local test runs]

**Research date:** 2026-07-17
**Valid until:** 2026-07-18 for latest-tag/dependency currency; architectural and locked-contract findings remain valid until the phase context changes.
