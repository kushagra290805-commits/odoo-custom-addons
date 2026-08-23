# Phase 43.4: Real Penpot Session Handshake Validation Report

## 1. Audit Phase 43.3 Implementation
- **Authoritative Context**: `ConnectorRuntimeContext.request_context` and `ExecutionContext.request_context` serve as the single, authoritative representations of ephemeral request context.
- **Separation**: `configuration_snapshot` is strictly limited to static configuration and credentials.
- **Propagation**: `McpProvider` safely passes `request_context` to `McpTransport`, which enforces the `allowed_request_context_fields_json` allowlist before placing the fields into the `meta` parameter of the MCP JSON-RPC tool call.

## 2. Actual Penpot Session Mechanism
Inspection of the Penpot MCP server source (`/opt/penpot/mcp/index.js` inside the `penpotapp/mcp:2.16` container) reveals the exact mechanism:
- The Penpot MCP server operates in `--multi-user` mode.
- A `userToken` is required to bind the MCP tool execution to an active Penpot browser/plugin session.
- **Discovery**: The MCP Server extracts `userToken` strictly from **HTTP Query Parameters** (`req.query.userToken`) during the initial HTTP Handshake for the transport connection (`/mcp` or `/sse`).
- **Mismatch**: The MCP Server **DOES NOT** read the `userToken` from the JSON-RPC `meta` parameter of individual tool execution requests. It establishes a `StreamableSession` or `SSEServerTransport` pinned to that `userToken` upon connection.

## 3. Generic Transport Compatibility
The generic Universal Capability Platform (UCP) maintains a **single, long-lived transport connection** per Connector (e.g., one SSE connection to Penpot) and multiplexes concurrent tool executions over it, distinguishing request-scoped session data via the official MCP `meta` object on each tool call.

Penpot's implementation requires a **separate transport connection for every user session**, authenticated via the URL query parameter at initialization. This is a fundamental impedance mismatch between Penpot's session architecture and the standard multiplexed MCP transport architecture expected by UCP.

## 4. Real Session Validation
As this validation was performed in a headless automated environment, no legitimate user was actively logged into the Penpot frontend (`http://localhost:9001`) with an open plugin to generate the ephemeral `userToken` required for WebSocket bridge synchronization. 

Without a real browser/plugin session, the project-bound tools (`export_shape`, `execute_code`) cannot be legitimately tested. Furthermore, even if a token were obtained, it cannot be passed through the canonical UCP `McpTransport` because UCP initializes the transport generically (without a request-specific `userToken` in the URL), and Penpot ignores the `meta` parameter on subsequent `call_tool` requests.

## 5. Exact Canonical Execution Path
If a real session existed, the path would be:
`UniversalCapabilityRouter` -> `ConnectorExecutionTarget` -> `ConnectorRuntime` -> `McpProvider` -> `McpTransport` (passes context in `meta`) -> `MCP Server`. 

Due to the mechanism mismatch, the MCP Server drops the `meta` context and throws an error that no `userToken` is associated with the transport connection.

## 6. Security Verification
- `userToken` concept is isolated purely in `request_context`.
- UCP enforces explicit allowlists, stripping unapproved ephemeral context fields.
- Static connector credentials remain isolated in `configuration_snapshot`.
- No tokens were generated, logged, or persisted during this phase.

## 7. Final Classification

**FAIL — PENPOT_SESSION_PROTOCOL_MISMATCH**

*Reasoning*: While we are also blocked by the lack of a real browser session (`BLOCKED — REAL_PENPOT_SESSION_REQUIRED`), the primary failure is architectural. The generic UCP path implemented in Phase 43.3 correctly utilizes the standard MCP `meta` mechanism for request context. However, the Penpot MCP server requires the session `userToken` to be injected into the transport connection URL during handshake, fundamentally breaking UCP's generic single-connection multiplexing architecture. Penpot's session propagation mechanism is incompatible with the generic MCP transport. No architectural changes were made to UCP, proving the limitation lies at the Penpot transport layer boundary.
