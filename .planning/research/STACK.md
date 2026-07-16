# Stack Research

**Domain:** Typed, bounded Python client contract extension for per-request HTTP
headers and SSE event metadata
**Researched:** 2026-07-17
**Confidence:** HIGH

## Recommendation

Add no runtime or development dependency for v0.3.0. The existing Python 3.13+
standard library, HTTPX, and Pydantic stack already provides every primitive the
conversation contract needs. Implement the delta inside the existing validation,
transport, and decoder layers so the package keeps one bounded public boundary.

The direct dependency set is current. A local `uv lock --upgrade --dry-run` on
2026-07-17 proposed no direct-package update; it only found transitive patch
updates for `coverage` (7.15.1 to 7.15.2) and `gitpython` (3.1.51 to 3.1.52).
Refresh those locked transitive patches as dependency hygiene before final
verification, but do not treat them as conversation-contract dependencies.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | `>=3.13` | Public typing, `StrEnum`, async generators, cancellation, and `asyncio.timeout` | All required contract primitives are in the supported standard library; no compatibility shim is needed. |
| HTTPX | `0.28.1` locked, `>=0.28.1,<1` declared | Async request dispatch and response streaming | `AsyncClient.stream()` owns and closes the individual response in a `finally` block while leaving the client open. Request headers can be supplied from a fresh mapping without mutating client defaults. |
| Pydantic | `2.13.4` locked, `>=2.13.4,<3` declared | Strict immutable public models and tolerant-but-bounded wire models | Existing `ConfigDict(frozen=True, strict=True)` and `StringConstraints` cover public immutability, type strictness, and length bounds; `extra="ignore"` preserves forward compatibility for additive wire fields. |

### Supporting Libraries

No new supporting library is required.

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Existing bounded SSE decoder | Repository implementation | Frame, byte, line, and event ordering enforcement | Extend its existing application-event mapping for `toolCallId` and terminal metadata; do not replace it. |
| Existing safe protocol exceptions | Repository implementation | Input-independent public failure metadata | Reuse `HermesTransportError(transient=False)` for invalid local session values and `HermesProtocolError` for malformed wire lifecycle metadata. |

### Development Tools

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| basedpyright | `1.39.9` | Strict typing and public-package verification | Keep strict mode; add enum exports and constructor signatures to package typing tests. |
| Ruff | `0.15.21` | Linting and formatting | No rule change is needed. |
| pytest / pytest-asyncio / pytest-cov | `9.1.1` / `1.4.0` / `7.1.0` | Async lifecycle, error-scrubbing, and 100% branch coverage tests | Preserve `fail_under = 100`; include cancellation, early close, traceback/cause/context, and generator-local canary assertions. |
| RESPX | `0.23.1` | HTTPX request capture and transport behavior | Verify independent header omission/presence, no bound-header mutation, pre-dispatch rejection, and injected-client ownership. |
| uv_build | `>=0.11.28,<0.12` | Wheel and sdist production | No build-backend change is needed; retain `py.typed` and package-root export checks. |

## Version-Sensitive Implementation Details

### 1. Validate session values before HTTPX sees them

HTTPX combines request-level and client-level headers, and its `Headers.update()`
replaces same-name keys case-insensitively. Construct a fresh plain `dict` from
the client's bound authorization headers, add `Content-Type`, and add each
validated Hermes session header independently. Never mutate `self._headers`, the
injected client's headers, or the caller's request mapping.

Validate `session_id` and `session_key` before constructing any HTTPX request or
header object. This keeps rejected values out of request objects, HTTPX
exceptions, and retained response/generator state. The existing
`async with http_client.stream(...)` pattern is correct: HTTPX closes the
response in `finally`; the client must continue to avoid calling
`AsyncClient.aclose()` for an injected transport.

### 2. Pydantic strict strings are not exact-type checks

