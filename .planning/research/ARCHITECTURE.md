# Architecture Research

**Domain:** Conversation-specific extensions to a typed, bounded, secret-safe async HTTP/SSE client
**Researched:** 2026-07-17
**Confidence:** HIGH for repository integration points and lifecycle ordering; MEDIUM-HIGH for the exact upstream terminal wire shape because the tagged Hermes source confirms it but the client fixture does not yet capture it

## Executive Recommendation

Extend the existing five-module architecture in place. Do not add a session
object, arbitrary-header API, stream-state manager, or second decoder. The
current boundaries are already appropriate:

- `models.py` owns the immutable public vocabulary.
- `protocol.py` owns strict private wire shapes and wire-to-public-safe parsing.
- `sse.py` owns bounded framing, application-record mapping, event ordering,
  terminal withholding, and raw-wire scrubbing.
- `client.py` owns local request validation, fresh header construction,
  dispatch, response lifetime, failure translation, and injected-client
  ownership.
- `__init__.py` owns the supported package-root surface.

The safest build order is: lock fixtures and bounds, extend public models,
extend private wire models, map records in the SSE decoder, add per-request
headers at the transport boundary, then run cross-cutting secrecy/lifecycle
and distribution verification. This order keeps each downstream layer typed
against an already-defined upstream contract.

## Standard Architecture

### System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Public package boundary                                             │
│ __init__.py                                                         │
│ Client + frozen event models + closed enums + typed failures        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│ Operation and ownership boundary                                    │
│ client.py                                                           │
│ active-client gate → session validation → fresh request headers     │
│ → request serialization → one response scope → safe failure mapping│
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP response bytes
┌───────────────────────────────▼──────────────────────────────────────┐
│ Bounded stream state machine                                        │
│ sse.py                                                              │
│ UTF-8/SSE framing → application record decode → ordering/terminal   │
│ withholding → raw-state scrub → typed events                        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ private parsed wire values
┌───────────────────────────────▼──────────────────────────────────────┐
│ Private protocol boundary                                           │
│ protocol.py                                                         │
│ strict Pydantic wire models → closed lifecycle fields → safe        │
│ parse sentinel or metadata-only protocol failure                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ explicit field-by-field construction
┌───────────────────────────────▼──────────────────────────────────────┐
│ Immutable public values                                             │
│ models.py                                                           │
│ ToolProgressEvent + TerminalEvent + existing event union            │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Status | Responsibility for v0.3.0 | Implementation direction |
|-----------|--------|---------------------------|--------------------------|
| `models.py` | Modified | Public closed enums and immutable event fields | Add `ToolProgressStatus`, `TerminalFailureReason`, `tool_call_id`, typed `status`, `partial`, and `failure_reason`; retain `_FrozenModel` strict/frozen configuration. |
| `protocol.py` | Modified | Private wire validation and safe parse sentinels | Extend `_ToolProgressWire`; add a private Hermes terminal metadata wire model; extend `_ChatChunkWire`; keep `extra="ignore"` and map only approved fields. |
| `sse.py` | Modified | Wire-to-public mapping, ordering, terminal semantics, and raw-state scrubbing | Map tool correlation and terminal metadata in `_decode_application_record`; preserve `_SSEDecoder` as the only stream state machine and keep terminal delivery deferred until the full stream validates. |
| `client.py` | Modified | Exact local-input validation, request header construction, transport dispatch, cleanup, and ownership | Extend only `stream_chat_events`; add private validation/header-builder helpers; pass a fresh per-operation mapping; clear sensitive locals on every exit path. |
| `__init__.py` | Modified | Stable package-root API | Export the two new enums alongside existing public events. |
| New source module | Not recommended | None | The change is too coupled to existing contract seams to justify a new abstraction or package. |
| `tests/fixtures/.../complete.sse` and derived fixtures | Modified/added | Exact-version evidence for completed tool events and terminal Hermes metadata | Keep raw fixture ownership in this repository; derive malformed/additive cases in tests where possible. |
| `tests/test_protocol.py` | Modified | Public vocabulary, frozen/strict construction, closed enums, safe failure state | Assert the event union remains closed and direct model construction cannot bypass bounds/types. |
| `tests/test_sse.py` | Modified | Wire parsing, additive-field ignoring, ordering, terminal mapping, and raw-error exclusion | Add exact mapping matrices and interrupted/unmatched tool lifecycle prefixes. |
| `tests/test_transport.py` | Modified | Header omission/combinations, pre-dispatch failure, request immutability, response cleanup | Test the private operation boundary with captured `httpx.Request` values and canary traversal. |
| `tests/test_client_lifecycle.py` | Modified | Public signature, generator cleanup, cancellation identity, injected-client ownership | Prove public early close/cancellation scrubs session values and never closes the injected client. |
| `tests/test_package.py` / `scripts/verify_dist.py` | Usually tests only | Package-root exports, `py.typed`, wheel/sdist import surface | Update expected exports; preserve the existing verifier rather than adding a parallel release check. |

