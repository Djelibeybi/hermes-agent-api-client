"""Immutable public models for the Hermes API boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)


class FailureCategory(StrEnum):
    """Stable categories for Hermes contract failures."""

    AUTHENTICATION = "authentication"
    HTTP_STATUS = "http_status"
    TRANSPORT = "transport"
    PROTOCOL = "protocol"


class TerminalOutcome(StrEnum):
    """Terminal outcomes exposed by the Hermes stream contract."""

    SUCCESS = "success"
    LENGTH = "length"
    UPSTREAM_ERROR = "upstream_error"


class ToolProgressStatus(StrEnum):
    """Closed lifecycle states for one Hermes tool invocation."""

    RUNNING = "running"
    COMPLETED = "completed"


class TerminalFailureReason(StrEnum):
    """Safe bounded reasons for a non-success terminal event."""

    OUTPUT_TRUNCATED = "output_truncated"
    AGENT_ERROR = "agent_error"
    UNKNOWN = "unknown"


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


class AssistantDeltaEvent(_FrozenModel):
    """One ordered piece of assistant-visible text."""

    text: str


class ToolProgressEvent(_FrozenModel):
    """Bounded non-assistant progress metadata for a tool invocation."""

    tool_call_id: str
    tool_name: str
    status: ToolProgressStatus

    @field_validator("tool_call_id", "tool_name", mode="before")
    @classmethod
    def _require_exact_lifecycle_text(cls, value: object) -> str:
        return _require_lifecycle_text(value)


class UsageEvent(_FrozenModel):
    """Token usage reported by Hermes for one stream."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class KeepaliveEvent(_FrozenModel):
    """A comment record that keeps the upstream stream active."""


class TerminalEvent(_FrozenModel):
    """An explicit success or typed non-success stream result."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    outcome: TerminalOutcome
    partial: bool = False
    failure_reason: TerminalFailureReason | None = None


type HermesEvent = (
    AssistantDeltaEvent
    | ToolProgressEvent
    | UsageEvent
    | KeepaliveEvent
    | TerminalEvent
)
