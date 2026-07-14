# Hermes Agent API Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify `hermes-agent-api-client` 0.1.0 as a typed, Home Assistant-independent async client for Hermes capability discovery and streaming Chat Completions.

**Architecture:** A public `HermesAgentApiClient` async context manager binds one endpoint and bearer credential. It delegates bounded HTTP operations to internal transport functions, validates untrusted JSON through strict Pydantic wire models, and yields frozen public event models from a transport-independent SSE state machine. The package accepts an injected `httpx.AsyncClient` or creates and closes its own client.

**Tech Stack:** Python 3.13+, uv 0.11.28, uv_build 0.11.28, httpx 0.28.1, Pydantic 2.13.4, Ruff 0.15.21, pytest 9.1.1, pytest-asyncio 1.4.0, respx 0.23.1, coverage 7.15.1, Microsoft Pyright 1.1.411.

## Global Constraints

- Distribution name is exactly `hermes-agent-api-client`; import package is exactly `hermes_agent_api_client`.
- Initial public version is `0.1.0`; Python requirement is `>=3.13`.
- Runtime dependencies are limited to `httpx>=0.28.1,<1` and `pydantic>=2.13.4,<3`.
- Build backend is `uv_build>=0.11.28,<0.12`; project metadata is static.
- The package contains no Home Assistant imports or lifecycle assumptions.
- `HermesAgentApiClient` is single-use and must be entered as an async context manager before operations.
- An injected `httpx.AsyncClient` is never closed by this package; an internally created client is always closed on context exit.
- A non-`None` `verify` argument is invalid when an HTTP client is injected.
- Capability and SSE payloads use strict Pydantic validation with additive unknown fields ignored.
- The byte-level SSE decoder remains custom, bounded, incremental, and transport-independent.
- Raw bearer keys, URL userinfo, request bodies, response bodies, parser inputs, and upstream exception messages never enter public exceptions, tracebacks, causes, contexts, `str`, or `repr`.
- `py.typed` ships in wheel and sdist; Pyright strict mode and `--verifytypes` must pass.
- Every commit uses a conventional prefix, GPG signing, and DCO signoff: `git commit -S -s -m "<type>: <message>"`.
- This plan stops after a verified standalone package commit. The Home Assistant cutover is a second plan written after that immutable commit is pushed, so its Git requirement contains the real immutable SHA.

---

## Planned file structure

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Static package metadata, dependencies, uv, pytest, Ruff, coverage, and Pyright configuration |
| `.python-version` | Local Python floor, `3.13` |
| `.gitignore` | Python, uv, coverage, build, editor, and OS artifacts |
| `README.md` | Supported endpoints, lifecycle/ownership contract, safe usage example, compatibility statement |
| `src/hermes_agent_api_client/__init__.py` | Deliberate public re-export surface and `__version__` |
| `src/hermes_agent_api_client/client.py` | Public context manager and internal bounded HTTP operations |
| `src/hermes_agent_api_client/models.py` | Frozen public Pydantic capabilities and stream-event models |
| `src/hermes_agent_api_client/protocol.py` | Safe exception taxonomy plus internal Pydantic wire validation |
| `src/hermes_agent_api_client/sse.py` | Bounded incremental SSE framing and event translation |
| `src/hermes_agent_api_client/py.typed` | PEP 561 marker |
| `tests/helpers/hermes.py` | Deterministic fixture loading and byte partition helpers |
| `tests/fixtures/hermes/v2026.7.7.2/` | Reviewed capability, SSE, and provenance evidence |
| `tests/test_package.py` | Metadata and public API contract |
| `tests/test_protocol.py` | Public models, capability validation, and safe exceptions |
| `tests/test_sse.py` | Byte framing, application records, terminal semantics, bounds, cancellation, and replay |
| `tests/test_transport.py` | HTTP endpoint, auth, timeout, classification, response ownership, and concurrency |
| `tests/test_client_lifecycle.py` | Owned/injected client lifetime and context state machine |
| `scripts/verify_dist.py` | Wheel/sdist contents, metadata, PEP 561 marker, and clean import verification |
| `.github/workflows/ci.yml` | Full-SHA-pinned Python 3.13/3.14 validation matrix |

---

### Task 1: Establish an installable typed package skeleton

**Files:**
- Create: `.python-version`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/hermes_agent_api_client/__init__.py`
- Create: `src/hermes_agent_api_client/py.typed`
- Create: `tests/test_package.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Consumes: Approved distribution/import names and dependency constraints from the design.
- Produces: Importable package `hermes_agent_api_client`, static `__version__ == "0.1.0"`, and locked development environment used by all later tasks.

