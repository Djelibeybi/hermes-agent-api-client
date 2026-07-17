"""Pure contracts for Hermes capabilities, events, and failures."""

from __future__ import annotations

import hashlib
import json
import traceback
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast, get_args

import pytest
from pydantic import ValidationError

import hermes_agent_api_client as hermes_api
import hermes_agent_api_client.models as hermes_models
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
from hermes_agent_api_client.protocol import (
    HermesCapabilityError,
    HermesIdentityError,
    validate_capabilities,
)
from tests.helpers.hermes import (
    add_json_key,
    load_golden_bytes,
    load_golden_json,
    remove_json_key,
    reorder_json_keys,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

_EVENT_RECORD_COUNT = 7
_MODEL_MAX_LENGTH = 255
_LIFECYCLE_TEXT_MAX_LENGTH = 256
_HOSTILE_ACCESS_CANARY = "hostile-mapping-access-canary"
_HOSTILE_EQUALITY_CANARY = "hostile-string-equality-canary"
_HOSTILE_ITERATION_CANARY = "hostile-mapping-iteration-canary"


class _HostileMapping(Mapping[str, object]):
    """A mapping whose key access raises a private upstream detail."""

    def __init__(self, values: dict[str, object], fail_key: str) -> None:
        self._values = values
        self._fail_key = fail_key

    def __getitem__(self, key: str) -> object:
        if key == self._fail_key:
            raise RuntimeError(_HOSTILE_ACCESS_CANARY)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


class _HostileIterationMapping(Mapping[str, object]):
    """A readable mapping whose normalization exposes a private failure."""

    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        raise RuntimeError(_HOSTILE_ITERATION_CANARY)

    def __len__(self) -> int:
        return len(self._values)


class _HostileString(str):
    """A string whose discriminator comparison raises a private detail."""

    __slots__ = ()
    __hash__ = str.__hash__

    def __eq__(self, value: object) -> bool:
        raise RuntimeError(_HOSTILE_EQUALITY_CANARY)

    def __ne__(self, value: object) -> bool:
        return self.__eq__(value)


def _supported_capabilities() -> dict[str, Any]:
    """Return a fresh copy of the supported capability golden."""
    return load_golden_json("capabilities/supported.json")


def _assert_sanitized_protocol_failure(value: object) -> HermesProtocolError:
    """Assert invalid wire state becomes only safe public metadata."""
    with pytest.raises(HermesProtocolError) as caught:
        validate_capabilities(value)

    error = caught.value
    assert error.category is FailureCategory.PROTOCOL
    assert error.status_code is None
    assert error.retryable is False
    assert error.__cause__ is None
    assert error.__context__ is None
    assert vars(error) == {}
    return error


def _package_traceback_locals(error: BaseException) -> tuple[dict[str, object], ...]:
    """Snapshot every package-owned frame retained by one public failure."""
    frames: list[dict[str, object]] = []
    cursor = error.__traceback__
    while cursor is not None:
        module_name = cursor.tb_frame.f_globals.get("__name__")
        if isinstance(module_name, str) and module_name.startswith(
            "hermes_agent_api_client"
        ):
            frames.append(dict(cursor.tb_frame.f_locals))
        cursor = cursor.tb_next
    assert frames
    return tuple(frames)


def _assert_package_traceback_is_scrubbed(
    error: BaseException,
    *,
    canaries: tuple[str, ...],
    forbidden_objects: tuple[object, ...],
) -> None:
    """Reject canaries and caller-owned inputs in nested package frame locals."""
    rendered_error = " | ".join(
        (str(error), repr(error), repr(error.args), repr(vars(error)))
    )
    assert all(canary not in rendered_error for canary in canaries)
    assert error.__cause__ is None
    assert error.__context__ is None

    for frame_locals in _package_traceback_locals(error):
        pending: list[object] = list(frame_locals.values())
        visited: set[int] = set()
        while pending:
            referenced = pending.pop()
            identity = id(referenced)
            if identity in visited:
                continue
            visited.add(identity)
            assert all(referenced is not forbidden for forbidden in forbidden_objects)
            rendered = f"{referenced!s} | {referenced!r}"
            assert all(canary not in rendered for canary in canaries)
            if isinstance(referenced, dict):
                mapping = cast("dict[object, object]", referenced)
                pending.extend(mapping.keys())
                pending.extend(mapping.values())
            elif isinstance(referenced, (list, tuple, set, frozenset)):
                pending.extend(cast("Iterable[object]", referenced))


def test_capability_fixture_matches_immutable_tag_provenance() -> None:
    """The complete captured handler bytes match their immutable provenance."""
    payload = load_golden_bytes("capabilities/supported.json")
    provenance = load_golden_json("provenance.json")
    capability_entry = next(
        entry
        for entry in provenance["fixtures"]
        if entry["path"] == "capabilities/supported.json"
    )
    assert provenance["hermes_release"] == "v2026.7.7.2"
    assert provenance["source_commit"] == ("9de9c25f620ff7f1ce0fd5457d596052d5159596")
    assert capability_entry["evidence_kind"] == "immutable-tag-capture"
    assert hashlib.sha256(payload).hexdigest() == capability_entry["sha256"]
    assert json.loads(payload)["model"] == "hermes-agent"


def test_supported_capabilities_expose_an_immutable_model() -> None:
    """A supported response exposes its exact model on the frozen public value."""
    result = validate_capabilities(_supported_capabilities())
    assert result.model == "hermes-agent"
    with pytest.raises(ValidationError, match="Instance is frozen"):
        result.model = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("model", ["", " ", "\t\n", 7, None, True])
def test_invalid_model_values_are_protocol_failures(model: object) -> None:
    """Invalid wire model values collapse into the safe protocol failure."""
    value = _supported_capabilities()
    value["model"] = model
    _assert_sanitized_protocol_failure(value)


@pytest.mark.parametrize("model", ["", " \t", "m" * (_MODEL_MAX_LENGTH + 1)])
def test_public_capabilities_reject_invalid_model_names(model: str) -> None:
    """Direct public model construction enforces the same bounded contract."""
    value = validate_capabilities(_supported_capabilities()).model_dump()
    value["model"] = model
    with pytest.raises(ValidationError):
        HermesCapabilities.model_validate(value)


def test_model_boundary_preserves_the_exact_advertised_value() -> None:
    """Valid boundary whitespace is retained rather than normalized."""
    value = _supported_capabilities()
    value["model"] = " " + "m" * (_MODEL_MAX_LENGTH - 2) + " "
    result = validate_capabilities(value)
    assert result.model == value["model"]


def test_over_limit_model_is_a_protocol_failure() -> None:
    """A model name beyond 255 code points is a safe protocol failure."""
    value = _supported_capabilities()
    value["model"] = "m" * (_MODEL_MAX_LENGTH + 1)
    _assert_sanitized_protocol_failure(value)


def test_supported_capabilities_produce_an_immutable_typed_value() -> None:
    """The canonical document maps to the exact supported semantic contract."""
    result = validate_capabilities(_supported_capabilities())

    assert result == HermesCapabilities(
        object="hermes.api_server.capabilities",
        platform="hermes-agent",
        model="hermes-agent",
        auth_type="bearer",
        auth_required=True,
        chat_completions=True,
        chat_completions_streaming=True,
    )
    with pytest.raises(ValidationError, match="Instance is frozen"):
        result.platform = "impersonated"  # type: ignore[misc]


def test_additive_and_reordered_documents_produce_the_same_value() -> None:
    """Unknown fields and JSON key order do not alter validated semantics."""
    canonical = _supported_capabilities()
    additive = add_json_key(canonical, ("future",), {"nested": [1, 2, 3]})
    additive = add_json_key(
        additive,
        ("auth", "future_auth_mode"),
        {"enabled": "maybe"},
    )
    additive = add_json_key(
        additive,
        ("features", "future_stream_mode"),
        {"enabled": "maybe"},
    )
    reordered = reorder_json_keys(additive, tuple(reversed(tuple(additive))))
    reordered = reorder_json_keys(
        reordered,
        tuple(reversed(tuple(reordered["auth"]))),
        path=("auth",),
    )
    reordered = reorder_json_keys(
        reordered,
        tuple(reversed(tuple(reordered["features"]))),
        path=("features",),
    )

    expected = validate_capabilities(canonical)
    assert validate_capabilities(additive) == expected
    assert validate_capabilities(reordered) == expected


@pytest.mark.parametrize(
    ("value", "case"),
    [
        (None, "null"),
        ({}, "empty object"),
        ([], "array"),
        ("hermes", "string"),
        (42, "number"),
        (True, "boolean"),
    ],
)
def test_degenerate_documents_are_protocol_failures(value: object, case: str) -> None:
    """Non-capability values fail through the stable protocol category."""
    error = _assert_sanitized_protocol_failure(value)

    assert isinstance(error, HermesContractError), case


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("object",), "not.hermes"),
        (("platform",), "not-hermes-agent"),
        (("auth",), None),
        (("auth", "type"), "none"),
        (("auth", "required"), False),
        (("auth", "required"), 1),
        (("features",), None),
        (("features", "chat_completions"), False),
        (("features", "chat_completions"), 1),
        (("features", "chat_completions_streaming"), False),
        (("features", "chat_completions_streaming"), 1),
    ],
)
def test_unsupported_semantics_are_safe_protocol_failures(
    path: tuple[str, ...], replacement: object
) -> None:
    """Identity, bearer-required, and streaming chat semantics are strict."""
    value = _supported_capabilities()
    target = value
    for key in path[:-1]:
        nested = target[key]
        assert isinstance(nested, dict)
        target = cast("dict[str, Any]", nested)
    target[path[-1]] = replacement

    _assert_sanitized_protocol_failure(value)


