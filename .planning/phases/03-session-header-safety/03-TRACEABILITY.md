---
phase: 03-session-header-safety
plan_authored_by: 03-04
recorded: 2026-10-20T07:44:17Z
open_gaps: 0
---

# Phase 3: Session Header Safety Traceability and Evidence Record

## Relationship to 03-VERIFICATION.md

This file is the plan-authored evidence record that decisions D-10 and D-11 require. Plan 03-04 wrote it; no verifier pass writes it.

- `gsd-verifier` writes `03-VERIFICATION.md` after the phase's plans finish. It lists this file under Required Artifacts and records the D-10 traceability truth and the D-11 mutation truth in its Observable Truths table.
- Each item under `## Gaps` in this file fails the phase truth that the section reads "None". The phase verification therefore carries it into the `gaps:` list of `03-VERIFICATION.md`, and per D-10 it drives `/gsd-plan-phase 3 --gaps`.
- Phase 4 reuses the `## D-10 Traceability` table here as the starting point for VERI-02.

This record holds no verdict, score or `gaps:` frontmatter. Those belong to the verifier's report.

## Provenance

PR #7 (`8843cfc fix: complete conversation contract (#7)`, 2026-07-17, released in v0.3.1 and contained in the v0.3.1, v0.3.2 and v0.3.3 tags) implemented the session behaviour. It added `session_id` and `session_key` to `HermesAgentApiClient.stream_chat_events`, together with `_is_valid_session_value`, `_chat_request_headers`, the PR #7 session tests in `tests/test_client_lifecycle.py` and `test_stream_discards_temporary_request_headers_before_yield` in `tests/test_transport.py`.

`src/hermes_agent_api_client/client.py`, `tests/test_client_lifecycle.py` and `tests/test_transport.py` were unchanged from `8843cfc` until Phase 3. `git log --oneline 8843cfc..main -- src/hermes_agent_api_client/client.py tests/test_client_lifecycle.py tests/test_transport.py` printed nothing.

Phase 3 added tests and evidence only. It did not build the session behaviour. On the phase branch `feat/phase-03-session-header-safety`:

```text
$ git log --oneline main..HEAD -- src/
(no output; exit 0)

$ git log --oneline main..HEAD -- tests/
64831d4 test(03-03): prove post-dispatch failures carry no session values
0c9f36c test(03-03): prove completed and closed streams retain no session values
1bb4d93 test(03-02): prove rejected session values leave no retained state
6ef46ef test(03-02): prove session values reach only their exact headers
247cbe0 test(03-01): prove early close keeps the injected client reusable
de5e53c test(03-01): prove mid-iteration cancellation keeps the injected client open
```

## D-11 Mutation Check

Run on 2026-10-20 on the real working tree (not a scratch copy), one mutation at a time, in the order G1, G2, G3, G3b, G4, G4b, S1. For each mutation:

1. `git diff --exit-code -- src/` confirmed clean.
2. The exact-string edit was applied at the anchor in `src/hermes_agent_api_client/client.py`, after an assertion that the anchor occurred exactly once.
3. `src/**/__pycache__` was purged, so no stale bytecode could carry a previous mutation into this run (the Plan 03-02 lesson).
4. `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q -rf` ran (with `-p no:cacheprovider`), and the failure count and every `FAILED` node ID were captured.
5. `git checkout -- src/hermes_agent_api_client/client.py` restored the file, `src/**/__pycache__` was purged again, and `git diff --exit-code -- src/` exited 0 before the next mutation.

Baseline on the clean tree before the first mutation: `198 passed`. Counts below are the ones this run produced; none was copied from research.

| ID | Guard | Location | Mutation | Failures | Expected inclusions present | Restored (`git diff` clean) |
|----|-------|----------|----------|----------|-----------------------------|-----------------------------|
| G1 | Value validation (D-11 "value validation") | `client.py:158` | `validated = _require_lifecycle_text(value)` → `validated = str(value)` | 37 | yes: `test_rejected_session_values_leave_no_retained_state[session-id-carriage-return]`, `[session-id-tab]` and `[session-id-bytes]`, plus all 24 `test_invalid_session_arguments_fail_locally_without_dispatch` cases | yes |
| G2 | Path-shape rejection (D-11 "path-shape rejection") | `client.py:185` | `reject_path_shape=True,` → `reject_path_shape=False,` (the `session_id` call) | 7 | yes: `test_path_shaped_session_ids_fail_before_dispatch[parent]` and `test_rejected_session_values_leave_no_retained_state[session-id-embedded-parent]` | yes |
| G3 | Fresh header copy, no bound or caller mutation (D-11 "fresh copy") | `client.py:193` | `request_headers = dict(headers)` → `request_headers = headers` (the copy followed by `if session_id is not None:`) | 17 | yes: `test_concurrent_streams_isolate_session_headers`, `test_session_values_appear_only_in_their_exact_headers[both]`, `test_stream_session_headers_are_independent_and_request_scoped[maximum-session-id]` and `test_injected_client_survives_public_stream_task_cancellation`. `test_stream_session_headers_are_independent_and_request_scoped[neither]` stayed green, as expected | yes |
| G3b | Inner header copy (defence in depth) | `client.py:435` | `request_headers = dict(headers)` → `request_headers = headers` (the copy followed by `request_headers["Content-Type"] = ...`) | 1 | yes: `tests/test_transport.py::test_stream_success_closes_response_and_refuses_redirects` | yes |
| G4 | Not closing the injected client, exit ownership (D-11 "not closing the injected client") | `client.py:601` | `owns_active = active is not None and self._injected_http_client is None` → `owns_active = active is not None` | 45 | yes: `test_injected_client_is_never_closed` and `test_injected_client_survives_public_stream_early_close` | yes |
| G4b | Not closing the injected client, stream path | `client.py:708` | insert `await active.aclose()` (8-space indent) before the `active = None` that is followed by `base_url = None`, `request = {}` and `event = None` | 32 | yes: both Plan 03-01 tests, `test_injected_client_survives_public_stream_early_close` and `test_injected_client_survives_public_stream_task_cancellation` | yes |
| S1 | Session-local scrub in `stream_chat_events` | `client.py:674-675` | delete `session_id = None` and `session_key = None` | 49 | yes: all five `test_post_dispatch_failures_carry_no_session_values` cases and `test_stream_request_cancellation_preserves_identity` | yes |

