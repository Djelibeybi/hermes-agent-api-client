# Feature Research

**Domain:** Typed, bounded conversation-stream contract for Python consumers
**Researched:** 2026-07-17
**Confidence:** HIGH for approved scope and existing-client dependencies; MEDIUM for exact future additive Hermes wire combinations beyond the approved mappings

## Research Scope

This is subsequent-milestone research for v0.3.0 only. The shipped v0.1.0
client already owns authenticated capability discovery, bounded SSE decoding,
typed failures, HTTP response cleanup, injected-client ownership, cancellation,
typing, packaging, and verification. v0.3.0 should extend that boundary with
conversation-specific metadata without reopening those decisions.

The approved conversation-contract design is authoritative. Observable Python
consumer behavior, rather than Home Assistant implementation policy, is the
feature boundary.

## Feature Landscape

### Table Stakes (Users Expect These)

These are mandatory for the v0.3.0 Conversation Contract. Omitting any one
would leave the Hermes Conversation integration unable to consume the public
package surface safely.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Independently optional per-request session arguments | A caller must be able to send transcript identity, durable-memory scope, both, or neither on one stream invocation | MEDIUM | `stream_chat_events(..., *, session_id=None, session_key=None)` maps only to `X-Hermes-Session-Id` and `X-Hermes-Session-Key`; `None` omits the corresponding header |
| Strict local session-value validation | Identifiers are header values and must fail safely before any network side effect | HIGH | Require exact `str` instances, 1-256 visible ASCII characters, no surrounding whitespace, controls, CR/LF/NUL, non-ASCII, or whitespace-only input; reject path-shaped session IDs; do not coerce |
| Fresh request-scoped header construction | Concurrent and repeated streams must not leak or retain another conversation's identity | HIGH | Copy bound authorization headers per request, add only approved session headers and content type, and preserve both the caller mapping and client-bound headers unchanged |
| Secret-safe rejection and generator cleanup | Session identifiers may be sensitive correlation material even though they are not bearer credentials | HIGH | Invalid values use `HermesTransportError(transient=False)` before dispatch; rejected/sent values must not survive in error text, `repr`, traceback, cause/context, or retained generator locals |
| Existing HTTP ownership and cancellation semantics | A per-request feature must not alter who owns the injected Home Assistant HTTP client | HIGH | Early close and cancellation close the response only; cancellation remains `asyncio.CancelledError`; package-owned clients still close at context exit |
| Correlated tool-progress events | A tool name alone cannot distinguish overlapping or repeated invocations | MEDIUM | Public immutable event carries bounded non-empty `tool_call_id`, bounded non-empty `tool_name`, and typed lifecycle `status`; preserve wire order |
| Closed tool lifecycle vocabulary | Consumers need deterministic matching rather than arbitrary status strings | MEDIUM | Export `ToolProgressStatus` with exactly `RUNNING="running"` and `COMPLETED="completed"`; missing, malformed, or unknown required lifecycle fields are `HermesProtocolError` |
| Additive-field isolation for tool progress | Tool progress must remain metadata, not a channel for tool secrets | MEDIUM | Ignore emoji, label, arguments, results, and other additive fields; never place raw wire payloads in public models or exceptions |
| Safe terminal partial-state metadata | Consumers need to distinguish complete output, truncation, and an upstream agent failure without inspecting raw errors | MEDIUM | Extend immutable `TerminalEvent` with `partial: bool = False` and optional typed failure reason |
| Closed terminal failure vocabulary and mapping | Stable application behavior requires safe classifications independent of upstream prose | HIGH | Export `TerminalFailureReason` with `OUTPUT_TRUNCATED`, `AGENT_ERROR`, and `UNKNOWN`; map stop, length/output-truncated, error/agent-error, and unknown safe error codes exactly as approved |
| Raw upstream error suppression | Error messages and exception types may contain secrets or implementation details | HIGH | Ignore raw `error.message`, exception type, Hermes error text, and unapproved error payload fields in both events and exceptions |
| Terminal ordering and exception separation | A terminal value must remain trustworthy and transport interruption must not masquerade as a protocol outcome | HIGH | Preserve the v0.1.0 rule that a terminal is delivered only after validation and response cleanup; disconnects remain `HermesTransportError`, cancellation propagates, and the client synthesizes no terminal event |
| Complete public/export and regression contract | A typed library feature is incomplete if it works only through private modules or breaks distribution guarantees | MEDIUM | Export new enums/models from package root; keep immutable strict models, `HermesEvent`, `py.typed`, wheel/sdist verification, strict typing, Ruff, and 100% branch coverage green |

