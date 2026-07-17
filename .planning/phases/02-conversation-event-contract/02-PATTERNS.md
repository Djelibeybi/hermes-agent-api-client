# Phase 2: Conversation Event Contract - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** 10 established files plus the new versioned fixture set
**Analogs found:** 5 strong analog families

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/hermes_agent_api_client/models.py` | public model | event-driven | Existing `_FrozenModel`, enums, and `HermesEvent` union in the same file | exact |
| `src/hermes_agent_api_client/protocol.py` | private wire model / validation utility | streaming transform | Existing `_WireModel`, pre-validators, sanitized parsers, and capability normalization in the same file | exact role; pair-aware intake is new |
| `src/hermes_agent_api_client/sse.py` | streaming decoder / event mapper | ordered streaming and event-driven | Existing `_decode_application_record`, `_SSEDecoder`, and `async_decode_hermes_sse` in the same file | exact |
| `src/hermes_agent_api_client/__init__.py` | package API facade | import/export | Existing explicit import list and `__all__` in the same file | exact |
| `tests/test_protocol.py` | unit/security test | direct construction and transform | Existing frozen-vocabulary, provenance-hash, and traceback-scrub tests in the same file | exact |
| `tests/test_sse.py` | async unit/security test | ordered streaming and event-driven | Existing golden-record, partitioning, malformed-record, secrecy, and delayed-terminal tests in the same file | exact |
| `tests/test_transport.py` | async integration/regression test | request-response plus streaming cleanup | Existing response-cleanup-before-terminal and early-close tests in the same file | exact |
| `tests/test_package.py` | package contract test | import/export | Existing exact `__all__` and star-import tests in the same file | exact |
| `tests/helpers/hermes.py` | test utility (conditional) | immutable file I/O / byte transforms | Existing golden loader and deterministic byte partition helper in the same file | exact; add a raw duplicate builder only if it improves readability |
| `tests/fixtures/hermes/v2026.7.7.2/chat_completions/*.sse` (new lifecycle fixtures) and `tests/fixtures/hermes/v2026.7.7.2/provenance.json` | immutable evidence fixture / manifest | file I/O and ordered streaming | Existing `complete.sse` plus its provenance entry | exact |

The planning inputs do not lock individual names for the new lifecycle fixtures. The planner should assign explicit paths under the version directory for: a correlated running/completed pair, valid length, valid agent error, design-derived unknown error, approved omission rows, and the tag-source-derived contradictory error row. Keep each path immutable after its SHA-256 is recorded.

## Pattern Assignments

### Public event vocabulary: `models.py` and `__init__.py`

**Analog:** the existing frozen event vocabulary in `src/hermes_agent_api_client/models.py`.

**Frozen strict base and closed enums** (`models.py` lines 11-29):

```python
class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)


class TerminalOutcome(StrEnum):
    """Terminal outcomes exposed by the Hermes stream contract."""

    SUCCESS = "success"
    LENGTH = "length"
    UPSTREAM_ERROR = "upstream_error"
```

Add `ToolProgressStatus` and `TerminalFailureReason` beside the existing public enums. Keep `ToolProgressEvent` and `TerminalEvent` as `_FrozenModel` subclasses and extend the existing `HermesEvent` union rather than introducing a second hierarchy (`models.py` lines 64-95):

```python
class ToolProgressEvent(_FrozenModel):
    """Bounded non-assistant progress metadata for a tool invocation."""

    tool_name: str
    status: str


class TerminalEvent(_FrozenModel):
    """An explicit success or typed non-success stream result."""

    outcome: TerminalOutcome


type HermesEvent = (
    AssistantDeltaEvent
    | ToolProgressEvent
    | UsageEvent
    | KeepaliveEvent
    | TerminalEvent
)
```

**Direct-construction analog:** `tests/test_protocol.py` lines 719-744 derives the union members with `get_args`, constructs each variant directly, and proves every model is frozen. Extend this test with exact built-in-string, 0/1/256/257, visible-ASCII, enum-instance, default-terminal, and mutation cases. Do not rely on Pydantic strict strings alone for `str` subclass rejection.

**Package-root export analog:** imports and `__all__` are deliberately duplicated and explicit (`src/hermes_agent_api_client/__init__.py` lines 5-24 and 28-46):

```python
from .models import (
    AssistantDeltaEvent,
    HermesCapabilities,
    HermesEvent,
    KeepaliveEvent,
    TerminalEvent,
    TerminalOutcome,
    ToolProgressEvent,
    UsageEvent,
)

__all__ = [
    "AssistantDeltaEvent",
    # ...
    "TerminalEvent",
    "TerminalOutcome",
    "ToolProgressEvent",
    "UsageEvent",
    "__version__",
]
```

Mirror both new enums in the exact-export assertion at `tests/test_package.py` lines 207-229 and in the star-import coverage adjacent to lines 232-243.

---

### Private wire DTO and approved-field projection: `protocol.py`

**Analog:** the strict additive-tolerant wire models plus sanitized parse boundary in `src/hermes_agent_api_client/protocol.py`.

**Wire model convention** (`protocol.py` lines 177-225):

```python
class _WireModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore",
        frozen=True,
        strict=True,
    )


class _FeaturesWire(_WireModel):
    chat_completions: Literal[True]
    chat_completions_streaming: Literal[True]

    @field_validator(
        "chat_completions",
        "chat_completions_streaming",
        mode="before",
    )
    @classmethod
    def _require_boolean_true(cls, value: object) -> object:
        if value is not True:
            raise ValueError
        return value
```

Use the same frozen/strict/`extra="ignore"` base for tool and terminal DTOs. Use `mode="before"` exact-type validation for approved booleans and for the shared 1-256 visible-ASCII lifecycle text contract. Keep wire status as `Literal["running", "completed"]`; construct the strict public enum explicitly in the mapper.

**Safe parser convention** (`protocol.py` lines 378-395):

```python
def _parse_tool_progress(value: object) -> _ToolProgressWire | None:
    """Parse tool progress without retaining wire validation details."""
    try:
        return _ToolProgressWire.model_validate(value)
    except ValidationError:
        return None


def _parse_chat_chunk(value: object) -> _ChatChunkWire | None:
    """Parse one chat chunk without retaining wire validation details."""
    try:
        return _ChatChunkWire.model_validate(value)
    except ValidationError:
        return None
```

Do not return or re-raise `ValidationError`, raw pair trees, or rejected values. Continue reducing failure to an input-independent sentinel and raise `HermesProtocolError` only from a raw-record-free frame, matching `sse.py` lines 46-48.

**Closest normalization analog** (`protocol.py` lines 324-337):

```python
def _normalize_capability_mapping(
    document: Mapping[object, object],
    features: Mapping[object, object],
) -> dict[object, object] | None:
    """Copy known mappings for Pydantic without leaking mapping failures."""
    try:
        normalized = dict(document)
        auth = normalized.get("auth")
        if isinstance(auth, Mapping):
            normalized["auth"] = dict(cast("Mapping[object, object]", auth))
        normalized["features"] = dict(features)
    except Exception:
        return None
    return normalized
```

The pair-aware projection is the one genuinely new repository pattern. Insert it before ordinary dictionary construction: `_load_json_safely` currently calls plain `json.loads(data)` at `sse.py` lines 73-78, after which duplicate evidence is gone. Replace that intake with a private object-pairs node and project only these singleton paths before DTO validation:

- tool record root: `toolCallId`, `tool`, `status`;
- chat root: `hermes`;
- approved single choice: `finish_reason`;
- root `hermes`: `completed`, `failed`, `partial`, `error_code`.

Reject same-value and conflicting duplicates at those paths. Ignore duplicates wholly inside additive objects, including raw error objects. Preserve missing separately from explicit `null`; never model absence solely as `T | None = None`.

---

### Ordered mapping and delayed terminal: `sse.py`

**Analog:** `_decode_application_record` owns the one-record-to-ordered-public-events transform (`sse.py` lines 94-144):

```python
if event_name == "hermes.tool.progress":
    progress = _parse_tool_progress(document)
    if progress is None:
        return None
    return (ToolProgressEvent(tool_name=progress.tool, status=progress.status),)

# ...
events: list[HermesEvent] = []
if content is not None:
    events.append(AssistantDeltaEvent(text=content))
# ... usage is appended next ...
if terminal_outcome is not None:
    events.append(TerminalEvent(outcome=terminal_outcome))
return tuple(events)
```

Keep one accepted progress record mapped to one event in record order. Do not add an ID registry, deduplicate repeated facts, demand running-before-completed, or synthesize completion after interruption. Replace the finish-reason precedence dictionary with one total helper that accepts only D-01 through D-03 and returns a safe enriched terminal or failure sentinel.

**Delayed-terminal insertion point** (`sse.py` lines 203-236):

```python
for event in events:
    if self._pending_terminal is not None:
        return None
    if isinstance(event, TerminalEvent):
        self._pending_terminal = event
    else:
        accepted.append(event)
# ...
accepted = self._accept_events(events)
events = ()
if accepted is None:
    self._fail()
```

Store the enriched `TerminalEvent` in the existing `_pending_terminal`; do not yield it from `_decode_application_record`. `finalize()` remains the decoder commit gate (`sse.py` lines 308-320), and `async_decode_hermes_sse` must continue closing the source before its final `yield` (`sse.py` lines 360-426).

**Scrub convention:** `_SSEDecoder.scrub()` clears framed data, decoded line state, `_pending_terminal`, and DONE state before failure (`sse.py` lines 169-189). Any new pair tree, projected metadata, or terminal scratch value must be local-only or explicitly cleared along the same paths.

The outer response guarantee has an exact integration analog at `tests/test_transport.py` lines 905-935: the test observes text while the response is open, then observes the terminal only after both byte stream and response are closed. Enrich the expected terminal there; do not relocate the gate.

---

### Versioned fixture evidence: `tests/fixtures/...` and `tests/helpers/hermes.py`

**Analog:** `tests/fixtures/hermes/v2026.7.7.2/chat_completions/complete.sse` lines 5-6 already preserves an upstream-shaped progress record including ignored fields and `toolCallId`:

```text
event: hermes.tool.progress
data: {"tool": "home_assistant", "emoji": "\ud83c\udfe0", "label": "Turn on the lamp", "toolCallId": "call-contract-001", "status": "running"}
```

New fixtures should remain complete immutable bytes, not Python dictionaries. This is mandatory for duplicate-key rejection cases because dictionaries cannot represent repeated members.

**Manifest convention:** `provenance.json` lines 20-38 records path, SHA-256, exact release/commit/source URL, evidence kind, and reproducible procedure. Its existing derived stream entry (`provenance.json` lines 59-90) explicitly says `evidence_kind: "synthetic-derived"` and `live_server_invoked: false`. Add each lifecycle fixture with an honest evidence kind that distinguishes tag-source-derived from design-derived, plus semantic assertions for acceptance or rejection. Never call a derived row a capture.

**Loader convention** (`tests/helpers/hermes.py` lines 12-35 and 95-106): golden paths are constrained below the pinned version root, bytes are returned immutably, JSON callers receive fresh state, and byte partitions are deterministic. If a duplicate-member builder is added, make it return fresh `bytes`/`str` and avoid parsing through a dictionary first.

**Integrity-test analog:** `tests/test_protocol.py` lines 173-186 loads the bytes and manifest, verifies tag/commit/evidence kind, and compares the actual SHA-256. Extend this pattern to every new fixture, preferably parameterized by path and expected evidence kind.

---

### Matrix, secrecy, and ordering tests: `tests/test_protocol.py`, `tests/test_sse.py`, `tests/test_transport.py`, `tests/test_package.py`

**Ordered fixture analog:** `tests/test_sse.py` lines 561-572 decodes the composite fixture bytewise and asserts the exact closed event order. Extend this expectation with `tool_call_id` and `ToolProgressStatus`; add a running/completed pair and repeated lifecycle records without reconciliation.

**Matrix analog:** `tests/test_sse.py` lines 602-620 parameterizes abnormal finish reasons and exact public terminals. Replace the broad two-row mapping with parameterized accepted and rejected rows covering every omission, exact boolean, null/coercion, bounded code, and contradiction in D-01 through D-04. Assertions should compare complete `TerminalEvent` values.

**Fail-closed analog:** malformed application records are built as raw SSE bytes and uniformly asserted as `HermesProtocolError` at `tests/test_sse.py` lines 680-731. Duplicate approved members belong in this family, but must be constructed as raw JSON text rather than `_data_record(...)`.

**Secrecy-canary analog:** `tests/test_protocol.py` lines 124-170 recursively inspects package-owned traceback locals, rejects forbidden object identities and rendered canaries, and also checks cause/context. `tests/test_sse.py` lines 734-802 applies that helper style to malformed JSON, rejected Pydantic fields, prior deltas, and raw payload identities. Add tool arguments/results/labels and raw Hermes error objects/text as canaries, and inspect both traceback state and retained decoder/generator state.

**Cleanup precedence analog:** `tests/test_sse.py` lines 852-907 proves protocol failure beats close failure and valid-terminal cleanup failure becomes `HermesTransportError`; lines 910-922 prove cancellation identity survives cleanup. Keep these exact classifications while enriching terminal values.

## Shared Patterns

### Exact public/private lifecycle text

Use one private validator/annotation for `type(value) is str`, length 1-256, and every character in `"!" <= char <= "~"`. Apply it to public `tool_call_id`/`tool_name`, private aliases `toolCallId`/`tool`, and safe error codes where applicable. Preserve accepted values exactly; do not strip, normalize, case-fold, or interpolate rejected values into errors.

### Strict approved fields, tolerant additive fields

The private DTO base ignores additive fields but approved fields are exact and fail closed. Pair-aware duplicate policy is path-specific, not global. Same-named fields outside root `hermes` are ignored for the canonical tag.

### Input-independent failure reduction

Validation helpers return safe sentinels (`None`, a closed enum, or another input-independent object). `HermesProtocolError` is raised from an input-free frame. Raw JSON, validation errors, pair nodes, ignored fields, and upstream prose must not survive in public values, exception text, cause/context, traceback locals, or decoder/generator state.

### Ordered facts and two-stage terminal commit

One valid record produces one event tuple in wire order. Nonterminals may be yielded immediately. Terminals remain pending until `[DONE]`, suffix/EOF validation, source closure, and the outer HTTP response scope all succeed.

### Immutable, truthful evidence

Versioned fixture bytes are immutable, hashed, source-linked, and classified by evidence origin. Fixture tests verify provenance rather than merely consuming examples.

## No Analog Found

| File/Concern | Role | Data Flow | Reason / Planner Guidance |
|---|---|---|---|
| Pair-preserving JSON object node and approved-path duplicate projector (likely private code in `protocol.py`, called from `sse.py`) | validation utility | streaming transform | No existing repository code preserves duplicate JSON names. Use standard `json.loads(object_pairs_hook=...)`, keep arrays distinguishable from objects, project only approved paths, and reduce all failures to the established safe sentinel boundary. Do not add a dependency or globally reject duplicates. |

## Metadata

**Analog search scope:** `src/hermes_agent_api_client/`, `tests/`, and `tests/fixtures/hermes/v2026.7.7.2/`
**Strong analog families:** public API, private protocol, SSE state machine, versioned evidence, contract/security tests
**Pattern extraction date:** 2026-07-17