Every mutation exited 1 with at least one named test red, and every expected inclusion was present. After the last mutation (S1) `git diff --exit-code -- src/` exited 0, and the restored tree ran `198 passed`.

Observations beyond the expected inclusions:

- G3 also turned all five `test_session_values_accept_exact_boundaries` cases red: each asserts that the client's bound headers equal their pre-stream copy. It turned `test_injected_client_survives_public_stream_early_close` red at its later-stream assertion `'X-Hermes-Session-Id' not in ...headers` (`tests/test_client_lifecycle.py:923`): with the copy removed, the earlier stream's session header leaked through the bound headers into a later stream that passed no session arguments.
- G4 turned `test_stream_session_headers_are_independent_and_request_scoped[neither]` red. That case is not about session values. The PR #7 test asserts `injected_http_client.is_closed is False` after the `async with` block (`tests/test_client_lifecycle.py:526`), which G4 breaks.
- G4b turned `test_completed_and_closed_streams_retain_no_session_values[completion]` and `[early-close-after-event]` red through their `injected_http_client.is_closed is False` assertion (`tests/test_client_lifecycle.py:1247`).

FAILED node IDs per mutation, as captured from the `-rf` short summary:

<details>
<summary>G1: 37 FAILED node IDs (pytest summary: <code>37 failed, 161 passed in 1.00s</code>)</summary>

- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-delete]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-embedded-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-empty]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-leading-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-newline]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-non-ascii]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-non-string]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-nul]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-subclass]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-too-long]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-trailing-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-delete]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-embedded-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-empty]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-leading-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-newline]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-non-ascii]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-non-string]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-nul]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-subclass]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-too-long]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-trailing-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free[invalid-id]`
- `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free[invalid-key]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-both-invalid]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-invalid-id]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-invalid-key]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-bytes]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-carriage-return]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-empty]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-tab]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-bytes]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-carriage-return]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-empty]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-tab]`

</details>

<details>
<summary>G2: 7 FAILED node IDs (pytest summary: <code>7 failed, 191 passed in 0.47s</code>)</summary>

- `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[backslash]`
- `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[drive-prefix]`
- `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[parent]`
- `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[slash]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-drive-prefix]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-embedded-parent]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-slash]`

</details>

<details>
<summary>G3: 17 FAILED node IDs (pytest summary: <code>17 failed, 181 passed in 0.66s</code>)</summary>

- `tests/test_client_lifecycle.py::test_concurrent_streams_isolate_session_headers`
- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`
- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-digit-colon-prefix]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-inner-colon]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-single-dots]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-key-maximum]`
- `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-key-minimum]`
- `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[both]`
- `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[id-only]`
- `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[key-only]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[both]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[maximum-session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[minimum-session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[path-shaped-session-key]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-key]`

</details>

<details>
<summary>G3b: 1 FAILED node IDs (pytest summary: <code>1 failed, 197 passed in 0.34s</code>)</summary>

- `tests/test_transport.py::test_stream_success_closes_response_and_refuses_redirects`

</details>

<details>
<summary>G4: 45 FAILED node IDs (pytest summary: <code>45 failed, 153 passed in 1.08s</code>)</summary>

- `tests/test_client_lifecycle.py::test_capability_context_close_failure_becomes_fresh_transport_error`
- `tests/test_client_lifecycle.py::test_capability_limit_failure_precedes_response_close_cancellation[declared]`
- `tests/test_client_lifecycle.py::test_capability_limit_failure_precedes_response_close_cancellation[observed]`
- `tests/test_client_lifecycle.py::test_capability_protocol_failure_precedes_response_close_cancellation[invalid-shape]`
- `tests/test_client_lifecycle.py::test_capability_protocol_failure_precedes_response_close_cancellation[malformed-json]`
- `tests/test_client_lifecycle.py::test_capability_protocol_failure_precedes_response_close_failure[invalid-shape]`
- `tests/test_client_lifecycle.py::test_capability_protocol_failure_precedes_response_close_failure[malformed-json]`
- `tests/test_client_lifecycle.py::test_capability_read_cancellation_precedes_response_close_failure`
- `tests/test_client_lifecycle.py::test_capability_read_transport_failure_precedes_response_close_cancellation[complete]`
- `tests/test_client_lifecycle.py::test_capability_read_transport_failure_precedes_response_close_cancellation[immediate]`
- `tests/test_client_lifecycle.py::test_capability_read_transport_failure_precedes_response_close_cancellation[partial]`
- `tests/test_client_lifecycle.py::test_capability_response_close_cancellation_preserves_identity`
- `tests/test_client_lifecycle.py::test_capability_response_close_failure_becomes_fresh_transport_error`
- `tests/test_client_lifecycle.py::test_capability_status_failure_precedes_response_close_cancellation`
- `tests/test_client_lifecycle.py::test_capability_status_failure_precedes_response_close_failure`
- `tests/test_client_lifecycle.py::test_closing_public_stream_immediately_closes_delegated_response`
- `tests/test_client_lifecycle.py::test_concurrent_streams_isolate_session_headers`
- `tests/test_client_lifecycle.py::test_delegated_close_preserves_cancellation_and_scrubs_iterator`
- `tests/test_client_lifecycle.py::test_delegated_primary_failure_precedes_close_cancellation[cancellation]`
- `tests/test_client_lifecycle.py::test_delegated_primary_failure_precedes_close_cancellation[runtime-error]`
- `tests/test_client_lifecycle.py::test_injected_client_is_never_closed`
- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`
- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[authentication-401]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[protocol-malformed-sse]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[status-503]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[transport-connect-error]`
- `tests/test_client_lifecycle.py::test_public_stream_accepts_delegated_iterator_without_aclose`
- `tests/test_client_lifecycle.py::test_stream_protocol_failure_precedes_response_close_cancellation[byte-limit]`
- `tests/test_client_lifecycle.py::test_stream_protocol_failure_precedes_response_close_cancellation[malformed-sse]`
- `tests/test_client_lifecycle.py::test_stream_protocol_failure_precedes_response_close_failure`
- `tests/test_client_lifecycle.py::test_stream_read_cancellation_precedes_response_close_cancellation`
- `tests/test_client_lifecycle.py::test_stream_read_cancellation_precedes_response_close_failure`
- `tests/test_client_lifecycle.py::test_stream_response_close_cancellation_preserves_identity`
- `tests/test_client_lifecycle.py::test_stream_response_close_failure_after_delta_becomes_transport_error`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[both]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[maximum-session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[minimum-session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[neither]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[path-shaped-session-key]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-key]`
- `tests/test_client_lifecycle.py::test_stream_status_failure_precedes_response_close_cancellation`
- `tests/test_client_lifecycle.py::test_stream_transport_failure_precedes_response_close_cancellation`

</details>

<details>
<summary>G4b: 32 FAILED node IDs (pytest summary: <code>32 failed, 166 passed in 0.87s</code>)</summary>

- `tests/test_client_lifecycle.py::test_bound_endpoint_and_auth_are_reused_across_operations`
- `tests/test_client_lifecycle.py::test_closing_public_stream_immediately_closes_delegated_response`
- `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[completion]`
- `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]`
- `tests/test_client_lifecycle.py::test_concurrent_streams_isolate_session_headers`
- `tests/test_client_lifecycle.py::test_delegated_close_preserves_cancellation_and_scrubs_iterator`
- `tests/test_client_lifecycle.py::test_delegated_primary_failure_precedes_close_cancellation[cancellation]`
- `tests/test_client_lifecycle.py::test_delegated_primary_failure_precedes_close_cancellation[runtime-error]`
- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`
- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[authentication-401]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[protocol-malformed-sse]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[status-503]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[transport-connect-error]`
- `tests/test_client_lifecycle.py::test_public_stream_accepts_delegated_iterator_without_aclose`
- `tests/test_client_lifecycle.py::test_stream_protocol_failure_precedes_response_close_cancellation[byte-limit]`
- `tests/test_client_lifecycle.py::test_stream_protocol_failure_precedes_response_close_cancellation[malformed-sse]`
- `tests/test_client_lifecycle.py::test_stream_protocol_failure_precedes_response_close_failure`
- `tests/test_client_lifecycle.py::test_stream_read_cancellation_precedes_response_close_cancellation`
- `tests/test_client_lifecycle.py::test_stream_read_cancellation_precedes_response_close_failure`
- `tests/test_client_lifecycle.py::test_stream_response_close_cancellation_preserves_identity`
- `tests/test_client_lifecycle.py::test_stream_response_close_failure_after_delta_becomes_transport_error`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[both]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[maximum-session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[minimum-session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[neither]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[path-shaped-session-key]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-id]`
- `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-key]`
- `tests/test_client_lifecycle.py::test_stream_status_failure_precedes_response_close_cancellation`
- `tests/test_client_lifecycle.py::test_stream_transport_failure_precedes_response_close_cancellation`

</details>

<details>
<summary>S1: 49 FAILED node IDs (pytest summary: <code>49 failed, 149 passed in 1.46s</code>)</summary>

- `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-delete]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-embedded-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-empty]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-leading-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-newline]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-non-ascii]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-non-string]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-nul]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-subclass]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-too-long]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-trailing-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-delete]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-embedded-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-empty]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-leading-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-newline]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-non-ascii]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-non-string]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-nul]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-subclass]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-too-long]`
- `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-trailing-space]`
- `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free[invalid-id]`
- `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free[invalid-key]`
- `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[backslash]`
- `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[drive-prefix]`
- `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[parent]`
- `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[slash]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[authentication-401]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[protocol-malformed-sse]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[status-503]`
- `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[transport-connect-error]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-both-invalid]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-invalid-id]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-invalid-key]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-bytes]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-carriage-return]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-drive-prefix]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-embedded-parent]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-slash]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-tab]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-bytes]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-carriage-return]`
- `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-tab]`
- `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity`

</details>

## D-10 Traceability

Every node ID below appears in the output of `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --collect-only -q --no-cov` (198 tests collected). A bare function ID without a `[case]` suffix means every collected case of that function.

"Pre-Phase 3" tests were committed before this phase. Those introduced by PR #7 (`8843cfc`) are marked (PR #7); the others are older lifecycle and transport tests that PR #7 inherited. "Phase 3" tests were added by Plans 03-01 to 03-03. The mutation column cites the D-11 run recorded above, and names a supplementary RED proof from a Plan 03-0x summary where no D-11 guard targets the criterion.

| Req | Criterion | Pre-Phase 3 tests | Phase 3 tests | D-11 mutation that turns a listed test red |
|-----|-----------|-------------------|---------------|--------------------------------------------|
| SESS-01 | Independence: `session_id`, `session_key`, both or neither can be supplied | `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[neither]`, `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-id]`, `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-key]`, `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[both]` (PR #7) | `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[id-only]`, `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[key-only]`, `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[both]` | G3 (`[session-id]`, `[session-key]`, `[both]` and all three Phase 3 cases red; `[neither]` green) |
| SESS-01 | `None` omits that argument's header | `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[neither]`, `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-id]`, `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[session-key]` (PR #7) | `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[id-only]`, `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[key-only]` | G3 (`[session-id]`, `[session-key]`, `[id-only]`, `[key-only]` red) |
| SESS-01 | Exact-only mapping: each value appears once, verbatim, only under its own header, never in another header, the body or the URL | none | `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[id-only]`, `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[key-only]`, `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[both]` | G3 (all three red). Supplementary: Plan 03-02 T1a (extra `X-Request-Trace` header) turned `[id-only]` and `[both]` red on the "not in other header values" assertion |
| SESS-01 | No arbitrary-header API: `stream_chat_events(self, request, *, session_id=None, session_key=None)` with no `*args` or `**kwargs` | none | `tests/test_client_lifecycle.py::test_stream_chat_events_accepts_no_arbitrary_headers` | No D-11 guard covers the signature. Supplementary: Plan 03-02 T1b (add a `headers` parameter) turned it red |
| SESS-02 | Exact built-in `str`: `str` subclass, non-string and `bytes` rejected | `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-subclass]`, `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-non-string]`, `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-subclass]`, `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-non-string]` (PR #7) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-bytes]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-bytes]` | G1 (all six red) |
| SESS-02 | 1-256 characters, with positive bounds for both arguments | `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-empty]`, `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_id-too-long]`, `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-empty]`, `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch[session_key-too-long]`, `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[minimum-session-id]`, `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[maximum-session-id]` (PR #7) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-empty]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-empty]`, `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-key-minimum]`, `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-key-maximum]` | G1 (all empty and too-long cases red); G3 (the four positive-boundary cases red through their bound-headers assertion). Supplementary: Plan 03-02 T2e (`<=` → `<` at the 256 bound) turned `[session-key-maximum]` red |
| SESS-02 | Visible ASCII `0x21..0x7e`, including carriage return and tab | `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch` (the `space`, `leading-space`, `trailing-space`, `embedded-space`, `newline`, `nul`, `delete` and `non-ascii` cases for both arguments) (PR #7) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-carriage-return]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-carriage-return]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-tab]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-key-tab]` | G1 (every listed case red) |
| SESS-02 | `session_id` path shape (D-05): `..` anywhere including embedded, `/`, `\`, letter-colon drive prefix; adjacency positives accepted | `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[parent]`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[slash]`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[backslash]`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch[drive-prefix]` (PR #7) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-embedded-parent]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-slash]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[session-id-drive-prefix]`, `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-single-dots]`, `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-inner-colon]`, `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries[session-id-digit-colon-prefix]` | G2 (all seven rejection cases red). The positives are red under G3 only through their bound-headers assertion. Supplementary: Plan 03-02 T2c (`".." in` → `== ".."`) turned `[session-id-embedded-parent]` red and T2d (`isalpha` → `isalnum`) turned `[session-id-digit-colon-prefix]` red |
| SESS-02 | `session_key` gets no path checks (D-06) | `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped[path-shaped-session-key]` (PR #7) | none | G3 (red through its bound-headers assertion). D-06 is the absence of a guard, so no D-11 mutation adds one |
| SESS-02 | Invalid pair fails atomically | `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free[invalid-id]`, `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free[invalid-key]` (PR #7) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-invalid-id]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-invalid-key]`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state[pair-both-invalid]` | G1 (all five red) |
| SESS-03 | Rejection happens before network dispatch (`requests == []`) | `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch`, `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free` (PR #7) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state` (14 cases) | G1 and G2 (every listed rejection case red under one of them) |
| SESS-03 | Safe, non-retryable local-input classification (`HermesTransportError`, category `TRANSPORT`, `status_code None`, `retryable False`) | `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch`, `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free` (PR #7, `retryable is False`) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state` (exact metadata, 14 cases) | G1 (no local error raised). Supplementary: Plan 03-02 T2f (`transient=False` → `True`) turned all 14 Phase 3 cases red |
| SESS-03 | Value-free text and metadata: exact `str`, `repr` and `args`, no canary | `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch`, `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free` (PR #7, rendered traceback text) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state` (exact `str`, `repr` and `args` in all 14 cases) | S1 (all 12 canary-bearing Phase 3 cases red, plus every PR #7 rejection case) |
| SESS-04 | Fresh request headers; the client's bound authorisation headers unchanged | `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped` (PR #7, `client._headers == bound_headers`), `tests/test_client_lifecycle.py::test_concurrent_streams_isolate_session_headers` (PR #7) | `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers`, `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries` | G3 (17 red, including `[maximum-session-id]`; `[neither]` green) |
| SESS-04 | The caller's request mapping is unchanged | `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped` (PR #7, `request_document == original_document`), `tests/test_client_lifecycle.py::test_bound_endpoint_and_auth_are_reused_across_operations` | none | No D-11 guard targets the request-mapping copy. G3 and G4b turn these tests red through their header and client-ownership assertions, not through the request-mapping assertion |
| SESS-04 | Concurrent isolation: the exact set of (id, key) pairs across 8 gathered streams, independent of dispatch order | `tests/test_client_lifecycle.py::test_concurrent_streams_isolate_session_headers` (PR #7) | none | G3 (red) |
| SESS-04 | No session header leaks into a later stream after cancel or early close | none | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation`, `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close` | G3 (both red; the early-close case fails at `'X-Hermes-Session-Id' not in ...headers` for the later stream, `tests/test_client_lifecycle.py:923`) |
| SESS-04 | Inner copy in the delegated stream, and temporary request headers cleared before the first yield | `tests/test_transport.py::test_stream_success_closes_response_and_refuses_redirects`, `tests/test_transport.py::test_stream_discards_temporary_request_headers_before_yield` (PR #7) | none | G3b (`test_stream_success_closes_response_and_refuses_redirects` red). The `request_headers.clear()` line is not a D-11 guard, so `test_stream_discards_temporary_request_headers_before_yield` stays green under all seven mutations |
| SESS-05 | Exit path: rejection | `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch`, `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free` (PR #7) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state` | S1 (every PR #7 rejection case and the 12 canary-bearing Phase 3 cases red) |
| SESS-05 | Exit path: successful completion | none | `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[completion]` | G4b (red, through its injected-client assertion). Its `ag_frame is None` assertion can only be shown red by the Plan 03-03 T1b test-side negative control, because CPython clears a finished generator's frame |
| SESS-05 | Exit path: early close (after an event, and before the first iteration) | `tests/test_client_lifecycle.py::test_closing_public_stream_immediately_closes_delegated_response` | `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]`, `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-before-first-iteration]`, `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close` | G4b (`[early-close-after-event]`, the Plan 03-01 test and the pre-Phase 3 test red). Supplementary: Plan 03-03 T1a (delegated `aclose()` → `pass`) and T1c (negative control) |
| SESS-05 | Exit path: cancellation at the request stage | `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity` | `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]` | S1 (both red) |
| SESS-05 | Exit path: cancellation mid-iteration (real `task.cancel()`) | none | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` | S1 (red: a canary remains in package frame locals); G4b also red |
| SESS-05 | Post-dispatch public failures (401, 503, malformed SSE, `ConnectError` embedding both values) | none | `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[authentication-401]`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[status-503]`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[protocol-malformed-sse]`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[transport-connect-error]` | S1 (all five cases of the function red) |
| HTTP-02 | Early close closes only the response; the injected client stays open and serves a later request | `tests/test_client_lifecycle.py::test_closing_public_stream_immediately_closes_delegated_response`, `tests/test_transport.py::test_stream_early_close_closes_response_and_preserves_client` (internal `_stream_chat_events`) | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`, `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]` | G4b (all three `tests/test_client_lifecycle.py` tests red) |
| HTTP-02 | Mid-iteration cancellation closes only the response; `CancelledError` propagates after cleanup and `task.cancelled()` is `True` | `tests/test_client_lifecycle.py::test_stream_read_cancellation_precedes_response_close_cancellation`, `tests/test_transport.py::test_stream_cancellation_is_unchanged_after_response_cleanup` (internal) | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` | G4b (the Phase 3 test and `test_stream_read_cancellation_precedes_response_close_cancellation` red) |
| HTTP-02 | Ownership at exit: `__aexit__` never closes an injected client | `tests/test_client_lifecycle.py::test_injected_client_is_never_closed` | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close` | G4 (both red) |
| HTTP-02 | Request-stage cancellation keeps its identity and propagates after cleanup | `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity` | `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]` | S1 (both red); G4 and G4b also turn the Phase 3 case red |

### Roadmap success criteria

| SC | Success criterion (ROADMAP Phase 3) | Requirements | Node IDs that prove it | D-11 mutations |
|----|-------------------------------------|--------------|------------------------|----------------|
| SC1 | Consumers can independently omit or provide `session_id` and `session_key`, with non-`None` values mapped only to their exact Hermes headers and no arbitrary-header API | SESS-01 | `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped`, `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers`, `tests/test_client_lifecycle.py::test_stream_chat_events_accepts_no_arbitrary_headers` | G3 (plus Plan 03-02 T1a and T1b) |
| SC2 | Only exact built-in strings of 1-256 visible ASCII characters are accepted, path-shaped session IDs are rejected, and invalid pairs fail atomically before dispatch as safe non-retryable local input errors | SESS-02, SESS-03 | `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch`, `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free`, `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state`, `tests/test_client_lifecycle.py::test_session_values_accept_exact_boundaries` | G1, G2 |
| SC3 | Concurrent streams use fresh headers and leave the request mapping, bound authorisation headers and every other stream's session values unchanged | SESS-04 | `tests/test_client_lifecycle.py::test_stream_session_headers_are_independent_and_request_scoped`, `tests/test_client_lifecycle.py::test_concurrent_streams_isolate_session_headers`, `tests/test_client_lifecycle.py::test_bound_endpoint_and_auth_are_reused_across_operations`, `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`, `tests/test_transport.py::test_stream_success_closes_response_and_refuses_redirects`, `tests/test_transport.py::test_stream_discards_temporary_request_headers_before_yield` | G3, G3b |
| SC4 | Session canaries are absent from public failures, text representations, traceback chains and retained generator locals after rejection, completion, early close or cancellation | SESS-05 | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state`, `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values`, `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation`, `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`, `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity`, `tests/test_client_lifecycle.py::test_closing_public_stream_immediately_closes_delegated_response` | S1, G4b |
| SC5 | Closing or cancelling a stream closes its response but never an injected caller-owned HTTP client, and `asyncio.CancelledError` propagates after cleanup | HTTP-02 | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`, `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation`, `tests/test_client_lifecycle.py::test_injected_client_is_never_closed`, `tests/test_client_lifecycle.py::test_closing_public_stream_immediately_closes_delegated_response`, `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity` | G4, G4b |

## D-08 Canary Exit-Path Matrix

Every cell names the tests that check it. The four exception-less cells use the wording agreed in Task 1 (`q1-accept-na`).

| Exit path | `str` / `repr` | Traceback chain `tb_frame.f_locals` | `__cause__` / `__context__` | `ag_frame` |
|-----------|----------------|-------------------------------------|-----------------------------|------------|
| Rejection | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state` (exact `str` and `repr`, no canary); `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch`, `tests/test_client_lifecycle.py::test_path_shaped_session_ids_fail_before_dispatch` and `tests/test_client_lifecycle.py::test_invalid_session_pair_is_atomic_and_secret_free` (rendered `traceback.format_exception`) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state` and the three PR #7 rejection tests (deep walk of package frame locals) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state`, `tests/test_client_lifecycle.py::test_invalid_session_arguments_fail_locally_without_dispatch` (both `is None`) | `tests/test_client_lifecycle.py::test_rejected_session_values_leave_no_retained_state` (`is None`) |
| Successful completion | `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[completion]` (no canary in `repr(stream)` or `repr(events)`) | N/A: no exception escapes. Proof: `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[completion]` ends normally with the SUCCESS terminal and an `aclose()` that completes without raising | N/A: no exception escapes. Same proof as the traceback cell | `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[completion]` (`is None`) |
| Early close | `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]`, `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-before-first-iteration]`, `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close` (no canary in `repr(stream)`) | N/A: no exception escapes. Proof: `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]` gets the first delta and then an `aclose()` that completes without raising | N/A: no exception escapes. Same proof as the traceback cell | `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-after-event]`, `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-before-first-iteration]`, `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close`, `tests/test_client_lifecycle.py::test_closing_public_stream_immediately_closes_delegated_response` |
| Cancellation, request stage | `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]` (`str` and `repr`); `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity` (rendered chain) | `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]` | `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]` | `tests/test_client_lifecycle.py::test_stream_request_cancellation_preserves_identity`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[request-stage-cancellation]` |
| Cancellation, mid-iteration | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` (`str` and `repr` of the recorded `CancelledError`) | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` | `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` |
| Post-dispatch public failures | `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[authentication-401]`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[status-503]`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[protocol-malformed-sse]`, `tests/test_client_lifecycle.py::test_post_dispatch_failures_carry_no_session_values[transport-connect-error]` | the same four cases | the same four cases | the same four cases |

## D-09 HTTP-02 Evidence

| D-09 assertion | Early close: `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_early_close` | Cancellation mid-iteration: `tests/test_client_lifecycle.py::test_injected_client_survives_public_stream_task_cancellation` |
|----------------|------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| Injected `httpx.AsyncClient` used through the public `stream_chat_events` | yes | yes |
| Response closed | `response_stream.closed is True` after `aclose()` | `gated.closed is True` after cancellation |
| Injected client still open | `injected_http_client.is_closed is False` after `aclose()` and again after `async with` exits | `injected_http_client.is_closed is False` inside and after `async with` |
| Later request on the same injected client succeeds | a later stream returns the expected events with no session header, then `probe_capabilities()` succeeds | a later stream returns the expected events with no session header |
| `asyncio.CancelledError` propagated after cleanup | not applicable (no cancellation) | `pytest.raises(asyncio.CancelledError)` on `await task`; the consumer recorded the library-raised error and re-raised it |
| `task.cancelled()` | not applicable | `task.cancelled() is True` |

`tests/test_client_lifecycle.py::test_injected_client_is_never_closed` alone is not counted towards D-09: it only enters and exits the wrapper, with no stream, no close or cancellation, and no later request. It is counted only for the HTTP-02 ownership-at-exit row in the D-10 table.

## User Decisions (D-02)

Task 1 put both questions to the user, who answered directly.

- **Q1: `q1-accept-na`.** The four exception-less cells of the D-08 matrix (completion and early close × traceback chain and `__cause__`/`__context__`) read "N/A: no exception escapes", backed by `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[completion]` and `[early-close-after-event]`. Phase 4 VERI-02 inherits that wording.
- **Q2: `q2-document-boundary`.** Pre-iteration retention stays released v0.3.x behaviour and is recorded under Known Boundaries (b). It is not a SESS-05 gap, and `src/` is not changed.

## Known Boundaries

- **(a) Validation runs on the first `anext()`.** `stream_chat_events` is an async generator, so session validation and the local-input raise happen on the first `anext()`, not when the method is called. This is still before network dispatch (the SESS-03 rows above). It is released behaviour and was not changed.
- **(b) Pre-iteration retention (`q2-document-boundary`).** Python binds async-generator arguments into the frame when `stream_chat_events(...)` is called. A stream that is created but never iterated or closed therefore holds `session_id` and `session_key` in `ag_frame.f_locals` until it is iterated, closed or garbage-collected. These are the caller's own in-process objects, and no trust boundary is crossed. The state is not one of SESS-05's four exit paths. Closing such a stream before iteration sends no request and clears the frame: `tests/test_client_lifecycle.py::test_completed_and_closed_streams_retain_no_session_values[early-close-before-first-iteration]` proves `requests == []` and `ag_frame is None` without inspecting the unstarted frame. Validating eagerly at call time would change the published async-generator contract that `hermes-conversation` consumes (a D-02 one-way door), so it is not done.
- **(c) In-flight boundary (research Pitfall 2).** While a consumer holds a suspended stream, the live `httpx.Response.request.headers` carries the session headers, because httpx keeps the sent request on the response. The library's own `request_headers` dict is cleared before the first yield (`tests/test_transport.py::test_stream_discards_temporary_request_headers_before_yield`), and SESS-05 scopes secrecy to after the exit paths.

## D-07 Upstream Hermes Record

Recorded from the upstream Hermes Agent source at tag `v2026.7.7.2`, peeled commit `9de9c25f620ff7f1ce0fd5457d596052d5159596` (03-RESEARCH.md "D-07 Upstream Hermes Analysis"):

- **`X-Hermes-Session-Id` becomes a filesystem name component on the server.** The API-server handler rejects CR, LF and NUL, values longer than 256 characters, and any value for which `_is_path_unsafe` (`gateway/session.py:107-118`) is true. `_is_path_unsafe` rejects `..`, `/`, `\` and a leading letter followed by `:`: the same rule set as the client's D-05 check.
- **Neither header is percent-decoded by Hermes code.** No `unquote` call appears in the API-server, session, agent-runtime or Honcho client modules; the header values are used as received apart from `.strip()`.
- **`X-Hermes-Session-Key` never reaches a filesystem path on the API-server route.** It is used as the Honcho memory session name (after sanitisation), the context-engine conversation ID, the `/model` override key, the session-context binding and an echoed response header.
- **Therefore there is no D-02 conflict, and D-05 stays as shipped.**
- **Out of scope:** upstream `_remove_session_files` (`hermes_state.py:5090`) interpolates the raw session ID into a `Path.glob` pattern. Glob metacharacters in a session ID could therefore widen an operator-initiated delete or prune to other sessions' `request_dump_*.json` files in the same directory. It is server-side, operator-initiated and not traversal, and the API `DELETE` handler does not reach it. The user may report it upstream.

## Edge-Probe and Prohibition Dispositions

- **16 edge-probe items.**
  - 13 are resolved as truths across Plans 03-01 to 03-04. Two of them are backstop truths, confirmed from code rather than a dedicated test: the SESS-03 concurrency edge (validation and the local-input raise happen inside the first `anext()` with no intervening `await`, `client.py:669-681`, Plan 03-02) and the SESS-04 adjacency edge (two streams with identical values each build their own header dict through the per-request `dict(headers)` copy at `client.py:193`; no test passes duplicate values across concurrent streams, Plan 03-04).
  - 3 are unclassified by the edge probe and stay unresolved and flagged for a reviewer: SESS-01 (Plan 03-02), SESS-05 (Plan 03-03) and HTTP-02 (Plan 03-01). Their criteria have test evidence in the D-10 table; only the edge category is missing.
- **3 prohibitions.**
  - No source change: `git log --oneline main..HEAD -- src/` is empty, and every D-11 mutation was restored with `git diff --exit-code -- src/` clean.
  - No identity derivation: the client transports opaque values only. `tests/test_client_lifecycle.py::test_session_values_appear_only_in_their_exact_headers[id-only]` and `[key-only]` show that one value never produces or fills the other header.
  - Provenance honesty: verified by judgement. The Provenance section credits PR #7 for the behaviour, and every claim here cites a collected node ID or a recorded command result.
- **Canon referrals.** Header injection, path traversal and secret exposure are covered by `/gsd-secure-phase`.

## Behavioural Spot-Checks

Run on 2026-10-20 on the phase branch after the D-11 record was committed, with `src/` clean.

| Behaviour | Command | Result | Status |
|-----------|---------|--------|--------|
| Two-module quick run | `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q` | `198 passed` | PASS |
| Full suite with the coverage gate | `uv run pytest` | `674 passed`; `Required test coverage of 100.0% reached. Total coverage: 100.00%` | PASS |
| Lint | `uv run ruff check .` | `All checks passed!` | PASS |
| Formatting | `uv run ruff format --check .` | `15 files already formatted` | PASS |
| Static typing | `uv run --no-sync basedpyright` | `0 errors, 0 warnings, 0 notes` | PASS |
| Public type completeness | `uv run --no-sync basedpyright --verifytypes hermes_agent_api_client --ignoreexternal` | `Type completeness score: 100%` | PASS |
| Full gate | `uv run --no-sync prek run --all-files` | every hook passed (uv lock, Ruff format, Ruff check, basedpyright, basedpyright verifytypes, tests with coverage, build distributions, verify distributions); exit 0 | PASS |
| Source unchanged | `git diff --exit-code -- src/` and `git log --oneline main..HEAD -- src/` | exit 0; no output | PASS |
| Node IDs resolve | `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --collect-only -q --no-cov` | `198 tests collected`; every node ID cited in this file is present | PASS |

## Requirements Coverage

| Requirement | Plans | Status | Evidence |
|-------------|-------|--------|----------|
| SESS-01 | PR #7, 03-02, 03-04 | Evidenced | Independence, omission, exact-only mapping and the signature lock (D-10 rows SESS-01; G3 red) |
| SESS-02 | PR #7, 03-02, 03-04 | Evidenced | Exact `str`, 1-256 bounds for both arguments, visible ASCII including CR and tab, D-05 path shape with adjacency positives, D-06, atomic pair (G1, G2 red) |
| SESS-03 | PR #7, 03-02, 03-04 | Evidenced | No dispatch, non-retryable classification, exact value-free text and metadata (G1, G2, S1 red) |
| SESS-04 | PR #7, 03-01, 03-02, 03-04 | Evidenced | Fresh headers, bound and caller mappings unchanged, concurrent isolation, no later-stream leak, inner copy (G3, G3b red) |
| SESS-05 | PR #7, 03-01, 03-02, 03-03, 03-04 | Evidenced | Full D-08 matrix plus post-dispatch failures; four cells N/A under `q1-accept-na` (S1, G4b red) |
| HTTP-02 | 03-01, 03-03, 03-04 | Evidenced | D-09 early close and mid-iteration cancellation with later reuse, ownership at exit, request-stage identity (G4, G4b red) |

## Post-Review Strengthening (Code Review CR-01, WR-01, WR-02)

The phase code review (`03-REVIEW.md`) found that the `ag_frame is None` assertions in `test_completed_and_closed_streams_retain_no_session_values` run after close or exhaustion. CPython clears the frame at that point regardless of the library, so those assertions could not detect retention. Two review mutants passed the whole suite: (A) session values kept in the suspended public generator frame, and (B) `operation_headers` kept until the generator ends. Neither falls under Known Boundaries or AR-03-01/AR-03-02.

Fixes (tests only; `src/` unchanged):

- `19f7631` (CR-01): `_assert_suspended_stream_retains_no_secrets` reads `ag_frame.f_locals` while the stream is suspended and rejects the session ID, session key and bearer canaries. It runs at every yield of `[completion]`, before `aclose()` in `[early-close-after-event]` and the early-close survival test, and at the cancellation gate. Re-verified by the orchestrator: mutant A gives 4 failed and 125 passed, mutant B gives 4 failed and 125 passed, and the shipped code passes 129. `[early-close-before-first-iteration]` stays green under both mutants, as expected (AR-03-01).
- `9a6d07b` (WR-01): the cancellation test's gate wait is bounded with `asyncio.timeout(5)` and races the consumer, so a regression fails instead of hanging.
- `5c64a5c` (WR-02): removed three `repr()` canary assertions that could never fail. A generator's `repr` exposes no locals, so those checks were not evidence.

D-08 matrix note: for the completion and early-close rows, the `ag_frame` cell's retention evidence is the suspended-frame check above. The post-exit `ag_frame is None` assertion is a lifecycle check only.

Info findings IN-01 to IN-04 remain open in `03-REVIEW-DISPOSITION.md`. They are non-blocking test-hygiene items.

## Gaps

None

## Gaps Summary

No gap is open. Every D-10 row and D-08 cell has test evidence, or the N/A wording that the user accepted under `q1-accept-na`. Every D-11 mutation (G1, G2, G3, G3b, G4, G4b and S1) turned at least one named test red, with every expected inclusion present, and was restored with `src/` clean. Pre-iteration retention is a documented boundary under `q2-document-boundary`, not a gap.

Two items stay open for a reviewer without being phase gaps: the three unclassified edge-probe rows (SESS-01, SESS-05 and HTTP-02) and the SESS-04 adjacency backstop truth, which the verifier must confirm from the `dict(headers)` copy at `client.py:193` or record as `human_needed`.
