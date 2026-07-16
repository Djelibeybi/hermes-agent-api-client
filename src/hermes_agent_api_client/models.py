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

    tool_name: str
    status: str


class UsageEvent(_FrozenModel):
    """Token usage reported by Hermes for one stream."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class KeepaliveEvent(_FrozenModel):
    """A comment record that keeps the upstream stream active."""


class TerminalEvent(_FrozenModel):
    """An explicit success or typed non-success stream result."""

    outcome: TerminalOutcome


type HermesEvent = (
    AssistantDeltaEvent
    | ToolProgressEvent
    | UsageEvent
    | KeepaliveEvent
    | TerminalEvent
)