On the locked Pydantic 2.13.4, a subclass of `str` is accepted by a strict
`str` field and normalized to a built-in `str`. The session contract is stricter,
so check `type(value) is str` manually before any Pydantic or HTTPX boundary.
Then enforce length 1 through 256, visible ASCII, no surrounding whitespace, and
the session-ID path-shape rule using input-independent control flow.

Do not rely on `ConfigDict(hide_input_in_errors=True)` for secret safety. It
hides the input from the rendered `ValidationError`, but the exception's default
structured `errors()` data still contains the rejected input. Session validation
should instead collapse to a neutral failure kind, clear references, and raise
the existing safe transport error from an input-free frame.

### 3. Decode wire literals before constructing strict public enums

On Pydantic 2.13.4, `ConfigDict(strict=True)` with a `StrEnum` field accepts an
enum instance but rejects the raw JSON string `"running"`. Keep wire models
strict and represent lifecycle values as
`Literal["running", "completed"]`; after validation, explicitly construct
`ToolProgressStatus(parsed.status)` for the public model. This creates a closed
wire set without weakening the strict public model.

Use bounded `Annotated[str, StringConstraints(...)]` aliases for `toolCallId`
and tool name, and retain `extra="ignore"` on the private wire model so `emoji`,
`label`, arguments, results, and future additive fields never enter the public
event. Freeze the exact identifier/name maximum in requirements before planning;
the design requires a bound but does not assign a number.

### 4. Keep safe terminal mapping in the existing decoder

Add `TerminalFailureReason` and the defaulted `partial` and `failure_reason`
fields to the frozen public model. Validate wire booleans strictly, map only the
approved error-code vocabulary, and reduce every unknown safe code to
`TerminalFailureReason.UNKNOWN`. Never store or interpolate raw `error.message`,
exception type, nested error payload, or Hermes error text.

This is an application-event mapping change, not a transport retry change.
Cancellation and disconnects remain exceptions, and the client should not add a
synthetic terminal event after transport failure.

## Installation

No package should be added to `pyproject.toml` for this milestone.