## Recommended Project Structure

```text
src/hermes_agent_api_client/
├── __init__.py        # Supported package-root exports
├── client.py          # Request-local validation, headers, HTTP and ownership
├── models.py          # Frozen public event/enumeration vocabulary
├── protocol.py        # Strict private wire models and safe parse outcomes
├── sse.py             # Bounded SSE state machine and public event mapping
└── py.typed            # Typed-package marker (unchanged)

tests/
├── fixtures/hermes/v2026.7.7.2/
│   └── chat_completions/  # Tagged upstream wire evidence
├── test_protocol.py       # Public/static contract
├── test_sse.py            # Transport-independent decoding and ordering
├── test_transport.py      # Request construction and response ownership
├── test_client_lifecycle.py # Public generator/client lifecycle
└── test_package.py        # Distribution/export surface
```

### Structure Rationale

- **Keep request validation in `client.py`:** session values are caller input
  used only to construct HTTP headers. They are neither server wire models nor
  reusable public value objects.
- **Keep wire models private in `protocol.py`:** Pydantic validation details
  must collapse into a sentinel before `sse.py` raises a fresh
  `HermesProtocolError` from a raw-record-free frame.
- **Keep mapping and ordering in `sse.py`:** terminal withholding and event
  order already live in `_SSEDecoder`; duplicating lifecycle state in the
  public client would create conflicting terminal semantics.
- **Keep public types in `models.py`:** consumers need stable enums and frozen
  values without exposure to Pydantic wire aliases such as `toolCallId` or to
  the upstream `hermes` metadata envelope.
- **Keep exact-version fixtures under the existing provenance directory:** the
  repository already treats Hermes `v2026.7.7.2` as its wire evidence source.

## Architectural Patterns

### Pattern 1: Validate, Copy, Then Dispatch

**What:** Validate each optional session value with one input-minimizing helper,
build a fresh operation header dictionary from the bound auth mapping, and
dispatch only after both headers and the request body are valid.

**When to use:** At the start of each `stream_chat_events` iteration, before
`http_client.stream(...)` can send anything.

**Trade-offs:** This allocates one small dictionary per stream. That cost is
intentional: it prevents cross-request mutation, supports concurrent streams,
and keeps the authorization mapping constructor-bound.

```python
# Architectural shape, not drop-in implementation.
request_headers = _chat_request_headers(
    bound_headers,
    session_id=session_id,
    session_key=session_key,
)
session_id = None
session_key = None
request_body = _serialize_request_safely(request)
if request_body is None:
    request_headers.clear()
    _raise_transport_failure(transient=False)
```

The validator should:

1. Accept `None` as omission independently for each argument.
2. Require `type(value) is str`, not `isinstance`, coercion, or `.strip()`
   normalization.
3. Enforce 1–256 characters and the approved ASCII/whitespace predicate.
4. Apply the path-safety predicate only to `session_id`: reject `..`, `/`,
   `\\`, and a leading drive-letter prefix such as `C:`. This matches the
   tagged Hermes entry-boundary rationale.
5. Replace the raw value before calling an input-free raiser that creates
   `HermesTransportError(transient=False)`.

The approved design says “visible ASCII” and separately rejects leading and
trailing whitespace. Because ASCII space is printable but not normally called
visible, the requirements phase should lock one exact predicate. The
conservative recommendation is bytes `0x21..0x7e` (therefore no spaces
anywhere), since identifiers are opaque and do not need human prose.

### Pattern 2: Private Wire DTO to Explicit Public Model Mapping

**What:** Parse only required upstream fields into private frozen wire models,
then construct a public model field-by-field. Ignore additive fields at the
wire model boundary.

**When to use:** Tool progress and terminal chat chunks.

**Trade-offs:** There is deliberate duplication between wire and public field
definitions. It prevents aliases, raw payloads, labels, arguments, results,
and error strings from accidentally becoming public API.

