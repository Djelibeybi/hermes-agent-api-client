---
phase: 02
slug: conversation-event-contract
status: verified
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: 2026-07-17
---

# Phase 2 — Security

> Per-phase security contract for the bounded conversation-event and provenance boundaries.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Python consumer → public models | Caller-controlled lifecycle values enter immutable public event construction. | Tool identifiers, lifecycle status, terminal state |
| Untrusted SSE JSON → pair-aware projection | Duplicate names, hostile nested values, and coercible values enter protocol decoding. | Raw JSON member pairs and chat/tool records |
| Private lifecycle DTOs → public events | Only approved bounded facts may leave the protocol layer. | Tool progress and terminal metadata |
| Pending terminal → consumer | Complete suffix validation and cleanup must succeed before a terminal becomes observable. | Terminal outcome and resource state |
| Official Hermes tags → detached source tree | A release name and peeled commit establish the external evidence identity. | Tag and commit identifiers |
| Detached source tree → local fixture manifest | Editor-controlled metadata must not authenticate its own fixture bytes or anchors. | Source paths, anchors, hashes, evidence roles |
| Validated fixture bytes → compatibility decision | Public equivalence must be computed from authenticated evidence rather than declarations. | Normalized lifecycle events |
| Manifest/source values → diagnostics | Hostile paths, ranges, case IDs, and malformed structures must not escape in errors. | Untrusted provenance metadata and parser failures |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01 | Tampering | Public lifecycle models and approved JSON projections | high | mitigate | Exact built-in string/type checks, 1–256 visible-ASCII bounds, pair preservation, approved-path duplicate rejection, and strict enums in `models.py` and `protocol.py`; direct and raw-byte matrix tests pass. | closed |
| T-02-02 | Tampering | Ordered tool mapping | medium | mitigate | `sse.py` maps one accepted record to one immutable event without reconciliation state; repeat, interleave, and interruption tests pass. | closed |
| T-02-03 | Information Disclosure | Validators, pair trees, terminal errors, and failure frames | high | mitigate | Approved-field projection, raw-root discard, input-independent sentinels, scrub paths, and traceback/generator canary assertions prevent untrusted values from reaching public state. | closed |
| T-02-04 | Tampering / Spoofing | Total terminal mapper | high | mitigate | Only the locked D-01–D-03 matrix is accepted; null, duplicate, tagged, generated, and contradictory combinations fail closed. | closed |
| T-02-05 | Tampering | Pending terminal, source close, and response cleanup | high | mitigate | The two-stage terminal commit remains gated on suffix validation and cleanup; failure and cancellation precedence tests pass. | closed |
| T-02-DOS | Denial of Service | Lifecycle identifiers and safe error codes | medium | mitigate | Semantic values are capped at 256 visible-ASCII characters in addition to the bounded SSE framing limits; oversized inputs fail with closed errors. | closed |
| T-02-E1 | Spoofing | Fixture provenance | high | mitigate | Canonical evidence records the exact tag, peeled commit, immutable source URLs, evidence kind, reproduction procedure, semantic assertions, and no-live-server claim. | closed |
| T-02-E2 | Tampering | Immutable fixture bytes | high | mitigate | Every required manifest entry is inventory-checked and SHA-256 verified before its bytes are consumed. | closed |
| T-02-E3 | Tampering | Latest-tag compatibility gate | high | mitigate | Numeric tags are re-enumerated and peeled; blocked enumeration emits only `latest-tag-verification-blocked`; ambiguity requires authenticated newer evidence. Both live scopes pass. | closed |
| T-02-P1 | Spoofing | Manifest and fixture release/commit identity | high | mitigate | Expected identity comes from independently verified tags; source-tree HEAD, manifest, entry, URL, and source-ref mismatches are rejected. | closed |
| T-02-P2 | Tampering | Newer fixture bytes, hashes, and anchors | high | mitigate | A newer release must provide the complete lifecycle inventory, valid hashes, exact anchors, and a detached tree at the externally expected commit. | closed |
| T-02-P3 | Tampering | Normalized public-event equivalence | high | mitigate | Canonical/newer compatibility is computed from validated fixture bytes and rejects behavioral differences despite declaration-map equality. | closed |
| T-02-P4 | Denial of Service | Temporary source-tree lifecycle | medium | mitigate | Manifest/SSE parsing remains bounded; temporary creation, initialization, validation, and cleanup failures are translated with validation precedence preserved. | closed |
| T-02-P5 | Tampering | Newer lifecycle normalization | high | mitigate | The provenance verifier reuses the production pair hook and event-specific projectors; all approved duplicate families reject while ignored additive duplicates remain compatible. | closed |
| T-02-P6 | Spoofing | Lifecycle evidence-role authorization | high | mitigate | Every required path must exactly match `_EXPECTED_KINDS`; unknown and swapped tag-source/design roles reject. | closed |
| T-02-P7 | Information Disclosure | `ProvenanceError`, traceback state, and CLI stderr | high | mitigate | Failures expose finite constant codes, suppress cause/context, translate outside active handlers, and emit one line without editor-controlled values. | closed |
| T-02-P8 | Denial of Service | Fixture parsing and diagnostic output | medium | mitigate | Recursive JSON, oversized integers/tags/ranges, malformed matrices, Unicode Git output, NUL paths, and temporary-resource errors are exception-total and bounded to closed diagnostics. | closed |
| T-02-SC | Tampering | Python dependency set | low | accept | Phase 2 changed no dependency metadata and used the locked environment; current patch drift is recorded below and DEPS-01 assigns refresh/verification to Phase 4. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*

*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` count toward `threats_open`.*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-02-01 | T-02-SC | Dependency metadata was intentionally immutable during the event-contract phase. `uv lock --check` passes; `uv tree --outdated --depth 1` currently reports only `prek` 0.4.9→0.4.10 and Ruff 0.15.21→0.15.22. Phase 4 requirement DEPS-01 owns the current-compatible refresh and complete distribution revalidation. | Phase 2 plan contract | 2026-07-17 |

---

## Verification Evidence

| Check | Result |
|-------|--------|
| Authored register | All six Phase 2 plans contain parseable trust-boundary and STRIDE blocks; 18 unique threat IDs were consolidated. |
| Summary threat flags | No summary contains a `Threat Flags` section. Review-discovered exception-boundary issues recorded in `02-06-SUMMARY.md` are covered by T-02-P7/P8 and their regression tests. |
| Static mitigation check | Required validators, pair projectors, terminal gate, provenance identity/hash/role checks, finite error boundary, and temporary-directory ownership are present and wired in current source. |
| Full test gate | `uv run --no-sync pytest -q` — 635 passed; 100% statement and branch coverage. |
| Live evidence gate | `check_phase2_provenance.py --scope release-and-tool` and `--scope terminal` — both emitted their success markers. |
| Dependency check | `uv lock --check` passed; latest-version drift is limited to the two accepted Phase 4 patch refreshes documented in R-02-01. |
| Deep review | `02-REVIEW.md` is clean and `02-VERIFICATION.md` passes 22/22 must-haves with no human verification or gaps. |

ASVS level 1 applies. Because the register was authored at plan time and L1 classification left `threats_open: 0`, the secure-phase short-circuit rule did not require an L2/L3 security-auditor run.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-17 | 18 | 18 | 0 | Codex secure-phase workflow (ASVS L1) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-17
