# Hermes Capability Identity Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a stronger package-root capability contract that returns a bounded Hermes model/profile name and distinguishes identity failures from missing Chat Completions support without weakening any existing sanitization guarantee.

**Architecture:** Capability parsing becomes a three-stage pipeline: reduce identity to a safe private failure kind, reduce required Chat Completions support to a safe private failure kind, then run the complete strict Pydantic wire model. Direct validation and HTTP probing carry only that private failure kind until raw inputs and transport state have been cleared, then raise fresh package-root exception subclasses from raw-input-free frames.

**Tech Stack:** Python 3.13+, Pydantic 2.13.4, HTTPX 0.28.1, pytest 9.1.1, pytest-cov 7.1.0, basedpyright 1.39.9, Ruff 0.15.21, uv 0.11.28, prek 0.4.9, python-semantic-release 10.6.1.

## Global Constraints

- Preserve the user-owned `pyproject.toml` and `uv.lock` basedpyright migration and the untracked `.idea/` directory; never overwrite, discard, stage, build, or publish `.idea/`.
- Keep protocol parsing, wire models, capability fixtures, error classification, and sanitization tests in this repository; do not modify Hermes Conversation.
- Compatibility evidence comes only from Hermes Agent tag `v2026.7.7.2` at commit `9de9c25f620ff7f1ce0fd5457d596052d5159596`, never a moving branch.
- `HermesCapabilities.model` preserves the advertised string exactly and accepts 1 through 255 Unicode code points only when at least one code point is non-whitespace.
- `HermesIdentityError` and `HermesCapabilityError` inherit `HermesProtocolError`, remain non-retryable protocol failures, and expose only `category`, `status_code`, and `retryable`.
- Identity classification precedes required-feature classification; authentication, streaming, model, JSON, body-size, and unrelated schema failures remain generic `HermesProtocolError` outcomes.
- Preserve literal-`True` support for `chat_completions_streaming`.
- Use Context7-backed current Pydantic, basedpyright, uv, and python-semantic-release behavior recorded during planning.
- Use pytest-cov through `uv run --no-sync pytest`; do not invoke the `coverage` CLI directly.
- Keep prek installed as the commit-time hook; CI continues to run direct commands rather than `prek run --all-files`.
- Every implementation commit uses conventional syntax, `git commit -S -s`, and a verified good GPG signature.
- Do not manually publish or manually choose the next version; the merged `feat:` commit drives the repository's pre-1.0 semantic-release policy.

## File Structure

- Modify `.github/workflows/ci.yml`: finish the in-progress basedpyright command migration while retaining direct CI gates.
- Modify `prek.toml`: finish the basedpyright hook migration while retaining prek's installed commit-hook role.
- Modify `pyproject.toml`: preserve the dependency migration, rename the tool table, and make semantic-release verify stamped artifacts.
- Preserve and stage `uv.lock`: retain the user's basedpyright resolution exactly after locked validation.
- Modify `tests/fixtures/hermes/v2026.7.7.2/capabilities/supported.json`: replace the minimized fixture with the immutable-tag-captured capability response containing `model`.
- Modify `tests/fixtures/hermes/v2026.7.7.2/provenance.json`: record exact capture provenance and the new SHA-256.
- Modify `src/hermes_agent_api_client/models.py`: add the frozen bounded public `model` field and its direct-construction invariant.
- Modify `src/hermes_agent_api_client/protocol.py`: add typed failures, private failure reduction, staged classification, and wire validation.
- Modify `src/hermes_agent_api_client/client.py`: preserve typed capability failures through bounded response cleanup.
- Modify `src/hermes_agent_api_client/__init__.py`: export both new failure types and derive `__version__` from installed metadata.
- Modify `scripts/verify_dist.py`: derive the expected artifact version from current project metadata rather than a duplicated literal.
- Modify `tests/test_protocol.py`: cover model semantics, classification precedence, inheritance, replay, and direct sanitization.
- Modify `tests/test_transport.py`: cover exact typed probe propagation and transport-frame sanitization.
- Modify `tests/test_client_lifecycle.py`: cover the package's public client returning `model` and preserving typed errors without bound-state leakage.
- Modify `tests/test_package.py`: cover exports, star imports, dynamic version consistency, built-wheel imports, and verifier version behavior.
- Modify `README.md`: document the supported document, model rule, taxonomy, and a package-root-only consumer example.
- Modify `CHANGELOG.md`: add an Unreleased feature entry without selecting the release version.

---

### Task 1: Complete the Existing Basedpyright Migration

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `prek.toml`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: the existing user-owned `basedpyright>=1.39.9` dependency and lock resolution.
- Produces: `uv run --no-sync basedpyright` and `uv run --no-sync basedpyright --verifytypes hermes_agent_api_client --ignoreexternal` as the exact local and CI type gates.

- [x] **Step 1: Confirm the preserved baseline before editing configuration**

Run:

```bash
git status --short --branch
git diff -- pyproject.toml uv.lock
uv lock --check
uv tree --locked --outdated --all-groups
```

