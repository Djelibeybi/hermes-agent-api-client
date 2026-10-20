# Phase 3: Session Header Safety - Research

**Researched:** 2026-10-20
**Domain:** Audit of shipped per-request session headers, secret scrubbing and transport ownership in an async `httpx` client library
**Confidence:** HIGH (all findings come from code read this session, the existing test suite, empirical probes run on Python 3.13.15 and 3.14.7, and the upstream Hermes source at the pinned tag)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Phase Approach

- **D-01:** Audit and close gaps. Plans must check each SESS-01 to SESS-05 and HTTP-02 criterion against the shipped code and tests. Add tests or fixes only where the audit proves something missing. Do not rewrite the PR #7 implementation.
- **D-02:** If shipped v0.3.x behaviour conflicts with `.planning/REQUIREMENTS.md` or the design spec, stop and raise it to the user before planning a change. Neither source wins automatically. — **Reversibility:** one-way — any change is to released v0.3.x public behaviour that `hermes-conversation` consumes.
- **D-03:** Change code only to fix a proven gap. No refactoring, renaming or deduplication (for example, with `_require_lifecycle_text`), even where the existing code is correct but awkward.
- **D-04:** Ship fixes through the normal flow: phase branch, PR and merge. PSR releases from the commit types as usual. Don't hold the release for Phase 4.

### Path-Shaped ID Rules

