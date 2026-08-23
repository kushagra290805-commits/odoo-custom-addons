# ADR 0067: Generic Session-Bound MCP Transport Architecture

## Status
Accepted

Phase 44.2 reconciliation:
- The implementation is `SessionTransportPool`
  (`services/connector/connectors/mcp/pool.py`); the name `McpTransportPool`
  used below refers to the same component. The implemented name is retained
  (ADR-0068).
- Hardening added in Phase 44.2 (W7): a hard `max_size` bound (100) with LRU
  eviction under the existing pool lock, in addition to the TTL eviction
  described below. No other pool behavior was changed; backward compatibility
  for `session_binding="none"` is preserved (pool bypassed entirely).

## Context
During the Universal Capability Platform (UCP) Phase 43.4 validation against the official Penpot MCP server, a critical architectural impedance mismatch was discovered.

UCP currently treats MCP connections as **Connection-Scoped**: it establishes a single, long-lived `McpTransport` (e.g., an SSE connection) per connector and multiplexes multiple execution requests over it. Any per-request identity or context is expected to be passed via the standard MCP JSON-RPC `meta` parameter on individual `call_tool` invocations (as implemented in ADR-0066).

However, Penpot MCP treats sessions as **Session-Bound**: it requires the ephemeral user session identity (`userToken`) to be passed via a URL query parameter during the initial HTTP/SSE transport connection handshake. It ignores the `meta` parameter on subsequent `call_tool` requests, fundamentally requiring **one active MCP transport connection per user session**.

To support this model without creating a Penpot-specific Python adapter, we must extend UCP to generically support both connection-scoped and session-bound MCP transports.

## Decision
We will introduce a **Session-Bound Transport Pool** managed strictly at the SDK Connector level (`McpConnector`), ensuring the higher-level `ConnectorDispatcher` remains agnostic to MCP transport pooling complexities.

### Configuration Extension
The `McpConfiguration` will be extended with a session binding policy:
```python
session_binding: str             # "none" | "request_context"
session_binding_field: str       # e.g., "userToken"
session_binding_location: str    # "query" | "header"
```

### The `McpConnector` Role
1. **Global Transport**: `McpConnector` will maintain a default global `McpTransport` (initialized without a session token). This is used for capabilities that do not require an active session (e.g., `tools.list`, `resources.list`), allowing UCP health checks and capability discovery to succeed globally.
2. **Session Transport Pool**: For execution capabilities (e.g., `tools.call`), if `session_binding` is active, the `McpProvider` will request a transport from an internal `McpTransportPool` using the identity extracted from `request_context[session_binding_field]`.

## Rejected Alternatives

1. **Continue using request-level MCP `meta`**: Rejected because the Penpot MCP server explicitly ignores this for session authentication, leading to a protocol mismatch.
2. **Recreate transport per request**: Creating a new SSE/WebSocket connection and performing the MCP `initialize` handshake per capability execution adds 200-500ms of latency and massive resource overhead. Rejected for performance.
3. **Generic transport factory managed by ConnectorDispatcher**: Forcing `ConnectorDispatcher` to manage session pools would pollute the generic dispatcher with MCP-specific connection semantics and break global health checks (which probe the connector without a user session).

## Security Model
- **Cache Key Protection**: Ephemeral tokens (like `userToken`) must never be used directly as dictionary cache keys in plaintext. The `McpTransportPool` will hash the token (e.g., `sha256(token)`) to derive the cache key, preventing memory inspection leaks.
- **Strict Isolation**: A transport connection initialized with User A's token will only be retrieved if the exact identical token is provided in the `request_context`.
- **Ephemeral Integrity**: Tokens remain strictly in memory and are never persisted to the Odoo database or logged.

## Lifecycle and Concurrency
- **Concurrency**: The `McpTransportPool` will be thread-safe, utilizing locks during transport initialization to prevent thundering herds for the same session.
- **Eviction**: A Time-To-Live (TTL) eviction policy (e.g., 10 minutes of inactivity) will reap idle session transports and shut down their background `asyncio` event loops gracefully.
- **Cleanup**: When `ConnectorDispatcher` shuts down the parent `McpConnector`, the connector will iteratively shut down the global transport and all active pooled transports.

## Backward Compatibility
Connectors with `session_binding="none"` (the default) will bypass the pool entirely and utilize a single global transport, preserving the exact legacy behavior for existing connectors like GitHub, Tavily, and Firecrawl.
