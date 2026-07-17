# Project Research Summary

**Project:** Hermes Agent API Client
**Domain:** Typed, bounded, secret-safe asynchronous Python HTTP/SSE client contract
**Researched:** 2026-07-17
**Confidence:** HIGH

## Executive Summary

v0.3.0 should extend the shipped client in place rather than introduce a new
session abstraction, decoder, or dependency. The existing package boundaries
already match the work: public immutable values in `models.py`, private strict
wire DTOs in `protocol.py`, stream ordering and terminal withholding in
`sse.py`, per-operation validation and ownership in `client.py`, and supported
exports in `__init__.py`. The implementation should begin at Phase 2 because
v0.1.0 is the preserved historical baseline.

The milestone has three inseparable feature families: independently optional
and secret-safe session headers, correlated bounded tool progress, and safe
terminal partial/failure metadata. Build the event contract first, add session
transport behavior second, and finish with combined lifecycle, secrecy,
typing, coverage, and distribution verification. Home Assistant identity
derivation and policy, arbitrary request headers, raw tool data, and raw
upstream errors remain outside this repository.

The principal risks are ambiguous wire semantics and retained sensitive state.
Requirements should freeze four decisions before implementation: 256-character
maximums for tool call IDs and names; visible ASCII as `0x21..0x7e`; pair-aware
duplicate detection before JSON objects collapse; and rejection of contradictory
terminal metadata rather than choosing a winning field. Session values must be
validated before dispatch and removed from traceback and generator state, while
the existing delayed-terminal and injected-client ownership rules remain
unchanged.

## Key Findings

### Recommended Stack

Add no dependency. Python 3.13+, HTTPX 0.28.1, Pydantic 2.13.4, and the existing
bounded SSE decoder cover the complete contract. Exact local session validation
must precede Pydantic and HTTPX because strict Pydantic strings are not the same
as `type(value) is str`, and raw wire enum strings should be validated as closed
`Literal` values before constructing public `StrEnum` instances. See
[STACK.md](STACK.md).

The declared direct dependencies are current, but the lockfile has two available
transitive patch updates: `coverage` 7.15.1 to 7.15.2 and `gitpython` 3.1.51 to
3.1.52. Under the repository instruction to use current dependency versions,
v0.3.0 **must refresh and review the lockfile before final verification**. These
updates are dependency hygiene, not conversation-contract dependencies, and
should not broaden `pyproject.toml`.

**Core technologies:**

- Python `>=3.13`: public enums, async generators, cancellation, and cleanup
- HTTPX `0.28.1`: request-scoped headers and response streaming without closing an injected client
- Pydantic `2.13.4`: strict frozen public models and bounded private wire DTOs
- Existing SSE decoder: bounded framing, ordered mapping, terminal withholding, and raw-state scrubbing

### Expected Features

The approved design defines one complete milestone rather than a reduced MVP.
See [FEATURES.md](FEATURES.md).

**Must have (table stakes):**

- Independent `session_id` and `session_key` arguments with exact local validation and fresh request headers
- Pre-dispatch, non-retryable, input-independent failures with no canary retention in errors or generator frames
- Correlated `ToolProgressEvent` values with bounded ID/name and closed `running`/`completed` statuses
- Enriched terminal events with strict partial state and safe closed failure reasons
- Existing ordering, cancellation, response cleanup, retryability, injected-client ownership, and distribution guarantees

**Should have (quality differentiators):**

- Metadata-only local and upstream failure surfaces
- Consumer-detectable unmatched tool calls without client-owned lifecycle policy
- Useful partial success distinct from cancellation or transport interruption
- Forward compatibility by ignoring additive fields while failing closed on behavioral fields

**Defer to a later evidence-backed milestone:**

- Additional tool statuses, terminal reasons, named request metadata, or API operations
- Any Home Assistant identity/session derivation or partial-response policy

**Anti-features:**

- Arbitrary per-request headers
- Raw tool arguments, results, labels, emoji, payloads, or upstream error text
- Client-owned tool-call tracking, synthetic terminal events, or automatic stream replay

### Architecture Approach

Keep one linear boundary: validate and copy request-local values in `client.py`,
stream bytes through the existing state machine in `sse.py`, validate only
approved wire fields in private `protocol.py` DTOs, and construct immutable
public `models.py` values field by field. Preserve the pending-terminal commit:
the response and suffix must validate and close before a terminal becomes
observable. See [ARCHITECTURE.md](ARCHITECTURE.md).

**Major components:**