Expected: only the approved design/plan history plus user-owned `pyproject.toml`, `uv.lock`, and `.idea/` state; `uv lock --check` exits 0. The outdated report confirms every direct dependency is current and identifies only transitive releases excluded by their direct package constraints.

- [x] **Step 2: Finish the command and configuration rename**

Change the configuration table and hook commands to:

```toml
[tool.basedpyright]
include = ["src", "tests"]
ignore = ["tests/helpers/hermes.py"]
pythonVersion = "3.13"
typeCheckingMode = "strict"
venv = ".venv"
venvPath = "."
```

```toml
[[repos.hooks]]
id = "basedpyright"
name = "basedpyright"
entry = "uv run --no-sync basedpyright"
language = "system"
pass_filenames = false
always_run = true
priority = 10

[[repos.hooks]]
id = "basedpyright-verifytypes"
name = "basedpyright verifytypes"
entry = "uv run --no-sync basedpyright --verifytypes hermes_agent_api_client --ignoreexternal"
language = "system"
pass_filenames = false
always_run = true
priority = 10
```

Change the two CI steps to:

```yaml
      - run: uv run --no-sync basedpyright
      - run: uv run --no-sync basedpyright --verifytypes hermes_agent_api_client --ignoreexternal
```

Keep existing `# pyright: ignore[...]` source comments: basedpyright intentionally supports pyright-compatible suppression directives.

- [x] **Step 3: Synchronize exactly once and prove both type gates**

Run:

```bash
uv sync --locked --all-groups --no-editable
uv run --no-sync basedpyright
uv run --no-sync basedpyright --verifytypes hermes_agent_api_client --ignoreexternal
uv run --no-sync prek validate-config prek.toml
```

Expected: locked sync succeeds; the project check reports 0 errors; verifytypes reports 100% type completeness; prek configuration is valid.

- [x] **Step 4: Commit only the completed migration**

Run:

```bash
git add pyproject.toml uv.lock prek.toml .github/workflows/ci.yml
git commit -S -s -m "chore: complete basedpyright migration"
git log -1 --show-signature --format=fuller
```

Expected: every installed hook runs with basedpyright, the commit contains a DCO sign-off, and GPG reports a good signature from Avi Miller.

---

### Task 2: Capture the Tagged Fixture and Add the Bounded Model Contract

**Files:**
- Modify: `tests/fixtures/hermes/v2026.7.7.2/capabilities/supported.json`
- Modify: `tests/fixtures/hermes/v2026.7.7.2/provenance.json`
- Modify: `tests/test_protocol.py`
- Modify: `src/hermes_agent_api_client/models.py`
- Modify: `src/hermes_agent_api_client/protocol.py`

**Interfaces:**
- Consumes: immutable upstream handler output with top-level `model` and existing `validate_capabilities(value: object) -> HermesCapabilities`.
- Produces: `HermesCapabilities.model: str`, preserving the exact valid wire value with a 255-code-point maximum.

- [x] **Step 1: Capture the response from the immutable upstream handler**

Create a temporary checkout outside the repository, detach it at the exact commit, and verify the tag resolves to that commit:

```bash
capture_root="$(mktemp -d)"
git clone --filter=blob:none --no-checkout https://github.com/NousResearch/hermes-agent.git "$capture_root/hermes-agent"
git -C "$capture_root/hermes-agent" checkout --detach 9de9c25f620ff7f1ce0fd5457d596052d5159596
test "$(git -C "$capture_root/hermes-agent" rev-list -n 1 v2026.7.7.2)" = "9de9c25f620ff7f1ce0fd5457d596052d5159596"
```

Use the tagged `APIServerAdapter` with a configured API key and its
`hermes-agent` fallback, invoke `_handle_capabilities`, and capture the actual
returned JSON object:

```bash
capture_json="$(cd "$capture_root/hermes-agent" && uv run --extra messaging --python 3.13 python -c 'import asyncio, json, os; from types import SimpleNamespace; from unittest.mock import patch; from gateway.config import PlatformConfig; from gateway.platforms.api_server import APIServerAdapter; os.environ.pop("API_SERVER_MODEL_NAME", None); profile_patch = patch("hermes_cli.profiles.get_active_profile_name", return_value="default"); profile_patch.start(); adapter = APIServerAdapter(PlatformConfig(enabled=True, extra={"key": "fixture-capture-key"})); profile_patch.stop(); request = SimpleNamespace(headers={"Authorization": "Bearer fixture-capture-key"}); response = asyncio.run(adapter._handle_capabilities(request)); print(json.dumps(json.loads(response.body), indent=2))')"
printf '%s\n' "$capture_json" | jq -e '.object == "hermes.api_server.capabilities" and .platform == "hermes-agent" and .model == "hermes-agent" and .auth.required == true and .features.chat_completions == true and .features.chat_completions_streaming == true'
```

Use `apply_patch` to replace `supported.json` with exactly `capture_json` plus
one trailing newline. Preserve the handler's complete response object, then
record:

```bash
shasum -a 256 tests/fixtures/hermes/v2026.7.7.2/capabilities/supported.json
```

