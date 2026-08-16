# Phase 36.6: Background Thread Audit

**Date**: 2026-08-16

## Objective
Audit all background threads associated with both the legacy MCP runtime and the canonical Universal Connector Platform to ensure safe deletion of the legacy components without breaking canonical execution.

## Thread Classifications

### 1. `McpEventLoopThread`
- **Creator/Owner:** `McpRuntimeAdapter` (`services/runtime/mcp/mcp_runtime_adapter.py`)
- **Purpose:** Hosts the dedicated `asyncio` event loop required for the legacy MCP runtime's background tasks and tool execution.
- **Lifecycle:** Started during Odoo boot when `McpRuntimeAdapter.startup()` was called by `platform_service.py`.
- **Shutdown Path:** `McpRuntimeAdapter.shutdown()` cancels tasks and stops the loop.
- **Classification:** **LEGACY** (Safe to delete).

### 2. `_health_monitor_loop`
- **Creator/Owner:** `McpRuntimeManager` (`services/runtime/mcp/mcp_runtime_manager.py`)
- **Purpose:** Periodically pings MCP clients in the legacy registry to update their health status.
- **Lifecycle:** Scheduled as an asyncio task on the `McpEventLoopThread` during initialization.
- **Shutdown Path:** Cancelled when `McpRuntimeManager.shutdown()` is called.
- **Classification:** **LEGACY** (Safe to delete).

### 3. `_watch_loop`
- **Creator/Owner:** `JsonRegistryProvider` (`services/runtime/mcp/registry_provider.py`)
- **Purpose:** Polls the `mcp_registry.json` file for changes and reloads the legacy registry.
- **Lifecycle:** Started as a daemon thread in `__init__`.
- **Shutdown Path:** Terminated when the python process exits (daemon thread).
- **Classification:** **LEGACY** (Safe to delete).

### 4. `McpStartupReconciliationThread`
- **Creator/Owner:** `ConnectorPlatformBootstrap` (`services/connector/integration/bootstrap.py`)
- **Purpose:** Discovers, validates, and initializes configured connectors dynamically in the background after Odoo boots to prevent blocking the WSGI worker.
- **Lifecycle:** Started once when `bootstrap.connector_runtime` reaches `READY` state. Exits automatically when reconciliation is complete.
- **Shutdown Path:** Runs to completion and terminates gracefully.
- **Classification:** **CANONICAL** (Must NOT be deleted).
  *Note: The thread name is a slight misnomer ("Mcp") but belongs entirely to the canonical UCP `ConnectorPlatformBootstrap` service.*

## Conclusion
The threads belonging to `McpEventLoopThread`, `_health_monitor_loop`, and `_watch_loop` are 100% owned by the `services/runtime/mcp/` architecture. By removing the instantiation of `McpRuntimeAdapter` from `platform_service.py` (completed in Phase 36.5), we guarantee these threads are no longer started in production.

They are completely safe for deletion. The canonical UCP relies exclusively on its own reconciliation thread and the single-flight recovery timers (`threading.Timer`), which remain untouched.