```bash
# Recreate the repository environment from the lockfile.
uv sync --locked --all-groups
uv run --no-sync prek install --prepare-hooks

# Before final verification, refresh the two observed transitive patch updates
# in an isolated dependency-hygiene change and review the resulting lock diff.
uv lock --upgrade
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Manual exact-type and visible-ASCII session validation feeding the existing safe error path | Pydantic request-parameter model | Only if future request options become a non-secret structured object and retained `ValidationError` input is acceptable. It is not appropriate for these header secrets. |
| Existing bounded SSE decoder plus private Pydantic wire models | Third-party SSE parser | Only if the package abandons its current byte/frame/order limits and can prove equivalent bounded behavior. No such requirement exists. |
| Fresh per-request `dict[str, str]` | Mutable shared `httpx.Headers` or client-default header mutation | Only for immutable client-wide defaults. Session identity is per request and independently optional. |
| Wire `Literal` followed by explicit `StrEnum` construction | Non-strict enum field or public `str` status | Only if coercion or an open status vocabulary is deliberately made part of the public contract. The approved design requires a closed enum. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| New runtime dependencies | The standard library, HTTPX, Pydantic, and existing decoder already cover the change; another package broadens the security and release surface without capability gain. | Existing stack. |
| Arbitrary per-request headers mapping | Expands the public transport surface and enables caller override/injection beyond the two approved headers. | Explicit keyword-only `session_id` and `session_key`. |
| `pydantic.SecretStr` for session arguments | Changes the public type, does not implement exact built-in-string acceptance, and does not by itself prevent retained validation inputs or HTTPX state. | Manual pre-dispatch validator plus reference scrubbing. |
| `hide_input_in_errors=True` as the only leak defense | It changes rendered error text, not all retained structured error state. | Do not construct/retain a validation exception containing the secret. |
| `httpx.Headers` stored on the client for session values | Per-request values could outlive the request or mutate shared state. | A fresh short-lived request dict, cleared on every exit path. |
| Tenacity or another retry library | The contract does not add retries, and replaying a streaming chat request could duplicate tool effects. | Preserve existing retryability metadata only. |
| Tool arguments, results, labels, emoji, or raw error payloads in public models | They violate the bounded, secret-safe contract and create an unstable upstream-coupled API. | Correlation ID, tool name, closed status, partial flag, and safe failure enum only. |
| Synthesized terminal events on disconnect or cancellation | It conflates transport uncertainty with a server-authored terminal result. | Preserve `CancelledError` and `HermesTransportError`; let the integration assess preceding text/tool events. |

## Stack Patterns by Variant

**If neither session value is supplied:**
- Reuse a fresh copy of the existing bound request headers without adding either
  Hermes session header.
- Preserve byte-for-byte v0.1.0 request behavior apart from the local copy.

**If one or both session values are supplied:**
- Validate each independently before dispatch, then add only the corresponding
  named header(s) to the fresh request mapping.
- Clear all short-lived header/value references after response close,
  cancellation, protocol failure, or transport failure.

**If a tool-progress payload contains additive fields:**
- Ignore them through the private wire model's `extra="ignore"` policy.
- Reject missing, malformed, unbounded, or unknown required lifecycle fields as
  `HermesProtocolError`.

**If an upstream terminal error code is unknown but structurally safe:**
- Map it to `TerminalFailureReason.UNKNOWN`.
- Do not expose or retain the raw code or any error text.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python `>=3.13` | HTTPX `0.28.1` | Existing async transport and stream context-manager behavior is sufficient. |
| Python `>=3.13` | Pydantic `2.13.4` / pydantic-core `2.46.4` | Built-in `StrEnum` is available, but strict enum fields require instances; validate raw wire values as literals first. |
| Pydantic `2.13.4` | Exact built-in-string contract | Strict `str` alone is insufficient because subclasses are accepted and normalized; use `type(value) is str`. |
| Pydantic `2.13.4` | Secret-safe local-input rejection | `hide_input_in_errors` only protects rendering; avoid retaining `ValidationError` objects built from session values. |
| HTTPX `0.28.1` | Caller-owned injected `AsyncClient` | `AsyncClient.stream()` closes the response only; retain the existing rule that only a client created by this package is closed by the package. |
| RESPX `0.23.1` | HTTPX `0.28.1` | Current locked test pair; the upgrade dry-run found no direct update. |

## Sources

- Context7 `/encode/httpx` — request/client header merging,
  `Headers.update()`, `AsyncClient.stream()`, response cleanup, and async stream
  exception mapping.
- [HTTPX client documentation](https://github.com/encode/httpx/blob/master/docs/advanced/clients.md) — client-level and request-level configuration behavior.
- [HTTPX `AsyncClient.stream` source](https://github.com/encode/httpx/blob/master/httpx/_client.py) — response closure in `finally` without client closure.
- Context7 `/pydantic/pydantic` — frozen models, strict fields and strings,
  literal validation, and input hiding in validation errors.
- [Pydantic model documentation](https://github.com/pydantic/pydantic/blob/main/docs/concepts/models.md) — `ConfigDict(frozen=True)` behavior.
- [Pydantic strict-mode documentation](https://github.com/pydantic/pydantic/blob/main/docs/concepts/strict_mode.md) — strict field validation behavior.
- [Pydantic configuration source](https://github.com/pydantic/pydantic/blob/main/pydantic/config.py) — `hide_input_in_errors` semantics.
- Local `pyproject.toml` and `uv.lock` — declared and exact locked versions.
- Local Pydantic 2.13.4 probes — strict `str` subclass normalization, strict
  `StrEnum` raw-string rejection, additive-field ignoring, and retained
  structured validation input.
- Local `uv lock --upgrade --dry-run` — direct dependencies current; two
  transitive patch updates available on 2026-07-17.

---
*Stack research for: v0.3.0 Conversation Contract*
*Researched: 2026-07-17*
