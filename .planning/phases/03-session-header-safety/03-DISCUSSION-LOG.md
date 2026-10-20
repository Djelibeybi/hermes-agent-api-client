# Phase 3: Session Header Safety - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-20
**Phase:** 3-session-header-safety
**Areas discussed:** Phase approach, Path-shaped ID rules, Evidence standard

**Pre-discussion finding:** PR #7 (`8843cfc`, released as v0.3.1) had already implemented the session headers and their tests outside GSD.

---

## Phase approach

| Option | Description | Selected |
|--------|-------------|----------|
| Audit and close gaps | Check each criterion against the shipped code and tests, add tests or fixes only where missing, produce VERIFICATION.md | ✓ |
| Verify only | Skip planning and execution; verify the existing code, then gap plans | |
| Re-plan from scratch | Treat PR #7 as a draft and allow restructuring | |

**User's choice:** Audit and close gaps

| Option | Description | Selected |
|--------|-------------|----------|
| Requirements win | Change the code to match REQUIREMENTS.md and the spec | |
| Shipped code wins | Update the requirements to describe v0.3.x behaviour | |
| Ask me per conflict | Raise each discrepancy as a decision | ✓ |

**User's choice:** Ask me per conflict

| Option | Description | Selected |
|--------|-------------|----------|
| No, fixes only | Change code only to close a proven gap | ✓ |
| Small tidy-ups allowed | Behaviour-preserving clean-ups in the session code paths | |

**User's choice:** No, fixes only

| Option | Description | Selected |
|--------|-------------|----------|
| Normal PR flow | Phase branch, PR, merge, PSR release | ✓ |
| Hold release | Use non-releasing commit types until Phase 4 | |

**User's choice:** Normal PR flow

---

## Path-shaped ID rules

**Research shown:** OWASP recommends allowlisting known-good input and lists encoded traversal forms (`%2e%2e%2f`, double encoding). The shipped check accepts `..%2f`, because `%` is visible ASCII.

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current set | `..`, `/`, `\`, drive prefix; percent-encoding left to the server | ✓ |
| Also reject `%` | Close off encoded traversal; changes released behaviour | |
| Allowlist charset | `[A-Za-z0-9._:-]` only; narrows SESS-02 | |

**User's choice:** Keep current set

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, check upstream | Research reads the tagged Hermes source for the server's own header handling | ✓ |
| No, client contract only | Don't investigate server behaviour | |

**User's choice:** Yes, check upstream

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, id only | `session_key` gets only the visible-ASCII and length rules | ✓ |
| Apply to both | Path-shape checks on `session_key` too | |

**User's choice:** Yes, id only

---

## Evidence standard

**Research shown:** The search found little on checking for leaked secrets in retained frames. The existing test suite already inspects `ag_frame` and traceback `f_locals`.

| Option | Description | Selected |
|--------|-------------|----------|
| Full exit-path matrix | Session canaries on rejection, completion, early close and cancellation; str/repr, traceback locals, cause/context, ag_frame | ✓ |
| Existing tests suffice | Current rejection and atomic-pair canaries plus general lifecycle scrubbing | |

**User's choice:** Full exit-path matrix

| Option | Description | Selected |
|--------|-------------|----------|
| Stream-specific tests | Injected client; early close and cancel mid-iteration; response closed, client still usable, CancelledError propagated | ✓ |
| Existing tests suffice | `test_injected_client_is_never_closed` plus the cancellation-precedence tests | |

**User's choice:** Stream-specific tests

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, in VERIFICATION.md | Each requirement mapped to named tests | ✓ |
| No, summary only | Narrative pass/fail per criterion | |

**User's choice:** Yes, in VERIFICATION.md

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, for key guards | Manual mutation of validation, path-shape, header copy and injected-client close | ✓ |
| No | Rely on 100% branch coverage | |

**User's choice:** Yes, for key guards

---

## Claude's Discretion

- Test naming, parameterisation and placement; wording of the audit findings.

## Deferred Ideas

- Milestone or version re-scoping (package at v0.3.3, milestone v0.3.0 still open).