@pytest.mark.parametrize(
    "path",
    [
        ("object",),
        ("platform",),
        ("model",),
        ("auth",),
        ("auth", "type"),
        ("auth", "required"),
        ("features",),
        ("features", "chat_completions"),
        ("features", "chat_completions_streaming"),
    ],
)
def test_missing_required_fields_are_safe_protocol_failures(
    path: tuple[str, ...],
) -> None:
    """Every required semantic field must be present and correctly nested."""
    value = _supported_capabilities()
    target = value
    for key in path[:-1]:
        nested = target[key]
        assert isinstance(nested, dict)
        target = cast("dict[str, Any]", nested)
    del target[path[-1]]

    _assert_sanitized_protocol_failure(value)


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
    """Invalid Hermes discriminators have one exact identity failure type."""
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
    """Missing or invalid Chat Completions support is a capability failure."""
    value = _supported_capabilities()
    value["features"] = features
    with pytest.raises(HermesCapabilityError) as caught:
        validate_capabilities(value)
    assert type(caught.value) is HermesCapabilityError
    assert isinstance(caught.value, HermesProtocolError)


def test_identity_failure_precedes_capability_failure() -> None:
    """Identity classification wins when both validation stages are invalid."""
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
    """Failures after identity and required-chat checks remain generic."""
    value = _supported_capabilities()
    target = value
    for key in path[:-1]:
        target = cast("dict[str, Any]", target[key])
    target[path[-1]] = replacement
    with pytest.raises(HermesProtocolError) as caught:
        validate_capabilities(value)
    assert type(caught.value) is HermesProtocolError


