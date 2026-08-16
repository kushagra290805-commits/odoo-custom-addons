# Phase 36 Pre-Implementation Unification Audit

**Date**: 2026-08-16
**Status**: Pre-Implementation

## 1. Current Architecture
Currently, the Nexora Studio ecosystem executes GenAI tools through a duplicate, parallel legacy MCP architecture (`services/runtime/mcp/`) that completely bypasses the newly established canonical Universal Connector Platform (UCP) located in `services/connector/`. The Generation Engine (`*Provider` models) fetches a legacy `McpRuntimeAdapter` and routes requests through `McpToolRouter` to `McpRuntimeManager` rather than dispatching through `ConnectorRuntime`.

## 2. Canonical Ownership Matrix
| Responsibility | Canonical Component | Path |
| :--- | :--- | :--- |
| **Registration** | `ConnectorRegistry` | `services/connector/registry/connector_registry.py` |
| **Runtime Orchestration** | `ConnectorRuntime` | `services/connector/runtime/connector_runtime.py` |
| **Tool Execution** | `ConnectorDispatcher` | `services/connector/runtime/dispatcher.py` |
| **Capabilities** | `ConnectorCapabilityIndex` | `services/connector/registry/capability_index.py` |
| **Health** | `ConnectorHealthMonitor` | `services/connector/runtime/health_monitor.py` |
| **Events** | `ConnectorEventBus` | `services/connector/events/bus.py` |

## 3. Legacy Ownership Matrix (To Be Retired)
| Legacy Responsibility | Duplicate Component | Path |
| :--- | :--- | :--- |
| **Registry** | `McpServerRegistry` | `services/runtime/mcp/mcp_server_registry.py` |
| **Runtime Orchestration** | `McpRuntimeManager` | `services/runtime/mcp/mcp_runtime_manager.py` |
| **Tool Execution** | `McpToolRouter` | `services/runtime/mcp/mcp_tool_router.py` |
| **Capabilities** | `McpCapabilityCatalog` | `services/runtime/mcp/mcp_capability_catalog.py` |
| **Platform Adapter** | `McpRuntimeAdapter` | `services/runtime/mcp/mcp_runtime_adapter.py` |

## 4. Production Consumers of Legacy MCP Runtime
The following components import and explicitly route through the legacy runtime:
- `models/github_provider.py` (`adapter = runtime.get_runtime('mcp_runtime')`)
- `models/context7_provider.py` (`adapter = runtime.get_runtime('mcp_runtime')`)
- `models/tavily_provider.py` (`adapter = runtime.get_runtime('mcp_runtime')`)
- `models/platform_service.py` (`_bootstrap_runtime()` instantiates `McpRuntimeAdapter`)

## 5. Migration Path
1. **Remove** `McpRuntimeAdapter` instantiation from `models/platform_service.py`.
2. **Refactor** `github_provider.py`, `context7_provider.py`, and `tavily_provider.py` to route execution requests directly to `ConnectorRuntime` via `ConnectorPlatformBootstrap.get_instance().connector_runtime.dispatch()`.
3. **Delete** all legacy classes inside `services/runtime/mcp/`.

## 6. Background-Thread Ownership
| Thread Name | Owner | Fate |
| :--- | :--- | :--- |
| `McpEventLoopThread` | `McpRuntimeAdapter` | **Delete** (Belongs to legacy adapter) |
| `_watch_loop` | `RegistryProvider` | **Delete** (Belongs to legacy registry) |
| `_health_monitor_loop` | `McpRuntimeManager` | **Delete** (Belongs to legacy manager) |
| `McpStartupReconciliationThread` | `ConnectorPlatformBootstrap` | **Keep** (Canonical UCP startup logic) |

## 7. Transport Ownership
**Current Legacy Transport:** `stdio_client.py` and `mcp_client.py` inside `services/runtime/mcp/`.
**Canonical Transport:** `McpTransport` inside `services/connector/connectors/mcp/transport.py`.
**Action:** Migrate execution to canonical transport; delete legacy transport.

## 8. Runtime Entry Points
- Legacy: `McpToolRouter.execute_capability(mcp_tool, request.payload)`
- Canonical: `ConnectorRuntime.dispatch(ConnectorExecutionRequest(...))`

## 9. Dependency Graph Risk Assessment
**Risk Level:** Low to Moderate. 
- The UCP is fully built and tested; the Generation Engine merely needs to point to the new interface.
- Removing `services/runtime/mcp/` is mechanically simple once the `*Provider` models are updated.
- Verification must ensure no capability resolution failures occur during real provider tool execution.

## 10. Files Safe to Delete After Migration
The entire `services/runtime/mcp/` directory, including:
- `mcp_runtime_adapter.py`
- `mcp_runtime_manager.py`
- `mcp_server_registry.py`
- `mcp_capability_catalog.py`
- `mcp_tool_router.py`
- `mcp_client.py`
- `stdio_client.py`
- `mcp_models.py`
- `security_context.py`
- `registry_provider.py`

## 11. Files That Must Remain
- `services/connector/*` (Entire Universal Connector Platform)
- All Generation Providers (`github_provider.py`, `context7_provider.py`, `tavily_provider.py`) (migrated)
- `services/connector/integration/bootstrap.py`
- `models/platform_service.py` (updated to remove legacy wiring)

## 12. Verification Plan
1. **Unit Tests:** Ensure all tests pass or are safely removed if they explicitly mocked the legacy MCP structure.
2. **Runtime Isolation:** Assert that `get_runtime('mcp_runtime')` throws or returns None.
3. **Execution Test:** Run canonical execution for all active connectors using real capabilities and trace logs to confirm execution via `ConnectorDispatcher`.
4. **Health Check:** Ensure no ghost threads remain active in the process namespace.

## 13. Explicit Proof That No New Parallel Architecture Is Required
The existing `ConnectorRuntime` already features an initialized `ConnectorDispatcher`, which fully implements tool routing, execution mapping, and lifecycle integration via `McpTransport`. The Generation Engine can construct a `ConnectorExecutionRequest` natively. There is ZERO need for any "UniversalMcpManager" or "ProviderConnectorRuntime". The canonical UCP architecture completely satisfies the execution routing requirement.