1. `models.py` and `__init__.py` — closed enums, bounded frozen events, and package-root exports
2. `protocol.py` — pair-aware JSON intake and strict private lifecycle/terminal shapes
3. `sse.py` — explicit safe mapping, wire order, delayed terminal commit, and scrubbing
4. `client.py` — exact session validation, fresh headers, dispatch, failure translation, and ownership
5. Tests, fixtures, and distribution verifier — boundary parity, lifecycle matrices, and installed-package proof

### Contract Decisions to Freeze

These are roadmap/requirements gates, not implementation details to improvise.

1. **ID and name bounds:** use a shared maximum of 256 characters for both
   `tool_call_id` and `tool_name`, enforced at wire and public boundaries. It
   matches the approved session ceiling and comfortably covers pinned Hermes
   evidence while remaining semantically bounded.
2. **Visible ASCII:** define accepted session characters as code points
   `0x21..0x7e` inclusive. This excludes spaces everywhere as well as controls,
   non-ASCII, CR/LF/NUL, and whitespace-only values. Continue applying the
   approved path-shape rejection only to `session_id`.
3. **Duplicate-invalid lifecycle fields:** decode JSON with pair awareness
   before normal mapping construction. Reject every duplicate occurrence,
   whether values agree or conflict, of approved singleton lifecycle fields at
   their relevant object level (`toolCallId`, `tool`, `status`, and terminal
   lifecycle members). Repeated lifecycle SSE records remain ordered facts and
   are not duplicates in this sense; the client must not add a tool registry.
4. **Contradictory terminal metadata:** `finish_reason` selects the candidate
   public outcome; safe Hermes metadata may refine only a compatible category
   and never overrides it. A normal `stop` cannot coexist with abnormal flags or
   an error code; `length` maps to `LENGTH`, `partial=True`, and
   `OUTPUT_TRUNCATED` and rejects metadata that denies truncation; `error` maps
   to `UPSTREAM_ERROR`, preserves a strict server boolean `partial`, maps
   `agent_error` to `AGENT_ERROR`, and maps any other bounded safe code to
   `UNKNOWN`. Any incompatible `completed`/`failed`/`partial`/`error_code`
   combination is `HermesProtocolError`; raw `error` content is never parsed
   into public or exception state. Exact accepted combinations must be captured
   as immutable fixtures and a decision-table test before mapping code lands.

### Critical Pitfalls

See [PITFALLS.md](PITFALLS.md) for the complete verification checklist.

1. **Session values retained by async generators** — use input-free validation outcomes and clear public/delegated generator locals on every exit
2. **Shared mutable headers or late validation** — atomically validate both values before serialization/dispatch and create one fresh header dictionary per request
3. **Duplicate lifecycle keys collapse silently** — detect relevant duplicates from JSON pairs before Pydantic sees a dictionary
4. **Terminal fields are guessed or raw errors escape** — pin exact-version examples, use a fail-closed consistency matrix, and never read raw error prose
5. **Bounds drift across layers** — define each semantic maximum once and test exact threshold, one-beyond, strict-type, and Unicode/control cases
6. **Source passes while the installed package is stale** — verify package-root exports, `HermesEvent`, `py.typed`, wheel/sdist imports, strict typing, Ruff, and 100% branch coverage

## Implications for Roadmap

The milestone starts at Phase 2; Phase 1 belongs to the preserved v0.1.0
historical baseline.

### Phase 2: Conversation Event Contract

**Rationale:** Wire evidence, public vocabulary, and ambiguity resolution must
exist before transport or consumer-facing integration work can rely on them.

**Delivers:**

- Pinned running/completed tool fixtures and abnormal terminal fixtures
- Frozen 256-character ID/name bounds, duplicate-key policy, and terminal consistency table
- `ToolProgressStatus`, `TerminalFailureReason`, enriched immutable events, and root exports
- Pair-aware duplicate rejection, strict private wire DTOs, explicit safe mapping, ordered tool events, and delayed terminal delivery

**Addresses:** Correlated tool progress, additive-field isolation, safe terminal
metadata, raw-error suppression, and installed public vocabulary.

**Avoids:** Duplicate-key last-value-wins, unbounded fields, guessed terminal
precedence, raw payload exposure, and premature terminal delivery.

### Phase 3: Session Header Safety

**Rationale:** Session transport is architecturally independent but touches the
most sensitive generator and cleanup paths. It should build on a stable decoder
contract and land with its own complete lifecycle tests.

**Delivers:**