@pytest.mark.parametrize("path", [("object",), ("platform",)])
def test_missing_identity_discriminator_maps_to_identity_error(
    path: tuple[str, ...],
) -> None:
    """Missing identity discriminators use the exact identity failure type."""
    value = remove_json_key(_supported_capabilities(), path)
    with pytest.raises(HermesIdentityError) as caught:
        validate_capabilities(value)
    assert type(caught.value) is HermesIdentityError


def test_missing_chat_completions_maps_to_capability_error() -> None:
    """A missing required Chat Completions key is a capability failure."""
    value = remove_json_key(_supported_capabilities(), ("features", "chat_completions"))
    with pytest.raises(HermesCapabilityError) as caught:
        validate_capabilities(value)
    assert type(caught.value) is HermesCapabilityError


def test_missing_identity_precedes_missing_chat_completions() -> None:
    """A missing discriminator wins over a missing required capability."""
    value = remove_json_key(_supported_capabilities(), ("platform",))
    value = remove_json_key(value, ("features", "chat_completions"))
    with pytest.raises(HermesIdentityError):
        validate_capabilities(value)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        ("object", None),
        ("object", "not.hermes"),
        ("platform", None),
        ("platform", "not-hermes-agent"),
    ],
)
def test_non_dict_mapping_identity_failures_are_exact(
    path: str,
    replacement: object,
) -> None:
    """Mapping semantics retain exact missing and invalid identity failures."""
    value = _supported_capabilities()
    if replacement is None:
        del value[path]
    else:
        value[path] = replacement

    with pytest.raises(HermesIdentityError) as caught:
        validate_capabilities(MappingProxyType(value))
    assert type(caught.value) is HermesIdentityError