Update provenance with `evidence_kind: "immutable-tag-capture"`, the exact tag/commit/source URL, configured bearer authentication, fallback model, the invocation procedure, and the printed digest. Do not alter the SSE fixture or its provenance entry.

- [x] **Step 2: Write failing model and provenance tests**

Add imports for `hashlib`, `json`, and `load_golden_bytes`, then add focused assertions:

```python
_MODEL_MAX_LENGTH = 255


def test_capability_fixture_matches_immutable_tag_provenance() -> None:
    payload = load_golden_bytes("capabilities/supported.json")
    provenance = load_golden_json("provenance.json")
    capability_entry = next(
        entry
        for entry in provenance["fixtures"]
        if entry["path"] == "capabilities/supported.json"
    )
    assert provenance["hermes_release"] == "v2026.7.7.2"
    assert provenance["source_commit"] == (
        "9de9c25f620ff7f1ce0fd5457d596052d5159596"
    )
    assert capability_entry["evidence_kind"] == "immutable-tag-capture"
    assert hashlib.sha256(payload).hexdigest() == capability_entry["sha256"]
    assert json.loads(payload)["model"] == "hermes-agent"


def test_supported_capabilities_expose_an_immutable_model() -> None:
    result = validate_capabilities(_supported_capabilities())
    assert result.model == "hermes-agent"
    with pytest.raises(ValidationError, match="Instance is frozen"):
        result.model = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("model", ["", " ", "\t\n", 7, None, True])
def test_invalid_model_values_are_protocol_failures(model: object) -> None:
    value = _supported_capabilities()
    value["model"] = model
    _assert_sanitized_protocol_failure(value)


def test_model_boundary_preserves_the_exact_advertised_value() -> None:
    value = _supported_capabilities()
    value["model"] = " " + "m" * (_MODEL_MAX_LENGTH - 2) + " "
    result = validate_capabilities(value)
    assert result.model == value["model"]


def test_over_limit_model_is_a_protocol_failure() -> None:
    value = _supported_capabilities()
    value["model"] = "m" * (_MODEL_MAX_LENGTH + 1)
    _assert_sanitized_protocol_failure(value)
```

Update the existing expected `HermesCapabilities(...)` construction to include `model="hermes-agent"`.
Add `("model",)` to the existing missing-required-field parameterization so an
absent model is also observed as a generic protocol failure.

- [x] **Step 3: Run the model tests and observe RED**

Run:

```bash
uv run --no-sync pytest tests/test_protocol.py -k "fixture_matches or immutable_model or invalid_model or model_boundary or over_limit" -vv
```

Expected: failures show the missing public `model` field and absent validation; no failure should come from malformed test setup.

- [x] **Step 4: Implement the strict public and wire model invariant**

In `models.py`, import `Annotated`, `StringConstraints`, and `field_validator`, then define:

```python
_HERMES_MODEL_MAX_LENGTH = 255
type _HermesModelName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=_HERMES_MODEL_MAX_LENGTH),
]


class HermesCapabilities(_FrozenModel):
    """Validated minimum semantics for a supported Hermes server."""

    object: str
    platform: str
    model: _HermesModelName
    auth_type: str
    auth_required: bool
    chat_completions: bool
    chat_completions_streaming: bool

    @field_validator("model")
    @classmethod
    def _reject_whitespace_only_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError
        return value
```

In `_CapabilitiesWire`, add the same strict bound and whitespace-only validator without normalizing the value:

```python
    model: Annotated[str, StringConstraints(min_length=1, max_length=255)]

    @field_validator("model")
    @classmethod
    def _reject_whitespace_only_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError
        return value
```

Pass `model=parsed.model` when constructing `HermesCapabilities`.

- [x] **Step 5: Run the model tests and the complete protocol module GREEN**

Run:

```bash
uv run --no-sync pytest tests/test_protocol.py -vv
uv run --no-sync basedpyright src/hermes_agent_api_client/models.py src/hermes_agent_api_client/protocol.py tests/test_protocol.py
```

Expected: all protocol tests pass and basedpyright reports 0 errors.

- [x] **Step 6: Commit the captured evidence and model contract**

Run:

```bash
git add tests/fixtures/hermes/v2026.7.7.2/capabilities/supported.json tests/fixtures/hermes/v2026.7.7.2/provenance.json tests/test_protocol.py src/hermes_agent_api_client/models.py src/hermes_agent_api_client/protocol.py
git commit -S -s -m "feat: expose advertised Hermes model"
git log -1 --show-signature --format=fuller
```

Expected: hook gates pass, the commit is signed off, and GPG verification is good.

---

### Task 3: Add Deterministic Identity and Capability Errors

**Files:**
- Modify: `tests/test_protocol.py`
- Modify: `src/hermes_agent_api_client/protocol.py`

**Interfaces:**
- Consumes: `validate_capabilities(value: object) -> HermesCapabilities` and the strict wire model from Task 2.
- Produces: `HermesIdentityError(HermesProtocolError)`, `HermesCapabilityError(HermesProtocolError)`, private `_CapabilityFailureKind`, and a parser returning a public immutable capability value or one safe failure kind.