### Differentiators (Competitive Advantage)

These are not extra scope; they are the quality characteristics that make the
mandatory features safer than a thin HTTP wrapper.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Metadata-only failure boundary for session inputs | Consumers can log and classify local-input failures without exposing the rejected identifier | HIGH | Extends the package's proven credential/body/upstream-detail scrubbing discipline to new header canaries and generator state |
| Detectable unmatched tool calls without client-owned policy | Ordered IDs and closed statuses let a consumer identify `running` calls that never completed after interruption | LOW in client; MEDIUM for consumer | The client supplies facts only; Home Assistant tracks the set and decides that an unmatched outcome is unknown |
| Partial success represented separately from transport failure | Consumers can retain useful assistant text while distinguishing truncation or an agent-reported error from a network disconnect | MEDIUM | `partial` is terminal metadata only; preceding text/tool events remain ordered and observable |
| Forward compatibility through selective ignorance | Additive upstream data can evolve without widening the public secrecy surface | MEDIUM | Strictly validate approved required fields while ignoring unapproved additive fields, matching existing v0.1.0 capability/event strategy |
| No new runtime dependency or generic transport escape hatch | The contract stays small, typed, auditable, and compatible with the existing package architecture | LOW | Existing Pydantic/httpx/SSE machinery is sufficient; v0.3.0 should not add a dependency to implement these mappings |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Arbitrary per-request headers mapping | Appears more flexible for integrations | Expands the public transport surface, permits authorization/header override, complicates secrecy guarantees, and bypasses the approved contract | Expose only the two keyword-only opaque session arguments |
| Client-side session or memory-key derivation | Seems convenient for callers | Couples the reusable package to Home Assistant profiles, config entries, users, devices, satellites, or credentials and violates repository ownership | `hermes-conversation` derives opaque identifiers; the client validates and transports them |
| Deriving durable memory scope from user/device/config-entry identity | Seems to provide finer-grained memory | Contradicts the approved stable Home Assistant instance scope and risks unstable or privacy-sensitive identity semantics | Derive the opaque stable-instance key in the integration according to its own policy |
| Raw tool arguments, results, labels, emoji, or payloads | Could support richer progress UI or debugging | Creates an unbounded secret-bearing API, widens model/version coupling, and duplicates integration/server concerns | Publish only call ID, tool name, and closed lifecycle status |
| Raw upstream error text, exception type, or error object | Seems useful for diagnostics | Breaks the package's secret-safe stable failure contract and makes consumer behavior depend on unstable prose | Publish only approved outcome, partial flag, and safe failure-reason enum |
| Open-ended tool status strings | Avoids future enum changes | Consumers cannot match lifecycle states reliably, typos become data, and unknown semantics silently pass | Fail unknown statuses as `HermesProtocolError`; add new statuses only through an evidence-backed contract change |
| Client-owned unmatched-call tracker or synthesized “unknown” tool event | Centralizes bookkeeping | Introduces cross-event policy/state into a decoder and cannot distinguish cancellation, disconnect, or consumer early-close policy | Preserve ordered events; let the integration track unmatched `running` IDs |
| Synthetic terminal events for disconnects or cancellation | Gives every stream a terminal object | Conflates transport/control flow with server-reported application outcomes and would weaken existing retry/cancellation semantics | Keep disconnects as `HermesTransportError` and cancellation as `CancelledError`; consumers retain already-seen events |
| Automatic retry of a partially consumed stream | Seems to improve reliability | Can duplicate assistant text or tool side effects and cannot safely replay opaque session progress | Preserve explicit retryability metadata and leave replay policy to the consumer |
| New API operations or Home Assistant lifecycle features | Might reduce integration code | Has no evidence in the approved milestone and would blur the published client/integration boundary | Start a separate evidence-backed milestone in the owning repository |