@pytest.mark.parametrize(
    "features",
    [
        cast("Mapping[str, object]", MappingProxyType({})),
        cast(
            "Mapping[str, object]",
            MappingProxyType({"chat_completions": False}),
        ),
        cast(
            "Mapping[str, object]",
            MappingProxyType({"chat_completions": 1}),
        ),
    ],
)
def test_non_dict_mapping_chat_failures_are_exact(
    features: Mapping[str, object],
) -> None:
    """Mapping-valued missing or invalid required chat support is classified."""
    value = _supported_capabilities()
    value["features"] = features

    with pytest.raises(HermesCapabilityError) as caught:
        validate_capabilities(MappingProxyType(value))
    assert type(caught.value) is HermesCapabilityError


def test_complete_non_dict_mappings_produce_immutable_capabilities() -> None:
    """Complete mapping inputs validate into the public immutable value."""
    value = _supported_capabilities()
    value["features"] = MappingProxyType(cast("dict[str, object]", value["features"]))

    result = validate_capabilities(MappingProxyType(value))

    assert result == validate_capabilities(_supported_capabilities())
    with pytest.raises(ValidationError, match="Instance is frozen"):
        result.platform = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("fail_key", ["object", "platform", "features"])
def test_hostile_mapping_access_becomes_a_scrubbed_generic_protocol_error(
    fail_key: str,
) -> None:
    """Mapping access exceptions and their inputs cannot escape validation."""
    rejected = _HostileMapping(_supported_capabilities(), fail_key)

    error = _assert_sanitized_protocol_failure(rejected)

    assert type(error) is HermesProtocolError
    assert _HOSTILE_ACCESS_CANARY not in "".join(traceback.format_exception(error))
    _assert_package_traceback_is_scrubbed(
        error,
        canaries=(_HOSTILE_ACCESS_CANARY,),
        forbidden_objects=(rejected,),
    )


def test_hostile_chat_support_access_is_a_scrubbed_protocol_error() -> None:
    """Nested feature access exceptions reduce to safe generic protocol."""
    features = cast("dict[str, object]", _supported_capabilities()["features"])
    rejected = _supported_capabilities()
    rejected["features"] = _HostileMapping(features, "chat_completions")

    error = _assert_sanitized_protocol_failure(MappingProxyType(rejected))

    assert type(error) is HermesProtocolError
    assert _HOSTILE_ACCESS_CANARY not in "".join(traceback.format_exception(error))
    _assert_package_traceback_is_scrubbed(
        error,
        canaries=(_HOSTILE_ACCESS_CANARY,),
        forbidden_objects=(rejected, rejected["features"]),
    )


@pytest.mark.parametrize("path", ["object", "platform"])
def test_hostile_discriminator_equality_is_a_scrubbed_protocol_error(
    path: str,
) -> None:
    """Discriminator comparison exceptions reduce to safe generic protocol."""
    rejected = _supported_capabilities()
    hostile_value = _HostileString(cast("str", rejected[path]))
    rejected[path] = hostile_value

    error = _assert_sanitized_protocol_failure(rejected)

    assert type(error) is HermesProtocolError
    assert _HOSTILE_EQUALITY_CANARY not in "".join(traceback.format_exception(error))
    _assert_package_traceback_is_scrubbed(
        error,
        canaries=(_HOSTILE_EQUALITY_CANARY,),
        forbidden_objects=(rejected, hostile_value),
    )