- [x] **Step 1: Write failing inheritance and classification tests**

Import both new exceptions from the package module once Task 5 exports them; during this task import them from `hermes_agent_api_client.protocol`. Add:

```python
@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("object",), None),
        (("object",), "not.hermes"),
        (("platform",), None),
        (("platform",), "not-hermes-agent"),
    ],
)
def test_invalid_identity_maps_to_identity_error(
    path: tuple[str, ...], replacement: object
) -> None:
    value = _supported_capabilities()
    value[path[0]] = replacement
    with pytest.raises(HermesIdentityError) as caught:
        validate_capabilities(value)
    assert type(caught.value) is HermesIdentityError
    assert isinstance(caught.value, HermesProtocolError)


@pytest.mark.parametrize(
    "features",
    [None, {}, {"chat_completions": False}, {"chat_completions": 1}],
)
def test_required_chat_support_maps_to_capability_error(features: object) -> None:
    value = _supported_capabilities()
    value["features"] = features
    with pytest.raises(HermesCapabilityError) as caught:
        validate_capabilities(value)
    assert type(caught.value) is HermesCapabilityError
    assert isinstance(caught.value, HermesProtocolError)


def test_identity_failure_precedes_capability_failure() -> None:
    value = _supported_capabilities()
    value["object"] = "identity-canary"
    value["features"] = None
    with pytest.raises(HermesIdentityError):
        validate_capabilities(value)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("auth", "type"), "none"),
        (("auth", "required"), False),
        (("features", "chat_completions_streaming"), False),
        (("model",), ""),
    ],
)
def test_other_valid_identity_failures_remain_generic_protocol_errors(
    path: tuple[str, ...], replacement: object
) -> None:
    value = _supported_capabilities()
    target = value
    for key in path[:-1]:
        target = cast("dict[str, Any]", target[key])
    target[path[-1]] = replacement
    with pytest.raises(HermesProtocolError) as caught:
        validate_capabilities(value)
    assert type(caught.value) is HermesProtocolError
```

Add missing-key variants for both discriminators and `chat_completions` using `remove_json_key`.

- [x] **Step 2: Run the classification tests and observe RED**

Run:

```bash
uv run --no-sync pytest tests/test_protocol.py -k "identity or capability_error or generic_protocol" -vv
```

Expected: collection or assertion failures show the new exceptions and staged precedence are not implemented.

- [x] **Step 3: Add metadata-only subclasses and safe raisers**

Add directly below `HermesProtocolError`:

```python
class HermesIdentityError(HermesProtocolError):
    """A capability document does not identify a Hermes Agent endpoint."""

    __slots__ = ()


class HermesCapabilityError(HermesProtocolError):
    """A Hermes endpoint lacks required Chat Completions support."""

    __slots__ = ()
```

Add a private enum and a safe raising function:

```python
class _CapabilityFailureKind(StrEnum):
    IDENTITY = "identity"
    CAPABILITY = "capability"
    PROTOCOL = "protocol"


def _raise_capability_failure(kind: _CapabilityFailureKind) -> Never:
    if kind is _CapabilityFailureKind.IDENTITY:
        raise HermesIdentityError
    if kind is _CapabilityFailureKind.CAPABILITY:
        raise HermesCapabilityError
    raise HermesProtocolError
```

The subclasses intentionally inherit the metadata-only constructor unchanged.

- [x] **Step 4: Replace one-shot parsing with staged failure reduction**

Import `StrEnum` from `enum`. Make `_parse_capabilities` return a public value
or a safe failure kind and never raise raw validation details:

```python
def _parse_capabilities(
    value: object,
) -> tuple[HermesCapabilities | None, _CapabilityFailureKind | None]:
    if not isinstance(value, dict):
        return (None, _CapabilityFailureKind.PROTOCOL)

    object_value = value.get("object")
    platform_value = value.get("platform")
    if (
        not isinstance(object_value, str)
        or object_value != "hermes.api_server.capabilities"
        or not isinstance(platform_value, str)
        or platform_value != "hermes-agent"
    ):
        return (None, _CapabilityFailureKind.IDENTITY)

    features = value.get("features")
    if not isinstance(features, dict) or features.get("chat_completions") is not True:
        return (None, _CapabilityFailureKind.CAPABILITY)

    try:
        parsed = _CapabilitiesWire.model_validate(value)
    except ValidationError:
        return (None, _CapabilityFailureKind.PROTOCOL)
    return (
        HermesCapabilities(
            object=parsed.object,
            platform=parsed.platform,
            model=parsed.model,
            auth_type=parsed.auth.type,
            auth_required=parsed.auth.required,
            chat_completions=parsed.features.chat_completions,
            chat_completions_streaming=parsed.features.chat_completions_streaming,
        ),
        None,
    )
```

Update `validate_capabilities` so raw input is cleared before raising:

```python
def validate_capabilities(value: object) -> HermesCapabilities:
    parsed, failure_kind = _parse_capabilities(value)
    if failure_kind is not None:
        value = None
        parsed = None
        _raise_capability_failure(failure_kind)
    return cast("HermesCapabilities", parsed)
```

