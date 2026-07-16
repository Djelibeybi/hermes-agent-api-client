# Phase 2: Conversation Event Contract - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers the public and wire-level conversation event contract: bounded correlated tool-progress events, enriched safe terminal metadata, strict duplicate and contradiction rejection, versioned upstream evidence, and preservation of the existing delayed-terminal and secret-safe stream boundary. Session header transport belongs to Phase 3; combined package, regression, and dependency verification belongs to Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Terminal Consistency Matrix

- **D-01:** For `finish_reason="stop"`, accept `completed` absent or `true`, `failed` absent or `false`, `partial` absent or `false`, and require `error_code` to be absent. Expose `SUCCESS`, `partial=False`, and no failure reason.
- **D-02:** For `finish_reason="length"`, accept `completed` absent or `false`, `failed` absent or `false`, `partial` absent or `true`, and `error_code` absent or `output_truncated`. Always expose `LENGTH`, `partial=True`, and `OUTPUT_TRUNCATED`.
- **D-03:** For `finish_reason="error"`, require an exact server `partial` boolean; accept `completed` absent or `false` and `failed` absent or `true`. An absent or `agent_error` code maps to `AGENT_ERROR`; another valid bounded safe code maps to `UNKNOWN`.
- **D-04:** Omission and `null` are different. When an approved metadata field is present, it must have its exact valid type and value; `null`, integers used as booleans, strings used as booleans, and other coercible lookalikes fail as `HermesProtocolError`.

### Tool Identifier and Name Text

- **D-05:** `tool_call_id` must be an exact built-in `str` containing 1-256 characters, each in the inclusive visible ASCII range `0x21..0x7e`.
- **D-06:** `tool_name` uses the same exact built-in `str`, 1-256 visible ASCII contract.
- **D-07:** Accepted tool IDs and names are preserved exactly. Do not trim, case-fold, normalize Unicode, apply path-shaped checks, or rewrite punctuation.
- **D-08:** Direct public `ToolProgressEvent` construction and private wire decoding enforce identical type, character, and length rules.

### Terminal Envelope Compatibility

- **D-09:** For the canonical `v2026.7.7.2` shape, read lifecycle metadata only from the root `hermes` object. Same-named fields elsewhere are unapproved additive data and are ignored rather than treated as aliases.
- **D-10:** The `hermes` object may be absent for `stop` and `length`; it is required for `error` because the exact server `partial` boolean is mandatory.
- **D-11:** Unknown fields inside `hermes`, including raw error objects and text, are ignored and discarded without entering public values, exceptions, or retained decoder state.
- **D-12:** Pair-aware duplicate rejection covers the root `hermes` member, choice-level `finish_reason`, and approved lifecycle members inside `hermes`. Duplicates confined to ignored additive data remain ignored.

### Fixture and Evidence Gate

- **D-13:** When tagged upstream source confirms the field schema but no captured fixture demonstrates an approved combination, an immutable design-derived fixture may define that approved combination. Combinations not explicitly approved remain rejected.
- **D-14:** Store versioned immutable fixture files with provenance that states whether each case is captured or design-derived and cites its exact source. Never represent derived data as captured upstream output.
- **D-15:** Phase 2 must verify both canonical Hermes `v2026.7.7.2` and the latest tagged Hermes release available during implementation.
- **D-16:** `v2026.7.7.2` root `hermes` remains the canonical envelope. An alternate latest-tag shape may also be accepted only when captured versioned evidence maps it unambiguously to the identical public event. Do not guess generic aliases; a behavioral difference that cannot preserve identical public semantics is a blocking contract decision.

### the agent's Discretion

No product-level behavior was delegated. Downstream planning may choose helper names, parser factoring, constant placement, and test parameterization while preserving every decision above and the established safe-sentinel, scrubbing, and delayed-terminal patterns.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Approved Contract

- `docs/superpowers/specs/2026-07-17-conversation-contract-design.md` — Authoritative requested public models, tool correlation, terminal mapping, secrecy boundaries, and acceptance tests.
- `.planning/REQUIREMENTS.md` — Phase 2 requirement IDs `TOOL-01` through `TOOL-04` and `TERM-01` through `TERM-07`, plus milestone-wide exclusions.
- `.planning/ROADMAP.md` — Phase boundary, dependency on the historical Phase 1 baseline, observable success criteria, and later-phase separation.

### Research and Evidence

- `.planning/research/SUMMARY.md` — Consolidated architecture, risk, phase ordering, and evidence recommendations.
- `.planning/research/ARCHITECTURE.md` — Existing module seams, tagged envelope location, data flow, and build-order analysis.
- `.planning/research/PITFALLS.md` — Duplicate-key collapse, raw-state retention, terminal precedence, field-bound, and artifact-regression hazards.
- `tests/fixtures/hermes/v2026.7.7.2/provenance.json` — Existing immutable upstream fixture provenance; new captured and derived fixtures must extend this versioned evidence pattern truthfully.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/hermes_agent_api_client/models.py`: `_FrozenModel`, `TerminalOutcome`, `ToolProgressEvent`, `TerminalEvent`, and `HermesEvent` provide the strict immutable public-model seam to extend.
- `src/hermes_agent_api_client/protocol.py`: `_WireModel`, strict Pydantic wire DTOs, and input-free parser failure sentinels provide the private validation pattern; lifecycle duplicate detection must occur before ordinary dictionary construction collapses keys.
- `src/hermes_agent_api_client/sse.py`: `_decode_application_record`, `_SSEDecoder._accept_events`, `_pending_terminal`, `scrub()`, and finalization already implement ordered mapping, raw-state cleanup, and delayed terminal delivery.
- `tests/helpers/hermes.py` and `tests/fixtures/hermes/v2026.7.7.2/`: Existing golden loading, byte partitioning, and immutable versioned fixtures can support captured and design-derived cases.

### Established Patterns

- Public failures carry safe metadata only; rejected wire values reduce to input-independent sentinels before `HermesProtocolError` is raised.
- Wire models are frozen, strict, and additive-field tolerant, while approved behavioral fields fail closed.
- Terminal events are withheld until `[DONE]`, suffix validation, and stream cleanup succeed; post-terminal data and duplicate completion fail before terminal exposure.
- Tests inspect formatted errors, cause/context, traceback locals, object identity, byte partitioning, exact bounds, and event ordering rather than checking happy-path output alone.

### Integration Points

- Extend public enums/models and the `HermesEvent` union in `models.py`, then export the public vocabulary from `__init__.py`.
- Extend pair-aware JSON intake and strict lifecycle DTOs in `protocol.py` without retaining raw validation details.
- Map only approved tool and terminal facts in `sse.py`, preserving `_SSEDecoder`'s pending-terminal state machine and scrub paths.
- Update versioned fixtures plus protocol/SSE/package tests; cross-cutting installed-distribution closure remains Phase 4.

</code_context>

<specifics>
## Specific Ideas

- The terminal decision table should be executable as parameterized tests before production mapping code is written.
- Captured and design-derived fixture provenance must be visibly distinguishable in file metadata or the version provenance manifest.
- Latest-tag compatibility is evidence-driven and shape-specific, never a generic alias or permissive fallback mechanism.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 2 scope.

</deferred>

---

*Phase: 2-conversation-event-contract*
*Context gathered: 2026-07-17*