@pytest.mark.parametrize(
    ("path", "replacement", "error_type"),
    [
        ("object", "not.hermes", HermesIdentityError),
        (
            "features",
            MappingProxyType({"chat_completions": False}),
            HermesCapabilityError,
        ),
    ],
)
def test_staged_mapping_failure_precedes_hostile_normalization(
    path: str,
    replacement: object,
    error_type: type[HermesProtocolError],
) -> None:
    """Safe staged classifications do not require hostile normalization."""
    value = _supported_capabilities()
    value[path] = replacement

    with pytest.raises(error_type) as caught:
        validate_capabilities(_HostileIterationMapping(value))
    assert type(caught.value) is error_type


def test_hostile_mapping_normalization_is_a_scrubbed_protocol_error() -> None:
    """A post-stage normalization exception reduces to safe generic protocol."""
    rejected = _HostileIterationMapping(_supported_capabilities())

    error = _assert_sanitized_protocol_failure(rejected)

    assert type(error) is HermesProtocolError
    assert _HOSTILE_ITERATION_CANARY not in "".join(traceback.format_exception(error))
    _assert_package_traceback_is_scrubbed(
        error,
        canaries=(_HOSTILE_ITERATION_CANARY,),
        forbidden_objects=(rejected,),
    )


@pytest.mark.parametrize(
    ("path", "replacement", "error_type"),
    [
        ("platform", "identity-traceback-canary", HermesIdentityError),
        (
            "features",
            {"chat_completions": "capability-traceback-canary"},
            HermesCapabilityError,
        ),
    ],
)
def test_invalid_capability_context_and_cause_exclude_canary_values(
    path: str,
    replacement: object,
    error_type: type[HermesProtocolError],
) -> None:
    """Pydantic details and raw invalid values never escape validation."""
    canary = (
        "identity-traceback-canary"
        if path == "platform"
        else "capability-traceback-canary"
    )
    value = _supported_capabilities()
    value[path] = replacement

    with pytest.raises(error_type) as caught:
        validate_capabilities(value)
    error = caught.value
    assert type(error) is error_type
    assert isinstance(error, HermesProtocolError)
    assert error.category is FailureCategory.PROTOCOL
    assert error.status_code is None
    assert error.retryable is False
    assert error.__cause__ is None
    assert error.__context__ is None
    assert vars(error) == {}
    public_state = " | ".join(
        (
            str(error),
            repr(error),
            repr(error.args),
            repr(vars(error)),
            "".join(traceback.format_exception(error)),
        )
    )
    assert canary not in public_state
    assert "ValidationError" not in public_state


@pytest.mark.parametrize(
    ("path", "replacement", "error_type"),
    [
        ("platform", "identity-traceback-canary", HermesIdentityError),
        (
            "features",
            {"chat_completions": "capability-traceback-canary"},
            HermesCapabilityError,
        ),
    ],
)
def test_direct_capability_failure_scrubs_raw_input_from_traceback_frames(
    path: str,
    replacement: object,
    error_type: type[HermesProtocolError],
) -> None:
    """Direct validation failures retain no rejected mapping or nested canary."""
    canary = (
        "identity-traceback-canary"
        if path == "platform"
        else "capability-traceback-canary"
    )
    rejected = _supported_capabilities()
    rejected[path] = replacement

    with pytest.raises(error_type) as caught:
        validate_capabilities(rejected)
    error = caught.value
    assert type(error) is error_type

    _assert_package_traceback_is_scrubbed(
        error,
        canaries=(canary,),
        forbidden_objects=(rejected,),
    )


def test_validation_is_deterministic_under_replay_and_concurrency() -> None:
    """Each call owns fresh immutable state and cannot leak classifications."""
    supported = _supported_capabilities()
    rejected = _supported_capabilities()
    rejected["platform"] = "not-hermes-agent"

    expected = validate_capabilities(supported)
    assert all(validate_capabilities(supported) == expected for _ in range(25))

    def classify(index: int) -> tuple[str, object]:
        if index % 2:
            try:
                validate_capabilities(rejected)
            except HermesProtocolError as err:
                return ("failure", err.category)
            msg = "Rejected capabilities unexpectedly passed"
            raise AssertionError(msg)
        return ("success", validate_capabilities(supported))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(classify, range(64)))

    assert results[::2] == (("success", expected),) * 32
    assert results[1::2] == (("failure", FailureCategory.PROTOCOL),) * 32


