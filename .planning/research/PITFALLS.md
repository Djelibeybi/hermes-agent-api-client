# Pitfalls Research

**Domain:** Secret-safe typed conversation-stream contracts in an asynchronous Python client
**Researched:** 2026-07-17
**Confidence:** HIGH for repository-specific lifecycle, secrecy, protocol, and packaging risks; MEDIUM for the exact upstream location and coexistence rules of terminal metadata not represented in the pinned fixture

## Critical Pitfalls

### Pitfall 1: Session values enter the generator before they are safely reduced

**What goes wrong:**
An invalid `session_id` or `session_key` reaches HTTPX, appears in an exception,
or remains reachable through an async-generator frame after rejection, early
closure, cancellation, or normal completion. A superficially safe
`HermesTransportError(transient=False)` can still leak the rejected value through
its traceback locals, implicit exception context, a validation exception, or a
suspended generator.

**Why it happens:**
`stream_chat_events()` and `_stream_chat_events()` are async generators. Their
arguments and locals remain in generator frames across each `yield`, and their
bodies do not execute until iteration begins. Adding a validator in the obvious
place is therefore not enough. Helpers that raise while still holding the raw
value also put that value in a package traceback frame. `isinstance(value, str)`
is additionally weaker than the approved real-`str`, no-subclass rule.

**How to avoid:**
Define one exact, input-independent validation result for each argument. Require
`type(value) is str`, 1-256 visible ASCII characters, no surrounding whitespace,
and the approved path-shape rejection. Validate both supplied arguments before
constructing headers or dispatching. Convert validation failures to a fresh
metadata-only `HermesTransportError(transient=False)` from a raw-input-free
frame, clear all value-bearing locals on every exit path, and explicitly scrub
the public and delegated generators before reraising. Lock the path-shape rule
with examples before implementation; do not leave it as an ad hoc URL/path
heuristic.

**Warning signs:**
- Validation is performed inline in `stream_chat_events()` with the original
  argument still named in a raising frame.
- The check uses coercion, `.strip()` as normalization, or `isinstance(...,
  str)` rather than rejecting subclasses.
- Tests only inspect `str(error)` and `repr(error)`, not formatted traceback,
  cause/context, package-frame locals, object identities, and suspended
  generator locals.
- A rejected value is tested only before the first `yield`, not after partial
  consumption and closure.

**Phase to address:**
Phase 3 — Session Header Safety; Phase 4 must independently audit every exit path.

---

### Pitfall 2: Request-scoped headers become shared mutable client state

**What goes wrong:**
One conversation's session identifier is sent on another concurrent or later
request, the bound authorization headers acquire session values, or caller-owned
request/header state is mutated. This creates a cross-conversation correlation
leak even when every individual request appears correct.

**Why it happens:**
It is tempting to update `self._headers`, pass a mutable mapping down and modify
it, cache a prepared header dictionary, or reuse a dictionary across requests.
The existing transport copies the bound headers inside `_stream_chat_events()`;
adding the new values in the wrong layer can silently defeat that isolation.

**How to avoid:**
Keep `self._headers` authorization-only. Build a fresh request header dictionary
per invocation, then add only `Content-Type` and the two approved names. Never
accept arbitrary per-request headers. Preserve the original request mapping and
bound-header mapping byte-for-byte. Clear the fresh dictionary after dispatch
completion or failure. Exercise repeated and concurrent combinations of neither,
either, and both session arguments using distinct canaries.

**Warning signs:**
- `self._headers.update(...)`, `headers[...] = ...` on a caller-provided mapping,
  or a default mutable headers argument.
- A test checks only the outgoing request and does not compare the original
  mappings afterward.
- Concurrent streams use the same session values, so header bleed cannot be
  detected.
- Capability probes unexpectedly carry session or JSON content headers.

**Phase to address:**
Phase 3 — Session Header Safety.

---

### Pitfall 3: Validation is “before decoding” but not before network dispatch

**What goes wrong:**
Invalid local input opens a connection, invokes the mock transport, or partially
serializes the body before failing. The public error category looks correct, but
the no-side-effect contract is broken.

**Why it happens:**
Validation may be placed after `http_client.stream(...)`, after URL construction,
or after request serialization because those operations already exist. Optional
arguments also invite independent lazy checks that allow the first header to be
installed before the second fails.

