# Phase 3: Session Header Safety - Pattern Map

**Mapped:** 2026-10-20
**Files analysed:** 2 (1 modified test module, 1 new evidence artefact)
**Analogs found:** 2 / 2

**Scope note:** the research found no source defects. This phase adds tests only (G-01 to G-08) in `tests/test_client_lifecycle.py` and writes the plan-authored D-10/D-11 evidence record `03-TRACEABILITY.md` (`gsd-verifier` alone writes `03-VERIFICATION.md`). `src/hermes_agent_api_client/client.py` is touched only temporarily for the D-11 mutation check and must be restored (`git checkout -- src/hermes_agent_api_client/client.py`, then `git diff --exit-code src/`). The client class is `HermesAgentApiClient`. Tests use `httpx.MockTransport`, never `respx`.

**Line-number correction:** RESEARCH.md cites some test line numbers that are off by a few lines. The ranges below were re-checked against the current tree and take precedence.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/test_client_lifecycle.py` (append G-01 to G-08 tests plus `GatedAsyncByteStream`) | test | streaming (async generator, MockTransport) | the PR #7 session tests and cancellation/early-close tests in the same file | exact |
| `.planning/phases/03-session-header-safety/03-TRACEABILITY.md` | doc (plan-authored evidence record) | n/a | `.planning/phases/02-conversation-event-contract/02-VERIFICATION.md` | role-match |
| `tests/test_transport.py` | test | streaming | (no change expected; new public-API tests belong in the lifecycle module) | n/a |

## Pattern Assignments

### `tests/test_client_lifecycle.py` (test, streaming)

**Placement:** add new tests directly after `test_concurrent_streams_isolate_session_headers` (ends at line 705), next to the PR #7 session tests. Do not edit the PR #7 parametrisations (provenance for D-10 and VERI-02). Put `GatedAsyncByteStream` with the other test doubles (after `TrackingAsyncByteStream`, lines 123-150).

**Imports** (lines 1-49). Module already imports `asyncio`, `traceback`, `cast`, `Protocol`, `httpx`, `pytest`, `HermesAgentApiClient`, `HermesEvent`, `HermesHttpStatusError`, `HermesProtocolError`, `HermesTransportError`, `AssistantDeltaEvent`, `TerminalEvent`, `TerminalOutcome`, and `FailureCategory`. `AsyncGenerator` and `AsyncIterator` sit under `TYPE_CHECKING` (lines 41-48). New tests will need to add at module top (all imports at top, per user rules):
- `import inspect` (G-02)
- `HermesAuthenticationError` from `hermes_agent_api_client` if G-07 parametrises a 401 (not currently imported; confirm it is exported).

**Constants** (lines 52-59): reuse `_BASE_URL_CANARY`, `_BEARER_KEY_CANARY`, `_UPSTREAM_STATUS_CODE` (503), `_MIN_UNIQUE_CANARY_LENGTH` (4). New numbers (for example 256, 401) need named constants (`PLR2004`).

**Standard test skeleton** (copy from `test_path_shaped_session_ids_fail_before_dispatch`, lines 553-604):
```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_session_id",
    ["..", "profile/child", "profile\\child", "C:profile"],
    ids=["parent", "slash", "backslash", "drive-prefix"],
)
async def test_path_shaped_session_ids_fail_before_dispatch(
    invalid_session_id: str,
) -> None:
    """Transcript identifiers cannot be interpreted as filesystem paths."""
    requests: list[httpx.Request] = []
    injected_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(_successful_transport(requests))
    )
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            with pytest.raises(HermesTransportError) as caught:
                await anext(
                    client.stream_chat_events(
                        {"model": "hermes"},
                        session_id=invalid_session_id,
                    )
                )

        assert caught.value.retryable is False
        assert requests == []
        _assert_no_sensitive_traceback_references(
            caught.value,
            canaries=(...),
            forbidden_objects=(invalid_session_id, client, injected_http_client),
        )
    finally:
        await injected_http_client.aclose()