def test_stream_vocabulary_is_closed_immutable_and_text_safe() -> None:
    """Seven isolated records use five closed event variants safely."""
    event_types = set(get_args(HermesEvent.__value__))
    assert event_types == {
        AssistantDeltaEvent,
        ToolProgressEvent,
        UsageEvent,
        KeepaliveEvent,
        TerminalEvent,
    }

    records = (
        AssistantDeltaEvent(text="hello"),
        ToolProgressEvent(
            tool_call_id="call-contract-001",
            tool_name="home_assistant",
            status=hermes_api.ToolProgressStatus.RUNNING,
        ),
        UsageEvent(input_tokens=2, output_tokens=3, total_tokens=5),
        KeepaliveEvent(),
        TerminalEvent(outcome=TerminalOutcome.SUCCESS),
        TerminalEvent(outcome=TerminalOutcome.LENGTH),
        TerminalEvent(outcome=TerminalOutcome.UPSTREAM_ERROR),
    )

    assert len(records) == _EVENT_RECORD_COUNT
    assert [record for record in records if hasattr(record, "text")] == [records[0]]
    for record in records:
        with pytest.raises(ValidationError, match="Instance is frozen"):
            record.unplanned = "mutable"  # type: ignore[attr-defined]


def test_conversation_event_enums_are_closed_and_stable() -> None:
    """The public tool and terminal metadata enums expose only approved values."""
    assert tuple(hermes_api.ToolProgressStatus) == (
        hermes_api.ToolProgressStatus.RUNNING,
        hermes_api.ToolProgressStatus.COMPLETED,
    )
    assert tuple(hermes_api.TerminalFailureReason) == (
        hermes_api.TerminalFailureReason.OUTPUT_TRUNCATED,
        hermes_api.TerminalFailureReason.AGENT_ERROR,
        hermes_api.TerminalFailureReason.UNKNOWN,
    )


@pytest.mark.parametrize(
    "value",
    [
        "!",
        "~" * _LIFECYCLE_TEXT_MAX_LENGTH,
        "Call.ID:/Case?Kept=Yes&value_1",
    ],
)
@pytest.mark.parametrize("field", ["tool_call_id", "tool_name"])
def test_tool_progress_identifiers_accept_exact_visible_ascii_bounds(
    field: str,
    value: str,
) -> None:
    """Valid lifecycle text is preserved exactly at both public fields."""
    fields = {
        "tool_call_id": "call-contract-001",
        "tool_name": "home_assistant",
        "status": hermes_api.ToolProgressStatus.RUNNING,
    }
    fields[field] = value

    event = ToolProgressEvent.model_validate(fields)

    assert getattr(event, field) == value
    assert type(getattr(event, field)) is str


class _LifecycleStringSubclass(str):
    """A coercible lifecycle value that the exact-type contract rejects."""

    __slots__ = ()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "x" * (_LIFECYCLE_TEXT_MAX_LENGTH + 1),
        "contains space",
        "\t",
        "line\nbreak",
        "nul\0byte",
        "café",
        _LifecycleStringSubclass("subclass"),
        b"bytes",
        7,
        True,
    ],
)
@pytest.mark.parametrize("field", ["tool_call_id", "tool_name"])
def test_tool_progress_identifiers_reject_non_contract_values(
    field: str,
    value: object,
) -> None:
    """Lifecycle identifiers reject type, range, and character lookalikes."""
    fields: dict[str, object] = {
        "tool_call_id": "call-contract-001",
        "tool_name": "home_assistant",
        "status": hermes_api.ToolProgressStatus.RUNNING,
    }
    fields[field] = value

    with pytest.raises(ValidationError):
        ToolProgressEvent.model_validate(fields)


