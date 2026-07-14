"""Pure contracts for Hermes capabilities, events, and failures."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from typing import Any, cast, get_args

import pytest
from pydantic import ValidationError

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
from tests.helpers.hermes import add_json_key, load_golden_json, reorder_json_keys

_EVENT_RECORD_COUNT = 7


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


def test_supported_capabilities_produce_an_immutable_typed_value() -> None:
    """The canonical document maps to the exact supported semantic contract."""
    result = validate_capabilities(_supported_capabilities())

    assert result == HermesCapabilities(
        object="hermes.api_server.capabilities",
        platform="hermes-agent",
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


def test_invalid_capability_context_and_cause_exclude_canary_values() -> None:
    """Pydantic details and raw invalid values never escape validation."""
    canary = "Bearer sk-capability-validation-canary"
    value = _supported_capabilities()
    value["platform"] = canary

    error = _assert_sanitized_protocol_failure(value)
    public_state = " | ".join(
        (
            str(error),
            repr(error),
            repr(error.args),
            repr(vars(error)),
        )
    )
    assert canary not in public_state
    assert "ValidationError" not in public_state


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
        ToolProgressEvent(tool_name="home_assistant", status="running"),
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