Recommended private shapes:

```python
class _ToolProgressWire(_WireModel):
    tool_call_id: _BoundedNonEmptyString = Field(alias="toolCallId")
    tool: _BoundedNonEmptyString
    status: Literal["running", "completed"]


class _TerminalMetadataWire(_WireModel):
    completed: bool
    partial: bool
    failed: bool
    error_code: str | None = None


class _ChatChunkWire(_WireModel):
    choices: Annotated[list[_ChoiceWire], Field(min_length=1, max_length=1)]
    usage: _UsageWire | None = None
    hermes: _TerminalMetadataWire | None = None
```

Hermes `v2026.7.7.2` places `completed`, `partial`, `failed`, `error`, and
`error_code` in a root `hermes` object on abnormal finish chunks. The parser
must omit `error` from the private model entirely (or rely on `extra="ignore"`)
and must never place it in a local used for public construction.

The design requests bounded non-empty tool IDs and names but does not specify
their numeric ceiling. Lock that ceiling before implementation. Reusing 256
characters is a coherent default because it matches the approved session
bound and is comfortably above the tagged fixture values; do not leave either
field unbounded.

### Pattern 3: Delayed Terminal Commit

**What:** Treat a terminal chunk as pending state, not immediately observable
output. Yield it only after the decoder has validated EOF/`[DONE]`, rejected
post-terminal content, closed its byte source, and the client has exited the
HTTP response context.

**When to use:** Every terminal outcome, including new partial/failure
metadata.

**Trade-offs:** The consumer sees terminal metadata slightly later, after
response cleanup. In exchange, a malformed suffix or duplicate terminal can
never be mistaken for a completed conversation.

The current `_SSEDecoder._pending_terminal`, `finalize()`, and
`_stream_chat_events` terminal list already implement this two-stage commit.
Extend the `TerminalEvent` value; do not alter the commit mechanism.

### Pattern 4: Closed Classification, Additive Envelope

**What:** Be forward-compatible at envelope boundaries while strict about
fields that change consumer behavior.

- Unknown JSON fields: ignore.
- `ToolProgressStatus`: accept only `running` and `completed`.
- `finish_reason`: keep the existing closed set.
- Known terminal error codes: map to stable public reasons.
- Unknown safe `error_code`: map to `TerminalFailureReason.UNKNOWN`.
- Missing/malformed fields required for the observed lifecycle condition:
  fail with `HermesProtocolError`.

**Trade-offs:** Unknown safe error codes remain usable without exposing raw
text. Unknown lifecycle states fail closed so consumers do not make incorrect
tool-state decisions.

### Pattern 5: Secret Lifetime Minimization Across Generator Frames

**What:** Treat valid session header values as sensitive even though they are
not bearer credentials. Minimize the number of frames and containers that
hold them, then clear or drop those references before any translated failure
or completed generator state can escape.

**When to use:** Public and private async-generator wrappers, request
construction, response failure handling, early close, and cancellation.

**Trade-offs:** The explicit cleanup code is verbose. That is consistent with
the repository’s existing evidence-backed secrecy model.

Specific integration guidance:

- After creating fresh headers, set raw `session_id` and `session_key` locals
  to `None` in both public and private generator frames.
- Once `httpx` has entered the response context, clear the temporary plain
  dictionary if `httpx` has already copied it; do not retain a second copy
  across event yields.
- Before raising any translated failure, clear request headers and body,
  release `response`, drop events/terminal lists, and replace request/session
  locals.
- Preserve the original `asyncio.CancelledError` identity after cleanup.
- Tests should inspect package traceback locals, causes, contexts, and closed
  generator frames recursively, not just `str(error)`.

## Data Flow

### Request Flow

```text
consumer calls stream_chat_events(request, session_id=?, session_key=?)
    ↓
HermesAgentApiClient verifies active lifecycle
    ↓
exact local-input validation (both optional values, deterministic order)
    ├── invalid → scrub raw values → fresh non-retryable HermesTransportError
    └── valid
         ↓
copy bound Authorization into fresh per-request headers
    + Content-Type
    + optional X-Hermes-Session-Id
    + optional X-Hermes-Session-Key
         ↓
copy/serialize request Mapping to compact JSON (caller mapping unchanged)
    ├── invalid → clear headers/body → fresh non-retryable transport error
    └── valid
         ↓
POST /v1/chat/completions through active httpx.AsyncClient
         ↓
own one response context only; never close injected client
```

