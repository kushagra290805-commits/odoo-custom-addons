# Phase 38C — Final Legacy MCP Retirement Gate

**Date:** 2026-08-17
**Objective:** Final read-only audit to prove ZERO production reachability for the legacy services/runtime/mcp/ architecture.

## 1. Legacy Directory Inventory
The following files remain in services/runtime/mcp/:
- __init__.py (Production callers: 0, Legacy callers: 0)
- mcp_capability_catalog.py (Production callers: 0, Legacy callers: 1)
- mcp_client.py (Production callers: 0, Legacy callers: 4)
- mcp_models.py (Production callers: 0, Legacy callers: 4)
- mcp_runtime_adapter.py (Production callers: 0, Legacy callers: 0)
- mcp_runtime_manager.py (Production callers: 0, Legacy callers: 1)
- mcp_server_registry.py (Production callers: 0, Legacy callers: 2)
- mcp_tool_router.py (Production callers: 0, Legacy callers: 1)
- mcp_tool_router_old.py (Production callers: 0, Legacy callers: 0)
- security_context.py (Production callers: 0, Legacy callers: 1)
- 	ransports.py (Production callers: 0, Legacy callers: 1)

**Deletion Eligibility:** ALL files are 100% eligible for deletion.

## 2. Production References & Call Graph
An exhaustive, repository-wide search was conducted for 24 distinct legacy symbols (classes, files, namespaces, dynamic imports).
- 421 occurrences were found in total.
- **ZERO active production dependencies exist.**
- The only matches for strings like get_runtime( map identically to canonical PlatformRuntime.get_runtime(runtime_id) usage within services/generation/platform/platform_runtime.py, which is 100% disconnected from the legacy MCP path.
- The only match for mcp_runtime outside of tests maps to the 
exora.builder_session.mcp_runtime_health database field definition in an XML view.

## 3. Dynamic Import Analysis
Searches for importlib, import_module, and __import__ yielded no dynamic loading of any legacy mcp_runtime or services.runtime.mcp namespaces. They are exclusively used by the services/source_framework/plugins/manager.py and standard Odoo dynamic module patterns.

## 4. Background-Thread Ownership
- McpEventLoopThread, _watch_loop, and _health_monitor_loop exist **only** inside the dead legacy files and test reports. They are never instantiated in production.
- McpStartupReconciliationThread is securely owned by the canonical UCP services/connector/integration/bootstrap.py.
- No raw 	hreading.Thread or daemon=True calls exist in production outside of the canonical ootstrap.py and tests.

## 5. Canonical UCP Protection Verification
services/connector/ and all canonical entities (e.g., ConnectorRuntime, ConnectorDispatcher, ConnectorRegistry) remain fully isolated from the legacy directory. McpTransport and stdio_client implementations reside correctly inside the canonical services/connector/connectors/mcp/transport.py and were excluded from deletion targeting.

## 6. Database Reference Analysis
A deep runtime execution against 
exora.runtime, 
exora.capability_registry, and 
exora.connector confirmed that **zero records** contain metadata or implementation paths mapping to services.runtime.mcp or McpRuntimeAdapter.

## 7. Startup/Import Verification
An isolated odoo-bin shell test successfully imported ConnectorPlatformBootstrap, ConnectorRuntime, ConnectorRegistry, and ConnectorCapabilityIndex without raising any module not found errors for legacy files, proving services/runtime/mcp/ is disconnected from Odoo boot.

## 8. Git State
Git confirms no production changes have occurred beyond the successful isolation and removal of egistry_provider.py (completed in Phase 38B).

---
**Verdict:** PHASE 38C — GO FOR RETIREMENT