**How to avoid:**
Validate both values as one pre-dispatch gate, then serialize the unchanged
request and create the response scope. Treat failure of either argument as an
atomic rejection: no transport callback, no response object, and no mutation.
Test this with a dispatch counter or transport that fails loudly if called.

**Warning signs:**
- A network mock is configured to return a response in invalid-input tests
  instead of asserting it was never called.
- Header construction happens incrementally around validation.
- Tests omit the case where the first value is valid and the second is invalid,
  and its inverse.

**Phase to address:**
Phase 3 — Session Header Safety.

---

### Pitfall 4: Early close or cancellation breaks response ownership semantics

**What goes wrong:**
Closing a public iterator leaves the HTTP response open, closes the injected
Home Assistant `AsyncClient`, swallows or replaces `CancelledError`, or lets a
secondary cleanup failure replace the primary protocol/transport/cancellation
outcome. Newly added header values can also remain in the nested generators
after cleanup.

**Why it happens:**
The stream has three nested lifetimes: the public generator, the delegated
generator, and HTTPX's response context. Existing code has deliberate precedence
and scrubbing logic at each layer. Adding parameters, validation, or event state
without threading them through every `finally` and outcome branch can bypass
that logic. `GeneratorExit` and `aclose()` are especially easy to treat like
ordinary exceptions.

**How to avoid:**
Preserve response-scoped ownership: always close the response and optional
source iterator, never close an injected client, and close a package-owned client
only at client context exit. Preserve the original cancellation object and clear
cause/context after cleanup. Retain the existing primary-outcome precedence over
ordinary or cancelling cleanup failures. Extend lifecycle tests to early close
after assistant text and after tool `running`, read cancellation, response-close
cancellation, and public delegated-close cancellation, all with session
canaries and forbidden-object checks.

**Warning signs:**
- New code calls `http_client.aclose()` from a stream method.
- Cancellation is caught under a broad `Exception`/`BaseException` branch and
  translated to `HermesTransportError`.
- Only full successful consumption is tested.
- Response closure is asserted without also asserting the injected client is
  still open and the original cancellation identity is preserved.

**Phase to address:**
Phase 3 — Session Header Safety, completed by Phase 4 — Contract Regression and Distribution Verification.

---

### Pitfall 5: Duplicate JSON lifecycle fields silently become last-value-wins

**What goes wrong:**
A record such as a tool event with conflicting duplicate `status` or
`toolCallId` keys is accepted according to whichever value `json.loads()` keeps.
An invalid duplicate can be hidden by a valid later value, or vice versa. This
violates the requirement that duplicate-invalid lifecycle fields fail as
`HermesProtocolError`.

**Why it happens:**
Pydantic only sees the already-created Python dictionary. The current
`json.loads(data)` step has already collapsed duplicate object members, so
adding stricter Pydantic fields cannot recover duplicate information.

**How to avoid:**
Detect duplicates during JSON pair decoding, before ordinary mapping
construction. Reject duplicates for approved singleton lifecycle fields at the
relevant object level while preserving the existing forward-compatible policy
for unrelated additive fields. Return only an input-free failure sentinel from
the parser and scrub pair lists and raw JSON before raising. Add conflicting,
same-value, invalid-first, and invalid-last cases for `toolCallId`, `tool`,
`status`, and terminal singleton fields.

**Warning signs:**
- The implementation changes only `_ToolProgressWire` or `_ChatChunkWire`.
- Tests create Python dictionaries; dictionaries cannot express duplicate JSON
  keys.
- Duplicate tests cover `[DONE]` or repeated SSE records but not duplicate keys
  inside one JSON object.

**Phase to address:**
Phase 2 — Public Models and Wire Decoding.

---

### Pitfall 6: Tool correlation is typed but not actually bounded and ordered

**What goes wrong:**
`toolCallId` is discarded, coerced, unbounded, or exposed under the wrong name;
unknown statuses pass as arbitrary strings; additive fields leak into public
models; or a client-side tracker reorders/collapses lifecycle events. Home
Assistant can no longer distinguish overlapping calls or detect a `running`
call left unmatched by interruption.

