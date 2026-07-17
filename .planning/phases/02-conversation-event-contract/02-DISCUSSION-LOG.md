# Phase 2: Conversation Event Contract - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 2-conversation-event-contract
**Areas discussed:** Terminal consistency matrix, Tool text rules, Terminal envelope compatibility, Fixture evidence gate

---

## Terminal Consistency Matrix

| Question | Selected | Alternatives considered |
|----------|----------|-------------------------|
| Compatible `stop` metadata | Consistent optional fields | Require explicit confirmation; require sparse canonical form |
| Compatible `length` metadata | Consistent optional truncation fields | Require truncation confirmation; derive from finish reason only |
| Required `error` evidence | Require exact `partial`, allow optional corroborating flags/code | Require error code; require full error tuple |
| Meaning of explicit `null` | Present field must contain an exact valid value | Treat null as absent; mixed boolean/code rule |

**User's choices:** `stop` accepts only compatible optional success values; `length` accepts only compatible optional truncation values; `error` requires exact `partial` while compatible flags remain optional; explicit `null` and coercible lookalikes fail.

**Notes:** Omission remains distinct from malformed presence. Contradictory combinations never use precedence guesses.

---

## Tool Text Rules

| Question | Selected | Alternatives considered |
|----------|----------|-------------------------|
| `tool_call_id` character contract | Exact built-in string, 1-256 visible ASCII | Any bounded Unicode; printable Unicode |
| `tool_name` character contract | Same visible-ASCII rule | Identifier grammar only; printable Unicode |
| Normalization | Preserve exact values | Lowercase names; trim whitespace |
| Public/wire validation split | Exact parity | Wire strict/public permissive; public strict/wire reduced |

**User's choices:** IDs and names share exact built-in-string, visible-ASCII, and 1-256 bounds. Neither value is normalized, and direct public construction enforces the wire contract.

**Notes:** Tool values do not use the session ID path-shape rule.

---

## Terminal Envelope Compatibility

| Question | Selected | Alternatives considered |
|----------|----------|-------------------------|
| Canonical metadata location | Tagged root `hermes` object only | Reject noncanonical lookalikes; support generic aliases |
| When `hermes` may be absent | Optional for `stop`/`length`, required for `error` | Always required; always optional |
| Unknown fields inside `hermes` | Ignore and discard | Reject all; ignore scalars only |
| Duplicate detection scope | Approved semantic paths only | Any duplicate anywhere; lifecycle members only |

**User's choices:** The canonical tag reads metadata from root `hermes`; same-named fields elsewhere and unknown fields inside the object are discarded. Duplicate rejection covers the semantic container, finish reason, and approved lifecycle members.

**Notes:** The later evidence discussion added a narrow captured-version exception for an equivalent latest-tag shape; no generic alias support was approved.

---

## Fixture Evidence Gate

| Question | Selected | Alternatives considered |
|----------|----------|-------------------------|
| Evidence without captured combination | Design-derived fixture plus tagged schema | Captured output required; schema inference alone |
| Fixture provenance | Versioned immutable files with captured/derived labeling | Inline builders; one canonical golden only |
| Version policy | Verify `v2026.7.7.2` and latest tag | Canonical tag only; replace canonical with latest |
| Latest-tag difference | Support both when public mapping is identical | Stop on every difference; newest tag wins |
| Reconcile envelope rule | Allow only version-evidenced equivalent shapes | Root `hermes` remains the sole shape |

**User's choices:** Approved design-derived fixtures may fill captured-example gaps, with truthful provenance. Phase 2 verifies both the canonical and latest tags. A latest-tag alternate shape is accepted only with captured versioned evidence and an unambiguous identical public mapping.

**Notes:** Generic aliases, inferred permissiveness, ambiguous mappings, and silently changed public semantics remain prohibited.

---

## the agent's Discretion

- Helper naming, parser factoring, constant placement, and test parameterization within the locked public behavior and established safety patterns.

## Deferred Ideas

None.