Validation should occur before request serialization so hostile request
mappings cannot execute while raw session argument objects remain in the same
failure path. Define and test deterministic validation precedence (recommended:
`session_id`, then `session_key`, then request serialization).

### Stream Decode Flow

```text
HTTP response bytes
    ↓
_SSEDecoder bounded UTF-8 and line/event framing
    ↓
json.loads into one temporary document
    ↓
event: hermes.tool.progress             unnamed/message chat chunk
    ↓                                      ↓
_ToolProgressWire                         _ChatChunkWire
    ↓                                      ├── delta → AssistantDeltaEvent
ToolProgressEvent                         ├── usage → UsageEvent
(id, name, closed status)                 └── finish + hermes metadata
                                                   ↓
                                             pending TerminalEvent
                                                   ↓
validate DONE/EOF and reject trailing records
    ↓
close byte iterator → exit HTTP response context
    ↓
yield TerminalEvent to consumer
```

### Terminal Mapping

The mapping belongs in one helper in `sse.py` (or immediately adjacent pure
logic called by `_decode_application_record`), fed only the validated private
wire values:

| Validated condition | Public terminal |
|---------------------|-----------------|
| `finish_reason="stop"` and no contradictory abnormal metadata | `SUCCESS`, `partial=False`, `failure_reason=None` |
| `finish_reason="length"` and `hermes.error_code="output_truncated"` | `LENGTH`, `partial=True`, `OUTPUT_TRUNCATED` |
| `finish_reason="error"` and `hermes.error_code="agent_error"` | `UPSTREAM_ERROR`, `partial=hermes.partial`, `AGENT_ERROR` |
| `finish_reason="error"` and another bounded safe code | `UPSTREAM_ERROR`, `partial=hermes.partial`, `UNKNOWN` |
| Contradictory, missing, or malformed lifecycle metadata | Fresh `HermesProtocolError` after decoder scrub |

The current approved mapping does not define every contradiction (for
example, `finish_reason="stop"` with `hermes.failed=true`, or `length` with
`partial=false`). The requirements phase should make that matrix explicit.
Recommendation: reject contradictory known fields rather than silently
normalizing them, because terminal classification drives retry and partial
response behavior.

### Tool Lifecycle State

The client should preserve wire order but should not maintain or synthesize a
tool-call registry. Each validated record becomes exactly one
`ToolProgressEvent`. The integration can track `running` IDs and remove them
on `completed`; a transport interruption naturally leaves unmatched IDs in
consumer state. This preserves repository ownership: transport decoding here,
Home Assistant conversation state in `hermes-conversation`.

“Duplicate-invalid” needs one exact requirement before implementation. If it
means a duplicate lifecycle transition (two `running` or two `completed`
records for the same ID), enforcing it would require client-side correlation
state and conflicts with the stated integration-owned unmatched-call tracker.
Recommendation: this client validates each record independently and preserves
duplicates in order; malformed or unknown fields fail. If it instead means
duplicate JSON object keys, the current `json.loads` call discards that
evidence and would need an `object_pairs_hook` duplicate detector. Do not
silently guess between these behaviors.

### Cleanup and Failure Precedence

Preserve the established precedence:

1. Cancellation identity, protocol failure, transport/status failure, and
   cleanup-only failures remain distinct according to existing tests.
2. A primary protocol/transport/cancellation outcome wins over a secondary
   response-close failure.
3. Terminal events remain withheld until decoder-source and HTTP-response
   cleanup complete.
4. Early public iterator closure closes the delegated decoder and response,
   but not the active injected client.
5. The client context closes an HTTP client only when it created that client.

## Scaling and Concurrency Considerations

This is an in-process client library; server-user counts are not the useful
scale axis. The relevant scale is concurrent stream count and hostile input
size.

| Scale | Architecture adjustment |
|-------|--------------------------|
| One/few streams | Existing module-level pure parsers and one decoder instance per stream are sufficient. |
| Many concurrent streams on one injected client | Keep all session headers and decoder lifecycle state operation-local; never write to `self._headers` or module globals. |
| Large/malicious wire input | Preserve `MAX_PENDING_BYTES`, `MAX_EVENT_DATA_CHARS`, strict one-choice bounds, bounded tool identifiers, and bounded terminal error codes. |

### Scaling Priorities