**Why it happens:**
The existing model uses `status: str`, `_ToolProgressWire` has only unbounded
non-empty strings, and the canonical fixture contains `toolCallId` but the
decoder ignores it. It is easy to add the field to the public model without
updating the wire alias, bounds, event union, fixture expectation, and strict
status vocabulary together. It is also tempting to “help” by tracking tool
state inside the decoder.

**How to avoid:**
Choose explicit finite maxima for both tool call ID and tool name before coding,
based on pinned Hermes evidence and existing package conventions. Apply the same
meaningful bounds at wire and public boundaries. Parse the exact `toolCallId`
member into `tool_call_id`, require the closed `ToolProgressStatus` enum, and
emit every accepted record in wire order. Ignore label, emoji, arguments,
results, and other additive fields. Keep unmatched-call tracking out of the
client: prove detectability by consuming `running`, interrupting before
`completed`, and showing the caller still has the ID.

**Warning signs:**
- The public model changes but the golden fixture still expects only tool name
  and string status.
- `status` remains `str`, or unknown strings are preserved “for forward
  compatibility.”
- Maxima exist in only Pydantic wire annotations or only public constructors.
- Tests use one tool call and a normal terminal only; they do not interleave two
  IDs, repeat a name, or interrupt after `running`.

**Phase to address:**
Phase 2 — Public Models and Wire Decoding.

---

### Pitfall 7: Terminal metadata guesses at wire precedence or exposes raw errors

**What goes wrong:**
Contradictory terminal fields produce a plausible but wrong public event,
unknown upstream error prose enters a model or exception, `partial` is coerced
from a lookalike value, or a terminal is yielded before the trailing stream and
response cleanup have been validated. Consumers then treat incomplete output as
complete or receive unstable sensitive upstream details.

**Why it happens:**
The current wire model knows only `finish_reason`; the approved design adds
`partial`, safe codes such as `output_truncated` and `agent_error`, and mentions
`failed`/`completed`, but the pinned golden fixture does not demonstrate all
their exact locations or coexistence. Mapping happy paths without first locking
the wire shape and precedence leaves contradictory and unknown combinations
undefined. Pydantic's general validation error also contains rejected input if
it escapes the safe sentinel boundary.

**How to avoid:**
Capture or transcribe immutable upstream examples for every approved terminal
shape before implementation, then define a decision table for required types,
coexistence, and precedence. Require a real boolean for server-provided
`partial`; map only the approved safe code values, reducing any other safe code
to `TerminalFailureReason.UNKNOWN`. Never read `error.message`, exception type,
raw `error`, or unapproved nested fields into public state. Preserve the
existing pending-terminal design: validate `[DONE]`, reject post-terminal data,
close the response, then yield exactly one enriched terminal.

**Warning signs:**
- Tests invent only one guessed JSON shape and cite no pinned source or fixture.
- Unknown `error_code` becomes a public string, or raw error text is used as an
  exception message.
- `partial` accepts `0`, `1`, or strings.
- A terminal is observable before a duplicate `[DONE]`, post-terminal record,
  or close failure is processed.

**Phase to address:**
Phase 2 — Public Models and Wire Decoding; exact upstream evidence is a planning gate, not a deferred test task.

---

### Pitfall 8: Bounds and strictness are inconsistent across layers

**What goes wrong:**
A value rejected by a public model is accepted from the wire, a huge identifier
is retained inside an otherwise bounded SSE record, a `str` subclass crosses a
local-input boundary, or defaults allow malformed terminal values to appear
valid.

**Why it happens:**
The package has separate local-input, wire-model, public-model, and framing
bounds. `MAX_EVENT_DATA_CHARS` limits a complete record but does not provide an
appropriate semantic identifier bound. Pydantic strict mode and `Literal`/enum
validation help, but they do not replace exact local-input rules or consistent
field maxima.

**How to avoid:**
Name and document each semantic maximum once and reuse it in wire/public model
annotations where possible. Test exact lower/upper boundaries and one beyond,
including Unicode, controls, whitespace-only values, booleans, coercible types,
and string subclasses. Keep `TerminalEvent.partial=False` and
`failure_reason=None` backward-compatible defaults, but validate explicit
inputs strictly. Do not add a runtime dependency for these checks.

