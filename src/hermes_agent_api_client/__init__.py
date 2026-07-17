"""Typed async client for the Hermes Agent API Server."""

from importlib.metadata import version

from .client import HermesAgentApiClient
from .models import (
    AssistantDeltaEvent,
    HermesCapabilities,
    HermesEvent,
    KeepaliveEvent,
    TerminalEvent,
    TerminalFailureReason,
    TerminalOutcome,
    ToolProgressEvent,
    ToolProgressStatus,
    UsageEvent,
)
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

__all__ = [
    "AssistantDeltaEvent",
    "HermesAgentApiClient",
    "HermesAuthenticationError",
    "HermesCapabilities",
    "HermesCapabilityError",
    "HermesContractError",
    "HermesEvent",
    "HermesHttpStatusError",
    "HermesIdentityError",
    "HermesProtocolError",
    "HermesTransportError",
    "KeepaliveEvent",
    "TerminalEvent",
    "TerminalFailureReason",
    "TerminalOutcome",
    "ToolProgressEvent",
    "ToolProgressStatus",
    "UsageEvent",
    "__version__",
]