Import `cast` from `typing`. The cast is an internal type invariant and does not
introduce an input-bearing assertion frame.

- [x] **Step 5: Add sanitization tests for each new exact type**

Parameterize the existing public-state and traceback-local helper across:

```python
(
    ("platform", "identity-traceback-canary", HermesIdentityError),
    ("features", {"chat_completions": "capability-traceback-canary"}, HermesCapabilityError),
)
```

For each error assert exact type, empty `vars`, safe protocol metadata, cause/context `None`, no canary in `args`, `str`, `repr`, formatted traceback, or recursively inspected package-frame locals, and no identity match with the rejected document.

- [x] **Step 6: Run the complete protocol suite GREEN**

Run:

```bash
uv run --no-sync pytest tests/test_protocol.py -vv
uv run --no-sync ruff check src/hermes_agent_api_client/protocol.py tests/test_protocol.py
uv run --no-sync basedpyright src/hermes_agent_api_client/protocol.py tests/test_protocol.py
```

Expected: protocol tests pass, Ruff is clean, and basedpyright reports 0 errors.

- [x] **Step 7: Commit the typed classification**

Run:

```bash
git add src/hermes_agent_api_client/protocol.py tests/test_protocol.py
git commit -S -s -m "feat: classify Hermes capability failures"
git log -1 --show-signature --format=fuller
```

Expected: all installed hooks pass and the signed commit is verifiable.

---

### Task 4: Preserve Typed Failures Through the HTTP and Public Client Layers

**Files:**
- Modify: `tests/test_transport.py`
- Modify: `tests/test_client_lifecycle.py`
- Modify: `src/hermes_agent_api_client/client.py`

**Interfaces:**
- Consumes: private `_CapabilityFailureKind`, `_parse_capabilities`, and `_raise_capability_failure` from Task 3.
- Produces: exact identity/capability error propagation from `_probe_capabilities()` and `HermesAgentApiClient.probe_capabilities()` after response and bound-state scrubbing.

- [x] **Step 1: Write failing transport propagation tests**

Add a parameterized transport test that mutates only the targeted semantic field:

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutate", "error_type", "canary"),
    [
        (lambda value: value.__setitem__("platform", "transport-identity-canary"), HermesIdentityError, "transport-identity-canary"),
        (lambda value: value["features"].__setitem__("chat_completions", "transport-capability-canary"), HermesCapabilityError, "transport-capability-canary"),
    ],
)
async def test_probe_propagates_typed_capability_failures_safely(
    mutate: Callable[[dict[str, Any]], None],
    error_type: type[HermesProtocolError],
    canary: str,
) -> None:
    document = _supported_capabilities()
    mutate(document)
    stream = TrackingAsyncByteStream((json.dumps(document).encode(),))
    response: httpx.Response | None = None

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal response
        response = httpx.Response(200, request=request, stream=stream)
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(error_type) as caught:
            await _probe(client)
        assert type(caught.value) is error_type
        assert response is not None and response.is_closed
        assert stream.closed
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert canary not in "".join(traceback.format_exception(caught.value))
        _assert_traceback_locals_are_safe(
            caught.value,
            canaries=(canary, "capability-bearer"),
            forbidden_objects=(response, document),
        )
    finally:
        await client.aclose()
```

Use named mutation helpers rather than lambdas if Ruff's annotation rules reject the inline callables.

- [x] **Step 2: Write failing public-client tests**

Extend the successful lifecycle assertion with:

```python
assert capabilities.model == "hermes-agent"
```

Add one public `probe_capabilities()` case for each new exact exception type. Assert the client object, bearer value, base URL, response body canary, and raw response are absent from all package-owned traceback locals.

- [x] **Step 3: Run the focused transport/client tests and observe RED**

Run:

```bash
uv run --no-sync pytest tests/test_transport.py tests/test_client_lifecycle.py -k "typed_capability or advertised_model" -vv
```

Expected: the current payload parser collapses both typed failures to `HermesProtocolError`, so exact-type assertions fail.

- [x] **Step 4: Carry a safe failure kind through response cleanup**

Replace `_parse_capabilities_payload` with:

```python
def _parse_capabilities_payload(
    payload: bytes,
) -> tuple[HermesCapabilities | None, _CapabilityFailureKind | None]:
    valid_json, document = _load_json(payload)
    if not valid_json:
        return (None, _CapabilityFailureKind.PROTOCOL)
    capabilities, failure_kind = _parse_capabilities(document)
    document = None
    if failure_kind is not None:
        return (None, failure_kind)
    if capabilities is None:
        return (None, _CapabilityFailureKind.PROTOCOL)
    return (capabilities, None)
```

Import the three private protocol helpers with package-local suppression comments where basedpyright requires them.

In `_read_capabilities_body`, replace `protocol_failed: bool` with `capability_failure: _CapabilityFailureKind | None`, assign the tuple returned by `_parse_capabilities_payload` at every existing parse site, and set `primary_outcome` when a failure kind is present. Before raising, clear `response`, `chunk`, `payload`, `capabilities`, `http_client`, `endpoint`, and `headers`, then call:

```python
if capability_failure is not None:
    _raise_capability_failure(capability_failure)
