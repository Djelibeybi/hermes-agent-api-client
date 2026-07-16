---
gsd_state_version: 1.0
milestone: v0.3.0
milestone_name: Conversation Contract
current_phase: 02
current_phase_name: conversation-event-contract
status: executing
stopped_at: Completed 02-05-PLAN.md
last_updated: "2026-07-16T22:06:53.538Z"
last_activity: 2026-07-17
last_activity_desc: Plan 02-05 provenance gap closure completed
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
  percent: 33
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-17)

**Core value:** Python consumers can use a typed, bounded, secret-safe asynchronous client for the documented Hermes Agent API Server boundary without implementing protocol or transport behaviour themselves.
**Current focus:** Phase 02 — conversation-event-contract

## Current Position

Phase: 02 (conversation-event-contract) — EXECUTING
Plan: 5 of 5
Status: Plan execution complete; awaiting phase verification
Last activity: 2026-07-17 — Plan 02-05 provenance gap closure completed

Progress: [██████████] 100%

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

### Historical Context

- v0.1.0 was imported as published baseline evidence and is preserved under `.planning/milestones/`.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 4 must re-check latest compatible dependency versions before refreshing the lockfile.

## Session Continuity

Last session: 2026-07-16T22:06:53.534Z
Stopped at: Completed 02-05-PLAN.md
Resume file: None

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 02 P01 | 7 min | 1 tasks | 7 files |
| Phase 02 P02 | 18min | 2 tasks | 7 files |
| Phase 02 P03 | 10min | 1 tasks | 6 files |
| Phase 02 P04 | 9min | 1 tasks | 9 files |
| Phase 02 P05 | 12min | 1 tasks | 2 files |
