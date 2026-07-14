"""Typed async client for the Hermes Agent API Server."""

from .client import HermesAgentApiClient
from .models import (
    AssistantDeltaEvent,
    HermesCapabilities,
    HermesEvent,
    KeepaliveEvent,
    TerminalEvent,
    TerminalOutcome,
    ToolProgressEvent,
    UsageEvent,
)
from .protocol import (
    HermesAuthenticationError,
    HermesContractError,
    HermesHttpStatusError,
    HermesProtocolError,
    HermesTransportError,
)

__version__ = "0.1.0"

__all__ = [
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
]
