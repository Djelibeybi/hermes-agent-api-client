---
gsd_state_version: 1.0
milestone: v0.3.0
milestone_name: Conversation Contract
current_phase: 02
current_phase_name: conversation-event-contract
status: executing
stopped_at: Completed 02-01-PLAN.md
last_updated: "2026-07-16T20:11:45.617Z"
last_activity: 2026-07-16
last_activity_desc: Phase 02 execution started
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 4
  completed_plans: 1
  percent: 25
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-17)

**Core value:** Python consumers can use a typed, bounded, secret-safe asynchronous client for the documented Hermes Agent API Server boundary without implementing protocol or transport behaviour themselves.
**Current focus:** Phase 02 — conversation-event-contract

## Current Position

Phase: 02 (conversation-event-contract) — EXECUTING
Plan: 2 of 4
Status: Ready to execute
Last activity: 2026-07-16 — Phase 02 execution started

Progress: [███░░░░░░░] 25%

## Accumulated Context

### Decisions

- Phase numbering continues from the completed historical Phase 1 baseline.
- Lifecycle IDs, names, and safe error codes are bounded at 256 characters.
- Visible ASCII means `0x21..0x7e`; duplicate approved lifecycle keys and contradictory terminal metadata fail closed.
- The client transports opaque bounded facts; Home Assistant identity derivation and policy remain out of scope.
- [Phase 02]: One input-value-free validator enforces exact built-in str, 1-256 characters, and visible ASCII for both public and private tool identifiers. — This makes D-05 through D-08 construction and wire semantics share one implementation boundary.
- [Phase 02]: Wire statuses remain closed string literals and map explicitly into strict public ToolProgressStatus members. — The private DTO accepts exact JSON literals without weakening strict direct public enum construction.
- [Phase 02]: Terminal metadata extends the existing frozen event without adding another HermesEvent union variant. — The richer value preserves the established closed event hierarchy and delayed-terminal state machine.

### Historical Context

- v0.1.0 was imported as published baseline evidence and is preserved under `.planning/milestones/`.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 2 planning must freeze tagged terminal coexistence fixtures before implementing the mapping.
- Phase 4 must re-check latest compatible dependency versions before refreshing the lockfile.

## Session Continuity

Last session: 2026-07-16T20:11:37.927Z
Stopped at: Completed 02-01-PLAN.md
Resume file: None

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 02 P01 | 7 min | 1 tasks | 7 files |
