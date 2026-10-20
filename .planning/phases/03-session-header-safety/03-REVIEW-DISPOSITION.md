---
phase: 03
review: 03-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "\"Retain no session values\" test checks only CPython-guaranteed state; suspended-frame retention passes the whole suite"
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Unbounded gate wait makes the cancellation test hang instead of failing"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "`repr()` canary assertions on generators and events cannot fail"
  - id: IN-01
    severity: info
    disposition: open
    title: "Rejected-value cases duplicate existing parametrisations"
  - id: IN-02
    severity: info
    disposition: open
    title: "\"First request gated, later requests succeed\" handler and SSE literal duplicated"
  - id: IN-03
    severity: info
    disposition: open
    title: "Completion mode does not assert the response scope closed"
  - id: IN-04
    severity: info
    disposition: open
    title: "Signature test name overclaims"
open: 4
total: 7
recorded: 2026-10-20T08:09:46.710Z
---

# Phase 03: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | fixed | 03-REVIEW-FIX.md |
| WR-01 | warning | fixed | 03-REVIEW-FIX.md |
| WR-02 | warning | fixed | 03-REVIEW-FIX.md |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