def test_tool_progress_requires_exact_fields_enum_and_immutability() -> None:
    """The enriched event is a strict frozen three-field public record."""
    event = ToolProgressEvent(
        tool_call_id="call-contract-001",
        tool_name="home_assistant",
        status=hermes_api.ToolProgressStatus.COMPLETED,
    )

    assert set(ToolProgressEvent.model_fields) == {
        "tool_call_id",
        "tool_name",
        "status",
    }
    assert event.status is hermes_api.ToolProgressStatus.COMPLETED
    with pytest.raises(ValidationError):
        ToolProgressEvent(
            tool_call_id="call-contract-001",
            tool_name="home_assistant",
            status="running",  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError, match="Instance is frozen"):
        event.status = hermes_api.ToolProgressStatus.RUNNING


def test_terminal_event_defaults_and_strict_metadata_contract() -> None:
    """Terminal metadata defaults safely and accepts only exact public types."""
    terminal = TerminalEvent(outcome=TerminalOutcome.SUCCESS)
    assert terminal == TerminalEvent(
        outcome=TerminalOutcome.SUCCESS,
        partial=False,
        failure_reason=None,
    )
    assert set(TerminalEvent.model_fields) == {
        "outcome",
        "partial",
        "failure_reason",
    }

    failure = TerminalEvent(
        outcome=TerminalOutcome.UPSTREAM_ERROR,
        partial=True,
        failure_reason=hermes_api.TerminalFailureReason.AGENT_ERROR,
    )
    assert failure.partial is True
    assert failure.failure_reason is hermes_api.TerminalFailureReason.AGENT_ERROR
    with pytest.raises(ValidationError):
        TerminalEvent(outcome=TerminalOutcome.SUCCESS, partial=1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        TerminalEvent(
            outcome=TerminalOutcome.UPSTREAM_ERROR,
            failure_reason="agent_error",  # type: ignore[arg-type]
        )
    for forbidden_field in ("completed", "failed", "error_code", "error"):
        with pytest.raises(ValidationError):
            TerminalEvent.model_validate(
                {
                    "outcome": TerminalOutcome.UPSTREAM_ERROR,
                    forbidden_field: True,
                }
            )
    with pytest.raises(ValidationError, match="Instance is frozen"):
        failure.partial = False


@pytest.mark.parametrize(
    "rejected",
    ["lifecycle secret canary", object()],
)
def test_lifecycle_validator_failure_is_input_value_free(rejected: object) -> None:
    """The shared validator raises without rendering rejected lifecycle data."""
    with pytest.raises(ValueError, match=r"^$") as caught:
        hermes_models._require_lifecycle_text(rejected)  # pyright: ignore[reportPrivateUsage]

    rendered = f"{caught.value!s} | {caught.value!r} | {caught.value.args!r}"
    assert "lifecycle secret canary" not in rendered


def test_failure_categories_are_stable_and_distinct() -> None:
    """The public failure vocabulary contains exactly the four locked categories."""
    assert tuple(FailureCategory) == (
        FailureCategory.AUTHENTICATION,
        FailureCategory.HTTP_STATUS,
        FailureCategory.TRANSPORT,
        FailureCategory.PROTOCOL,
    )
    assert {category.value for category in FailureCategory} == {
        "authentication",
        "http_status",
        "transport",
        "protocol",
    }


@pytest.mark.parametrize("status_code", [401, 403])
def test_authentication_failures_are_non_retryable(status_code: int) -> None:
    """Authentication failures retain only their safe status classification."""
    error = HermesAuthenticationError(status_code=status_code)

    assert isinstance(error, HermesContractError)
    assert error.category is FailureCategory.AUTHENTICATION
    assert error.status_code == status_code
    assert error.retryable is False


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [
        (400, False),
        (404, False),
        (408, False),
        (429, True),
        (500, True),
        (503, True),
        (599, True),
        (600, False),
    ],
)
def test_http_status_retryability_is_deterministic(
    status_code: int, retryable: object
) -> None:
    """Only rate limits and server failures are retryable HTTP outcomes."""
    error = HermesHttpStatusError(status_code=status_code)

    assert error.category is FailureCategory.HTTP_STATUS
    assert error.status_code == status_code
    assert error.retryable is retryable


