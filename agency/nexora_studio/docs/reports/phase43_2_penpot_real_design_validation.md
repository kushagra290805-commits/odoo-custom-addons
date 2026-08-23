# Phase 43.2: Penpot Real Design Session Validation

**Status:** Completed
**Date:** 2026-08-19

## Objective
Validate whether the generic UCP architecture can successfully execute a project-bound/read-only Penpot capability (`export_shape`) when a real Penpot plugin session is required, identifying how authentication and session context (`userToken`) propagate to the remote MCP server.

## Architecture Inspected
- **`UniversalCapabilityRouter` / `ConnectorExecutionTarget`**: Accepts `context` (which includes `configuration_snapshot` containing dynamic session context).
- **`McpProvider`**: Receives `context` in its `execute` method but strictly drops it when delegating to `_tools_call(parameters)`.
- **`McpTransport`**: Initializes connection headers exactly once at startup utilizing static credentials from `nexora.mcp_server_config` and `nexora.mcp_credential`. It provides no interface for per-request header injection or dynamic context propagation during `call_tool`.

## Penpot Session Model
The Penpot MCP server running in multi-user mode requires a `userToken` to associate the MCP execution with an active browser/plugin session. This token is expected to be present in the session context (likely via headers or a dedicated MCP extension protocol) for any tool interacting directly with a user's canvas. 

## Test Configuration
- **Canonical Entry Point:** `ConnectorExecutionTarget.execute(...)` bridging `ConnectorRuntime`.
- **Selected Capability:** `penpot_mcp.export_shape` (A read operation targeting the active page).
- **Payload:**
  ```json
  {
    "namespace": "penpot_mcp.export_shape",
    "inputs": {"shapeId": "page"},
    "context": {},
    "correlation_id": "phase43_2_validation"
  }
  ```

## Execution Result
- **Latency:** ~6.09s
- **Success Flag:** `True` (Note: The Penpot MCP server returned `isError: False` despite the execution failing).
- **Data Returned:**
  ```json
  {
    "content": [
      {
        "type": "text",
        "text": "Tool execution failed: Error: No userToken found in session context. Multi-user mode requires authentication."
      }
    ]
  }
  ```

## Session Context Propagation Result
The capability reached the Penpot MCP server cleanly, but the tool failed to execute due to the missing `userToken`. 

**Architectural Gap Identified:** The current Universal Capability Platform (UCP) `McpTransport` entirely drops dynamic request context. There is no mechanism to pass a `userToken` (or any dynamic session state) from the UCEL payload down into the MCP transport layer (e.g., as dynamic HTTP headers or MCP session metadata). 

## Proposed Smallest Reusable Mechanism
To fix this generic gap for all MCPs requiring dynamic session binding:
1. **Extend `McpProvider`:** Update `_tools_call(self, parameters, context)` to pass the context down.
2. **Extend `McpTransport`:** Add support for injecting dynamic context variables as HTTP Headers or MCP Metadata on a per-request basis (if supported by the MCP SDK) or by negotiating session contexts prior to tool execution. 

*(Note: As per the strict architectural safety rules, no Penpot-specific hack was implemented, and execution is halted pending approval of the generic context propagation fix).*

## Final Verdict
`FAIL — GENERIC_UCP_SESSION_PROPAGATION_DEFECT`
