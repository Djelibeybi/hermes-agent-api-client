"""Wire validation and safe failures for the Hermes API boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from .models import FailureCategory, HermesCapabilities


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
    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)


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
    auth: _AuthWire
    features: _FeaturesWire


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


def _parse_capabilities(value: object) -> _CapabilitiesWire | None:
    """Parse supported wire semantics without retaining validation details."""
    try:
        return _CapabilitiesWire.model_validate(value)
    except ValidationError:
        return None


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