- **D-05:** Keep the shipped `session_id` path-shape rejection exactly as it is: reject values containing `..`, `/` or `\`, and values that start with a letter followed by `:` (a Windows drive prefix). Don't add `%`, percent-encoding detection or a narrower character allowlist. Encoded traversal is the Hermes server's responsibility, and the client check is defence in depth.
- **D-06:** `session_key` gets no path-shape checks, only the exact-`str`, 1-256 character, visible-ASCII (`0x21..0x7e`) rules, as SESS-02 states and as shipped.
- **D-07:** Research must read the tagged upstream Hermes source and record how the server uses `X-Hermes-Session-Id` and `X-Hermes-Session-Key`: whether either value becomes a file or path component, and whether the server decodes either value. If the server's handling makes D-05 insufficient, raise it as a conflict under D-02. Don't change the rules silently.

### Evidence Standard

- **D-08:** SESS-05 needs a complete exit-path matrix of explicit session-value canary tests for rejection, successful completion, early close and cancellation. Each cell checks `str`/`repr`, the traceback chain (`tb_frame.f_locals`), `__cause__`/`__context__`, and the async generator's retained frame (`ag_frame`). Reuse the existing canary helpers in `tests/test_client_lifecycle.py`, and add only the cells the audit finds missing.
- **D-09:** HTTP-02 needs stream-specific tests with an injected `httpx.AsyncClient`, covering both early close and cancellation mid-iteration. Each test asserts that the response closed, the injected client is still open and usable for a later request, and `asyncio.CancelledError` propagated after cleanup in the cancellation case. The generic `test_injected_client_is_never_closed` alone doesn't count.
- **D-10:** VERIFICATION.md must include a traceability table mapping each SESS-01 to SESS-05 and HTTP-02 criterion, and each roadmap success criterion, to the exact test names that prove it. Gaps in the table drive the gap-fill plans. Phase 4 reuses the table for VERI-02.
- **D-11:** Verification must include a manual mutation check of the key guards. Temporarily break each one, confirm at least one named test fails, restore it, and record the result in VERIFICATION.md. The guards are value validation, path-shape rejection, the fresh copy of the request headers (no mutation of bound or caller headers), and not closing the injected client. Add no new mutation-testing tooling.

### Claude's Discretion

- Test naming, parameterisation and placement within the existing test modules.
- How to phrase the audit and traceability findings, provided D-10's mapping is complete.

### Deferred Ideas (OUT OF SCOPE)

- Milestone or version re-scoping: the package is already at v0.3.3 while milestone v0.3.0 still has Phases 3 and 4 open. This is a roadmap and milestone housekeeping question, not Phase 3 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SESS-01 | A Python consumer can independently provide `session_id`, `session_key`, both, or neither to `stream_chat_events`, with non-`None` values mapped only to `X-Hermes-Session-Id` and `X-Hermes-Session-Key`. | Audit table row SESS-01: mostly covered; two proven test gaps (value confined to its own header only; no arbitrary-header API). See "Gap G-01" and "Gap G-02". |
| SESS-02 | A Python consumer receives local rejection unless each supplied session value is an exact built-in `str` containing 1-256 characters in the visible ASCII range `0x21..0x7e`, and `session_id` additionally rejects path-shaped values. | Audit row SESS-02: covered except CR (`\r`), which the approved spec names explicitly, and positive `session_key` boundaries. See "Gap G-03". Upstream server analysis (D-07) found no conflict with D-05. |
| SESS-03 | An invalid session value fails before network dispatch as the existing safe, non-retryable local-input classification, without including the rejected value in text or metadata. | Audit row SESS-03: covered for dispatch and classification; exact `str`/`repr` text never asserted for the local-input error. See "Gap G-04". |
| SESS-04 | Each stream constructs fresh request headers without mutating the caller's request mapping, the client's bound authorisation headers, or another concurrent request's session values. | Audit row SESS-04: covered. Mutation G3 proves the tests detect a broken copy. |
| SESS-05 | Session values are absent from public failures, `str`, `repr`, tracebacks, causes, contexts, and retained generator locals after rejection, completion, early close, or cancellation. | D-08 matrix (5 rows × 4 columns, with cancellation split into request-stage and mid-iteration): 6 cells covered, 2 partial, 8 missing, 4 N/A. Mid-iteration cancellation and completion are the big holes. Post-dispatch public failures carry no session canary tests at all. See "Gap G-05" to "Gap G-07". |
| HTTP-02 | Closing or cancelling a stream closes only its response, never an injected caller-owned HTTP client, and `asyncio.CancelledError` propagates after cleanup. | D-09 audit: partially covered. No test proves the injected client is usable for a later request, and no test cancels a real task mid-iteration. See "Gap G-08". |
</phase_requirements>

## Summary

This is an audit phase, not a greenfield build. The session-header behaviour was implemented outside GSD in **PR #7** (`8843cfc fix: complete conversation contract (#7)`, released in **v0.3.1**). That commit added `session_id`/`session_key` to `HermesAgentApiClient.stream_chat_events` (`src/hermes_agent_api_client/client.py:653`), plus `_is_valid_session_value` (`client.py:153`) and `_chat_request_headers` (`client.py:176`). It also added the six session tests named in CONTEXT.md and `test_stream_discards_temporary_request_headers_before_yield` in `tests/test_transport.py` [VERIFIED: `git show 8843cfc -- tests`]. Neither `client.py` nor the two test modules has changed since then (`git log 8843cfc..HEAD` on those paths is empty). Phase 3 must not claim to have implemented this behaviour. It verifies the behaviour and closes test-evidence gaps.

The audit found **no behavioural defect**. Empirical probes on CPython 3.13.15 (project `.venv`) and 3.14.7 (the CI matrix covers `3.13` and `3.14`) show these results [VERIFIED: probe runs this session]:

- Session canaries are absent from `str`, `repr`, `traceback.format_exception`, package traceback `f_locals`, `__cause__` and `__context__`.
- `ag_frame` is `None` after rejection, completion, early close, real `task.cancel()` mid-iteration, and post-dispatch 401, protocol and connect failures.
- The injected client stays open and serves a later request after cancellation, and `task.cancelled()` is `True`.

Every gap is therefore a **missing test**, not missing behaviour. Gap-fill plans are test-only (`test:` commits). Under the configured PSR tags (`patch_tags = ["fix", "perf"]`, `minor_tags = ["feat"]`), a test-only change does not cut a release.

The upstream Hermes server at `v2026.7.7.2` (peeled commit `9de9c25f620ff7f1ce0fd5457d596052d5159596`, confirmed by `git ls-remote` this session) **does** use `X-Hermes-Session-Id` as a filesystem name component. It does **not** percent-decode either header. Its own entry guard `_is_path_unsafe` applies exactly the rule set the client ships under D-05, so the client check mirrors the server rather than falling short of it. `X-Hermes-Session-Key` never reaches a filesystem path on the API-server route. **No D-02 conflict on traversal.** One adjacent server-side observation (glob metacharacters in a raw `Path.glob` pattern) is recorded for the user's awareness under D-02. It is not a traversal vector, and D-05 stays unchanged.

**Primary recommendation:** Plan two test-only gap-fill plans: (1) the SESS-01/02/03/05 canary and contract cells, and (2) the HTTP-02 injected-client early-close and real-cancellation tests. Then plan a verification task that runs the D-11 mutation check, using the guard locations and expected failing tests listed below, and writes the D-10 traceability table. Add new tests next to the PR #7 tests rather than editing them, so provenance stays clear.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Session argument surface (keyword-only `session_id`, `session_key`, no arbitrary headers) | Public client API (`HermesAgentApiClient.stream_chat_events`) | — | The public signature is the only consumer entry point. Identity derivation stays in Home Assistant (PROJECT.md boundary). |
| Value validation (exact `str`, 1-256, `0x21..0x7e`) | Shared validator (`models._require_lifecycle_text`) | `client._is_valid_session_value` | Phase 2 created one input-value-free validator. Session validation delegates to it (D-03 forbids deduplication or refactoring). |
| Path-shape rejection (`session_id` only) | `client._is_valid_session_value(reject_path_shape=True)` | Hermes server `_is_path_unsafe` (authoritative) | The client is defence in depth (D-05). The server owns filesystem path safety. |
| Fresh per-request header construction | `client._chat_request_headers` | `client._stream_chat_events` (second copy plus `Content-Type`) | Two copies mean neither the bound auth dict nor the caller mapping is mutated. |
| Secret scrubbing of locals, tracebacks and chains | `stream_chat_events` / `_stream_chat_events` / `_reraise_scrubbed_failure` | `_raise_transport_failure` (safe frame) | Scrubbing has to happen in the frames that held the values. |
| Response lifetime | `_stream_chat_events` (`async with http_client.stream(...)`) | Public wrapper `finally: await delegated_stream.aclose()` | The library owns only the response. It never owns an injected client. |
| HTTP client ownership | `HermesAgentApiClient.__aenter__` / `__aexit__` | — | `owns_active` is `True` only when no client was injected. |
| Session persistence and file naming | Hermes server (upstream) | — | Out of the client's control, so the client transports opaque values only. |

## Project Constraints (from CLAUDE.md)

`./CLAUDE.md` and `./.claude/CLAUDE.md` do not exist in this repository (`config.json` points `claude_md_path` at `./.claude/CLAUDE.md`, which is absent). No `.claude/skills/` or `.agents/skills/` directory exists. The user's global instructions apply:

- Use Australian English spelling in prose.
- Use `uv` exclusively (`uv run pytest`, `uv run ruff`, `uv add`). Never use pip, poetry or conda.
- Put all imports at the top of the file. This matters for new test code: no function-local imports.
- Use the latest version when adding dependencies. This phase adds none.
- Don't ignore failing tests or uncommitted files.
- Commit with `git commit -s` and the GPG key 27B3A9EA9D847501F05627B166D6066620F03B05 (automatic). The orchestrator commits this file, so the researcher does not.

Repository-enforced quality gate [VERIFIED: `pyproject.toml`, `prek.toml` read this session]:

- `[tool.coverage.report] fail_under = 100` with `branch = true` and `source = ["hermes_agent_api_client"]`. Test-helper code is not measured, but any source change must stay at 100% branch coverage.
- `[tool.basedpyright] typeCheckingMode = "strict"` over `src` and `tests`.
- `[tool.ruff.lint] select = ["ALL"]`, ignoring only `COM812`, `D203`, `D213` and `ISC001`. Tests additionally ignore `S101` and `SLF001`. New tests therefore need docstrings (pydocstyle), no magic-number comparisons without named constants (`PLR2004`), stored `create_task` references (`RUF006`), and single-statement `pytest.raises` blocks (`PT012`).
- `prek.toml` hooks: `uv lock --check`, `ruff format --check`, `ruff check`, `basedpyright`, `basedpyright --verifytypes hermes_agent_api_client --ignoreexternal`, and `uv run pytest` (with coverage).
- `[tool.pytest.ini_options] asyncio_mode = "auto"`. The existing convention still decorates every async test with `@pytest.mark.asyncio`, so follow it.

## Standard Stack

No new packages. The phase uses only what is already locked [VERIFIED: `uv run --no-sync python -c ...` this session]:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 | Injected `AsyncClient`, `MockTransport`, `AsyncByteStream` test doubles | Already the transport. Every existing lifecycle and transport test uses `httpx.MockTransport` and custom `AsyncByteStream` subclasses. |
| pytest | 9.1.1 | Test runner | Locked dev dependency |
| pytest-asyncio | 1.4.0 | Async tests (`asyncio_mode = "auto"`) | Locked dev dependency |
| pytest-cov | 7.1.0 | 100% branch coverage gate | Locked dev dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `traceback` / `inspect` (stdlib) | CPython 3.13 / 3.14 | `traceback.format_exception` for rendered-chain checks; `inspect.signature` for the no-arbitrary-header check | New SESS-01 and SESS-05 cells |

**Correction to CONTEXT.md:** CONTEXT.md says `respx` mocks are "already used by the lifecycle and transport tests". `respx==0.23.1` is a locked dev dependency, but no test module imports it. `grep -n respx tests/*.py` returns nothing. Every stream test uses `httpx.MockTransport(handler)` with custom `httpx.AsyncByteStream` or `httpx.AsyncBaseTransport` subclasses. New tests should follow that pattern and should not introduce `respx`.

**Installation:** none.

## Package Legitimacy Audit

This phase installs no external packages. The gate is not applicable.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Shipped Implementation (verbatim, for audit reference)

Constants [VERIFIED: `src/hermes_agent_api_client/client.py:50-52`]:

```python
_VISIBLE_ASCII_MIN = 0x21
_VISIBLE_ASCII_MAX = 0x7E
_WINDOWS_DRIVE_PREFIX_LENGTH = 2
```

Shared validator [VERIFIED: `src/hermes_agent_api_client/models.py:47-58`]:

```python
_LIFECYCLE_TEXT_MAX = 256


def _require_lifecycle_text(value: object) -> str:
    """Require exact bounded visible ASCII without retaining rejected values."""
    if type(value) is not str:
        raise ValueError
    if not 1 <= len(value) <= _LIFECYCLE_TEXT_MAX:
        raise ValueError
    if any(not "!" <= char <= "~" for char in value):
        raise ValueError
    return value
```

Session guard and header construction [VERIFIED: `client.py:153-198`]. These are the key lines:

```python
def _is_valid_session_value(value: object, *, reject_path_shape: bool) -> bool:
    ...
        validated = _require_lifecycle_text(value)          # line 158  (guard G1)
    ...
    return not (
        reject_path_shape
        and (
            ".." in validated
            or "/" in validated
            or "\\" in validated
            or (
                len(validated) >= _WINDOWS_DRIVE_PREFIX_LENGTH
                and validated[0].isalpha()
                and validated[1] == ":"
            )
        )
    )

def _chat_request_headers(headers, *, session_id, session_key):
    invalid = not _is_valid_session_value(
        session_id,
        reject_path_shape=True,                              # line 185  (guard G2)
    ) or not _is_valid_session_value(
        session_key,
        reject_path_shape=False,
    )
    if invalid:
        return None

    request_headers = dict(headers)                          # line 193  (guard G3)
    if session_id is not None:
        request_headers["X-Hermes-Session-Id"] = session_id
    if session_key is not None:
        request_headers["X-Hermes-Session-Key"] = session_key
    return request_headers
```

Public wrapper scrubbing [VERIFIED: `client.py:669-681`]:

```python
        operation_headers = _chat_request_headers(
            headers,
            session_id=session_id,
            session_key=session_key,
        )
        session_id = None
        session_key = None
        headers = {}
        if operation_headers is None:
            active = None
            base_url = None
            request = {}
            _raise_transport_failure(transient=False)
```

Second header copy inside the delegated stream [VERIFIED: `client.py:434-437`, clearing at `client.py:459`]:

```python
    endpoint = _operation_url(base_url, "/v1/chat/completions")
    request_headers = dict(headers)
    request_headers["Content-Type"] = "application/json"
    headers = {}
```

Ownership at exit [VERIFIED: `client.py:601`]:

```python
        owns_active = active is not None and self._injected_http_client is None
```

Local-input error text format [VERIFIED: `src/hermes_agent_api_client/protocol.py:67-85` and `models.py:21` `TRANSPORT = "transport"`]:

```python
    def _safe_message(self) -> str:
        """Build a deterministic message without private upstream details."""
        status = "none" if self.status_code is None else str(self.status_code)
        retryable = str(self.retryable).lower()
        return (
            f"Hermes {self.category.value} failure "
            f"(status={status}, retryable={retryable})"
        )
    ...
    def __repr__(self) -> str:
        """Return safe structured metadata for debugging."""
        return (
            f"{type(self).__name__}(category={self.category.value!r}, "
            f"status_code={self.status_code!r}, retryable={self.retryable!r})"
        )
```

For `HermesTransportError(transient=False)`, this formats as `str` == `Hermes transport failure (status=none, retryable=false)` and `repr` == `HermesTransportError(category='transport', status_code=None, retryable=False)`. The existing test `_assert_fresh_cleanup_transport_failure` asserts the `retryable=true` forms verbatim at `tests/test_client_lifecycle.py:298-301`.

**Behavioural detail:** `stream_chat_events` is an async generator, so validation runs on the **first `anext()`**, not at call time. That still satisfies "fails before network dispatch", and every existing rejection test uses `await anext(stream)`. Changing this to raise at call time would change released public behaviour (D-02 one-way door). Do not plan it.

## Requirement Audit (D-01 / D-10 input)

Verdicts come from reading each test body this session. "Covered" means at least one named test asserts the criterion directly and a mutation proves the test can fail.

| Req | Criterion | Shipped code | Existing test(s) proving it | Verdict |
|-----|-----------|--------------|-----------------------------|---------|
| SESS-01 | Independent `session_id` / `session_key`, either, both or neither | `client.py:653-659` (signature), `client.py:194-197` | `test_stream_session_headers_are_independent_and_request_scoped[neither, session-id, session-key, both]` (`tests/test_client_lifecycle.py:381-464`) | **Covered** |
| SESS-01 | `None` omits that header | `client.py:194-197` | same test, `assert name not in sent.headers` branch | **Covered** |
| SESS-01 | Non-`None` values mapped **only** to their exact headers | `client.py:194-197` | same test checks the two header names only. Nothing asserts the canary is absent from the body, URL or any other header | **Partial → G-01** |
| SESS-01 / SC1 | No arbitrary-header API | `client.py:653-659`: keyword-only `session_id`, `session_key`, no `headers` or `**kwargs` | none (no `inspect.signature` test exists; `grep signature tests/test_package.py` is empty) | **Gap → G-02** |
| SESS-02 | Exact built-in `str` (subclass and non-string rejected) | `models.py:52` | `test_invalid_session_arguments_fail_locally_without_dispatch[*-subclass, *-non-string]` (`:473-550`) | **Covered** |
| SESS-02 | 1-256 characters | `models.py:54` | `[*-empty]`, `[*-too-long]` (257) for both args; positive `minimum-session-id` (`"!"`) and `maximum-session-id` (`"~" * 256`) for `session_id` only | **Covered** for `session_id`; positive boundaries for `session_key` untested → **G-03** |
| SESS-02 | Visible ASCII `0x21..0x7e` | `models.py:56` | `[*-space, *-leading-space, *-trailing-space, *-embedded-space, *-newline, *-nul, *-delete, *-non-ascii]` | **Partial**: the spec names "CR/LF/NUL" explicitly, but CR (`\r`) and TAB are never exercised → **G-03** |
| SESS-02 | `session_id` rejects path shapes (`..`, `/`, `\`, drive prefix) | `client.py:161-173` | `test_path_shaped_session_ids_fail_before_dispatch[parent, slash, backslash, drive-prefix]` (`:553-598`). Each parameter isolates one operand, and mutation G2 fails all four | **Covered** |
| SESS-02 | `session_key` has no path checks (D-06) | `client.py:186-188` | `test_stream_session_headers_are_independent_and_request_scoped[path-shaped-session-key]` (`"../opaque\\key"` accepted) | **Covered** |
| SESS-02 / SC2 | Invalid pair fails atomically | `client.py:183-191` | `test_invalid_session_pair_is_atomic_and_secret_free[invalid-key, invalid-id]` (`:601-643`), `requests == []` | **Covered** |
| SESS-03 | Fails before network dispatch | `client.py:677-681` | all three rejection tests assert `requests == []` | **Covered** |
| SESS-03 | Safe non-retryable local-input classification | `client.py:681`, `_raise_transport_failure(transient=False)` | `caught.value.retryable is False` in all three rejection tests | **Covered** |
| SESS-03 | Rejected value absent from text and metadata | `protocol.py:67-85` (metadata-only) | canary checked through `traceback.format_exception` in `_assert_no_sensitive_traceback_references`. No test asserts exact `str(error)`, `repr(error)` or `error.args` for the local-input error | **Partial → G-04** |
| SESS-04 | Fresh headers; bound auth headers unchanged | `client.py:193`, `client.py:435` | `test_stream_session_headers_are_independent_and_request_scoped` (`client._headers == bound_headers`), `test_concurrent_streams_isolate_session_headers` (`:646-705`) | **Covered** (mutation G3 → 7 failures) |
| SESS-04 | Caller's request mapping unchanged | `client.py:201-221` (`dict(request)` only) | `test_stream_session_headers_are_independent_and_request_scoped` (`request_document == original_document`); `test_bound_endpoint_and_auth_are_reused_across_operations` (`MappingProxyType`) | **Covered** |
| SESS-04 / SC3 | No cross-contamination between concurrent streams | `client.py:193` | `test_concurrent_streams_isolate_session_headers`: 8 `gather`ed streams, set of exact pairs equals the expected 8 pairs | **Covered** |
| SESS-05 / SC4 | Exit-path canary matrix | `client.py:674-676`, `:692`, `:708-714`, `:459`, `:493-520` | see D-08 matrix below | **Partial → G-05, G-06, G-07** |
| HTTP-02 / SC5 | Close or cancel closes only the response; injected client untouched; `CancelledError` propagates after cleanup | `client.py:450-520`, `:700-707`, `:601` | see D-09 audit below | **Partial → G-08** |

### Roadmap success criteria mapping

| SC | Text (abridged) | Requirements | Verdict |
|----|-----------------|--------------|---------|
| SC1 | Independent omit or provide; only exact Hermes headers; no arbitrary-header API | SESS-01 | Partial (G-01, G-02) |
| SC2 | Exact `str`, 1-256 visible ASCII, path-shaped IDs rejected, atomic, safe non-retryable | SESS-02, SESS-03 | Partial (G-03, G-04) |
| SC3 | Fresh headers; request mapping, bound auth and other streams unchanged | SESS-04 | Covered |
| SC4 | Canaries absent from failures, text, traceback chains, retained generator locals across four exit paths | SESS-05 | Partial (G-05 to G-07) |
| SC5 | Close or cancel closes the response, never the injected client; `CancelledError` propagates after cleanup | HTTP-02 | Partial (G-08) |

## D-08 Canary Exit-Path Matrix

Columns follow D-08. Existing helpers are in `tests/test_client_lifecycle.py` (line ranges below).

| Exit path | `str` / `repr` | Traceback chain `tb_frame.f_locals` | `__cause__` / `__context__` | `ag_frame` |
|-----------|----------------|-------------------------------------|-----------------------------|------------|
| **Rejection** (invalid value / pair / path shape) | **Partial.** `str` is covered through `traceback.format_exception` in `test_invalid_session_arguments_fail_locally_without_dispatch`, `test_path_shaped_session_ids_fail_before_dispatch` and `test_invalid_session_pair_is_atomic_and_secret_free`. `repr(error)` is never asserted. Short values (fewer than 4 non-space characters, for example `".."`, `""`, `" "`) are excluded from canaries by `_MIN_UNIQUE_CANARY_LENGTH` and checked by identity only. | **Covered** by the same three tests (deep walk plus forbidden-object identity) | **Covered** explicitly (`is None`) in `test_invalid_session_arguments_fail_locally_without_dispatch`. Implicit only (rendered chain) in the pair and path-shape tests | **GAP.** No rejection test inspects `ag_frame` |
| **Successful completion** (valid id and key, iterate to terminal) | **GAP.** `test_stream_session_headers_are_independent_and_request_scoped` and `test_concurrent_streams_isolate_session_headers` complete with session values but never check secrecy | N/A (no exception object exists on this path) | N/A (no exception) | **GAP.** No completion test with session values inspects `ag_frame` |
| **Early close** (valid values, `aclose()` after first event) | **GAP** for `repr(stream)`; `aclose()` returns `None` | N/A (no exception) | N/A (no exception) | **Covered**: `test_closing_public_stream_immediately_closes_delegated_response` (`:2327-2366`) with `early-close-session-canary` / `early-close-key-canary` asserts `ag_frame is None` |
| **Cancellation, request stage** (transport raises `CancelledError` while sending) | **Partial**: `str` through `format_exception`; `repr` not asserted | **Covered**: `test_stream_request_cancellation_preserves_identity` (`:2267-2302`) with `cancel-session-canary` / `cancel-key-canary` | **Covered**: same test | **Covered**: same test |
| **Cancellation, mid-iteration** (real `task.cancel()` after first event) | **GAP** | **GAP** | **GAP** | **GAP** |

Two extra findings sit outside D-08's four rows but inside SESS-05's wording:

- **Post-dispatch public failures** (HTTP status, protocol, transport/connect error) with session values: **GAP**. SESS-05 says "absent from public failures". No existing post-dispatch failure test passes `session_id` or `session_key`. A probe this session confirmed the behaviour is clean: a `httpx.ConnectError` whose message deliberately embeds the `X-Hermes-Session-Id` value does not leak. → **G-07**
- **Early close before first iteration**: `aclose()` on an unstarted stream returns, never dispatches, and leaves `ag_frame is None` (probe). Untested. Recommend adding it as a parameter of the early-close cell (cheap; locks behaviour). → part of **G-06**

**N/A cells:** completion and early close raise no exception, so the traceback and cause/context cells have no object to inspect. Recommend recording them in VERIFICATION.md as "N/A: no exception escapes", backed by the test asserting that `aclose()` returns `None` and iteration ends normally. This interpretation needs user confirmation (see Open Questions, Q1).

### Existing helpers to reuse (do not duplicate)

From `tests/test_client_lifecycle.py` [VERIFIED: read this session]:

| Helper | Lines | Signature / purpose |
|--------|-------|---------------------|
| `_HasAsyncGeneratorFrame` | 212-218 | `Protocol` with `ag_frame -> FrameType \| None`; use as `cast("_HasAsyncGeneratorFrame", stream).ag_frame` |
| `_package_traceback_locals` | 221-233 | `(error: BaseException) -> tuple[dict[str, object], ...]`; package frames only; **asserts at least one package frame** |
| `_assert_safe_lifecycle_error` | 236-250 | constant-message plus shallow `repr(frame_locals)` canary check |
| `_assert_no_sensitive_traceback_references` | 253-283 | `(error, *, canaries: tuple[str, ...], forbidden_objects: tuple[object, ...])`; renders `traceback.format_exception(error)` (covers `str` and any chained exceptions' text) and deep-walks package frame locals, rejecting `httpx.AsyncClient`, `httpx.Response` and `HermesAgentApiClient` instances |
| `_assert_fresh_cleanup_transport_failure` | 286-309 | exact `str` / `repr` pattern for `retryable=True` (template for G-04's `retryable=False` assertions) |
| `TrackingAsyncByteStream` | 123-150 | `(chunks, *, close_failure=None, iteration_failure=None)`; `.closed` flag |
| `_successful_transport` | 345-367 | `MockTransport` handler that appends requests and serves a delta plus `[DONE]` (or capabilities) |
| `CancellingRequestTransport` | 97-107 | raises a given `CancelledError` from `handle_async_request` |
| `_BASE_URL_CANARY`, `_BEARER_KEY_CANARY`, `_MIN_UNIQUE_CANARY_LENGTH` | 55-59 | `"https://hermes.example/private-base"`, `"lifecycle-bearer-key-canary"`, `4` |

From `tests/test_transport.py`: `_HasAsyncGeneratorFrame` (62-68), `_library_traceback_locals` (71-83), `_assert_traceback_locals_are_safe` (86-114), and a different `TrackingAsyncByteStream(chunks=(), *, delay=0, failure=None)` (137-166). These test the internal `_stream_chat_events` directly. Put new public-API session tests in `tests/test_client_lifecycle.py`, where the PR #7 session tests and the D-08 helpers live.

**New helper needed (one):** a gated byte stream that yields one SSE chunk, sets an `asyncio.Event`, then awaits forever. This makes mid-iteration cancellation deterministic without sleeps. Nothing like it exists in `tests/test_client_lifecycle.py`. `tests/test_sse.py:2078-2098` uses a similar `wait_forever = asyncio.Event()` pattern for the decoder only.

## D-09 HTTP-02 Audit

| Required assertion (D-09) | Early close: closest existing test | Cancellation: closest existing tests |
|---------------------------|-------------------------------------|--------------------------------------|
| Injected `httpx.AsyncClient` through the public stream | `test_closing_public_stream_immediately_closes_delegated_response` ✓ | `test_stream_read_cancellation_precedes_response_close_failure`, `test_stream_read_cancellation_precedes_response_close_cancellation`, `test_stream_read_cancellation_precedes_httpx_close_failure`, `test_stream_response_close_cancellation_preserves_identity` ✓ |
| Mid-iteration (after at least one event) | ✓ (`anext` returns the delta first) | ✗ The `CancelledError` is raised by the byte stream (`iteration_failure`) on the **first** read, before any event, and it is not a real `task.cancel()` |
| Response closed | ✓ `response_stream.closed is True` | ✓ `response_stream.closed is True` |
| Injected client still open | ✓ `is_closed is False` | ✓ in the first two (not asserted in `..._httpx_close_failure`) |
| Injected client **usable for a later request** | ✗ | ✗ |
| `CancelledError` propagated **after cleanup** | n/a | partial: identity is asserted and the stream is closed at catch time, but this is not task-level cancellation and `task.cancelled()` is never checked |

`test_injected_client_is_never_closed` (`:913-927`) only enters and exits the wrapper. `tests/test_transport.py::test_stream_early_close_closes_response_and_preserves_client` and `::test_stream_cancellation_is_unchanged_after_response_cleanup` exercise the internal `_stream_chat_events`, not the public wrapper, with no session values and no later request.

**Verdict: Partial → G-08.** Two new tests are required:

1. **Early close:** injected client, valid session canaries, `anext` one delta, `aclose()`. Assert the response stream closed, `injected_http_client.is_closed is False`, `ag_frame is None`, then **run a second stream (or `probe_capabilities()`) through the same wrapper and assert it succeeds**. Finally assert the client is still open after `async with` exits.
2. **Cancellation:** injected client, valid session canaries, consumer **task** iterating the public stream; gated byte stream; `await gate.wait()`; `task.cancel()`. Inside the consumer, catch `CancelledError`, record it, re-raise. Outside, assert `pytest.raises(asyncio.CancelledError)` on `await task` and `task.cancelled() is True`. Also assert that the recorded error has `__cause__ is None` and `__context__ is None`, that `_assert_no_sensitive_traceback_references` passes with both session canaries, that the response stream closed, that `ag_frame is None`, that the injected client is open, and that a later stream on the same client succeeds.

Probe evidence that both pass against shipped code on 3.13.15 and 3.14.7: response stream closed `True`, client closed `False`, cause/context `None`, no traceback canary, `ag_frame None`, `task.cancelled() True`, later request status `200`.

These two tests also fill the D-08 "cancellation, mid-iteration" row and the HTTP-02 row at once. Plan them as one test pair with D-08 and D-09 assertions combined, so the planner does not create duplicate tests.

## Gap List (drives gap-fill plans)

All gaps are test-only. No source change is indicated.

| Gap | Requirement / cell | Test to add (suggested name; placement `tests/test_client_lifecycle.py` next to the PR #7 session tests) |
|-----|--------------------|-----------------------------------------------------------------------------------------------------------|
| G-01 | SESS-01 "only" | `test_session_values_appear_only_in_their_exact_headers`: for `both`, assert the canaries are absent from `request.content`, `str(request.url)`, and every header other than the two session headers, and that the session header values equal the inputs exactly |
| G-02 | SESS-01 / SC1 no arbitrary headers | `test_stream_chat_events_accepts_no_arbitrary_headers`: `inspect.signature(HermesAgentApiClient.stream_chat_events)` parameters are exactly `self`, `request` (positional-or-keyword), `session_id` and `session_key` (both `KEYWORD_ONLY`, default `None`), with no `VAR_KEYWORD` / `VAR_POSITIONAL` |
| G-03 | SESS-02 | Extend coverage without editing PR #7 parametrisations: a new parametrised test (or new parameters) for `"carriage\rreturn"`, `"tab\tchar"` and `b"bytes-canary"` (coercible non-`str`) on both arguments, plus positive `session_key` boundaries `"!"` and `"~" * 256` |
| G-04 | SESS-03 text and metadata | In the new rejection-matrix test, assert `str(error) == "Hermes transport failure (status=none, retryable=false)"`, the exact `repr`, `error.args == (str(error),)`, `error.status_code is None`, and `error.category is FailureCategory.TRANSPORT` |
| G-05 | D-08 rejection row: `repr`, `ag_frame` | `test_rejected_session_values_leave_no_retained_state`: parametrised over invalid id / invalid key / path-shaped id, with canary-length values. Assert `repr(error)`, `format_exception`, deep traceback locals, cause/context `None`, and `cast("_HasAsyncGeneratorFrame", stream).ag_frame is None` |
| G-06 | D-08 completion and early-close rows | `test_completed_and_closed_streams_retain_no_session_values`: parametrise `completion` / `early-close-after-event` / `early-close-before-first-iteration`. Assert `ag_frame is None`, the canaries are absent from `repr(stream)` and `repr(events)`, `aclose()` returns `None`, and before-first-iteration produced no request |
| G-07 | SESS-05 post-dispatch public failures | `test_post_dispatch_failures_carry_no_session_values`: parametrise 401 (`HermesAuthenticationError`), 503 (`HermesHttpStatusError`), malformed SSE (`HermesProtocolError`), and a `httpx.ConnectError` whose message embeds the session header value (`HermesTransportError`). Assert `str`, `repr`, `format_exception`, deep traceback locals, cause/context `None`, and `ag_frame is None` |
| G-08 | HTTP-02 plus D-08 mid-iteration cancellation row | `test_injected_client_survives_public_stream_early_close` and `test_injected_client_survives_public_stream_task_cancellation` (see D-09 above) |

**TDD note (`tdd_mode: true`):** these are characterisation tests of behaviour that already ships, so they go green immediately. The "red" step is meaningless unless you prove the test can fail. For each new test, the executor should temporarily break the guard the test targets and confirm a red run before restoring. For example, delete `request_headers.clear()` at `client.py:459`, or delete `session_id = None` / `session_key = None` at `client.py:674-675`, or swap `_reraise_scrubbed_failure` for a bare `raise`. This is the same discipline as D-11 and uses no new tooling.

## D-07 Upstream Hermes Analysis (tag `v2026.7.7.2`)

Source: `git clone --depth 1 --branch v2026.7.7.2 https://github.com/NousResearch/hermes-agent.git`. `HEAD` is `9de9c25f620ff7f1ce0fd5457d596052d5159596`, and `git ls-remote` shows `refs/tags/v2026.7.7.2^{}` peeling to the same commit (tag object `b7751df34688835a108e0d630f3495fc11f3df79`). All paths and lines below are at that commit [VERIFIED: upstream source read this session].

### `X-Hermes-Session-Id`

- **Entry handling** (`gateway/platforms/api_server.py:2138-2169`). The handler reads `request.headers.get("X-Hermes-Session-Id", "").strip()`. It requires a configured API key (403 otherwise). It then rejects `re.search(r'[\r\n\x00]', provided_session_id) or _is_path_unsafe(provided_session_id)` with 400 `"Invalid session ID"`, rejects length `> self._MAX_SESSION_HEADER_LEN` (`_MAX_SESSION_HEADER_LEN = 256`, `api_server.py:1086`), and assigns `session_id = provided_session_id`. The comment at `api_server.py:2152-2157` says the guard exists because the ID is "interpolated into on-disk artifact filenames (session snapshots, request dumps)".
- **Server path guard** (`gateway/session.py:107-118`), verbatim:

  ```python
  def _is_path_unsafe(value: object) -> bool:
      """Return True if ``value`` could traverse outside the sessions dir."""
      if not value:
          return False
      s = str(value)
      if ".." in s or "/" in s or "\\" in s:
          return True
      ...
      return len(s) >= 2 and s[0].isalpha() and s[1] == ":"
  ```

  This is the **same rule set** as the client's D-05 check (`client.py:161-173`): `..`, `/`, `\`, and a leading letter followed by `:`.
- **Does it become a file or path component? Yes.**
  - `hermes_state.py:5072-5093` (`_remove_session_files`) interpolates the **raw** ID: `p = sessions_dir / f"{session_id}{suffix}"` (line 5083) and `sessions_dir.glob(f"request_dump_{session_id}_*.json")` (line 5090). It is called from `delete_session`, `delete_session_if_empty`, `delete_sessions` and the prune paths (`hermes_state.py:2544, 5135-5136, 5178, 5259-5261, 5353, 5600`) **only when a `sessions_dir` is passed**. The API server's own `DELETE` handler (`api_server.py:1798-1809`) calls `db.delete_session(session_id)` without `sessions_dir`, so file removal there happens only from CLI or TUI operator actions (`cli.py:15537`, `hermes_cli/main.py:14159, 14208, 14313`, `tui_gateway/server.py:5983`).
  - The session JSON log and request dumps pass the ID through `_safe_session_filename_component` first (`run_agent.py:329-351`, used at `run_agent.py:2553-2554` and `agent/agent_runtime_helpers.py:1458-1459`). That function collapses every non-`[\w-]` character to `_`, truncates to 96 characters, and appends a SHA-256 suffix when sanitisation changed the value.
  - The ID becomes a `state.db` session row key (`run_agent.py:590-606` `_ensure_db_session` → `create_session(session_id=self.session_id, ...)`), and history is loaded with `db.get_messages_as_conversation(session_id)` (`api_server.py:2170-2173`).
- **Decoding: none.** `grep -c unquote` returns `0` for `gateway/platforms/api_server.py`, `gateway/session.py`, `run_agent.py`, `agent/agent_runtime_helpers.py` and `plugins/memory/honcho/client.py`. The three hits in `hermes_state.py` (lines 4365, 4402, 4417) are FTS5 query-quoting comments, not URL decoding. The header value is used as received apart from `.strip()`. Whether aiohttp itself ever percent-decodes header values is training knowledge, not verified here [ASSUMED], but no Hermes code path does so.

### `X-Hermes-Session-Key`

- **Entry handling** (`api_server.py:1088-1138`, `_parse_session_key_header`). The handler reads `.strip()`, requires an API key (403), rejects `[\r\n\x00]` (400) and length `> 256` (400). It applies **no** path guard. `_is_session_key_unsafe` (`gateway/session.py:121-143`) is used only by the native gateway's `SessionEntry.from_dict` (`gateway/session.py:794`), not by the API server. Its docstring states that `session_key` "never touches the filesystem".
- **Downstream use (API-server route):** `AIAgent(gateway_session_key=...)` (`api_server.py:1362`) → `agent._gateway_session_key` (`agent/agent_init.py:403`). From there it is used as:
  - the Honcho memory session name, after `re.sub(r'[^a-zA-Z0-9_-]+', '-', gateway_session_key).strip('-')` (`plugins/memory/honcho/client.py:698-701`)
  - the context-engine `conversation_id` (`run_agent.py:665`, `agent/agent_init.py:1940`)
  - the `/model` override lookup key (`api_server.py:1296-1297`)
  - the session-context binding (`api_server.py:4055-4058`)
  - an echoed response header (`api_server.py:2345-2346`)

  No filesystem path is built from it on this route.
- **Decoding: none** (same grep evidence).

### D-02 conflict assessment

- **Traversal (D-05 sufficiency): no conflict.** The server does not decode either header, so an encoded form such as `%2e%2e%2f` stays a literal string containing `%`. It contains no `..`, `/` or `\`, so no path component can escape `sessions_dir` through pathlib. The client's rule set equals the server's own `_is_path_unsafe`, and the server filename sanitiser adds a further layer. D-05 stays as shipped.
- **Adjacent observation, raised for user awareness and not a recommendation to change rules:** both client and server accept the visible-ASCII glob metacharacters `*`, `?`, `[` and `]` in `session_id`. Upstream `_remove_session_files` (`hermes_state.py:5090`) interpolates the raw ID into a `Path.glob` pattern. A session whose ID were, say, `*` could therefore make an **operator-initiated** delete or prune remove other sessions' `request_dump_*.json` files inside the same `sessions_dir`. This is not traversal: it cannot leave the directory, it is not reachable through the API `DELETE` handler, and it affects debug dumps only. It is a server-side defect. Under D-02 and D-05 the client rules stay unchanged. The user may wish to report it upstream. Home Assistant derives `session_id` from profile namespace plus conversation identity, so it is unlikely to contain glob characters [ASSUMED].

## D-11 Mutation Check: Guard Locations and Expected Failures

Each mutation below was applied this session to a **scratch copy** of `src/`, `tests/` and `pyproject.toml` (`PYTHONPATH=<copy>/src`, project `.venv` interpreter), one at a time, and the suite was run. The copy lacked `README.md` and git metadata, so `tests/test_package.py` produced 2 failures and 38 errors in **every** run, including mutations that touched nothing it tests. Those are artefacts of the copy, not mutation signal. Run the recorded check restricted to `tests/test_client_lifecycle.py tests/test_transport.py`.

| Guard (D-11) | Location | Mutation | Tests that failed (exact names) |
|--------------|----------|----------|--------------------------------|
| G1 Value validation | `client.py:158` `validated = _require_lifecycle_text(value)` | → `validated = str(value)` | 26: all 24 `test_invalid_session_arguments_fail_locally_without_dispatch[{session_id,session_key}-{empty,space,leading-space,trailing-space,embedded-space,newline,nul,delete,non-ascii,too-long,subclass,non-string}]` and `test_invalid_session_pair_is_atomic_and_secret_free[invalid-key]`, `[invalid-id]` |
| G2 Path-shape rejection | `client.py:184-186` `session_id,` / `reject_path_shape=True,` | → `reject_path_shape=False` | 4: `test_path_shaped_session_ids_fail_before_dispatch[parent]`, `[slash]`, `[backslash]`, `[drive-prefix]` |
| G3 Fresh header copy (no bound/caller mutation) | `client.py:193` `request_headers = dict(headers)` | → `request_headers = headers` | 7: `test_stream_session_headers_are_independent_and_request_scoped[session-id]`, `[session-key]`, `[minimum-session-id]`, `[maximum-session-id]`, `[path-shaped-session-key]`, `[both]`, and `test_concurrent_streams_isolate_session_headers` (`[neither]` correctly still passes) |
| G3b Inner copy (defence in depth) | `client.py:435` `request_headers = dict(headers)` | → `request_headers = headers` | 1: `tests/test_transport.py::test_stream_success_closes_response_and_refuses_redirects` (the `MappingProxyType` headers make the write raise) |
| G4 Not closing injected client (exit ownership) | `client.py:601` `owns_active = active is not None and self._injected_http_client is None` | → `owns_active = active is not None` | 38 lifecycle tests, including `test_injected_client_is_never_closed`, `test_closing_public_stream_immediately_closes_delegated_response`, `test_stream_session_headers_are_independent_and_request_scoped[*]` and `test_concurrent_streams_isolate_session_headers` |
| G4b Not closing injected client (stream path) | before `client.py:708` (`active = None` after the `finally`) | insert `await active.aclose()` | 23, including `test_closing_public_stream_immediately_closes_delegated_response`, `test_stream_response_close_cancellation_preserves_identity`, `test_stream_read_cancellation_precedes_response_close_failure`, `test_bound_endpoint_and_auth_are_reused_across_operations` and `test_stream_session_headers_are_independent_and_request_scoped[*]` |
| (extra) Session local scrub | `client.py:674-675` `session_id = None` / `session_key = None` | delete both lines | 31: all 24 invalid-argument cases, 4 path-shape cases, 2 pair cases, `test_stream_request_cancellation_preserves_identity` |

Recommended procedure for the recorded run: edit `client.py` in the working tree and run `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q`. Then restore with `git checkout -- src/hermes_agent_api_client/client.py` and confirm `git diff --exit-code src/` before anything is committed. The `prek` hooks and the 100% coverage gate are a backstop, not the primary safeguard. After G-08 lands, re-run G4b: the new tests should be among the failures.

## Architecture Patterns

### System Architecture Diagram

```
consumer (Home Assistant)
   │  stream_chat_events(request, *, session_id=?, session_key=?)
   ▼
HermesAgentApiClient.stream_chat_events  (async generator; runs on first anext)
   │  bindings = (injected-or-owned AsyncClient, base_url, bound auth headers)
   ▼
_chat_request_headers ──► _is_valid_session_value(id, reject_path_shape=True)
   │                      _is_valid_session_value(key, reject_path_shape=False)
   │                            └─► models._require_lifecycle_text (exact str, 1-256, 0x21..0x7e)
   │  invalid? ── yes ──► scrub locals ──► _raise_transport_failure(transient=False)  [no dispatch]
   │  no
   ▼  fresh dict(bound headers) + X-Hermes-Session-Id / X-Hermes-Session-Key
scrub session_id/session_key/headers locals
   ▼
_stream_chat_events (delegated async generator)
   │  dict(headers) + Content-Type; drop the original reference
   ▼
async with http_client.stream(POST /v1/chat/completions) ──► Hermes server
   │  request_headers.clear() once the response opens          (strip, CR/LF/NUL, _is_path_unsafe, ≤256)
   ▼                                                            └─► state.db row, sanitised filenames,
async_decode_hermes_sse ─► yield events (terminal withheld)        raw-ID unlink/glob on operator delete
   │
   ├─ early close (GeneratorExit) ─► wrapper finally: delegated.aclose() ─► response closed
   ├─ CancelledError ─► record .with_traceback(None) ─► response closed ─► _reraise_scrubbed_failure
   ├─ status/protocol/transport ─► fresh metadata-only HermesContractError (no chain)
   └─ success ─► response closed ─► yield terminal
   ▼
injected AsyncClient: never closed by stream or __aexit__; owned client closed only in __aexit__
```

### Pattern 1: Characterisation test with a proven failure mode
**What:** each gap-fill test asserts existing behaviour, and the executor proves it can fail by temporarily breaking one guard.
**When to use:** every G-01 to G-08 test (TDD mode on already-shipped code).

### Pattern 2: Deterministic mid-iteration cancellation
**What:** a gated `httpx.AsyncByteStream` yields one chunk, sets an `asyncio.Event`, then awaits forever. The test waits for the event, then calls `task.cancel()`.
**When to use:** G-08 cancellation. Never use `asyncio.sleep(n)` timing for this.

### Pattern 3: Inspect the library-raised exception inside the task
**What:** the consumer coroutine catches `asyncio.CancelledError`, appends it to a list, and re-raises. The outer test asserts `task.cancelled()` and inspects the recorded object.
**Why:** this proves propagation (re-raise) and gives direct access to the exact object the library raised for traceback and chain checks.

### Anti-Patterns to Avoid
- **Editing PR #7 tests to add cells:** this blurs provenance for D-10 and Phase 4 VERI-02. Add new tests next to them instead.
- **Using `respx`:** no test module uses it. Keep `httpx.MockTransport`.
- **Asserting only `is_closed is False`** for HTTP-02: D-09 requires a later successful request on the same injected client.
- **Short canaries:** values under `_MIN_UNIQUE_CANARY_LENGTH` (4) collide with ordinary strings. Use long, unique canaries such as `"matrix-session-id-canary"` for any cell that checks rendered text.
- **Changing validation timing or adding `%` checks:** forbidden by D-02, D-03 and D-05.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Traceback canary scanning | a new frame walker | `_assert_no_sensitive_traceback_references` / `_package_traceback_locals` | already deep-walks dicts, lists and tuples, checks identities, and renders the chain; D-08 mandates reuse |
| `ag_frame` access under strict basedpyright | `getattr(stream, "ag_frame")` | `cast("_HasAsyncGeneratorFrame", stream).ag_frame` | existing structural protocol keeps strict typing green |
| Response-closure tracking | custom flags on `httpx.Response` | `TrackingAsyncByteStream.closed` (lifecycle version) | already records `aclose()` on the response stream |
| Mutation testing | `mutmut` or other tooling | manual edit, run, restore (D-11) | D-11 forbids new tooling |
| Exact error text | re-deriving formats ad hoc | the `_assert_fresh_cleanup_transport_failure` pattern with `retryable=false` literals | keeps assertions consistent with `protocol.py:67-85` |

**Key insight:** the secrecy machinery and its assertion helpers already exist and pass. The work is to point existing assertions at the missing exit-path cells, not to build new inspection logic.

## Common Pitfalls

### Pitfall 1: Unstarted generator retains session values
**What goes wrong:** a test inspects `stream.ag_frame` **before** the first `anext()` and finds the canaries in `f_locals`.
**Why it happens:** Python binds async-generator arguments into the frame at call time. Validation and scrubbing run only on the first iteration. This is inherent to the shipped async-generator design (probe: `1 unstarted: ag_frame has canary = True`). After `aclose()` the frame is `None` and no request was sent.
**How to avoid:** do not treat this as a SESS-05 gap. It is not one of the four enumerated exit paths, and fixing it would change public behaviour (Open Questions, Q2). Test only "early close before first iteration → `ag_frame is None`".

### Pitfall 2: In-flight values are reachable while suspended
**What goes wrong:** while the consumer holds a suspended stream, `ag_frame.f_locals["delegated_stream"].ag_frame.f_locals["response"].request.headers` still contains the session headers (probe 2d).
**Why it happens:** `httpx` keeps the sent `Request` on the live `Response`. That is required for the request itself.
**How to avoid:** SESS-05 scopes secrecy to *after* the exit paths, and `request_headers` is already cleared before the first yield (`test_stream_discards_temporary_request_headers_before_yield`). Do not plan a change. Mention it in VERIFICATION.md as a known in-flight boundary.

### Pitfall 3: `task.cancel()` against the wrong await point
**What goes wrong:** the test cancels before the stream is blocked, so cancellation lands in request dispatch rather than mid-iteration, or it races.
**How to avoid:** first `await anext(stream)` (or wait on the gate event set after the first chunk), then `task.cancel()`. In the probe, the gate is set after the first chunk is yielded, and the consumer has already received the delta.

### Pitfall 4: `_package_traceback_locals` asserts that package frames exist
**What goes wrong:** for `CancelledError` objects whose traceback contains no package frames, the helper's `assert frames` fails spuriously.
**How to avoid:** inspect the exception recorded inside the consumer coroutine (Pattern 3). Its traceback includes `stream_chat_events` and `_reraise_scrubbed_failure` frames (probe: traceback scan executed with package frames present).

### Pitfall 5: The later-request check hangs
**What goes wrong:** the gated stream blocks every response, so the "usable for a later request" call hangs. This happened in this session's first probe.
**How to avoid:** the `MockTransport` handler serves the gated stream only for the **first** chat request and a normal SSE body afterwards (or serves capabilities on `/v1/capabilities`).

### Pitfall 6: Ruff and basedpyright strictness in new tests
**What goes wrong:** the `prek` gate fails on `PT012` (multi-statement `pytest.raises`), `RUF006` (unstored task), `PLR2004` (magic numbers), missing docstrings, or untyped helpers.
**How to avoid:** mirror existing test style (named constants, docstrings on every class, method and test, `cast(...)` for generator protocols). Run `uv run ruff check . && uv run ruff format --check . && uv run --no-sync basedpyright` before committing.

### Pitfall 7: Mutation residue
**What goes wrong:** a D-11 mutation is left in `client.py`.
**How to avoid:** restore with `git checkout -- src/hermes_agent_api_client/client.py` and confirm `git diff --exit-code src/`. Record each mutation's failing test names in VERIFICATION.md immediately.

## Code Examples

These are skeletons for the planner and executor. Helper names and constants come from `tests/test_client_lifecycle.py` as quoted above. The new class and test names are suggestions (Claude's discretion).

### Gated stream and task-cancellation test (G-08 plus D-08 mid-iteration row)

```python
# Source: pattern verified by probe this session; helpers from tests/test_client_lifecycle.py
class GatedAsyncByteStream(httpx.AsyncByteStream):
    """Yield one chunk, signal, then block until cancelled; record closure."""

    def __init__(self, first_chunk: bytes) -> None:
        """Store the first chunk and the gate signalled after it is yielded."""
        self.first_chunk = first_chunk
        self.blocked = asyncio.Event()
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield the first chunk and then wait forever."""
        yield self.first_chunk
        self.blocked.set()
        await asyncio.Event().wait()

    async def aclose(self) -> None:
        """Record response-scope closure."""
        self.closed = True


@pytest.mark.asyncio
async def test_injected_client_survives_public_stream_task_cancellation() -> None:
    """Mid-iteration task cancellation closes only the response and propagates."""
    session_id = "cancel-mid-session-id-canary"
    session_key = "cancel-mid-session-key-canary"
    delta = (
        b'data: {"choices":[{"index":0,"delta":{"content":"hello"},'
        b'"finish_reason":null}]}\n\n'
    )
    gated = GatedAsyncByteStream(delta)
    requests: list[httpx.Request] = []
    later = _successful_transport(requests)

    def respond(request: httpx.Request) -> httpx.Response:
        if not requests:
            requests.append(request)
            return httpx.Response(200, request=request, stream=gated)
        return later(request)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY, _BEARER_KEY_CANARY, http_client=injected_http_client
    )
    recorded: list[asyncio.CancelledError] = []
    try:
        async with client:
            stream = client.stream_chat_events(
                {"model": "hermes"}, session_id=session_id, session_key=session_key
            )

            async def consume() -> None:
                try:
                    async for _event in stream:
                        pass
                except asyncio.CancelledError as caught:
                    recorded.append(caught)
                    raise

            task = asyncio.create_task(consume())
            await gated.blocked.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

            assert task.cancelled() is True
            assert gated.closed is True
            assert injected_http_client.is_closed is False
            assert cast("_HasAsyncGeneratorFrame", stream).ag_frame is None
            # later request through the same injected client succeeds
            events = [event async for event in client.stream_chat_events({"model": "hermes"})]
            assert isinstance(events[-1], TerminalEvent)

        assert injected_http_client.is_closed is False
        failure = recorded[0]
        assert failure.__cause__ is None
        assert failure.__context__ is None
        _assert_no_sensitive_traceback_references(
            failure,
            canaries=(session_id, session_key),
            forbidden_objects=(client, injected_http_client),
        )
    finally:
        await injected_http_client.aclose()
```

Executor notes: confirm `stream` typing (`cast("AsyncGenerator[HermesEvent]", ...)` if `aclose` is used), and keep imports at module top (`AsyncIterator` and `AsyncGenerator` are already under `TYPE_CHECKING` at `tests/test_client_lifecycle.py:41-48`).

### Rejection cell additions (G-04 and G-05)

```python
# Source: protocol.py:67-85 format; helpers from tests/test_client_lifecycle.py
assert str(error) == "Hermes transport failure (status=none, retryable=false)"
assert repr(error) == (
    "HermesTransportError(category='transport', status_code=None, retryable=False)"
)
assert error.args == (str(error),)
assert error.__cause__ is None
assert error.__context__ is None
assert cast("_HasAsyncGeneratorFrame", stream).ag_frame is None
_assert_no_sensitive_traceback_references(
    error, canaries=(session_id, session_key), forbidden_objects=(client, injected_http_client)
)
```

### No arbitrary-header API (G-02)

```python
# Source: client.py:653-659 signature
parameters = inspect.signature(HermesAgentApiClient.stream_chat_events).parameters
assert list(parameters) == ["self", "request", "session_id", "session_key"]
assert parameters["session_id"].kind is inspect.Parameter.KEYWORD_ONLY
assert parameters["session_key"].kind is inspect.Parameter.KEYWORD_ONLY
assert parameters["session_id"].default is None
assert parameters["session_key"].default is None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No per-request session metadata | Keyword-only `session_id` / `session_key` mapped to fixed Hermes headers | PR #7 / v0.3.1 (`8843cfc`, 2026-07-17) | Phase 3 audits it; no API change |
| Bound headers passed straight to the delegated stream | Two fresh copies (`client.py:193`, `client.py:435`) plus `request_headers.clear()` on response open | PR #7 | SESS-04 and the suspension-time scrub |

**Deprecated/outdated:** none relevant.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | aiohttp does not percent-decode header values before Hermes reads them (no Hermes code calls `unquote` on these headers; aiohttp internals were not read) | D-07 Upstream | Low. Even if decoded, the server runs `_is_path_unsafe` on the decoded string it uses, so traversal is still rejected server-side |
| A2 | Home Assistant-derived `session_id` values will not contain glob metacharacters (`*`, `?`, `[`, `]`) | D-07 adjacent observation | Low. Affects only operator-initiated cleanup of other sessions' debug dumps on the server |
| A3 | Recording completion and early-close traceback and cause/context cells as "N/A: no exception escapes" satisfies D-08's "each cell" wording | D-08 matrix | Medium. If the user wants a different proof for those cells, G-06's assertions change (no source impact) |

## Open Questions

1. **D-08 N/A cells (needs user confirmation).**
   - What we know: completion and early close raise nothing, so the traceback and cause/context columns have no exception object.
   - What's unclear: whether the user accepts "N/A: no exception escapes, proven by normal return" as the cell evidence.
   - Recommendation: record N/A with that proof in VERIFICATION.md. Ask at plan review if in doubt.
2. **Pre-iteration retention (informational, D-02).**
   - What we know: an unstarted stream holds the session values in `ag_frame` until it is first iterated or closed. This is inherent to async generators.
   - What's unclear: nothing in SESS-05 lists "created but never iterated" as an exit path.
   - Recommendation: no change, because eager validation would alter released behaviour (one-way door). Document it in VERIFICATION.md.
3. **Upstream glob observation (D-02 / D-07, for user awareness).**
   - What we know: upstream `hermes_state.py:5090` uses the raw ID in `Path.glob`.
   - Recommendation: D-05 stays unchanged. The user may choose to report it upstream. This is not phase scope.
4. **New tests vs editing PR #7 tests.**
   - Recommendation: add new tests (provenance for D-10 and VERI-02). Claude's discretion allows either.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all commands | ✓ | 0.13.3 | — |
| CPython 3.13 (project `.venv`) | tests | ✓ | 3.13.15 | — |
| CPython 3.14 (CI matrix) | optional local cross-check | ✓ | 3.14.7 | CI runs both (`.github/workflows/ci.yml:22` `python-version: ["3.13", "3.14"]`) |
| prek | pre-commit gate | ✓ (via `uv run --no-sync prek`) | 0.4.9 | run the individual hooks |
| basedpyright / ruff | gate | ✓ | locked | — |
| Network | none (MockTransport only) | n/a | — | — |

Baseline gate, run this session: `uv run --no-sync pytest -q` → **641 passed, 100.00% coverage**; `ruff check .` → all checks passed; `basedpyright` → 0 errors. Working tree clean.

**Missing dependencies:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`), pytest-cov 7.1.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`, `[tool.coverage.*]` |
| Quick run command | `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q` (verified: 165 passed in 0.34s) |
| Focused session subset | `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "session or injected_client or closing_public_stream or stream_request_cancellation"` (verified: 43 passed) |
| Full suite command | `uv run pytest` (enforces `fail_under = 100` branch coverage; verified 641 passed) |
| Full gate | `uv run --no-sync prek run --all-files` |

### Phase Requirements → Test Map
| Req ID | Behaviour | Test Type | Automated Command | File Exists? |
|--------|-----------|-----------|-------------------|-------------|
| SESS-01 | independent mapping; only exact headers; no arbitrary headers | unit (MockTransport) | `uv run --no-sync pytest tests/test_client_lifecycle.py --no-cov -q -k "session_headers_are_independent or appear_only_in_their_exact_headers or accepts_no_arbitrary_headers"` | ✅ existing / ❌ G-01, G-02 |
| SESS-02 | exact str, 1-256, visible ASCII, path shape | unit | `... -k "invalid_session_arguments or path_shaped_session_ids or session_boundaries"` | ✅ existing / ❌ G-03 |
| SESS-03 | no dispatch, non-retryable, value-free text | unit | `... -k "invalid_session or rejected_session_values"` | ✅ existing / ❌ G-04 |
| SESS-04 | fresh headers, no mutation, concurrency isolation | unit | `... -k "session_headers_are_independent or concurrent_streams_isolate"` | ✅ |
| SESS-05 | D-08 matrix and post-dispatch failures | unit | `... -k "rejected_session_values or retain_no_session_values or post_dispatch_failures or closing_public_stream or stream_request_cancellation or task_cancellation"` | partial ✅ / ❌ G-05 to G-08 |
| HTTP-02 | early close and real cancellation with injected client; later request succeeds | unit (asyncio task) | `... -k "injected_client_survives or injected_client_is_never_closed"` | ❌ G-08 |

### Sampling Rate
- **Per task commit:** quick run command (two modules, `--no-cov`, under 1 s)
- **Per wave merge:** `uv run pytest` (full suite with the 100% gate)
- **Phase gate:** `uv run --no-sync prek run --all-files` green, plus the D-11 mutation results recorded, before `/gsd-verify-work`

### Wave 0 Gaps
- None for framework or fixtures. The only new shared helper is `GatedAsyncByteStream` in `tests/test_client_lifecycle.py`, created by the G-08 plan itself.

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (bearer handling unchanged; out of scope) | — |
| V3 Session Management | no (opaque IDs are transported, not managed) | — |
| V4 Access Control | no | — |
| V5 Validation, Sanitisation and Encoding | yes | exact `str`, length, visible-ASCII allowlist (`_require_lifecycle_text`) blocks CR/LF/NUL header injection; `session_id` path-shape rejection as defence in depth |
| V6 Cryptography | no | — |
| V7 Error Handling and Logging | yes | metadata-only `HermesContractError`; `_raise_transport_failure`; `_reraise_scrubbed_failure` strips traceback and chain |
| V8 Data Protection | yes | scrub sensitive locals (`session_id = None`, `request_headers.clear()`); no retained generator frames after exit |
| V12 Files and Resources | server-side only | upstream `_is_path_unsafe` plus `_safe_session_filename_component` |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| HTTP header injection through CR/LF in session values | Tampering | visible-ASCII allowlist; httpx also rejects CR/LF in header values [ASSUMED] |
| Path traversal through `session_id` reaching server filenames | Tampering / Elevation | client D-05 check mirrors server `_is_path_unsafe`; server sanitises filenames |
| Session identifier disclosure through exceptions, tracebacks or retained frames | Information disclosure | scrubbed locals, fresh metadata-only errors, `with_traceback(None)`, no chaining |
| Cross-request header contamination under concurrency | Information disclosure | per-request `dict(...)` copies; bound headers never written |
| Closing a caller-owned shared HTTP client | Denial of service | `owns_active` ownership check; stream owns only the response |

## Sources

### Primary (HIGH confidence)
- `src/hermes_agent_api_client/client.py` (lines 50-52, 83-94, 153-198, 427-520, 591-619, 653-714): read this session
- `src/hermes_agent_api_client/models.py:15-58`, `src/hermes_agent_api_client/protocol.py:54-99, 387-399`: read this session
- `tests/test_client_lifecycle.py` (helpers 52-367; session tests 381-705; ownership and cancellation tests 913-927, 1531-1604, 1950-2302, 2327-2512, 2610-2651, 2720-2750) and `tests/test_transport.py` (1-264, 860-1050, 1425-1518): read this session
- `docs/superpowers/specs/2026-07-17-conversation-contract-design.md` §1 and Acceptance tests: read this session
- Upstream Hermes Agent at `v2026.7.7.2` / `9de9c25f620ff7f1ce0fd5457d596052d5159596` (https://github.com/NousResearch/hermes-agent): `gateway/platforms/api_server.py`, `gateway/session.py`, `hermes_state.py`, `run_agent.py`, `agent/agent_runtime_helpers.py`, `agent/agent_init.py`, `plugins/memory/honcho/client.py`, read from a shallow clone of the tag this session
- Empirical probes (scratchpad, not committed): exit-path secrecy, post-dispatch failures, real `task.cancel()`, injected-client reuse, on CPython 3.13.15 and 3.14.7
- Mutation runs G1-G4b plus the scrub mutation on a scratch copy of the repository

### Secondary (MEDIUM confidence)
- https://owasp.org/www-community/attacks/Path_Traversal: background for encoded traversal (CONTEXT.md canonical ref; not re-fetched)

### Tertiary (LOW confidence)
- aiohttp and httpx header-value handling details (A1 and the CR/LF note): training knowledge

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. No new packages; versions read from the environment.
- Audit verdicts and D-08/D-09 matrices: HIGH. Every test body was read, and probes plus mutations confirm the tests' sensitivity.
- Upstream D-07 analysis: HIGH for the code paths quoted; LOW only for aiohttp internals (A1).
- Pitfalls: HIGH. Several were reproduced in this session's probes.

**Research date:** 2026-10-20
**Valid until:** 2026-11-19 (stable: pinned upstream tag, no code changes since PR #7)