```

Body-limit failures assign `_CapabilityFailureKind.PROTOCOL`. Preserve the existing cancellation, HTTP-status, read-transport, cleanup, and precedence branches unchanged.

- [x] **Step 5: Run focused tests GREEN, then the complete transport/lifecycle pair**

Run:

```bash
uv run --no-sync pytest tests/test_transport.py tests/test_client_lifecycle.py -k "typed_capability or advertised_model" -vv
uv run --no-sync pytest tests/test_transport.py tests/test_client_lifecycle.py -vv
uv run --no-sync basedpyright src/hermes_agent_api_client/client.py tests/test_transport.py tests/test_client_lifecycle.py
```

Expected: exact typed errors propagate, all response/bound-state sanitization tests pass, and basedpyright reports 0 errors.

- [x] **Step 6: Commit transport propagation**

Run:

```bash
git add src/hermes_agent_api_client/client.py tests/test_transport.py tests/test_client_lifecycle.py
git commit -S -s -m "feat: propagate typed capability failures"
git log -1 --show-signature --format=fuller
```

Expected: installed hooks pass and the signed commit verifies.

---

### Task 5: Export the Contract and Make Release Metadata Self-Consistent

**Files:**
- Modify: `src/hermes_agent_api_client/__init__.py`
- Modify: `tests/test_package.py`
- Modify: `scripts/verify_dist.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `HermesIdentityError`, `HermesCapabilityError`, extended `HermesCapabilities`, and semantic-release's stamped `project.version`.
- Produces: package-root imports, exact `__all__`, metadata-derived `__version__`, and a verifier that validates the stamped version without a duplicated literal.

- [x] **Step 1: Write failing package-root and star-import tests**

Extend the exact export set with `HermesIdentityError` and `HermesCapabilityError`, then add:

```python
def test_public_version_matches_distribution_metadata() -> None:
    import hermes_agent_api_client

    assert hermes_agent_api_client.__version__ == version(
        "hermes-agent-api-client"
    )


def test_public_failure_types_are_available_through_star_import() -> None:
    namespace: dict[str, object] = {}
    exec("from hermes_agent_api_client import *", namespace)
    identity_type = namespace["HermesIdentityError"]
    capability_type = namespace["HermesCapabilityError"]
    protocol_type = namespace["HermesProtocolError"]
    assert isinstance(identity_type, type)
    assert isinstance(capability_type, type)
    assert isinstance(protocol_type, type)
    assert issubclass(identity_type, protocol_type)
    assert issubclass(capability_type, protocol_type)
```

Replace hard-coded `0.1.0` package-version assertions with distribution metadata comparisons. Keep tests that intentionally mutate the Version metadata field.

- [x] **Step 2: Run the package tests and observe RED**

Run:

```bash
uv run --no-sync pytest tests/test_package.py -k "public_version or public_exports or star_import" -vv
```

Expected: both new exceptions are missing from the package root and `__all__`.

- [x] **Step 3: Export both exceptions and derive the runtime version**

Update `__init__.py`:

```python
from importlib.metadata import version

from .protocol import (
    HermesAuthenticationError,
    HermesCapabilityError,
    HermesContractError,
    HermesHttpStatusError,
    HermesIdentityError,
    HermesProtocolError,
    HermesTransportError,
)

__version__ = version("hermes-agent-api-client")
```

Add both names to `__all__` in alphabetic order. Do not export private parser helpers or the 255-character constant.

- [x] **Step 4: Write a failing verifier test for source-derived expected version**

Add a test that reads `pyproject.toml` with `tomllib`, confirms the built wheel metadata Version equals `project.version`, and confirms `scripts/verify_dist.py` accepts the artifacts. This test fails only if the verifier still carries a mismatched duplicated version literal after a semantic-release stamp.

- [x] **Step 5: Derive verifier expectations from project metadata**

In `scripts/verify_dist.py`, import `tomllib`, define the project root once, and load the version without importing the package:

```python
_PROJECT_ROOT = Path(__file__).parents[1]


def _project_version() -> str:
    with (_PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
        project_data = tomllib.load(project_file)
    version_value = project_data["project"]["version"]
    if not isinstance(version_value, str) or not version_value:
        _fail(_INVALID_METADATA_MESSAGE)
    return version_value
```

Build `_EXPECTED_SINGLETON_METADATA` with `"Version": _project_version()` after `_fail` is defined, or pass the expected version into `_metadata_is_valid` so module initialization cannot emit an unsanitized parse failure. Wrap TOML/file/key/type failures in the existing constant `_INVALID_METADATA_MESSAGE` path.

Update semantic-release's build command to verify stamped artifacts:

```toml
build_command = """
  uv lock --upgrade-package "$PACKAGE_NAME"
  uv build
  uv run --no-sync python scripts/verify_dist.py dist/*.whl dist/*.tar.gz
"""
```

Semantic-release supplies `PACKAGE_NAME`, stamps `version_toml` before this command, and aborts before commit/tag creation if verification fails.

- [x] **Step 6: Run package, build, verifier, and public type gates GREEN**