1. **First failure mode: shared mutable request state.** Prevent it with a
   fresh header mapping and request-local decoder for every invocation.
2. **Second failure mode: retained sensitive/raw values.** Prevent it with
   bounded fields, no raw payload public surface, and explicit generator-frame
   cleanup.
3. **Do not optimize prematurely:** a tool-call registry, cross-stream cache,
   or new background task layer would add state without solving a current
   bottleneck.

## Anti-Patterns

### Anti-Pattern 1: Arbitrary Per-Request Headers

**What people do:** Add `headers: Mapping[str, str] | None` to the public
method.

**Why it is wrong:** It permits authorization override, accidental secret
retention, CR/LF injection attempts, and an unbounded public transport surface.

**Do this instead:** Expose exactly `session_id` and `session_key`, then map
them internally to the two approved names.

### Anti-Pattern 2: Mutating Bound Headers

**What people do:** Add session headers to `self._headers` and remove them
after the request.

**Why it is wrong:** Concurrent streams race, values bleed across requests,
and exceptions/cancellation can skip restoration.

**Do this instead:** Copy bound auth into a fresh operation dictionary.

### Anti-Pattern 3: Pydantic Validation Directly in the Public Failure Path

**What people do:** Let `ValidationError`, `ValueError`, or raw input appear in
the public traceback.

**Why it is wrong:** Pydantic errors can retain rejected values and nested wire
documents.

**Do this instead:** Parse into a value-or-sentinel private helper, scrub raw
state, then raise a fresh metadata-only contract error from an input-free
frame.

### Anti-Pattern 4: Exposing the Hermes Metadata Object

**What people do:** Return `hermes`, `error`, labels, tool arguments/results,
or the original JSON document.

**Why it is wrong:** It turns an additive upstream object into a public API and
can disclose raw upstream error text or tool data.

**Do this instead:** Map only closed enums, a boolean partial flag, tool ID,
and tool name.

### Anti-Pattern 5: Yielding Terminal Immediately

**What people do:** Yield on the finish chunk before validating `[DONE]`, EOF,
or trailing records.

**Why it is wrong:** A malformed or duplicated suffix can become a false
success/non-success completion.

**Do this instead:** Preserve the existing pending-terminal commit.

### Anti-Pattern 6: Client-Synthesized Terminal on Disconnect

**What people do:** Convert cancellation/read failure into a partial
`TerminalEvent`.

**Why it is wrong:** It erases the exception type and retryability boundary and
cannot know upstream terminal intent.

**Do this instead:** Keep cancellation and transport disconnects as exceptions;
the consumer uses already-yielded text/tool prefixes to classify partial work.

### Anti-Pattern 7: Client-Owned Tool Correlation Policy

**What people do:** Reject unmatched completion, synthesize completion, or
hide repeated lifecycle records based on an internal registry.

**Why it is wrong:** The integration explicitly needs to observe unmatched
`running` calls after interruption, and policy belongs to its conversation
state.

**Do this instead:** Validate every record, preserve exact order, and expose
the correlation ID plus closed status.

## Integration Points

### External Services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| Hermes Agent API Server `v2026.7.7.2` | Authenticated `POST /v1/chat/completions` with optional session headers and SSE response | Tagged source confirms independent headers, `toolCallId`/`running`/`completed`, and abnormal finish metadata under root `hermes`. |
| Home Assistant `hermes-conversation` | Consumer of package-root models and client method | Derives opaque identities and owns unmatched tool-call tracking, partial-response UX, and retry policy. |
| Injected `httpx.AsyncClient` | Shared caller-owned transport | The operation owns only its response; `HermesAgentApiClient.__aexit__` closes only clients it created. |

### Internal Boundaries

| Boundary | Communication | Contract |
|----------|---------------|----------|
| `HermesAgentApiClient.stream_chat_events` → private transport helper | Direct call / async iterator | Public arguments become validated fresh headers; caller mapping and bound headers remain unchanged. |
| `client.py` → `httpx` | HTTP request + response context | Refuse redirects, preserve timeouts, own response only. |
| `client.py` → `sse.py` | `response.aiter_bytes()` | Byte iterator is closed by decoder/response scope on success, failure, cancellation, or early close. |
| `sse.py` → `protocol.py` | Temporary decoded object | Private parsers return strict wire value or `None`; no validation exception escapes. |
| `protocol.py`/`sse.py` → `models.py` | Explicit construction | Only approved safe fields enter immutable public events. |
| package → `hermes-conversation` | Package-root imports | No private protocol types, raw headers, or raw payloads cross the repo boundary. |

