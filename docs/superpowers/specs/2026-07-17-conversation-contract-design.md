## Conversation Contract Design

The following functionality is requested by the Hermes Conversation integration for Home Assistant.

## 1. Per-request session headers

Extend [client.py](/Volumes/External/Developer/Djelibeybi/hermes-agent-api-client/src/hermes_agent_api_client/client.py:607):

```python
async def stream_chat_events(
    self,
    request: Mapping[str, object],
    *,
    session_id: str | None = None,
    session_key: str | None = None,
) -> AsyncIterator[HermesEvent]:
    ...
```

Wire mapping:

| Argument      | Header                 | Meaning                                                             |
|---------------|------------------------|---------------------------------------------------------------------|
| `session_id`  | `X-Hermes-Session-Id`  | Transcript identity; changes for each new Home Assistant chat       |
| `session_key` | `X-Hermes-Session-Key` | Durable-memory scope; stable and unique per Home Assistant instance |

Contract:

- Arguments are independent; either, both, or neither may be supplied.
- `None` omits that header.
- Do not accept an arbitrary headers mapping.
- Do not derive either identifier in the client.
- Construct fresh per-request headers; never mutate the client’s bound authorization headers.
- Preserve the caller’s request mapping unchanged.
- Scrub header values from failures, tracebacks, exception context, and retained generator state.
- Closing or cancelling the stream must close only the response, never an injected Home Assistant HTTP client.

Validation:

- Real `str`, not subclasses or coercible values.
- Between 1 and 256 visible ASCII characters.
- Reject empty, whitespace-only, leading/trailing whitespace, non-ASCII, control characters, CR/LF/NUL, and path-shaped session IDs.
- Invalid values fail before network dispatch using the existing safe, non-retryable local-input classification—currently `HermesTransportError(transient=False)`.
- Error text and metadata must not include the rejected value.

The integration will derive:

- `session_id` from the selected profile/config-entry namespace plus Home Assistant conversation identity.
- `session_key` as an opaque derivation of stable Home Assistant instance identity. It is not derived from user, device, satellite, endpoint, credential, or config-entry identity.

## 2. Correlated tool-progress events

Hermes `v2026.7.7.2` already emits `toolCallId`, but the client’s [_ToolProgressWire](src/hermes_agent_api_client/protocol.py:232) currently discards it.

Change the public model to:

```python
class ToolProgressStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"


class ToolProgressEvent(_FrozenModel):
    tool_call_id: str
    tool_name: str
    status: ToolProgressStatus
```

Requirements:

- Parse wire `toolCallId` into `tool_call_id`.
- Accept only the closed `running` and `completed` status set.
- Require a bounded, non-empty tool-call ID and tool name.
- Ignore `emoji`, `label`, arguments, results, and other additive fields.
- Preserve ordered start/completion events.
- Missing, malformed, duplicate-invalid, or unknown lifecycle fields fail as `HermesProtocolError`.
- Never expose arguments, results, labels, or the raw payload.

This lets the integration track unmatched `running` calls. If a stream terminates while any call ID remains unmatched, Home Assistant can safely classify the tool outcome as unknown.

## 3. Safe terminal metadata

The current [TerminalEvent](src/hermes_agent_api_client/models.py:80) exposes only `outcome`, while Hermes already emits safe `partial`, `failed`, `completed`, and `error_code` fields.

Add:

```python
class TerminalFailureReason(StrEnum):
    OUTPUT_TRUNCATED = "output_truncated"
    AGENT_ERROR = "agent_error"
    UNKNOWN = "unknown"


class TerminalEvent(_FrozenModel):
    outcome: TerminalOutcome
    partial: bool = False
    failure_reason: TerminalFailureReason | None = None
```

Mapping:

| Wire condition                                      | Public event                                                              |
|-----------------------------------------------------|---------------------------------------------------------------------------|
| `finish_reason="stop"`                              | `SUCCESS`, `partial=False`, no reason                                     |
| `finish_reason="length"` / `output_truncated`       | `LENGTH`, `partial=True`, `OUTPUT_TRUNCATED`                              |
| `finish_reason="error"` / `agent_error`             | `UPSTREAM_ERROR`, server-provided partial flag, `AGENT_ERROR`             |
| Unknown safe error code                             | `UPSTREAM_ERROR`, `UNKNOWN`                                               |

Continue ignoring the raw `error.message`, exception type, and Hermes `error` text.

Transport failures and cancellation remain exceptions:

- `asyncio.CancelledError` propagates after resource cleanup.
- Transport disconnects remain `HermesTransportError`.
- The integration tracks whether text or tool events preceded the exception; the client need not synthesize a terminal event.

## Acceptance tests

The client change is complete when tests prove:

- Each session header is omitted, sent independently, and sent together.
- Input mappings and bound authorization headers remain unchanged.
- Invalid header values fail before dispatch and leak no canaries through `str`, `repr`, traceback, cause, context, or generator locals.
- Cancellation and early iterator closure release the response without closing injected transport.
- `toolCallId` and the closed status enum survive decoding in order.
- Unmatched running tool calls remain detectable after interruption.
- Terminal partial state and safe failure reasons map correctly.
- Raw Hermes error text never enters public models or exceptions.
- Existing authentication, rate-limit, retryability, protocol, ownership, and terminal-order guarantees remain unchanged.
- Package-root exports, `py.typed`, wheel/sdist verification, strict typing, Ruff, and 100% branch coverage remain green.