- [ ] **Step 1: Write the package metadata test before the package exists**

Create `tests/test_package.py` with this initial contract:

```python
from __future__ import annotations

from importlib.metadata import metadata, version
from pathlib import Path


def test_distribution_metadata_and_typed_marker() -> None:
    assert version("hermes-agent-api-client") == "0.1.0"
    package_metadata = metadata("hermes-agent-api-client")
    assert package_metadata["Requires-Python"] == ">=3.13"
    assert package_metadata["License-Expression"] == "UPL-1.0"

    package_root = Path(__file__).parents[1] / "src" / "hermes_agent_api_client"
    assert (package_root / "py.typed").is_file()


def test_public_version_is_static() -> None:
    import hermes_agent_api_client

    assert hermes_agent_api_client.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the focused test and confirm the expected failure**

Run:

```bash
uv run --no-project pytest tests/test_package.py -q
```

Expected: failure because no project environment or installed distribution exists yet. Do not weaken the test.

- [ ] **Step 3: Create exact project configuration**

Create `.python-version` containing `3.13` and create `pyproject.toml` with these sections:

```toml
[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[project]
name = "hermes-agent-api-client"
version = "0.1.0"
description = "Typed async client for the Hermes Agent API Server"
readme = "README.md"
requires-python = ">=3.13"
license = "UPL-1.0"
license-files = ["LICENSE"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Framework :: AsyncIO",
  "License :: OSI Approved :: Universal Permissive License (UPL)",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Typing :: Typed",
]
dependencies = [
  "httpx>=0.28.1,<1",
  "pydantic>=2.13.4,<3",
]

[project.urls]
Repository = "https://github.com/Djelibeybi/hermes-agent-api-client"
Issues = "https://github.com/Djelibeybi/hermes-agent-api-client/issues"

[dependency-groups]
dev = [
  "coverage[toml]==7.15.1",
  "pytest==9.1.1",
  "pytest-asyncio==1.4.0",
  "respx==0.23.1",
  "ruff==0.15.21",
]

[tool.uv]
required-version = "==0.11.28"
default-groups = ["dev"]

[tool.uv.build-backend]
source-include = ["uv.lock"]

[tool.pytest.ini_options]
addopts = "-ra --strict-config --strict-markers"
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
branch = true
source = ["hermes_agent_api_client"]

[tool.coverage.report]
fail_under = 100
show_missing = true
skip_covered = true

[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["ALL"]
ignore = ["COM812", "ISC001"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "SLF001"]

[tool.pyright]
include = ["src", "tests"]
pythonVersion = "3.13"
typeCheckingMode = "strict"
```

- [ ] **Step 4: Create the minimal package and project documentation**

Create `src/hermes_agent_api_client/__init__.py`:

```python
"""Typed async client for the Hermes Agent API Server."""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

Create an empty `src/hermes_agent_api_client/py.typed`, an empty `tests/__init__.py`, and a README that states only the approved 0.1.0 scope, Python floor, install command, UPL license, and that API examples will be added with the client task. Do not claim PyPI availability before publication.

Create `.gitignore` containing:

```gitignore
.coverage
.DS_Store
.pytest_cache/
.ruff_cache/
.venv/
__pycache__/
build/
dist/
htmlcov/
*.egg-info/
*.py[cod]
```

- [ ] **Step 5: Lock, sync, and run the package test**

Run:

```bash
uv lock
uv sync --locked --all-groups
uv run pytest tests/test_package.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Run initial formatting and metadata checks**

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv build
```

Expected: all commands exit 0 and `dist/` contains one wheel and one sdist.

- [ ] **Step 7: Commit the skeleton**

```bash
git add .python-version .gitignore README.md pyproject.toml uv.lock src tests/test_package.py tests/__init__.py
git commit -S -s -m "build: establish typed client package"
```

---

### Task 2: Migrate immutable models, safe errors, and capability validation to Pydantic

**Files:**
- Create: `src/hermes_agent_api_client/models.py`
- Create: `src/hermes_agent_api_client/protocol.py`
- Create: `tests/helpers/__init__.py`
- Create: `tests/helpers/hermes.py`
- Create: `tests/fixtures/hermes/v2026.7.7.2/capabilities/supported.json`
- Create: `tests/fixtures/hermes/v2026.7.7.2/provenance.json`
- Create: `tests/test_protocol.py`
- Modify: `src/hermes_agent_api_client/__init__.py`

**Interfaces:**
- Consumes: Pydantic 2.13.4 and the Phase 1 capability fixture/provenance from `hermes_conversation`.
- Produces: Frozen public event/capability models, `HermesEvent` union, safe public exception hierarchy, and internal `validate_capabilities(value: object) -> HermesCapabilities`.

- [ ] **Step 1: Migrate fixtures and helper tests using normal package boundaries**

Use `apply_patch` to create the capability fixture and provenance document with byte-for-byte content from:

```text
hermes_conversation/tests/fixtures/hermes/v2026.7.7.2/capabilities/supported.json
hermes_conversation/tests/fixtures/hermes/v2026.7.7.2/provenance.json
hermes_conversation/tests/helpers/hermes.py
```

Create `tests/helpers/__init__.py`. In `tests/test_protocol.py`, migrate the pure model, validation, immutability, concurrency, retryability, safe-state, and canary tests from `hermes_conversation/tests/test_capabilities.py`. Replace dynamic module loading with these imports:

```python
from hermes_agent_api_client import (
    AssistantDeltaEvent,
    HermesAuthenticationError,
    HermesCapabilities,
    HermesContractError,
    HermesEvent,
    HermesHttpStatusError,
    HermesProtocolError,
    HermesTransportError,
    KeepaliveEvent,
    TerminalEvent,
    TerminalOutcome,
    ToolProgressEvent,
    UsageEvent,
)
from hermes_agent_api_client.models import FailureCategory
from hermes_agent_api_client.protocol import validate_capabilities
```

Update immutability assertions from dataclass `FrozenInstanceError` to Pydantic's frozen-instance `ValidationError`. Add assertions that additive unknown fields at the root, `auth`, and `features` levels are ignored, while missing/wrong required values fail with a sanitized `HermesProtocolError`.

- [ ] **Step 2: Run protocol tests and confirm import failure**

Run:

```bash
uv run pytest tests/test_protocol.py -q
```

Expected: collection fails because the exported models and errors do not exist.

- [ ] **Step 3: Implement frozen public models**

Create `models.py` with a shared base and these exact public shapes:

```python
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)


class FailureCategory(StrEnum):
    AUTHENTICATION = "authentication"
    HTTP_STATUS = "http_status"
    TRANSPORT = "transport"
    PROTOCOL = "protocol"


class TerminalOutcome(StrEnum):
    SUCCESS = "success"
    LENGTH = "length"
    UPSTREAM_ERROR = "upstream_error"


class HermesCapabilities(_FrozenModel):
    object: str
    platform: str
    auth_type: str
    auth_required: bool
    chat_completions: bool
    chat_completions_streaming: bool


class AssistantDeltaEvent(_FrozenModel):
    text: str


class ToolProgressEvent(_FrozenModel):
    tool_name: str
    status: str


class UsageEvent(_FrozenModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class KeepaliveEvent(_FrozenModel):
    pass


class TerminalEvent(_FrozenModel):
    outcome: TerminalOutcome


type HermesEvent = (
    AssistantDeltaEvent
    | ToolProgressEvent
    | UsageEvent
    | KeepaliveEvent
    | TerminalEvent
)
```

- [ ] **Step 4: Implement safe errors and Pydantic capability wire models**

Create `protocol.py` by preserving the Phase 1 exception metadata contract and moving `FailureCategory` imports to `models.py`. Add strict frozen internal models:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError


class _WireModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)


class _AuthWire(_WireModel):
    type: Literal["bearer"]
    required: Literal[True]


class _FeaturesWire(_WireModel):
    chat_completions: Literal[True]
    chat_completions_streaming: Literal[True]


class _CapabilitiesWire(_WireModel):
    object: Literal["hermes.api_server.capabilities"]
    platform: Literal["hermes-agent"]
    auth: _AuthWire
    features: _FeaturesWire
```

Implement validation without retaining `ValidationError` context:

```python
def _parse_capabilities(value: object) -> _CapabilitiesWire | None:
    try:
        return _CapabilitiesWire.model_validate(value)
    except ValidationError:
        return None


def validate_capabilities(value: object) -> HermesCapabilities:
    parsed = _parse_capabilities(value)
    if parsed is None:
        raise HermesProtocolError
    return HermesCapabilities(
        object=parsed.object,
        platform=parsed.platform,
        auth_type=parsed.auth.type,
        auth_required=parsed.auth.required,
        chat_completions=parsed.features.chat_completions,
        chat_completions_streaming=parsed.features.chat_completions_streaming,
    )
```

Do not attach Pydantic errors or raw values to any public exception.

- [ ] **Step 5: Export the deliberate public surface**

Update `__init__.py` to import the public models from `models.py`, errors from `protocol.py`, and list every design-approved name in `__all__`. Export `HermesEvent`, not the old internal name `HermesStreamEvent`. Keep `validate_capabilities` internal to the `protocol` module.

- [ ] **Step 6: Run focused and security-sensitive tests**

Run:

```bash
uv run pytest tests/test_protocol.py -q
uv run pytest tests/test_protocol.py -q -k "canary or safe or context or cause"
```

Expected: all protocol tests pass; the focused security subset selects and passes tests rather than reporting zero selected.

- [ ] **Step 7: Run lint and strict types**

```bash
uv run ruff format .
uv run ruff check .
npx --yes pyright@1.1.411
```

Expected: all commands exit 0.

- [ ] **Step 8: Commit contracts**

```bash
git add src/hermes_agent_api_client tests/helpers tests/fixtures tests/test_protocol.py
git commit -S -s -m "feat: add typed Hermes protocol contracts"
```

---

### Task 3: Migrate the bounded SSE state machine and Pydantic wire events

**Files:**
- Create: `src/hermes_agent_api_client/sse.py`
- Create: `tests/fixtures/hermes/v2026.7.7.2/chat_completions/complete.sse`
- Create: `tests/test_sse.py`
- Modify: `src/hermes_agent_api_client/protocol.py`

**Interfaces:**
- Consumes: `HermesEvent`, public event models, `TerminalOutcome`, and `HermesProtocolError` from Task 2.
- Produces: Internal `async_decode_hermes_sse(byte_chunks: AsyncIterable[bytes]) -> AsyncIterator[HermesEvent]` used by Task 4.

- [ ] **Step 1: Migrate the complete SSE contract tests**

Use `apply_patch` to create the golden SSE fixture byte-for-byte from `hermes_conversation/tests/fixtures/hermes/v2026.7.7.2/chat_completions/complete.sse`. Migrate all behavior tests from `hermes_conversation/tests/test_sse.py`, replace dynamic loading with:

```python
from hermes_agent_api_client import (
    AssistantDeltaEvent,
    HermesProtocolError,
    KeepaliveEvent,
    TerminalEvent,
    TerminalOutcome,
    ToolProgressEvent,
    UsageEvent,
)
from hermes_agent_api_client.sse import (
    MAX_EVENT_DATA_CHARS,
    MAX_PENDING_BYTES,
    async_decode_hermes_sse,
)
```

Remove `_require_sse` and call `async_decode_hermes_sse` directly. Preserve every byte-partition, CR/LF/CRLF, concurrency, cancellation, bound, terminal, `[DONE]`, keepalive, and canary assertion. Change additive JSON-field cases to expect successful validation where the approved design requires `extra="ignore"`.

- [ ] **Step 2: Run SSE tests and confirm missing module failure**

```bash
uv run pytest tests/test_sse.py -q
```

Expected: collection fails with `ModuleNotFoundError: hermes_agent_api_client.sse`.

- [ ] **Step 3: Add strict internal event wire models**

In `protocol.py`, import `Annotated`, `Field`, and `StringConstraints`, then add
internal `_WireModel` subclasses with constrained fields:

```python
type _NonEmptyString = Annotated[str, StringConstraints(min_length=1)]
type _NonNegativeInteger = Annotated[int, Field(ge=0)]


class _ToolProgressWire(_WireModel):
    tool: _NonEmptyString
    status: _NonEmptyString


class _DeltaWire(_WireModel):
    role: Literal["assistant"] | None = None
    content: str | None = None


class _ChoiceWire(_WireModel):
    delta: _DeltaWire
    finish_reason: Literal["stop", "length", "error"] | None


class _UsageWire(_WireModel):
    prompt_tokens: _NonNegativeInteger
    completion_tokens: _NonNegativeInteger
    total_tokens: _NonNegativeInteger


class _ChatChunkWire(_WireModel):
    choices: Annotated[list[_ChoiceWire], Field(min_length=1, max_length=1)]
    usage: _UsageWire | None = None
```

The strict configuration rejects booleans as integers. Provide internal parsing
functions that return `None` after `ValidationError`; the SSE module raises a
fresh `HermesProtocolError` outside the exception context.

- [ ] **Step 4: Port the framing state machine with typed wire translation**

Create `sse.py` from the reviewed Phase 1 state machine. Preserve constants
`MAX_PENDING_BYTES = 262_144` and `MAX_EVENT_DATA_CHARS = 65_536`, and preserve
the exact public-to-internal signature
`async_decode_hermes_sse(byte_chunks: AsyncIterable[bytes]) -> AsyncIterator[HermesEvent]`.

```python
MAX_PENDING_BYTES = 262_144
MAX_EVENT_DATA_CHARS = 65_536
```

Use the Task 3 internal wire parsers instead of handwritten JSON-shape checks. Keep framing logic independent of httpx. Preserve deferred terminal delivery rules: post-terminal application data fails, duplicate `[DONE]` fails, ordinary EOF without a terminal fails, and cancellation is never translated.

- [ ] **Step 5: Run SSE tests and eliminate coverage gaps**

```bash
uv run coverage erase
uv run coverage run -m pytest tests/test_protocol.py tests/test_sse.py
uv run coverage report
```

Expected: tests pass and package line/branch coverage is 100%. Add targeted tests for any reported uncovered branch; do not use coverage exclusions for reachable protocol behavior.

- [ ] **Step 6: Run lint and strict types**

```bash
uv run ruff format .
uv run ruff check .
npx --yes pyright@1.1.411
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit SSE decoding**

```bash
git add src/hermes_agent_api_client/protocol.py src/hermes_agent_api_client/sse.py tests/fixtures tests/test_sse.py
git commit -S -s -m "feat: add bounded Hermes SSE decoding"
```

---

### Task 4: Migrate bounded HTTP capability and streaming operations

**Files:**
- Create: `src/hermes_agent_api_client/client.py`
- Create: `tests/test_transport.py`

**Interfaces:**
- Consumes: `validate_capabilities`, `async_decode_hermes_sse`, public events, and safe errors from Tasks 2-3.
- Produces: Internal `_probe_capabilities` and `_stream_chat_events` functions with caller-owned HTTP client semantics; Task 5 wraps these in the public class.

- [ ] **Step 1: Migrate transport tests without Home Assistant terminology**

Create `tests/test_transport.py` from the HTTP portions of `hermes_conversation/tests/test_capabilities.py` and all of `hermes_conversation/tests/test_http_ownership.py`. Replace dynamic imports with normal package imports and rename descriptions from "Home Assistant-managed" to "injected". Import private transport functions explicitly for focused tests:

```python
from hermes_agent_api_client.client import (
    _CAPABILITIES_DEADLINE_SECONDS,
    _CHAT_STREAM_READ_TIMEOUT_SECONDS,
    _MAX_CAPABILITIES_BYTES,
    _probe_capabilities,
    _stream_chat_events,
)
```

Preserve endpoint, encoded-path, exact-size, trickle timeout, status matrix, request failure, JSON failure, URL userinfo, invalid bearer, invalid mapping, response cleanup, terminal-after-cleanup, cancellation, repeat, and concurrency tests. Add assertions that `follow_redirects=False` is passed for both operations.

- [ ] **Step 2: Run transport tests and confirm missing implementation**

```bash
uv run pytest tests/test_transport.py -q
```

Expected: collection fails because `hermes_agent_api_client.client` does not exist.

- [ ] **Step 3: Implement normalized endpoint, safe auth, and serialization helpers**

Port the Phase 1 helpers with these stable signatures:

- `_normalize_base_url(base_url: str) -> httpx.URL`
- `_operation_url(base_url: httpx.URL, path: str) -> httpx.URL`
- `_request_headers(bearer_key: str, *, json_body: bool = False) -> dict[str, str]`
- `_serialize_request(request: Mapping[str, object]) -> bytes`
- `_status_failure(status_code: int) -> HermesContractError`

Normalize and reject invalid schemes, relative URLs, missing hosts, and URL userinfo without retaining the rejected value. Preserve encoded base paths. Allow only ASCII visible bearer characters. Serialize with `ensure_ascii=False`, `allow_nan=False`, and compact separators; translate failures after leaving the parser exception context.

- [ ] **Step 4: Implement bounded capability probing**

Port the current constants unchanged:

```python
_CAPABILITY_REQUEST_TIMEOUT = httpx.Timeout(10.0)
_CAPABILITIES_DEADLINE_SECONDS = 10.0
_MAX_CAPABILITIES_BYTES = 65_536
```

Implement `_probe_capabilities(http_client: httpx.AsyncClient, base_url:
httpx.URL, headers: Mapping[str, str]) -> HermesCapabilities`.

Use `asyncio.timeout`, incremental response reading, declared/observed byte bounds, `follow_redirects=False`, response-scope cleanup, safe status classification, safe JSON parsing, and `validate_capabilities`.

- [ ] **Step 5: Implement streaming operation with response-owned lifetime**

Preserve:

```python
_HERMES_SSE_KEEPALIVE_SECONDS = 30.0
_CHAT_STREAM_READ_TIMEOUT_SECONDS = 45.0
_CHAT_STREAM_TIMEOUT = httpx.Timeout(
    10.0,
    read=_CHAT_STREAM_READ_TIMEOUT_SECONDS,
)
```

Implement `_stream_chat_events(http_client: httpx.AsyncClient, base_url:
httpx.URL, headers: Mapping[str, str], request: Mapping[str, object]) ->
AsyncIterator[HermesEvent]`.

Pass `follow_redirects=False`. Yield non-terminal events while the response is open, retain the terminal locally, close the response, then yield the terminal. Translate httpx failures only after leaving their active exception contexts. Propagate `CancelledError` unchanged.
Build a fresh request-header mapping containing the stored authorization header
plus `Content-Type: application/json`; never mutate the client instance's
stored authentication mapping.

- [ ] **Step 6: Run transport tests, coverage, lint, and types**

```bash
uv run coverage erase
uv run coverage run -m pytest tests/test_protocol.py tests/test_sse.py tests/test_transport.py
uv run coverage report
uv run ruff format .
uv run ruff check .
npx --yes pyright@1.1.411
```

Expected: all tests pass, coverage is 100%, and static checks exit 0.

- [ ] **Step 7: Commit transport operations**

```bash
git add src/hermes_agent_api_client/client.py tests/test_transport.py
git commit -S -s -m "feat: add bounded Hermes HTTP transport"
```

---

### Task 5: Add the public async context-managed client

**Files:**
- Modify: `src/hermes_agent_api_client/client.py`
- Modify: `src/hermes_agent_api_client/__init__.py`
- Create: `tests/test_client_lifecycle.py`

**Interfaces:**
- Consumes: Internal transport functions from Task 4.
- Produces: Public `HermesAgentApiClient` with `probe_capabilities()` and `stream_chat_events()` methods and exact owned/injected lifecycle semantics.

- [ ] **Step 1: Write lifecycle tests before the public class**

Create `tests/test_client_lifecycle.py` with one test for each exact behavior:

- `test_owned_client_is_created_on_entry_and_closed_on_exit`
- `test_owned_client_closes_when_context_body_raises`
- `test_injected_client_is_never_closed`
- `test_non_default_verify_is_rejected_with_injected_client`
- `test_operations_before_entry_raise_constant_runtime_error`
- `test_operations_after_exit_raise_constant_runtime_error`
- `test_double_entry_is_rejected`
- `test_reentry_after_exit_is_rejected`
- `test_bound_endpoint_and_auth_are_reused_across_operations`
- `test_owned_client_honors_verify_false`

Patch `httpx.AsyncClient` with a typed factory spy for owned-client tests. Assert exact safe messages `"HermesAgentApiClient is not active"` and `"HermesAgentApiClient instances are single-use"`; assert no endpoint or key appears in either message.

- [ ] **Step 2: Run lifecycle tests and confirm missing public class**

```bash
uv run pytest tests/test_client_lifecycle.py -q
```

Expected: collection fails because `HermesAgentApiClient` is not exported.

- [ ] **Step 3: Implement the single-use client state machine**

Add this public constructor and methods to `client.py`:

```python
from collections.abc import AsyncIterator, Mapping
from types import TracebackType
from typing import Self
import ssl


class HermesAgentApiClient:
    def __init__(
        self,
        base_url: str,
        bearer_key: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        verify: ssl.SSLContext | bool | None = None,
    ) -> None:
        if http_client is not None and verify is not None:
            raise ValueError(
                "verify cannot be supplied with an injected HTTP client"
            )
        self._base_url = _normalize_base_url(base_url)
        self._headers = _request_headers(bearer_key)
        self._injected_http_client = http_client
        self._verify = True if verify is None else verify
        self._active_http_client: httpx.AsyncClient | None = None
        self._entered = False
        self._exited = False

    async def __aenter__(self) -> Self:
        if self._entered or self._exited:
            raise RuntimeError("HermesAgentApiClient instances are single-use")
        active = self._injected_http_client
        if active is None:
            active = httpx.AsyncClient(
                verify=self._verify,
                follow_redirects=False,
            )
        self._active_http_client = active
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        active = self._active_http_client
        self._active_http_client = None
        self._exited = True
        if active is not None and self._injected_http_client is None:
            await active.aclose()

    def _require_active_client(self) -> httpx.AsyncClient:
        if self._active_http_client is None:
            raise RuntimeError("HermesAgentApiClient is not active")
        return self._active_http_client

    async def probe_capabilities(self) -> HermesCapabilities:
        return await _probe_capabilities(
            self._require_active_client(),
            self._base_url,
            self._headers,
        )

    async def stream_chat_events(
        self,
        request: Mapping[str, object],
    ) -> AsyncIterator[HermesEvent]:
        async for event in _stream_chat_events(
            self._require_active_client(),
            self._base_url,
            self._headers,
            request,
        ):
            yield event
```

Do not add public `open`, `close`, or retry methods.

- [ ] **Step 4: Export the class and verify only approved names**

Import `HermesAgentApiClient` from `client.py` in `__init__.py`, add it to `__all__`, and extend `tests/test_package.py` to assert:

```python
assert set(hermes_agent_api_client.__all__) == {
    "AssistantDeltaEvent",
    "HermesAgentApiClient",
    "HermesAuthenticationError",
    "HermesCapabilities",
    "HermesContractError",
    "HermesEvent",
    "HermesHttpStatusError",
    "HermesProtocolError",
    "HermesTransportError",
    "KeepaliveEvent",
    "TerminalEvent",
    "TerminalOutcome",
    "ToolProgressEvent",
    "UsageEvent",
    "__version__",
}
```

- [ ] **Step 5: Run lifecycle and full package tests**

```bash
uv run pytest tests/test_client_lifecycle.py -q
uv run coverage erase
uv run coverage run -m pytest
uv run coverage report
```

Expected: all tests pass and line/branch coverage is 100%.

- [ ] **Step 6: Run lint, Pyright, and public type completeness**

```bash
uv run ruff format .
uv run ruff check .
npx --yes pyright@1.1.411
npx --yes pyright@1.1.411 --verifytypes hermes_agent_api_client --ignoreexternal
```

Expected: all commands exit 0 and verifytypes reports 100% type completeness.

- [ ] **Step 7: Commit the public client**

```bash
git add src/hermes_agent_api_client tests/test_client_lifecycle.py tests/test_package.py
git commit -S -s -m "feat: add context-managed Hermes client"
```

---

### Task 6: Prove distributable artifacts and CI reproducibility

**Files:**
- Modify: `README.md`
- Create: `scripts/verify_dist.py`
- Create: `.github/workflows/ci.yml`
- Modify: `tests/test_package.py`

**Interfaces:**
- Consumes: Complete public package from Tasks 1-5.
- Produces: User-facing documentation, deterministic distribution validation, and full-SHA-pinned CI evidence on Python 3.13/3.14.

- [ ] **Step 1: Write failing distribution-content tests**

Extend `tests/test_package.py` with a test that invokes `uv build`, opens the generated wheel with `zipfile.ZipFile` and sdist with `tarfile.open`, and asserts:

```python
required_wheel_suffixes = {
    "hermes_agent_api_client/__init__.py",
    "hermes_agent_api_client/client.py",
    "hermes_agent_api_client/models.py",
    "hermes_agent_api_client/protocol.py",
    "hermes_agent_api_client/sse.py",
    "hermes_agent_api_client/py.typed",
}
assert required_wheel_suffixes <= wheel_names
assert not any("tests/" in name for name in wheel_names)
assert not any("fixtures/" in name for name in wheel_names)
assert any(name.endswith("LICENSE") for name in wheel_names)
```

Also assert the sdist contains `pyproject.toml`, `README.md`, `LICENSE`, package
source, and `uv.lock`; assert that it contains no `tests/`, fixture paths,
`.coverage`, `.venv`, or `dist` recursion.

- [ ] **Step 2: Run the distribution test and confirm the missing verifier/documentation gap**

```bash
rm -rf dist
uv run pytest tests/test_package.py -q
```

Expected: the new distribution test fails until archive verification and package inclusion configuration are complete.

- [ ] **Step 3: Complete README with exact supported behavior**

Document:

- Installation from Git at an immutable commit before PyPI publication.
- The async-context-manager example with both owned and injected clients.
- Injected/owned client closure and TLS `verify` rules.
- Supported endpoints: `GET /v1/capabilities` and streaming `POST /v1/chat/completions` only.
- Public events and safe error metadata.
- Hermes compatibility target v2026.7.7.2 and fixture-derived, non-live evidence scope.
- Security warning that Hermes API access exposes the configured agent toolset.
- Development commands using `uv sync --locked --all-groups`, Ruff, pytest/coverage, Pyright, and `uv build`.
- UPL-1.0 license.

Do not claim PyPI publication, Home Assistant compatibility, live-server validation, retries, or unsupported endpoints.

- [ ] **Step 4: Create a standalone artifact verifier**

Create `scripts/verify_dist.py` using only the standard library. It must:

1. Require exactly one `.whl` and one `.tar.gz` argument.
2. Validate the required/forbidden names from Step 1.
3. Read wheel `METADATA` and assert name, version, Python floor, UPL expression, and both runtime dependency ranges.
4. Extract the wheel to a temporary directory.
5. Launch `sys.executable -I -c` in a subprocess, pass the extraction directory
   as `sys.argv[1]`, insert it at `sys.path[0]` inside the isolated script, and
   import every name in `__all__`.
6. Print only `distribution verification passed` on success.

Return non-zero with constant messages on malformed archives; never print archive file contents.

- [ ] **Step 5: Add full-SHA-pinned CI**

Create `.github/workflows/ci.yml` with read-only permissions, concurrency cancellation, and Python `3.13`/`3.14` matrix. Pin actions exactly:

```yaml
permissions:
  contents: read

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.13", "3.14"]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6.3.0
        with:
          python-version: ${{ matrix.python-version }}
      - uses: astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990 # v8.3.2
        with:
          version: "0.11.28"
          enable-cache: true
      - run: uv sync --locked --all-groups --python "${{ matrix.python-version }}"
      - run: uv run ruff format --check .
      - run: uv run ruff check .
      - run: uv run coverage run -m pytest
      - run: uv run coverage report
      - run: npx --yes pyright@1.1.411
      - run: npx --yes pyright@1.1.411 --verifytypes hermes_agent_api_client --ignoreexternal
      - run: uv build
      - run: uv run python scripts/verify_dist.py dist/*.whl dist/*.tar.gz
```

Add top-level `name`, pull-request/push triggers for `main`, and a concurrency group keyed by workflow and ref. Do not add publish permissions or secrets.

- [ ] **Step 6: Run every local release gate from a clean build directory**

```bash
rm -rf build dist
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run coverage erase
uv run coverage run -m pytest
uv run coverage report
npx --yes pyright@1.1.411
npx --yes pyright@1.1.411 --verifytypes hermes_agent_api_client --ignoreexternal
uv build
uv run python scripts/verify_dist.py dist/*.whl dist/*.tar.gz
```

Expected: every command exits 0; coverage and type completeness report 100%; verifier prints `distribution verification passed`.

- [ ] **Step 7: Verify the wheel in an isolated temporary uv environment**

```bash
tmpdir=$(mktemp -d)
uv venv --python 3.13 "$tmpdir/venv"
uv pip install --python "$tmpdir/venv/bin/python" dist/*.whl
"$tmpdir/venv/bin/python" -I -c 'import hermes_agent_api_client as h; assert h.__version__ == "0.1.0"; assert h.HermesAgentApiClient'
rm -rf "$tmpdir"
```

Expected: all commands exit 0 with no output from the import smoke test.

- [ ] **Step 8: Commit distribution and CI proof**

```bash
git add README.md scripts/verify_dist.py .github/workflows/ci.yml tests/test_package.py
git commit -S -s -m "ci: verify client distributions"
```

---

### Task 7: Final package audit and immutable handoff

**Files:**
- Modify only if a failing gate identifies a concrete defect.

**Interfaces:**
- Consumes: Complete package and CI configuration.
- Produces: One verified signed commit SHA suitable for pushing and pinning in the later `hermes_conversation` cutover plan.

- [ ] **Step 1: Confirm repository scope and absence of private paths**

```bash
git status --short --branch
private_root_pattern="/""Volumes/|/""Users/|file:""//|[A-Za-z]:\\\\"
rg -n -i "$private_root_pattern" --glob '*.md' --glob '*.rst' --glob '*.txt' .
rg -n 'homeassistant|custom_components' src tests README.md pyproject.toml
```

Expected: clean branch status; the private-path scan returns no matches; the Home Assistant scan returns no matches.

- [ ] **Step 2: Run the complete verification sequence again**

```bash
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run coverage erase
uv run coverage run -m pytest
uv run coverage report
npx --yes pyright@1.1.411
npx --yes pyright@1.1.411 --verifytypes hermes_agent_api_client --ignoreexternal
rm -rf build dist
uv build
uv run python scripts/verify_dist.py dist/*.whl dist/*.tar.gz
git diff --check
```

Expected: every gate exits 0 with 100% coverage and type completeness.

- [ ] **Step 3: Inspect signed/DCO history and final diff**

```bash
git log --show-signature --format=fuller --stat origin/main..HEAD
git diff --stat origin/main..HEAD
git status --short --branch
```

Expected: every implementation commit has a good GPG signature and `Signed-off-by`; the working tree is clean; only package-scoped files are present.

- [ ] **Step 4: Push only after explicit authorization**

Report the final commit SHA and verification evidence. Do not push automatically. After the user pushes the package commit, write the separate `hermes_conversation` cutover plan with that exact public SHA and verify GitHub can fetch it.