@pytest.mark.parametrize(
    ("transient", "retryable"),
    [(True, True), (False, False)],
)
def test_transport_retryability_is_explicit(
    transient: object, retryable: object
) -> None:
    """Transport callers classify transient and non-transient failures explicitly."""
    assert isinstance(transient, bool)
    error = HermesTransportError(transient=transient)

    assert error.category is FailureCategory.TRANSPORT
    assert error.status_code is None
    assert error.retryable is retryable


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "not a URL",
        "ftp://user:password@private.invalid/path?token=url-canary",
    ],
)
def test_invalid_base_url_outcome_is_non_retryable_and_url_safe(base_url: str) -> None:
    """Every invalid base maps to one URL-free domain result."""
    error = HermesTransportError(transient=False)

    assert error.retryable is False
    if base_url:
        assert base_url not in str(error)
        assert base_url not in repr(error)
        assert base_url not in repr(vars(error))


def test_protocol_failures_share_the_complete_safe_contract() -> None:
    """Capability validation uses the same immutable metadata-only base."""
    error = _assert_sanitized_protocol_failure(None)

    assert isinstance(error, HermesContractError)


def test_failure_public_state_contains_only_safe_metadata() -> None:
    """Exceptions expose only category, optional status, and retryability."""
    errors = (
        HermesAuthenticationError(status_code=401),
        HermesHttpStatusError(status_code=503),
        HermesTransportError(transient=True),
        HermesProtocolError(),
    )

    assert HermesContractError.__slots__ == (
        "category",
        "status_code",
        "retryable",
    )
    for error in errors:
        assert vars(error) == {}
        assert type(error).__slots__ == ()
        with pytest.raises(FrozenInstanceError):
            error.retryable = not error.retryable  # type: ignore[misc]


def test_failure_strings_representations_and_fields_exclude_canaries() -> None:
    """Credentials, bodies, headers, and full URLs never enter public state."""
    canaries = (
        "Bearer sk-super-secret-canary",
        "Authorization",
        '{"prompt":"private household body"}',
        "https://user:pass@private.invalid/v1/capabilities?token=url-canary",
    )
    errors = (
        HermesAuthenticationError(status_code=403),
        HermesHttpStatusError(status_code=500),
        HermesTransportError(transient=True),
        HermesProtocolError(),
    )

    for error in errors:
        public_state = " | ".join(
            (
                str(error),
                repr(error),
                repr(error.args),
                repr(vars(error)),
                repr(error.category),
                repr(error.status_code),
                repr(error.retryable),
            )
        )
        assert all(canary not in public_state for canary in canaries)
        assert error.__cause__ is None
        assert error.__context__ is None


@pytest.mark.parametrize(
    ("constructor_name", "argument"),
    [
        ("HermesAuthenticationError", True),
        ("HermesHttpStatusError", True),
        ("HermesHttpStatusError", "503"),
    ],
)
def test_status_metadata_must_be_an_integer(
    constructor_name: str, argument: object
) -> None:
    """Boolean and string lookalikes cannot enter the integer status field."""
    constructors: dict[str, Any] = {
        "HermesAuthenticationError": HermesAuthenticationError,
        "HermesHttpStatusError": HermesHttpStatusError,
    }
    constructor = constructors[constructor_name]
    with pytest.raises(TypeError):
        constructor(status_code=argument)


def test_transport_metadata_requires_a_real_boolean() -> None:
    """Retryability cannot be selected with a truthy non-boolean value."""
    with pytest.raises(TypeError):
        HermesTransportError(transient=1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("category", "retryable"),
    [
        (cast("FailureCategory", "protocol"), False),
        (FailureCategory.PROTOCOL, cast("bool", 1)),
    ],
)
def test_base_failure_metadata_requires_closed_runtime_types(
    category: FailureCategory,
    retryable: object,
) -> None:
    """The public base cannot retain lookalike category or retryability values."""
    assert isinstance(retryable, bool) or retryable == 1
    with pytest.raises(TypeError):
        HermesContractError(
            category=category,
            status_code=None,
            retryable=cast("bool", retryable),
        )