**Warning signs:**
- “Bounded” means only that the 64-KiB SSE record limit exists.
- Tests use representative lengths instead of exact threshold values.
- Wire fields use `_NonEmptyString` while public fields use a different maximum.
- Validation code normalizes malformed input into an accepted form.

**Phase to address:**
Phase 2 for event bounds; Phase 3 for session-value bounds; Phase 4 for boundary parity tests.

---

### Pitfall 9: Source behavior changes but the installed typed package does not

**What goes wrong:**
Tests pass by importing internal modules, while package-root consumers cannot
import the new enums or receive stale type information from built artifacts.
`HermesEvent`, `__all__`, `py.typed`, wheel/sdist contents, or release metadata
drift from the implementation.

**Why it happens:**
Model and decoder tests naturally import source modules directly. The repository
already enforces an exact public export set and isolated distribution checks, so
adding names only in `models.py` breaks a different gate than ordinary unit
tests. A locally editable source tree can mask missing artifact content.

**How to avoid:**
Update package-root imports, exact `__all__`, `HermesEvent`, and public typing in
the same phase as the models. Build one wheel and one sdist, run the repository's
standalone verifier, and import/construct the new public types from an isolated
artifact environment. Run Ruff, strict basedpyright, `--verifytypes`, and 100%
branch coverage using the locked environment and established `uv run --no-sync`
follow-up pattern.

**Warning signs:**
- New tests import `hermes_agent_api_client.models` rather than the package root.
- `py.typed` exists in source, but artifact contents are not checked.
- Coverage is 100% line coverage without branch coverage.
- A dependency is changed without refreshing the lock or checking its current
  release/documentation.

**Phase to address:**
Phase 4 — Contract Regression and Distribution Verification.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Put session fields in `self._headers` | Minimal signature plumbing | Cross-request identity leakage and mutable auth state | Never |
| Reuse the bearer validator unchanged | Less code | It permits a different character/shape contract and may accept subclasses | Never; share only proven low-level predicates |
| Rely on Pydantic after `json.loads()` for duplicate detection | Simple wire models | Conflicting singleton fields become last-value-wins before validation | Never for approved lifecycle fields |
| Leave tool status as `str` | No enum migration | Consumers cannot distinguish supported states from typos or future semantics | Never for v0.3.0 |
| Add client-owned tool-call tracking | Convenient consumer API | Stateful decoder policy, replay ambiguity, and cancellation coupling | Never in this package; caller owns tracking |
| Pass raw upstream errors through for diagnostics | Easier debugging | Secret leakage and unstable public behavior | Never at the public boundary |
| Add only unit tests around helper functions | Fast implementation | Misses suspended generators, response ownership, and artifact drift | Acceptable only as the first red-green step, never as completion |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Home Assistant HTTP client | Closing the injected `AsyncClient` when a stream closes | Close only the response/source iterator; the integration owns its client |
| Home Assistant conversation identity | Deriving session ID/key from users, devices, credentials, config entries, or endpoints in this package | Accept validated opaque values; derivation and memory policy stay in `hermes-conversation` |
| Hermes headers | Offering an arbitrary headers mapping or allowing overrides of authorization/content type | Expose only the two keyword-only session arguments and create fresh headers internally |
| Hermes tool progress | Matching calls by tool name or collapsing records into current state | Preserve every bounded ID/name/status event in wire order; consumer tracks unmatched IDs |
| Hermes terminal records | Treating any error payload as a transport exception or any EOF as success | Map only server-reported safe terminal metadata; disconnect remains an exception and no terminal is synthesized |
| Hermes additive fields | Rejecting every unknown field or surfacing all unknown data | Ignore unapproved additive fields while strictly validating approved required lifecycle fields |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Retaining per-stream header/request/event objects after `yield` | Memory and sensitive identities remain reachable for long-lived paused streams | Minimize generator locals and clear value-bearing objects on every exit | Any suspended stream; worse with many concurrent HA conversations |
| Tracking all tool calls in the client | Per-stream state grows and policy survives longer than transport facts | Emit bounded events only; caller keeps the small active-ID set | Long streams or tools that never complete |
| Treating the SSE record limit as a field bound | One ID/name can consume almost the whole 64-KiB application budget | Apply small explicit semantic maxima before public model creation | A single hostile or malformed event |
| Copying the whole request or headers repeatedly inside the event loop | Allocation scales with event count | Serialize/copy once per request, outside event iteration | High-frequency progress streams |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Session canary remains in traceback or generator locals | Correlation identity leaks through diagnostics or introspection | Raw-input-free failure frames, explicit clearing, and package-frame/object-identity assertions |
| Session header is shared across calls | One household conversation is attributed to another | Fresh per-request dictionary plus concurrent isolation tests |
| CR/LF/control or string subclasses accepted | Header injection or adversarial overridden string behavior | `type(value) is str` and exact visible-ASCII/length/shape rules before dispatch |
| Duplicate lifecycle keys collapse silently | Ambiguous records bypass closed-contract validation | Pair-aware duplicate detection before dictionary construction |
| Raw tool arguments/results/labels or upstream error text enter models | Household data or secrets cross the bounded public boundary | Select only approved fields; use metadata-only public failures |
| Secondary cleanup exception replaces the primary outcome | Raw transport detail escapes and retry/cancellation behavior changes | Preserve established primary-outcome precedence and fresh safe error translation |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Unmatched `running` is silently converted to `completed`/success | Home Assistant reports a tool succeeded after interruption | Preserve the last observed ID/status and let the integration classify it as unknown |
| Truncated output appears as ordinary success | Partial assistant text is presented as complete | Emit `LENGTH`, `partial=True`, and `OUTPUT_TRUNCATED` |
| Agent-reported failure discards useful prior text | User loses partial response even though transport completed | Preserve ordered prior events and expose safe partial/failure metadata |
| Unknown safe error code is rejected as raw protocol data | Forward-compatible upstream failures become unusable | Map an otherwise valid unknown safe code to `UNKNOWN`, while still rejecting malformed types/shapes |
| Arbitrary headers become public API | Consumers depend on unsafe transport details | Keep the two explicit keyword-only session parameters |