```
Every test: `@pytest.mark.asyncio`, a docstring, `try/finally: await injected_http_client.aclose()`, single-statement `pytest.raises` (`PT012`).

---

#### G-01 `test_session_values_appear_only_in_their_exact_headers` (SESS-01 "only")

**Analog:** `test_stream_session_headers_are_independent_and_request_scoped`, lines 380-464. Copy the setup (lines 419-447) and the sent-request inspection:
```python
        assert len(requests) == 1
        sent = requests[0]
        for name in ("X-Hermes-Session-Id", "X-Hermes-Session-Key"):
            if name in expected_headers:
                assert sent.headers[name] == expected_headers[name]
            else:
                assert name not in sent.headers
```
Extend with: canaries absent from `sent.content`, `str(sent.url)`, and every header other than the two session headers. Use long unique canaries (at least `_MIN_UNIQUE_CANARY_LENGTH`).

#### G-02 `test_stream_chat_events_accepts_no_arbitrary_headers` (SESS-01 / SC1)

**Analog:** none in-module (no `inspect.signature` test exists). Use the RESEARCH.md "No arbitrary-header API (G-02)" snippet; synchronous `def test_...` with a docstring, no client needed. Also assert no `VAR_KEYWORD` / `VAR_POSITIONAL` parameter.

#### G-03 / G-04 / G-05 rejection-matrix tests (SESS-02, SESS-03, D-08 rejection row)

**Analog:** `test_invalid_session_arguments_fail_locally_without_dispatch`, lines 470-550 (two stacked `parametrize` decorators, `argument` switch, `cast("str", invalid)`):
```python
@pytest.mark.parametrize("argument", ["session_id", "session_key"])
async def test_invalid_session_arguments_fail_locally_without_dispatch(
    argument: str,
    invalid: object,
) -> None:
    ...
        async with client:
            if argument == "session_id":
                stream = client.stream_chat_events(
                    {"model": "hermes"},
                    session_id=cast("str", invalid),
                )
            else:
                stream = client.stream_chat_events(
                    {"model": "hermes"},
                    session_key=cast("str", invalid),
                )
            with pytest.raises(HermesTransportError) as caught:
                await anext(stream)

        assert caught.value.retryable is False
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert requests == []
```
New G-03 parameters: `"carriage\rreturn"`, `"tab\tchar"`, `b"bytes-canary"` on both arguments; positive `session_key` boundaries `"!"` and `"~" * 256` (copy the success shape of lines 380-464).

**Exact-text pattern for G-04** — copy `_assert_fresh_cleanup_transport_failure`, lines 286-309, with `retryable=false` literals:
```python
    assert type(error) is HermesTransportError
    assert error.category is FailureCategory.TRANSPORT
    assert error.status_code is None
    assert error.retryable is True
    assert str(error) == "Hermes transport failure (status=none, retryable=true)"
    assert repr(error) == (
        "HermesTransportError(category='transport', status_code=None, retryable=True)"
    )
```
Add `error.args == (str(error),)`.

**G-05 `ag_frame` assertion** — keep the stream in a variable (as in lines 527-536), then `cast("_HasAsyncGeneratorFrame", stream).ag_frame is None`. Use canary-length values (for example `"invalid session-id-canary"`, pattern from `test_invalid_session_pair_is_atomic_and_secret_free`, lines 601-643).

#### G-06 `test_completed_and_closed_streams_retain_no_session_values` (D-08 completion and early-close rows)

**Analog:** `test_closing_public_stream_immediately_closes_delegated_response`, lines 2327-2366:
```python
    response_stream = TrackingAsyncByteStream(
        (
            b'data: {"choices":[{"index":0,"delta":{"content":"hello"},'
            b'"finish_reason":null}]}\n\n',
        )
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=response_stream)
    ...
            public_stream = cast(
                "AsyncGenerator[HermesEvent]",
                client.stream_chat_events(
                    {"model": "hermes", "messages": (), "stream": True},
                    session_id="early-close-session-canary",
                    session_key="early-close-key-canary",
                ),
            )
            assert await anext(public_stream) == AssistantDeltaEvent(text="hello")
            assert response_stream.closed is False

            await public_stream.aclose()

            assert response_stream.closed is True
            assert injected_http_client.is_closed is False
            assert cast("_HasAsyncGeneratorFrame", public_stream).ag_frame is None