## Feature Dependencies

```text
[v0.1.0 safe typed transport + bounded SSE + cleanup]
    |--requires-before--> [Per-request session headers]
    |                         `--requires--> [Strict validation + scrubbed local failure]
    |
    |--requires-before--> [Public tool ID/status model]
    |                         `--requires-before--> [Strict tool wire decoding]
    |                                                      `--enables--> [Consumer unmatched-call detection]
    |
    `--requires-before--> [Public terminal partial/reason model]
                              `--requires-before--> [Safe terminal wire mapping]

[All three feature families]
    `--require--> [Package-root exports + regression/security/lifecycle/distribution verification]

[Arbitrary/raw transport data] --conflicts-with--> [Bounded secret-safe public contract]
[Client-owned HA identity/policy] --conflicts-with--> [Cross-repository ownership boundary]
```

### Dependency Notes

- **Session headers require the v0.1.0 request/ownership path:** the existing
  per-call header copy and response-scoped cleanup are the base that prevents
  mutation of authorization state or closure of an injected HTTP client.
- **Session dispatch requires validation and scrubbing first:** both optional
  values must be validated before serialization or network dispatch, then
  copied into fresh headers only after validation succeeds.
- **Strict tool wire decoding requires the public model/enums:** the decoder
  cannot emit the approved typed event until `tool_call_id` and
  `ToolProgressStatus` exist. The wire-schema bound for call IDs and tool names
  must be explicit and finite; the design intentionally does not approve raw
  payload retention.
- **Unmatched-call detection requires only ordered correlated events:** the
  client must preserve `running`/`completed` order and IDs, but no new client
  state machine is needed. Interruption behavior remains the existing
  exception behavior.
- **Safe terminal mapping requires the enriched terminal model:** partial and
  failure reason are derived while raw error fields are still confined to the
  wire-validation layer. Existing delayed terminal delivery must remain intact.
- **Feature work converges at verification:** shared event unions, package-root
  exports, secrecy tests, lifecycle tests, strict typing, and distribution
  checks must be updated after the feature-specific contracts exist.

### Recommended Implementation Order

1. Define and export immutable tool/terminal enums and enriched event models.
2. Extend strict wire schemas and SSE mapping, including additive-field
   isolation, malformed/unknown cases, ordering, and raw-error suppression.
3. Add exact session-value validation and keyword-only public arguments, then
   construct/scrub fresh per-request headers through the existing transport.
4. Complete cross-cutting secrecy, cancellation, early-close, concurrent-call,
   package/export, typing, coverage, and distribution regression verification.

The tool/terminal model work and session validation are logically independent,
but each should land with its own focused tests before the final combined gate.

## MVP Definition

For this subsequent milestone, “MVP” means the complete approved v0.3.0
contract. There is no reduced useful subset: the integration needs all three
feature families and the preserved baseline guarantees.

### Launch With (v0.3.0)

- [ ] Strict independently optional `session_id` and `session_key` arguments,
      fresh headers, pre-dispatch safe validation, and no caller/client mutation
- [ ] Correlated bounded `ToolProgressEvent` values with a closed
      `ToolProgressStatus` lifecycle and ordered decoding
- [ ] `TerminalEvent.partial` and safe `TerminalFailureReason` mapping without
      raw upstream error details
- [ ] Existing exception, terminal-order, response cleanup, injected-client
      ownership, cancellation, typing, coverage, and distribution guarantees
- [ ] Public package-root exports for every new enum and enriched model surface

### Add After Validation (Later Evidence-Backed Milestone)

- [ ] Additional tool lifecycle statuses — only when an immutable Hermes
      release and an integration requirement define their semantics
- [ ] Additional safe terminal failure reasons — only when consumers need a
      stable behavioral distinction that can be exposed without raw details
- [ ] Additional named request metadata — only after independent secrecy,
      ownership, and cross-repository-boundary review

### Future Consideration (Separate Owner or Milestone)

- [ ] Home Assistant identity derivation, session lifecycle, and memory policy —
      belongs in `hermes-conversation`, not this package