## Recommended Build Order

### 1. Lock wire evidence and unresolved bounds

- Add/derive tagged fixtures for a `running`/`completed` pair sharing one
  `toolCallId` and abnormal finish chunks whose metadata is in root `hermes`.
- Decide numeric bounds for tool ID/name and safe `error_code`.
- Decide the exact ASCII predicate, contradiction matrix, and meaning of
  “duplicate-invalid.”

**Why first:** Parser implementation without these decisions will encode
guesswork that tests later make expensive to reverse.

### 2. Extend immutable public models and exports

- Add the closed enums and fields in `models.py`.
- Update `HermesEvent` only if necessary (the variant remains
  `ToolProgressEvent`/`TerminalEvent`; no new union member is needed).
- Export enums from `__init__.py` and update package contract tests.

**Dependency:** Every parser and consumer test needs these types.

### 3. Extend private protocol wire models

- Add bounded `toolCallId`, bounded tool name, and closed status.
- Add the root `hermes` metadata model; omit raw `error`.
- Preserve strict validation and `extra="ignore"`.
- Keep parsers value-or-sentinel and validation-detail-free.

**Dependency:** `sse.py` should never inspect arbitrary mappings directly for
these fields.

### 4. Map application records and preserve terminal commit

- Construct correlated `ToolProgressEvent` values in record order.
- Map the finish reason plus validated Hermes metadata to the expanded
  `TerminalEvent`.
- Preserve pending terminal behavior, `[DONE]` rules, EOF checks, and scrub
  paths.

**Dependency:** Requires public and private types from steps 2–3.

### 5. Add session headers at the operation boundary

- Extend the public method signature with keyword-only optional values.
- Add exact validator and fresh-header builder in `client.py`.
- Validate before serialization/dispatch; clear raw and copied header state on
  every path.
- Keep response-only cleanup and caller-owned injected transport behavior.

**Dependency:** Architecturally independent of stream models, but sequencing it
after parser work reduces simultaneous changes to already-complex generator
cleanup code.

### 6. Cross-cutting verification and distribution gate

- Canary tests across `str`, `repr`, traceback rendering, cause, context,
  recursive package locals, and closed/failed generator state.
- Matrix tests for omitted/independent/combined headers, concurrency, early
  close, cancellation, protocol failure, and transport failure.
- Existing regression suites for auth, rate limiting, retryability, terminal
  ordering, limits, and injected-client ownership.
- Package-root export, `py.typed`, strict basedpyright, Ruff, 100% branch
  coverage, wheel/sdist verification.

## Sources

### Primary repository evidence

- `.planning/PROJECT.md` — v0.3.0 scope and cross-repository ownership.
- `docs/superpowers/specs/2026-07-17-conversation-contract-design.md` — approved contract and acceptance tests.
- `src/hermes_agent_api_client/client.py` — current operation, scrubbing, terminal withholding, and ownership boundaries.
- `src/hermes_agent_api_client/models.py` — strict frozen public models.
- `src/hermes_agent_api_client/protocol.py` — private strict wire models and safe failure translation.
- `src/hermes_agent_api_client/sse.py` — bounded framing, ordering, terminal state, and raw-state cleanup.
- `tests/test_protocol.py`, `tests/test_sse.py`, `tests/test_transport.py`, and
  `tests/test_client_lifecycle.py` — enforced public, decoding, transport, and
  cleanup invariants.
- `tests/fixtures/hermes/v2026.7.7.2/chat_completions/complete.sse` — current
  exact-version fixture proving `toolCallId` on a running event.

### Upstream exact-version evidence

- [Hermes Agent API server at `v2026.7.7.2`](https://github.com/NousResearch/hermes-agent/blob/v2026.7.7.2/gateway/platforms/api_server.py) — independent session headers, 256-character server cap, tool lifecycle emission, and abnormal streaming finish metadata under the root `hermes` object.
- [Hermes path-safety guard at `v2026.7.7.2`](https://github.com/NousResearch/hermes-agent/blob/v2026.7.7.2/gateway/session.py#L98-L118) — rejects `..`, path separators, and drive-letter-shaped session IDs.

---
*Architecture research for: Hermes Agent API Client v0.3.0 Conversation Contract*
*Researched: 2026-07-17*