## "Looks Done But Isn't" Checklist

- [ ] **Session omission matrix:** Verify neither, each independently, and both headers on the actual HTTP request.
- [ ] **Atomic pre-dispatch rejection:** Verify all invalid type/length/ASCII/whitespace/control/path cases, including valid-first-invalid-second and invalid-first-valid-second, make zero transport calls.
- [ ] **No mutation or bleed:** Verify caller request mapping and bound authorization headers are unchanged after success/failure, and concurrent streams carry only their own canaries.
- [ ] **Complete secrecy:** Verify invalid and valid session canaries are absent from `str`, `repr`, `args`, `vars`, formatted traceback, cause, context, package-frame locals, forbidden object identities, and retained public/delegated generator locals.
- [ ] **Lifecycle ownership:** Verify normal completion, early close after text, early close after tool `running`, read cancellation, and close failure close the response but not the injected client.
- [ ] **Cancellation precedence:** Verify original `CancelledError` identity survives cleanup and primary protocol/transport/cancellation outcomes outrank secondary close failure/cancellation.
- [ ] **Tool correlation:** Verify bounded `toolCallId` maps to `tool_call_id`, closed enum statuses survive in wire order, two interleaved calls remain distinct, and interruption leaves a caller-detectable unmatched `running` ID.
- [ ] **Malformed and duplicate tool records:** Verify missing, empty, oversized, subclass/coercible, unknown-status, and conflicting duplicate required fields fail with a scrubbed `HermesProtocolError`.
- [ ] **Additive tool isolation:** Verify emoji, label, arguments, results, and nested canaries are ignored and absent from public event state and failures.
- [ ] **Terminal decision table:** Verify stop, length/output-truncated, error/agent-error with both partial booleans, and unknown safe code map exactly; reject malformed and contradictory combinations according to the pinned rule.
- [ ] **Raw terminal secrecy:** Verify raw error messages, exception types, nested upstream errors, and canaries never enter public models, exceptions, tracebacks, or retained decoder state.
- [ ] **Terminal ordering:** Verify post-terminal data, duplicate finish, duplicate `[DONE]`, disconnect, and cleanup failure never expose a premature terminal.
- [ ] **Public typing:** Verify new enums/models are immutable and strict, present in `HermesEvent`, importable from the package root, and exactly listed in `__all__`.
- [ ] **Release artifacts:** Verify `py.typed`, isolated wheel/sdist imports, exact public exports, Ruff, strict basedpyright, `--verifytypes`, and 100% branch coverage using the locked environment.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Session/header leakage found before release | MEDIUM | Stop feature work, add canary/object-identity regression tests for every exit, move failure raising to raw-input-free helpers, and audit concurrent requests |
| Session/header leakage released | HIGH | Treat as a security-sensitive contract defect, patch immediately, avoid logging affected failures, document the safe version, and coordinate consumer upgrade |
| Duplicate lifecycle fields accepted | MEDIUM | Introduce pair-aware parsing, add raw-byte duplicate fixtures, and confirm additive-field compatibility remains intact |
| Incorrect terminal mapping | HIGH | Pin exact upstream examples, formalize precedence, add the complete decision table, and release a compatibility fix before consumers encode policy around the wrong meaning |
| Response/client ownership regression | HIGH | Restore nested `finally`/`aclose` behavior and outcome precedence, then run the full lifecycle matrix rather than patching only the failing path |
| Public/export artifact drift | LOW | Update `HermesEvent`, root exports, exact export tests, build artifacts, and isolated verification before release |

