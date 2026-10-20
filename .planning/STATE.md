---
gsd_state_version: "1.0"
milestone: v0.3.0
current_phase: 4
current_phase_name: Contract and Distribution Verification
status: "Phase 3 shipped — PR #11"
stopped_at: Phase 03 complete, ready to plan Phase 4
last_updated: "2026-10-20T08:27:30.491Z"
last_activity: 2026-10-20
state_head: c8366d5643ea8e374fc14ac4fea6feba4961a0fb
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 10
  completed_plans: 10
  percent: 75
milestone_name: Conversation Contract
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-10-20)

**Core value:** Python consumers can use a typed, bounded, secret-safe asynchronous client for the documented Hermes Agent API Server boundary without implementing protocol or transport behaviour themselves.
**Current focus:** Phase 4 — Contract and Distribution Verification

## Current Position

Phase: 4 — Contract and Distribution Verification
Plan: Not started
Status: Phase 3 shipped — PR #11
Last activity: 2026-10-20

Progress: [████████░░] 75%

## Accumulated Context

### Decisions

- Phase numbering continues from the completed historical Phase 1 baseline.
- Lifecycle IDs, names, and safe error codes are bounded at 256 characters.
- Visible ASCII means `0x21..0x7e`; duplicate approved lifecycle keys and contradictory terminal metadata fail closed.
- The client transports opaque bounded facts; Home Assistant identity derivation and policy remain out of scope.
- [Phase 02]: One input-value-free validator enforces exact built-in str, 1-256 characters, and visible ASCII for both public and private tool identifiers. — This makes D-05 through D-08 construction and wire semantics share one implementation boundary.
- [Phase 02]: Wire statuses remain closed string literals and map explicitly into strict public ToolProgressStatus members. — The private DTO accepts exact JSON literals without weakening strict direct public enum construction.
- [Phase 02]: Terminal metadata extends the existing frozen event without adding another HermesEvent union variant. — The richer value preserves the established closed event hierarchy and delayed-terminal state machine.
- [Phase 02]: Observed latest numeric Hermes tag v2026.7.7.2 remains canonical-current; no D-16 alternate fixture root is active. — Live official tag enumeration and annotated peel verification matched the pinned canonical commit.
- [Phase 02]: Structured evidence source references bind allowed paths and exact line ranges to detached-tree anchor hashes. — Commit-looking URLs alone do not prove that a referenced path and line anchor exist.
- [Phase 02]: Every JSON object remains a private pair node until event-specific duplicate checks complete. — This preserves duplicate evidence without replacing the bounded SSE framing state machine.
- [Phase 02]: Tool projection retains only approved lifecycle facts while chat projection recursively materializes additive-compatible trees. — This satisfies tool secrecy and existing nested chat forward compatibility at the same boundary.
- [Phase 02]: Root hermes and choice finish_reason duplicates fail before materialization. — Plan 02-04 can extend the same pair-aware seam to terminal lifecycle members without lost evidence.
- [Phase 02]: Root hermes is projected into an omission-aware private DTO and excluded from ordinary chat-tree materialization. — Only approved lifecycle facts cross the trust boundary; raw error members are discarded.
- [Phase 02]: The terminal mapper accepts only D-01 through D-03; explicit null finish_reason is nonterminal only without approved lifecycle facts. — Unlisted combinations fail closed without precedence guesses.
- [Phase 02]: Unknown bounded safe error codes collapse to TerminalFailureReason.UNKNOWN. — Raw upstream codes never enter public or retained state.
- [Phase 02]: Release evidence is authenticated from externally expected release and commit values; entry-owned fields never establish their own trust root. — This closes CR-01 and D-14 by binding source anchors to the exact checked-out commit.
- [Phase 02]: Newer-tag compatibility is computed from validated immutable lifecycle bytes instead of declaration-map equality. — This closes CR-02 and D-16 while retaining difference_summary as audit metadata.
- [Phase 02]: Historical evidence_scope.live_server_tested validation remains canonical-only. — New release manifests use the release-agnostic identity, inventory, hash, and anchor contract without requiring a legacy field.
- [Phase 02]: Lifecycle compatibility reuses the production pair hook and event-specific projectors, rejecting approved duplicates while retaining additive compatibility.
- [Phase 02]: Every required lifecycle path must match its exact source-derived or design-derived evidence role before normalization.
- [Phase 02]: Provenance failures expose one finite constant code and translate lower-level exceptions outside active handlers.
- [Phase 03]: 03-01: G-08 closed by two public-API tests (task cancellation, early close); shipped src unchanged, RED proven by G4, G4b and scrub mutations
- [Phase 03]: 03-02: SESS-01/02/03 and the D-08 rejection row closed by 23 characterisation cases on shipped src; RED proven by nine mutations (purge __pycache__ around same-length mutations)
- [Phase 03]: 03-03: D-08 completion/early-close rows and SESS-05 post-dispatch failure matrix closed by 8 characterisation cases; RED by delegated-close and scrub mutations plus two test-side negative controls (finished-generator ag_frame cells cannot be mutation-red)
- [Phase 03]: 03-04: D-02 user decisions q1-accept-na (four exception-less D-08 cells N/A) and q2-document-boundary (pre-iteration retention is a known boundary, not a SESS-05 gap); src unchanged
- [Phase 03]: 03-04: D-11 mutation check on the working tree turned named tests red for all seven guards (G1 37, G2 7, G3 17, G3b 1, G4 45, G4b 32, S1 49); evidence lives in 03-TRACEABILITY.md with open_gaps 0

### Historical Context

- v0.1.0 was imported as published baseline evidence and is preserved under `.planning/milestones/`.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 4 must re-check latest compatible dependency versions before refreshing the lockfile.

## Session Continuity

Last session: 2026-10-20T08:25:09Z
Stopped at: Phase 03 complete, ready to plan Phase 4
Resume file: None

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 02 P01 | 7 min | 1 tasks | 7 files |
| Phase 02 P02 | 18min | 2 tasks | 7 files |
| Phase 02 P03 | 10min | 1 tasks | 6 files |
| Phase 02 P04 | 9min | 1 tasks | 9 files |
| Phase 02 P05 | 12min | 1 tasks | 2 files |
| Phase 02 P06 | 12min | 1 tasks | 2 files |
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 03 P01 | 4 min | 2 tasks | 1 files |
| Phase 03 P02 | 4 min | 2 tasks | 1 files |
| Phase 03 P03 | 4 min | 2 tasks | 1 files |
| Phase 03 P04 | 8 min | 3 tasks | 1 files |