Run:

```bash
uv run --no-sync pytest tests/test_package.py -vv
rm -rf dist
uv build
uv run --no-sync python scripts/verify_dist.py dist/*.whl dist/*.tar.gz
uv run --no-sync basedpyright --verifytypes hermes_agent_api_client --ignoreexternal
```

Expected: package tests pass, exactly one wheel and one sdist build, verifier prints `distribution verification passed`, and verifytypes reports 100% completeness.

- [x] **Step 7: Commit exports and release consistency**

Run:

```bash
git add src/hermes_agent_api_client/__init__.py tests/test_package.py scripts/verify_dist.py pyproject.toml
git commit -S -s -m "feat: export capability failure taxonomy"
git log -1 --show-signature --format=fuller
```

Expected: installed hooks pass and the signed commit verifies.

---

### Task 6: Document the Consumer Contract and Verify the Release Candidate

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/plans/2026-07-16-capability-identity-contract-implementation.md` only to check completed boxes during execution.

**Interfaces:**
- Consumes: the final package-root public API and exact classification table.
- Produces: consumer documentation and an Unreleased changelog entry without a manually selected version.

- [x] **Step 1: Update README with a package-root-only consumer example**

Use this import and classification pattern:

```python
from hermes_agent_api_client import (
    HermesAgentApiClient,
    HermesCapabilityError,
    HermesIdentityError,
)


async def discover_hermes(base_url: str, bearer_key: str) -> str:
    try:
        async with HermesAgentApiClient(base_url, bearer_key) as client:
            capabilities = await client.probe_capabilities()
    except HermesIdentityError:
        return "not a Hermes Agent endpoint"
    except HermesCapabilityError:
        return "Hermes Agent lacks Chat Completions support"
    return capabilities.model
```

Document the supported capability shape with `model`, its exact resolution semantics, strict 1-255/non-whitespace-only validation, preserved value, both exception subclasses, the complete wire-condition mapping, generic protocol fallback, and the immutable compatibility tag/SHA. Remove prose that hard-codes the package's current release as `0.1.0` where it would become stale.

- [x] **Step 2: Add an Unreleased changelog section**

Add directly below the version-list marker:

```markdown
## Unreleased

- Added the immutable `HermesCapabilities.model` field with strict 1-255
  character validation.
- Added package-root `HermesIdentityError` and `HermesCapabilityError`
  subclasses for deterministic capability-probe classification.