## Pitfall-to-Phase Mapping

Recommended phase names/numbers are supplied for roadmap synthesis; the
milestone roadmap had not yet assigned v0.3.0 phases during this research.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Duplicate JSON lifecycle fields | Phase 2 — Public Models and Wire Decoding | Raw JSON duplicate-key matrix fails safely before terminal delivery |
| Tool correlation/bounds/order | Phase 2 — Public Models and Wire Decoding | Golden fixture plus interleaved IDs, closed enum, exact bounds, additive-field isolation, and interruption tests |
| Terminal mapping/raw error suppression | Phase 2 — Public Models and Wire Decoding | Pinned terminal fixtures and complete mapping/precedence/secrecy matrix |
| Session validation and generator retention | Phase 3 — Session Header Safety | Zero-dispatch invalid matrix plus traceback and suspended-generator canary audit |
| Shared header mutation/cross-request bleed | Phase 3 — Session Header Safety | Neither/either/both and concurrent distinct-canary request inspection |
| Cancellation, early-close, and injected ownership | Phase 3, completed in Phase 4 | Response/client state, cancellation identity, failure precedence, and forbidden-object assertions |
| Cross-layer bounds/strictness | Phase 2 and Phase 3, audited in Phase 4 | Exact thresholds and invalid-type parity at local, wire, and public boundaries |
| Public API/distribution drift | Phase 4 — Contract Regression and Distribution Verification | Root import, exact `__all__`, `HermesEvent`, `py.typed`, wheel/sdist, Ruff, strict typing, 100% branch coverage |

## Sources

- `docs/superpowers/specs/2026-07-17-conversation-contract-design.md` — authoritative v0.3.0 contract and acceptance criteria
- `.planning/PROJECT.md` and `.planning/research/FEATURES.md` — milestone boundary, exclusions, feature dependencies, and implementation order
- `src/hermes_agent_api_client/client.py` — current per-request header copy, nested generator cleanup, cancellation scrubbing, and injected-client ownership
- `src/hermes_agent_api_client/models.py`, `protocol.py`, and `sse.py` — current strict immutable models, Pydantic wire boundary, JSON decoding, bounded SSE state, pending-terminal ordering, and raw-state scrubbing
- `tests/test_client_lifecycle.py`, `test_transport.py`, `test_protocol.py`, `test_sse.py`, and `test_package.py` — existing secrecy, lifecycle precedence, ordering, exact exports, coverage, and artifact verification seams
- `tests/fixtures/hermes/v2026.7.7.2/provenance.json` and `chat_completions/complete.sse` — pinned source identity and canonical tool-progress evidence; do not overclaim terminal combinations absent from this fixture
- [Pydantic strict string validation and `string_sub_type`](https://github.com/pydantic/pydantic/blob/main/docs/errors/validation_errors.md) — current Context7-resolved primary documentation confirming strict string fields reject string subtypes
- [Pydantic `Literal` validation](https://github.com/pydantic/pydantic/blob/main/docs/api/standard_library_types.md) — current Context7-resolved primary documentation for closed literal vocabularies

---
*Pitfalls research for: v0.3.0 Conversation Contract*
*Researched: 2026-07-17*
