---
gsd_state_version: 1.0
milestone: v0.3.0
milestone_name: Conversation Contract
current_phase: 02
current_phase_name: conversation-event-contract
status: executing
stopped_at: Completed 02-03-PLAN.md
last_updated: "2026-07-16T20:46:58.254Z"
last_activity: 2026-07-17
last_activity_desc: Plan 03 duplicate-aware correlated tool decoding completed
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 4
  completed_plans: 3
  percent: 75
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-17)

**Core value:** Python consumers can use a typed, bounded, secret-safe asynchronous client for the documented Hermes Agent API Server boundary without implementing protocol or transport behaviour themselves.
**Current focus:** Phase 02 — conversation-event-contract

## Current Position

Phase: 02 (conversation-event-contract) — EXECUTING
Plan: 4 of 4
Status: Ready to execute
Last activity: 2026-07-17 — Plan 03 duplicate-aware correlated tool decoding completed

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

### Historical Context

- v0.1.0 was imported as published baseline evidence and is preserved under `.planning/milestones/`.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 4 must re-check latest compatible dependency versions before refreshing the lockfile.

## Session Continuity

Last session: 2026-07-16T20:46:39.376Z
Stopped at: Completed 02-03-PLAN.md
Resume file: None

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 02 P01 | 7 min | 1 tasks | 7 files |
| Phase 02 P02 | 18min | 2 tasks | 7 files |
| Phase 02 P03 | 10min | 1 tasks | 6 files |
