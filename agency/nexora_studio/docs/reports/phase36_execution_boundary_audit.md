# Phase 36.1: Execution Boundary Audit

**Date**: 2026-08-16

## Objective
Trace the canonical execution entry point of the Universal Connector Platform (UCP) to determine the exact boundary for Generation Provider migration.

## Trace Path

1. **Entry Boundary:**
   `ConnectorRuntime.dispatch(request: ConnectorExecutionRequest) -> ConnectorExecutionResult`
   *(Location: `services/connector/runtime/connector_runtime.py:211`)*
   This is the top-level orchestrator. It performs health/recovery interception and routes to the dispatcher.

2. **Dispatcher:**
   `ConnectorDispatcher.dispatch(request) -> ConnectorExecutionResult`
   *(Location: `services/connector/runtime/dispatcher.py:59`)*
   Resolves the capability namespace to a specific `Connector` instance (using failover if necessary), fetches the configuration, and creates/initializes the SDK connector implementation.

3. **SDK Component Connector:**
   `ComponentConnector.execute(namespace, params, context)`
   *(Location: `services/connector/sdk/connector_components.py:65`)*
   Delegates to the specific provider (e.g., `McpProvider`).

4. **Protocol Provider:**
   `McpProvider.execute(namespace, params, context)`
   *(Location: `services/connector/connectors/mcp/provider.py:17`)*
   Translates UCP capability namespaces (e.g., `tools.call`, `resources.read`) into specific MCP transport methods.

5. **Transport:**
   `McpTransport.call_tool(name, arguments)`
   *(Location: `services/connector/connectors/mcp/transport.py`)*
   Serializes the request and passes it to the `ClientSession` (`stdio_client`).

## Verification
- **Is `ConnectorRuntime.dispatch()` genuinely the canonical API?**
  Yes. It is the only component in the UCP that handles telemetry, asynchronous transport failure interception, and canonical recovery logic. Providers *must* enter here, not at the `ConnectorDispatcher` or `McpTransport` levels.
- **Does it support capability routing?**
  Yes, the `ConnectorDispatcher` uses `ConnectorCapabilityIndex` internally.

## Conclusion
The authoritative, canonical provider-facing API is `ConnectorRuntime.dispatch()`. No parallel adapter is needed; Generation Providers will wrap their payloads in `ConnectorExecutionRequest` and submit them directly.
