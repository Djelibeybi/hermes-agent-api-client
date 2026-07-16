"""Wire validation and safe failures for the Hermes API boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Never, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from .models import (
    FailureCategory,
    HermesCapabilities,
    _require_lifecycle_text,  # pyright: ignore[reportPrivateUsage]
)


def _validate_error_metadata(
    category: object,
    status_code: object,
    retryable: object,
) -> None:
    """Reject unsafe or incorrectly typed public exception metadata."""
    if not isinstance(category, FailureCategory):
        raise TypeError
    if status_code is not None and (
        isinstance(status_code, bool) or not isinstance(status_code, int)
    ):
        raise TypeError
    if not isinstance(retryable, bool):
        raise TypeError


def _validate_status_code(status_code: object) -> None:
    """Require a real integer rather than a boolean or lookalike."""
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise TypeError


def _validate_transient(transient: object) -> None:
    """Require an explicit real boolean transport classification."""
    if not isinstance(transient, bool):
        raise TypeError


@dataclass(frozen=True, slots=True, repr=False)
class HermesContractError(Exception):
    """Catchable safe base for failures at the public Hermes boundary."""

    category: FailureCategory
    status_code: int | None
    retryable: bool

    def __post_init__(self) -> None:
        """Initialize the exception with a metadata-only safe message."""
        _validate_error_metadata(self.category, self.status_code, self.retryable)
        Exception.__init__(self, self._safe_message())

    def _safe_message(self) -> str:
        """Build a deterministic message without private upstream details."""
        status = "none" if self.status_code is None else str(self.status_code)
        retryable = str(self.retryable).lower()
        return (
            f"Hermes {self.category.value} failure "
            f"(status={status}, retryable={retryable})"
        )

    def __str__(self) -> str:
        """Return the safe public failure message."""
        return self._safe_message()

    def __repr__(self) -> str:
        """Return safe structured metadata for debugging."""
        return (
            f"{type(self).__name__}(category={self.category.value!r}, "
            f"status_code={self.status_code!r}, retryable={self.retryable!r})"
        )


class HermesProtocolError(HermesContractError):
    """An invalid or unsupported Hermes protocol value."""

    __slots__ = ()

    def __init__(self) -> None:
        """Initialize a deterministic non-retryable protocol failure."""
        super().__init__(
            category=FailureCategory.PROTOCOL,
            status_code=None,
            retryable=False,
        )


class HermesIdentityError(HermesProtocolError):
    """A capability document does not identify a Hermes Agent endpoint."""

    __slots__ = ()


class HermesCapabilityError(HermesProtocolError):
    """A Hermes endpoint lacks required Chat Completions support."""

    __slots__ = ()


class _CapabilityFailureKind(StrEnum):
    IDENTITY = "identity"
    CAPABILITY = "capability"
    PROTOCOL = "protocol"


@dataclass(frozen=True, slots=True)
class _JsonObjectPairs:
    """One JSON object whose ordered members retain duplicate-name evidence."""

    pairs: tuple[tuple[str, object], ...]


def _json_object_pairs_hook(  # pyright: ignore[reportUnusedFunction]
    pairs: list[tuple[str, object]],
) -> _JsonObjectPairs:
    """Keep one decoded JSON object distinct from arrays and ordinary mappings."""
    return _JsonObjectPairs(tuple(pairs))


def _materialize_json_value(value: object) -> object:
    """Recursively convert private pair nodes into ordinary JSON containers."""
    if isinstance(value, _JsonObjectPairs):
        return {
            key: _materialize_json_value(member_value)
            for key, member_value in value.pairs
        }
    if isinstance(value, list):
        items = cast("list[object]", value)
        return [_materialize_json_value(item) for item in items]
    return value


def _has_duplicate_member(value: _JsonObjectPairs, member_name: str) -> bool:
    """Report whether one exact object member occurs more than once."""
    found = False
    for name, _ in value.pairs:
        if name != member_name:
            continue
        if found:
            return True
        found = True
    return False


def _last_member_value(value: _JsonObjectPairs, member_name: str) -> object:
    """Return the last value for an additive-compatible object member."""
    result: object = _MISSING_JSON_MEMBER
    for name, member_value in value.pairs:
        if name == member_name:
            result = member_value
    return result


_MISSING_JSON_MEMBER = object()
_TOOL_PROGRESS_MEMBERS = frozenset(("toolCallId", "tool", "status"))


def _project_tool_progress_object(  # pyright: ignore[reportUnusedFunction]
    value: object,
) -> dict[str, object] | None:
    """Project unique approved progress members and discard all additive data."""
    if not isinstance(value, _JsonObjectPairs):
        return None

    projected: dict[str, object] = {}
    try:
        for name, member_value in value.pairs:
            if name not in _TOOL_PROGRESS_MEMBERS:
                continue
            if name in projected:
                return None
            projected[name] = _materialize_json_value(member_value)
    except RecursionError:
        return None
    return projected


def _project_chat_chunk_object(  # pyright: ignore[reportUnusedFunction]
    value: object,
) -> dict[str, object] | None:
    """Check approved chat duplicates, then materialize the complete wire tree."""
    if not isinstance(value, _JsonObjectPairs):
        return None
    if _has_duplicate_member(value, "hermes"):
        return None

    choices = _last_member_value(value, "choices")
    choice_values = cast("list[object]", choices) if isinstance(choices, list) else []
    if (
        len(choice_values) == 1
        and isinstance(choice_values[0], _JsonObjectPairs)
        and _has_duplicate_member(choice_values[0], "finish_reason")
    ):
        return None

    try:
        materialized = _materialize_json_value(value)
    except RecursionError:
        return None
    return cast("dict[str, object]", materialized)


def _raise_capability_failure(kind: _CapabilityFailureKind) -> Never:
    """Raise the exact safe capability failure from an input-free frame."""
    if kind is _CapabilityFailureKind.IDENTITY:
        raise HermesIdentityError
    if kind is _CapabilityFailureKind.CAPABILITY:
        raise HermesCapabilityError
    raise HermesProtocolError


class HermesAuthenticationError(HermesContractError):
    """A bearer credential was rejected by the Hermes server."""

    __slots__ = ()

    def __init__(self, *, status_code: int | None = None) -> None:
        """Initialize a deterministic non-retryable authentication failure."""
        super().__init__(
            category=FailureCategory.AUTHENTICATION,
            status_code=status_code,
            retryable=False,
        )


class HermesHttpStatusError(HermesContractError):
    """A non-authentication HTTP status rejected a Hermes operation."""

    __slots__ = ()

    def __init__(self, *, status_code: int) -> None:
        """Initialize an HTTP failure using the stable retryability matrix."""
        _validate_status_code(status_code)
        super().__init__(
            category=FailureCategory.HTTP_STATUS,
            status_code=status_code,
            retryable=(
                status_code == _RATE_LIMIT_STATUS
                or _SERVER_ERROR_MIN <= status_code <= _SERVER_ERROR_MAX
            ),
        )


class HermesTransportError(HermesContractError):
    """A transient or non-transient failure before protocol validation."""

    __slots__ = ()

    def __init__(self, *, transient: bool) -> None:
        """Initialize a transport failure without retaining private details."""
        _validate_transient(transient)
        super().__init__(
            category=FailureCategory.TRANSPORT,
            status_code=None,
            retryable=transient,
        )


_RATE_LIMIT_STATUS = 429
_SERVER_ERROR_MIN = 500
_SERVER_ERROR_MAX = 599


class _WireModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore",
        frozen=True,
        strict=True,
    )


class _AuthWire(_WireModel):
    type: Literal["bearer"]
    required: Literal[True]

    @field_validator("required", mode="before")
    @classmethod
    def _require_boolean_true(cls, value: object) -> object:
        if value is not True:
            raise ValueError
        return value


class _FeaturesWire(_WireModel):
    chat_completions: Literal[True]
    chat_completions_streaming: Literal[True]

    @field_validator(
        "chat_completions",
        "chat_completions_streaming",
        mode="before",
    )
    @classmethod
    def _require_boolean_true(cls, value: object) -> object:
        if value is not True:
            raise ValueError
        return value


class _CapabilitiesWire(_WireModel):
    object: Literal["hermes.api_server.capabilities"]
    platform: Literal["hermes-agent"]
    model: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    auth: _AuthWire
    features: _FeaturesWire

    @field_validator("model")
    @classmethod
    def _reject_whitespace_only_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError
        return value


type _NonNegativeInteger = Annotated[int, Field(ge=0)]


class _ToolProgressWire(_WireModel):
    tool_call_id: str = Field(alias="toolCallId")
    tool: str
    status: Literal["running", "completed"]

    @field_validator("tool_call_id", "tool", mode="before")
    @classmethod
    def _require_exact_lifecycle_text(cls, value: object) -> str:
        return _require_lifecycle_text(value)


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


_MAPPING_ACCESS_FAILURE = object()
_STRING_COMPARISON_FAILURE = object()


def _safe_mapping_get(mapping: Mapping[object, object], key: str) -> object:
    """Read one mapping value or return an input-independent sentinel."""
    try:
        return mapping.get(key)
    except Exception:  # noqa: BLE001 - hostile mappings reduce to safe metadata
        return _MAPPING_ACCESS_FAILURE


def _safe_exact_string_match(value: object, expected: str) -> object:
    """Compare one string or return an input-independent failure sentinel."""
    if not isinstance(value, str):
        return False
    try:
        return value == expected
    except Exception:  # noqa: BLE001 - hostile strings reduce to safe metadata
        return _STRING_COMPARISON_FAILURE


def _classify_capability_identity(
    document: Mapping[object, object],
) -> _CapabilityFailureKind | None:
    """Classify the required identity discriminators in wire order."""
    object_value = _safe_mapping_get(document, "object")
    if object_value is _MAPPING_ACCESS_FAILURE:
        return _CapabilityFailureKind.PROTOCOL
    object_matches = _safe_exact_string_match(
        object_value,
        "hermes.api_server.capabilities",
    )
    if object_matches is _STRING_COMPARISON_FAILURE:
        return _CapabilityFailureKind.PROTOCOL
    if object_matches is not True:
        return _CapabilityFailureKind.IDENTITY

    platform_value = _safe_mapping_get(document, "platform")
    if platform_value is _MAPPING_ACCESS_FAILURE:
        return _CapabilityFailureKind.PROTOCOL
    platform_matches = _safe_exact_string_match(platform_value, "hermes-agent")
    if platform_matches is _STRING_COMPARISON_FAILURE:
        return _CapabilityFailureKind.PROTOCOL
    return None if platform_matches is True else _CapabilityFailureKind.IDENTITY


def _classify_required_chat_support(
    document: Mapping[object, object],
) -> tuple[Mapping[object, object] | None, _CapabilityFailureKind | None]:
    """Return mapping-valued features or the safe required-chat failure."""
    features = _safe_mapping_get(document, "features")
    if features is _MAPPING_ACCESS_FAILURE:
        return (None, _CapabilityFailureKind.PROTOCOL)
    if not isinstance(features, Mapping):
        return (None, _CapabilityFailureKind.CAPABILITY)

    feature_values = cast("Mapping[object, object]", features)
    chat_completions = _safe_mapping_get(feature_values, "chat_completions")
    if chat_completions is _MAPPING_ACCESS_FAILURE:
        return (None, _CapabilityFailureKind.PROTOCOL)
    if chat_completions is not True:
        return (None, _CapabilityFailureKind.CAPABILITY)
    return (feature_values, None)


def _normalize_capability_mapping(
    document: Mapping[object, object],
    features: Mapping[object, object],
) -> dict[object, object] | None:
    """Copy known mappings for Pydantic without leaking mapping failures."""
    try:
        normalized = dict(document)
        auth = normalized.get("auth")
        if isinstance(auth, Mapping):
            normalized["auth"] = dict(cast("Mapping[object, object]", auth))
        normalized["features"] = dict(features)
    except Exception:  # noqa: BLE001 - hostile mappings reduce to safe metadata
        return None
    return normalized


def _parse_capabilities(
    value: object,
) -> tuple[HermesCapabilities | None, _CapabilityFailureKind | None]:
    """Reduce capability validation into a public value or safe failure kind."""
    if not isinstance(value, Mapping):
        return (None, _CapabilityFailureKind.PROTOCOL)

    document = cast("Mapping[object, object]", value)
    identity_failure = _classify_capability_identity(document)
    if identity_failure is not None:
        return (None, identity_failure)

    features, capability_failure = _classify_required_chat_support(document)
    if capability_failure is not None:
        return (None, capability_failure)
    normalized = _normalize_capability_mapping(
        document,
        cast("Mapping[object, object]", features),
    )
    if normalized is None:
        return (None, _CapabilityFailureKind.PROTOCOL)

    try:
        parsed = _CapabilitiesWire.model_validate(normalized)
        capabilities = HermesCapabilities(
            object=parsed.object,
            platform=parsed.platform,
            model=parsed.model,
            auth_type=parsed.auth.type,
            auth_required=parsed.auth.required,
            chat_completions=parsed.features.chat_completions,
            chat_completions_streaming=parsed.features.chat_completions_streaming,
        )
    except ValidationError:
        return (None, _CapabilityFailureKind.PROTOCOL)
    return (capabilities, None)


def _parse_tool_progress(  # pyright: ignore[reportUnusedFunction]
    value: object,
) -> _ToolProgressWire | None:
    """Parse tool progress without retaining wire validation details."""
    try:
        return _ToolProgressWire.model_validate(value)
    except ValidationError:
        return None


def _parse_chat_chunk(  # pyright: ignore[reportUnusedFunction]
    value: object,
) -> _ChatChunkWire | None:
    """Parse one chat chunk without retaining wire validation details."""
    try:
        return _ChatChunkWire.model_validate(value)
    except ValidationError:
        return None


def validate_capabilities(value: object) -> HermesCapabilities:
    """Validate the minimum forward-compatible Hermes capability semantics."""
    parsed, failure_kind = _parse_capabilities(value)
    if failure_kind is not None:
        value = None
        parsed = None
        _raise_capability_failure(failure_kind)
    return cast("HermesCapabilities", parsed)