```
Completion case: use `_successful_transport(requests)` (lines 345-367) and iterate to `TerminalEvent`. Before-first-iteration case: `aclose()` without `anext`, assert `requests == []`. Do not inspect `ag_frame` before the first `anext` (Pitfall 1: argument values are bound at call time).

#### G-07 `test_post_dispatch_failures_carry_no_session_values` (SESS-05 public failures)

**Analogs:**
- ConnectError transport: `test_operation_failures_scrub_bound_state_from_tracebacks`, lines 2720-2750:
```python
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(failure_message, request=request)

    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
```
  For G-07, embed `request.headers["X-Hermes-Session-Id"]` in the `ConnectError` message.
- Status failure shape: `test_stream_request_status_error_remains_typed`, lines 2305-2324 (`StatusFailingRequestTransport`, lines 110-120) and `test_stream_status_failure_precedes_response_close_cancellation` (starts line 1749).
- Protocol failure: `test_stream_protocol_failure_precedes_response_close_failure` (starts line 1608).
Assert with `_assert_no_sensitive_traceback_references(error, canaries=(session_id, session_key), forbidden_objects=(client, injected_http_client))`, `__cause__`/`__context__` `None`, and `ag_frame is None`.

#### G-08 `test_injected_client_survives_public_stream_early_close` / `..._task_cancellation` (HTTP-02 plus D-08 mid-iteration row)

**Analogs:**
- Early close: lines 2327-2366 above, plus a later successful request on the same wrapper. For the later request, the handler must switch to `_successful_transport(requests)` after the first chat request (Pitfall 5).
- Cancellation identity and secrecy checks: `test_stream_request_cancellation_preserves_identity`, lines 2267-2302:
```python
            with pytest.raises(asyncio.CancelledError) as failure:
                await anext(public_stream)

        assert failure.value is cancellation
        assert failure.value.__cause__ is None
        assert failure.value.__context__ is None
        assert cast("_HasAsyncGeneratorFrame", public_stream).ag_frame is None
        _assert_no_sensitive_traceback_references(
            failure.value,
            canaries=("cancel-session-canary", "cancel-key-canary"),
            forbidden_objects=(client, injected_http_client),
        )
```
- New `GatedAsyncByteStream`: model on `TrackingAsyncByteStream`, lines 123-150 (`__init__` with docstring, `async def __aiter__(self) -> AsyncIterator[bytes]`, `aclose` sets `self.closed = True`). Full skeleton plus the consumer-task test is in RESEARCH.md "Code Examples" (lines 536-623). Store the `create_task` result (`RUF006`); record `CancelledError` inside the consumer and re-raise (Pattern 3, avoids Pitfall 4); assert `task.cancelled() is True`.
- Ownership baseline: `test_injected_client_is_never_closed`, lines 913-927 (assert `injected_http_client.is_closed is False` after `async with` exits).

---

### `.planning/phases/03-session-header-safety/03-TRACEABILITY.md` (doc)

**Analog:** `.planning/phases/02-conversation-event-contract/02-VERIFICATION.md`, for table layout only. The verdict frontmatter and goal-achievement sections belong to the verifier's `03-VERIFICATION.md`, which this phase's plans never write. Section headings in the analog (line numbers in analog):
- `# Phase 2: ... Verification Report` (25), `## Goal Achievement` (34), `### Observable Truths` (38), `## Required Artifacts` (79), `## Key Link Verification` (96), `## Behavioral Spot-Checks` (122), `## Requirements Coverage` (139), `## Anti-Patterns Found` (157), `## Human Verification Required` (165), `## Gaps Summary` (169).

