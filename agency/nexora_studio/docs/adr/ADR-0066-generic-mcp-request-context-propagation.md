# ADR-0066: Generic MCP Request Context Propagation

## Status
Accepted

## Context & Problem Statement
During Phase 43 (Connector MCP Onboarding Platform), testing the live Penpot connector revealed that the Universal Capability Platform (UCP) effectively dropped request-level context during capability execution. The generic `McpProvider` invoked the generic `McpTransport` without passing down `context`, causing any dynamic, per-request session metadata (like Penpot's `userToken`) to be lost before reaching the MCP Server.

UCP requires a robust mechanism to pass dynamic execution context through the Generic Connector framework, without compromising security or inadvertently treating connection configuration and request context as the same conceptual entity.

## Decision
1. **Context Model Separation**: We enforce a strict separation between **Connection Configuration** (static endpoint, static transport config, permanent credentials) and **Request Context** (ephemeral session ID, dynamic tokens, request-scoped correlations).
2. **Generic Context Extensibility**: We introduced `request_context` to `ExecutionContext` and `ConnectorRuntimeContext`.
3. **Allowlist Policy**: Not all context information is safe to propagate. An explicit policy `allowed_request_context_fields_json` is added to `nexora.mcp_server_config` to govern which keys in `request_context` are permitted to be propagated to the MCP server.
4. **Transport Mechanism**: We mapped the approved request context fields to the `meta` parameter of the MCP Python SDK's `session.call_tool()` function, which perfectly models per-request context in the MCP specification.

### Rejected Alternatives
- **Penpot-Specific Adapter**: Rejected as UCP enforces a universal, generic architecture.
- **`userToken` Hardcoding**: Rejected as it breaks the universal model.
- **Blind Forwarding**: Rejected due to the severe security risk of leaking internal UCP variables, static credentials, or unrelated metadata into the remote MCP server.

## Consequences
- Dynamic authentication mechanisms (like browser-plugin handshakes) are now natively supported.
- Connectors requiring request-scoped variables must specify an explicit JSON allowlist in their configuration.
- Backward compatibility is fully maintained; legacy execution paths and existing configurations are unaffected.