```

Do not write `0.2.0`; semantic-release owns the release heading and version.

- [x] **Step 3: Run documentation-adjacent and full verification gates**

Run in this exact order:

```bash
uv sync --locked --all-groups --no-editable
uv lock --check
uv tree --locked --outdated --all-groups
uv run --no-sync ruff format --check .
uv run --no-sync ruff check .
uv run --no-sync basedpyright
uv run --no-sync basedpyright --verifytypes hermes_agent_api_client --ignoreexternal
uv run --no-sync pytest
rm -rf dist
uv build
uv run --no-sync python scripts/verify_dist.py dist/*.whl dist/*.tar.gz
uv run --no-sync prek validate-config prek.toml
uv run --no-sync prek install --prepare-hooks
git diff --check
```

Expected: every command exits 0; pytest reports 100% coverage; verifier prints `distribution verification passed`; basedpyright reports 0 errors and 100% completeness.

- [x] **Step 4: Verify isolated wheel installation and package-root behavior**

Create isolated Python 3.13 and 3.14 environments outside the repository and install only the wheel:

```bash
wheel_path="$(printf '%s\n' dist/*.whl)"
for python_version in 3.13 3.14; do
  isolated_dir="$(mktemp -d)"
  uv venv --python "$python_version" "$isolated_dir/.venv"
  uv pip install --python "$isolated_dir/.venv/bin/python" "$wheel_path"
  "$isolated_dir/.venv/bin/python" -I -c 'from hermes_agent_api_client import HermesCapabilities, HermesIdentityError, HermesCapabilityError, HermesProtocolError, __version__; assert issubclass(HermesIdentityError, HermesProtocolError); assert issubclass(HermesCapabilityError, HermesProtocolError); assert HermesCapabilities.model_fields["model"].is_required(); assert __version__'
done
```

Expected: both isolated imports exit 0 and use no source-checkout path.

- [x] **Step 5: Review the complete diff against the approved specification**

Run:

```bash
git status --short --branch
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- . ':(exclude).idea'
git log --show-signature --format=fuller origin/main..HEAD
```

Confirm every design requirement has code or test evidence, all commits are signed and signed off, only intended files are included, and `.idea/` remains untracked.

- [x] **Step 6: Commit documentation and final plan state**

Run:

```bash
git add README.md CHANGELOG.md docs/superpowers/plans/2026-07-16-capability-identity-contract-implementation.md
git commit -S -s -m "docs: document capability identity contract"
git log -1 --show-signature --format=fuller
```

Expected: the installed hook reruns every gate successfully and the signed commit verifies.

---

### Task 7: Create the Merge-Ready PR and Verify the Published Release

**Files:**
- No source changes expected before review feedback.

**Interfaces:**
- Consumes: fully verified signed branch commits.
- Produces: merge-ready GitHub PR, then verified GitHub/PyPI release evidence after merge.

- [ ] **Step 1: Push the feature branch and create the PR**

Run:

```bash
git push -u origin codex/extend-client-contract
gh pr create --base main --head codex/extend-client-contract --title "feat: extend Hermes capability identity contract" --body $'## Summary\n- expose the immutable advertised Hermes model with strict 1-255 character validation\n- distinguish non-Hermes identity from missing required Chat Completions support\n- preserve sanitized non-retryable protocol behavior through the public client\n- finish the existing basedpyright migration while keeping prek as the installed hook\n\n## Upstream evidence\n- Hermes Agent v2026.7.7.2\n- commit 9de9c25f620ff7f1ce0fd5457d596052d5159596\n- capability fixture captured from the immutable tagged handler\n\n## Verification\n- uv sync --locked --all-groups --no-editable\n- Ruff format and lint\n- basedpyright project and verifytypes checks\n- pytest with 100% coverage\n- wheel and sdist build plus scripts/verify_dist.py\n- isolated Python 3.13 and 3.14 wheel imports\n\nPublishing remains delegated to the post-merge semantic-release workflow.'
```

The PR body must summarize the bounded model contract, exact error taxonomy, immutable upstream tag/SHA, basedpyright migration coordination, fixture provenance, sanitization boundaries, and every verification command/result. It must state that publishing is intentionally delegated to the post-merge release workflow.

- [ ] **Step 2: Verify PR checks and merge readiness without merging**

Run:

```bash
gh pr checks --watch --fail-fast
gh pr view --json url,state,mergeable,reviewDecision,statusCheckRollup,headRefName,baseRefName
```

Expected: Python 3.13 and 3.14 CI checks pass and GitHub reports the PR mergeable. Do not merge without explicit user authority.

- [ ] **Step 3: After the user or maintainer merges, verify semantic-release**

Run:

```bash
git fetch --prune origin
merge_sha="$(gh pr view --json mergeCommit --jq '.mergeCommit.oid')"
test -n "$merge_sha"
gh pr view --json state,mergedAt,mergeCommit,url
gh run list --workflow release.yml --branch main --limit 5
```

Watch the release run associated with the merge commit:

```bash
release_run_id="$(gh run list --workflow release.yml --branch main --limit 10 --json databaseId,headSha | jq -r --arg sha "$merge_sha" '.[] | select(.headSha == $sha) | .databaseId' | head -1)"
test -n "$release_run_id"
gh run watch "$release_run_id" --exit-status
```

- [ ] **Step 4: Verify the released GitHub and PyPI artifacts**

Obtain the release tag/version from the fetched signed tag containing the merge
commit and run:

```bash
git fetch --tags origin
release_tag="$(git tag --contains "$merge_sha" --list 'v*' --sort=-version:refname | head -1)"
test -n "$release_tag"
release_version="${release_tag#v}"
gh release view "$release_tag" --json url,tagName,publishedAt,assets
curl -fsS "https://pypi.org/pypi/hermes-agent-api-client/$release_version/json" | jq -e --arg version "$release_version" '.info.version == $version and ([.urls[].packagetype] | sort) == ["bdist_wheel", "sdist"]'
```

Download wheel and sdist from the PyPI response's immutable URLs into a fresh
temporary directory and compare local SHA-256 values with PyPI's recorded
digests:

```bash
pypi_json="$(mktemp)"
curl -fsS "https://pypi.org/pypi/hermes-agent-api-client/$release_version/json" -o "$pypi_json"
artifact_dir="$(mktemp -d)"
wheel_url="$(jq -r '.urls[] | select(.packagetype == "bdist_wheel") | .url' "$pypi_json")"
sdist_url="$(jq -r '.urls[] | select(.packagetype == "sdist") | .url' "$pypi_json")"
curl -fL "$wheel_url" -o "$artifact_dir/$(basename "$wheel_url")"
curl -fL "$sdist_url" -o "$artifact_dir/$(basename "$sdist_url")"
wheel_sha="$(shasum -a 256 "$artifact_dir"/*.whl | awk '{print $1}')"
sdist_sha="$(shasum -a 256 "$artifact_dir"/*.tar.gz | awk '{print $1}')"
test "$wheel_sha" = "$(jq -r '.urls[] | select(.packagetype == "bdist_wheel") | .digests.sha256' "$pypi_json")"
test "$sdist_sha" = "$(jq -r '.urls[] | select(.packagetype == "sdist") | .digests.sha256' "$pypi_json")"
```

Install the downloaded wheel in a fresh isolated environment and repeat the
package-root import/inheritance assertions from Task 6.

- [ ] **Step 5: Report the complete final handoff**

Report the released package version; exact public symbols and inheritance; model semantics and 255-character maximum; complete wire-condition mapping; upstream tag/SHA; GitHub release URL; PyPI URL; wheel and sdist SHA-256 values; every verification command and result; PR URL; release workflow URL; and confirmation that Hermes Conversation was not modified.
