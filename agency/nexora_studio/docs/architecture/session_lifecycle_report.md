# MCP Session Lifecycle Report

## Overview
This report validates the session instantiation, persistence, multiplexing, and clean teardown of MCP connections within the Universal Connector Platform.

## Session Lifecycle Dynamics
- **Instantiation:** The `ConnectorDispatcher` lazily instantiates the MCP Transport (and its backing subprocess) on the first `dispatch()` call to a registered connector. The SDK instance is cached in `_active_connectors`.
- **Multiplexing:** Subsequent requests route through the persistent cached `McpConnector` instance, which multiplexes JSON-RPC messages asynchronously over the dedicated `anyio` stdio streams.
- **Eviction / Reconnection:** If a connector faults (e.g. timeout, malformed json, crash), the dispatcher catches the exception, forcibly pops the connector from `_active_connectors`, and attempts a graceful `shutdown()`. The next request structurally forces a fresh cold-start instantiation, proving self-healing behavior without leaking zombie processes.
- **Teardown (Shutdown):** When `runtime.shutdown()` or `runtime.deregister_connector()` is invoked, all cached connectors are iterated and shut down. The `McpTransport._thread` is joined and the underlying loop is closed.

## Isolation Evidence
Validation demonstrated that multiple MCP connectors (e.g., `session.a` and `session.b`) map to distinct `ConnectorRuntimeContext` IDs and operate completely independent subprocesses concurrently. State is perfectly siloed by `connector_id` within the `ConnectorDispatcher` cache.

## Certification Status
**GO.** The Universal Connector Platform reliably manages persistent long-lived subprocesses, isolates state across different connectors, and strictly garbage-collects resources on failure or shutdown.
