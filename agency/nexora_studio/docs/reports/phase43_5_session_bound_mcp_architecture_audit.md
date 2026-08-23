# Phase 43.5: Generic Session-Bound MCP Transport Architecture Audit

## 1. Current Architecture
The Universal Capability Platform (UCP) leverages a generic `ConnectorDispatcher` which caches exactly one active SDK Connector (`McpConnector`) instance per `connector_id`. The `McpConnector` encapsulates a single `McpProvider` and a single `McpTransport`. Consequently, the architecture currently enforces a strict 1:1 mapping between a registered connector and a long-lived network transport.

## 2. Exact Transport Lifecycle
- **Initialization**: A transport is created and connected upon the first dispatch to a connector (or during a recovery handshake).
- **Execution**: All subsequent tool executions are multiplexed over this single background `asyncio` event loop and `ClientSession`.
- **Termination**: The transport remains open indefinitely until the connector is disabled, transitions out of `RUNNING`/`HEALTHY`, or the UCP shuts down.

## 3. Exact Penpot Session Lifecycle
- **Handshake Requirements**: The Penpot MCP server requires the `userToken` to be present as a query parameter (e.g., `?userToken=...`) when establishing the SSE or Streamable HTTP connection. 
- **Session Binding**: It associates that HTTP connection persistently with the user session. 
- **Execution Mismatch**: Penpot explicitly ignores the official MCP `meta` object inside individual `call_tool` requests, meaning a single transport connection cannot multiplex requests for different users.

## 4. Existing Reusable Abstractions
- **Dispatch Caching**: `ConnectorDispatcher._active_connectors` handles global connector caching.
- **Context Injection**: `ExecutionContext.request_context` provides a secure, ephemeral transmission mechanism for tokens (implemented in ADR-0066).
- **No Existing Pool**: The codebase currently lacks an LRU connection pool or transport cache abstraction within the SDK layer.

## 5. Architecture Gap
UCP correctly implements **Connection-Scoped** MCPs (where static API keys authenticate the transport globally), but it lacks native support for **Session-Bound** MCPs (where the transport itself must be authenticated ephemerally per user session). Relying on the standard MCP JSON-RPC `meta` parameter (as UCP currently does) is insufficient for servers like Penpot that require transport-level binding.

## 6. Options Evaluated
| Option | Description | Verdict | Reason |
|--------|-------------|---------|--------|
| A | Continue using request-level MCP `meta` | **REJECTED** | Fails outright; Penpot ignores `meta`. |
| B | Recreate transport per request | **REJECTED** | Unacceptable performance penalty (re-initializing MCP connection costs 200-500ms per tool call). |
| C | **Session-bound transport pool in `McpConnector`** | **RECOMMENDED** | Maintains dispatch purity, securely caches connections per session, preserves global tools.list. |
| D | Generic transport factory in `ConnectorDispatcher` | **REJECTED** | Pollutes dispatcher with transport mechanics; breaks global capability discovery (health probes have no session context). |
| E | Separate Penpot-specific transport | **REJECTED** | Violates "Universal" platform invariants; creates parallel architecture. |

## 7. Recommended Architecture
Extend the SDK `McpConnector` to manage a **Session-Bound Transport Pool**.
- **Global Transport**: `McpConnector` maintains its existing `McpTransport` for capability discovery (`tools.list`, `resources.list`), allowing UCP health probes to succeed without user sessions.
- **Pooled Transports**: If the configuration defines `session_binding`, the `McpProvider` borrows a transport from an internal `McpTransportPool` keyed by the secure hash of the session identity extracted from `request_context`.

## 8. Security Analysis
- **Token Protection**: The cache keys in the pool must be cryptographically hashed (e.g., `sha256(userToken)`) to prevent sensitive tokens from leaking via memory dumps or debug logs.
- **Isolation**: A transport bound to User A cannot process requests for User B, preventing cross-user data leakage.
- **Persistence**: Tokens remain ephemeral in memory; they are never persisted to Odoo or written to logs.

## 9. Concurrency Analysis
- The `McpTransportPool` must implement thread-safe locking during transport initialization to prevent thundering herds for identical sessions.
- An LRU/TTL eviction policy (e.g., 5-10 minutes) must run periodically to shut down idle session transports, preventing unbounded memory growth.

## 10. Backward Compatibility
The architecture guarantees strict backward compatibility. Connectors with `session_binding="none"` (the default configuration) will bypass the pool entirely and utilize a single global transport, perfectly preserving the existing mechanics for standard MCPs (GitHub, Tavily).

## 11. Implementation Boundaries
The required changes are strictly confined to the `McpConnector` SDK layer and its configuration models. **No modifications** will be made to:
- `ConnectorDispatcher`
- `ConnectorRuntime`
- Core Domain Models
- Existing Production Connectors
- Odoo Database Schema (except adding JSON configuration fields to the MCP config model)

## 12. Explicit List of Files for Future Modification
- `models/connector/nexora_mcp_server_config.py` (Add configuration fields)
- `services/connector/connectors/mcp/configuration.py` (Map fields)
- `services/connector/connectors/mcp/connector.py` (Orchestrate pool vs global transport)
- `services/connector/connectors/mcp/provider.py` (Route execution to correct transport)
- `services/connector/connectors/mcp/pool.py` (**NEW**: Implement `McpTransportPool`)

### Final Outcome:
**`ARCHITECTURE_READY_FOR_IMPLEMENTATION`**