Phase 3 additions required by CONTEXT.md:
- PR #7 provenance statement (`8843cfc`, v0.3.1): verified, not implemented here.
- D-10 traceability table: SESS-01 to SESS-05, HTTP-02 and SC1 to SC5 mapped to exact test names (seed from RESEARCH.md "Requirement Audit" and "Roadmap success criteria mapping").
- D-08 matrix with N/A cells recorded as "N/A: no exception escapes" (Open Question Q1).
- D-11 mutation table: copy RESEARCH.md "D-11 Mutation Check" layout (guard, location, mutation, failing tests), re-run on the working tree with `uv run --no-sync pytest tests/test_client_lifecycle.py tests/test_transport.py --no-cov -q`; re-run G4b after G-08 lands.
- Known boundaries: pre-iteration retention (Pitfall 1) and in-flight response headers (Pitfall 2).

## Shared Patterns

### Secrecy assertions
**Source:** `tests/test_client_lifecycle.py` lines 212-283
**Apply to:** G-04, G-05, G-07, G-08
- `_HasAsyncGeneratorFrame` (212-218): `cast("_HasAsyncGeneratorFrame", stream).ag_frame is None`
- `_package_traceback_locals` (221-233): asserts at least one package frame exists
- `_assert_no_sensitive_traceback_references(error, *, canaries, forbidden_objects)` (253-283): renders `traceback.format_exception`, deep-walks package frame locals, and rejects `httpx.AsyncClient`, `httpx.Response` and `HermesAgentApiClient` instances
- `_assert_fresh_cleanup_transport_failure` (286-309): exact `str`/`repr` template

### Injected-client fixture shape
**Source:** lines 419-433 and 2340-2347
**Apply to:** every new stream test
```python
    injected_http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = HermesAgentApiClient(
        _BASE_URL_CANARY,
        _BEARER_KEY_CANARY,
        http_client=injected_http_client,
    )
    try:
        async with client:
            ...
    finally:
        await injected_http_client.aclose()
```

### Transport doubles
- `_successful_transport(requests)` (345-367): records requests, serves delta plus `[DONE]` or capabilities
- `TrackingAsyncByteStream(chunks, *, close_failure=None, iteration_failure=None)` (123-150): `.closed` flag
- `CancellingRequestTransport` (97-107), `StatusFailingRequestTransport` (110-120)

### Typing and lint
- Cast public streams: `cast("AsyncGenerator[HermesEvent]", client.stream_chat_events(...))` when calling `aclose()`
- Invalid non-`str` inputs: `cast("str", invalid)`
- Private access: `client._headers  # pyright: ignore[reportPrivateUsage]`
- Gate: `uv run ruff check . && uv run ruff format --check . && uv run --no-sync basedpyright`, then `uv run pytest` (100% branch coverage)

## No Analog Found

| File / item | Role | Data Flow | Reason |
|-------------|------|-----------|--------|
| G-02 signature test | test | n/a | no `inspect.signature` test exists; use the RESEARCH.md snippet |
| `GatedAsyncByteStream` | test double | streaming | no gated byte stream in the lifecycle module; model on `TrackingAsyncByteStream` plus RESEARCH.md skeleton (`tests/test_sse.py:2078-2098` has a similar `asyncio.Event` wait for the decoder only) |

## Metadata

**Analog search scope:** `tests/test_client_lifecycle.py`, `tests/test_transport.py`, `.planning/phases/02-conversation-event-contract/`
**Files scanned:** 4
**Tracked-source check:** `git ls-files` confirms both test modules are tracked
**Pattern extraction date:** 2026-10-20