- [ ] New Hermes operations — require new captured evidence and a new client
      milestone rather than expansion of the conversation contract

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Strict per-request session headers | HIGH | HIGH | P1 |
| Correlated closed tool-progress events | HIGH | MEDIUM | P1 |
| Safe terminal partial/failure metadata | HIGH | MEDIUM | P1 |
| Secret/traceback/generator-state scrubbing | HIGH | HIGH | P1 |
| Ownership, cancellation, and terminal-order preservation | HIGH | HIGH | P1 |
| Public exports, strict typing, full coverage, distribution verification | HIGH | MEDIUM | P1 |
| Additional statuses/reasons beyond approved values | LOW until evidenced | MEDIUM | P3 |
| Arbitrary headers/raw tool or error details | Negative | HIGH | Exclude |

**Priority key:**
- P1: Must have for v0.3.0
- P2: Useful but not present in the approved milestone (none identified)
- P3: Defer until concrete wire and consumer evidence exists

## Consumer Approach Analysis

There is no like-for-like “competitor product” in scope; the meaningful
comparison is how a Python integration could consume the same server boundary.

| Feature | Direct `httpx` in consumer | Integration-local adapter | Published client approach |
|---------|----------------------------|---------------------------|---------------------------|
| Session headers | Caller manually validates/copies headers per request | HA-specific wrapper can derive and send them but duplicates transport logic | Client accepts two opaque validated values; integration retains derivation policy |
| Tool correlation | Caller parses raw SSE and tracks arbitrary JSON | Adapter can map IDs but duplicates protocol models/tests | Client emits immutable bounded ID/name/status facts; consumer tracks unmatched IDs |
| Terminal metadata | Caller inspects finish/error payloads and risks exposing raw details | Adapter invents local classifications tied to one integration | Client emits stable partial/reason enums while suppressing raw details |
| Safety and lifecycle | Every consumer must reproduce traceback scrubbing, response cleanup, cancellation, and ownership | Better centralized locally, but still duplicated across Python consumers | Reuses the shipped v0.1.0 bounded transport and verification guarantees |

## Requirement Traceability to Approved Design

| Approved design area | Mandatory observable requirement |
|----------------------|----------------------------------|
| Per-request session headers | Independent optional arguments; exact header mapping; strict safe validation; no arbitrary headers/derivation/mutation; scrubbed failures and generator state; response-only cleanup |
| Correlated tool progress | Bounded required ID/name; closed running/completed enum; ordered events; unknown/malformed lifecycle fails closed; additive/raw details ignored |
| Safe terminal metadata | Exact outcome/partial/reason mapping; unknown safe code maps to `UNKNOWN`; raw errors ignored; transport and cancellation remain exceptions |
| Acceptance tests | Omission/independent/together matrix, nonmutation, pre-dispatch rejection, canary leakage checks, interruption/cleanup, ordering, unmatched detectability, terminal mapping, regressions, exports, typing, lint, coverage, artifacts |

## Open Planning Detail

- The design requires bounded non-empty tool-call IDs and tool names but does
  not state numeric maxima. Planning should choose explicit finite bounds using
  the captured `v2026.7.7.2` fixture and existing package conventions, then
  encode the same bounds in wire models, public models, and boundary tests.
  This is an implementation parameter, not permission to broaden the fields.

## Sources

- `docs/superpowers/specs/2026-07-17-conversation-contract-design.md` —
  authoritative v0.3.0 feature contract and acceptance criteria
- `.planning/PROJECT.md` — active milestone goal, public boundary, and explicit
  exclusions
- `.planning/milestones/v0.1.0-REQUIREMENTS.md` — shipped baseline guarantees
  that v0.3.0 must preserve
- `src/hermes_agent_api_client/models.py`, `protocol.py`, `sse.py`, and
  `client.py` — current immutable models, safe wire parsing, terminal ordering,
  per-request copies, cleanup, and exception-scrubbing architecture
- `tests/test_protocol.py`, `tests/test_sse.py`, and `tests/test_transport.py` —
  current observable behavior and regression seams
- `tests/fixtures/hermes/v2026.7.7.2/provenance.json` — immutable captured
  evidence that canonical tool progress includes `tool_call_id`

---
*Feature research for: v0.3.0 Conversation Contract*
*Researched: 2026-07-17*