- Exact built-in-string validation, length 1-256, `0x21..0x7e`, and session-ID path-shape rejection
- Independent optional arguments and exact two-header mapping from fresh operation-local state
- Atomic zero-dispatch rejection and no caller/bound-header mutation or concurrent bleed
- Traceback, cause/context, early-close, cancellation, generator-local, response, and injected-client ownership proof

**Uses:** Existing HTTPX request/response ownership and metadata-only transport failure classification.

**Implements:** The operation and ownership boundary in `client.py` without an arbitrary-header escape hatch.

### Phase 4: Contract Regression and Distribution Verification

**Rationale:** The milestone is complete only when all three feature families and
the v0.1.0 guarantees pass together from source and built artifacts.

**Delivers:**

- Combined secrecy and lifecycle matrices, malformed/duplicate/contradictory wire tests, and unmatched-call interruption proof
- Exact package-root exports, strict basedpyright and `--verifytypes`, Ruff, 100% branch coverage, `py.typed`, wheel, and sdist verification
- Reviewed lockfile refresh for `coverage` 7.15.2 and `gitpython` 3.1.52, subject to confirming those remain latest when the phase executes
- Full regression proof for authentication, HTTP status/retryability, bounded protocol ordering, cleanup precedence, and injected-client ownership

### Phase Ordering Rationale

- Wire evidence and public types precede mapping so tests encode approved semantics rather than implementation guesses.
- Session work follows the event decoder to limit simultaneous edits in nested async-generator cleanup paths.
- Cross-cutting verification and the required latest-version lock refresh happen last so artifacts are built from the final locked environment.
- Each phase preserves the ownership split: this client transports typed bounded facts; `hermes-conversation` derives identities and owns Home Assistant policy.

### Research Flags

Phases needing explicit evidence checks during planning:

- **Phase 2:** Verify exact tagged terminal envelope shapes and freeze every accepted `completed`/`failed`/`partial`/`error_code` combination before implementation.
- **Phase 3:** Audit generator-frame secrecy and cleanup precedence against the existing repository-specific lifecycle tests.
- **Phase 4:** Re-check current package versions before refreshing the lockfile because the observed patch versions can drift.

Phases with standard patterns after those gates:

- **Phase 2 model/export work:** Established strict frozen-model and package-root patterns already exist.
- **Phase 4 build verification:** Existing Ruff, basedpyright, coverage, wheel/sdist, and standalone verification commands should be reused.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Direct versions and behavior were checked against the lockfile, local probes, Context7, and official sources. |
| Features | HIGH | The approved design and project boundary define the milestone precisely. |
| Architecture | HIGH | Existing source and tests expose clear extension seams and lifecycle ownership. |
| Terminal wire combinations | MEDIUM-HIGH | Tagged Hermes source confirms the envelope, but immutable client fixtures do not yet cover every coexistence case. |
| Pitfalls | HIGH | Risks map directly to existing secrecy, ordering, ownership, typing, and artifact gates. |

**Overall confidence:** HIGH

### Gaps to Address

- **Terminal coexistence evidence:** Transcribe or capture exact tagged examples and freeze the fail-closed matrix in Phase 2 before writing mapping code.
- **Safe `error_code` bound:** Choose a small explicit semantic maximum in Phase 2 and apply it at pair-aware and wire-model boundaries; raw values remain private and unknown valid codes reduce to `UNKNOWN`.
- **Latest transitive versions:** Re-run the dependency update check in Phase 4; refresh the lockfile to the then-current compatible patches rather than assuming 7.15.2 and 3.1.52 remain latest.

## Sources

### Primary (HIGH confidence)

- Approved design: `docs/superpowers/specs/2026-07-17-conversation-contract-design.md`
- Project boundary: `.planning/PROJECT.md`
- Existing client, model, protocol, SSE, lifecycle tests, fixtures, and distribution verifier in this repository
- Context7 `/encode/httpx` — request headers, async streaming, and response cleanup
- Context7 `/pydantic/pydantic` — strict/frozen models, literals, enums, and validation-error behavior
- Hermes Agent API Server `v2026.7.7.2` tagged source — session header limits, tool lifecycle records, and terminal metadata envelope

### Secondary (MEDIUM confidence)

- Local Pydantic 2.13.4 behavior probes — exact strict-string/enum and retained-validation-input behavior
- Local `uv lock --upgrade --dry-run` — two available transitive patch updates on 2026-07-17

---
*Research completed: 2026-07-17*
*Ready for roadmap: yes*
