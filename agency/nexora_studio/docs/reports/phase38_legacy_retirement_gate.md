# Phase 38 — Legacy MCP Retirement Gate

**Date:** 2026-08-17
**Objective:** Establish exact production reachability of the legacy MCP runtime (`services/runtime/mcp/`) to determine if it is safe to delete.

## 1. Exact Legacy Files
The complete legacy runtime consists of 12 files inside `services/runtime/mcp/`:
- `__init__.py`
- `mcp_capability_catalog.py`
- `mcp_client.py`
- `mcp_models.py`
- `mcp_runtime_adapter.py`
- `mcp_runtime_manager.py`
- `mcp_server_registry.py`
- `mcp_tool_router.py`
- `mcp_tool_router_old.py`
- `registry_provider.py`
- `security_context.py`
- `transports.py`

## 2. Exact Production Callers
A complete repository scan of all legacy symbols revealed exactly **one** active production caller importing from the legacy directory:

- `services/capabilities/bootstrap.py` (Line 6)
  `python
  from ..runtime.mcp.registry_provider import JsonRegistryProvider
  `

## 3. Exact Call Chains
Tracing `services/capabilities/bootstrap.py` reveals the following executable chain during Odoo module initialization:

1. `__init__.py` -> `post_init_provider_platform(env)` (Line 24)
2. Calls `env['nexora.registry_bootstrap_service'].execute_bootstrap()`
3. Instantiates `provider = JsonRegistryProvider(registry_path)` inside `bootstrap.py` (Line 45)
4. Reaches into `services/runtime/mcp/registry_provider.py` (Line 27)

## 4. Exact Executable Legacy Paths
The only executable path from production into the legacy folder is:
**`services/runtime/mcp/registry_provider.py` (`JsonRegistryProvider`)**

*Note: `JsonRegistryProvider` does not import any other legacy components. The dependency stops at this single file.*

## 5. Dead / Unreachable Legacy Paths
The remaining 11 legacy files are completely isolated and have 0 active imports or invocations from production paths. They are fully dead:
- `mcp_runtime_adapter.py`
- `mcp_runtime_manager.py`
- `mcp_server_registry.py`
- `mcp_capability_catalog.py`
- `mcp_tool_router.py`
- `mcp_tool_router_old.py`
- `mcp_client.py`
- `mcp_models.py`
- `security_context.py`
- `transports.py`
- `__init__.py`

*Note: References to `mcp_runtime` found in `models/builder_session.py`, `models/builder_session_mcp.py`, and `services/source_framework/transport/mcp_transport.py` are local variables or recordset names representing `nexora.runtime` records, not module dependencies on the legacy architecture.*

## 6. Test-Only References
The following files contain legacy imports but are non-production test/verification artifacts:
- `tests/test_runtime_health.py`
- `tests/test_platform_runtime_mcp_bootstrap.py`
- `discover_context7.py`
- `verification/provider_conformance_suite.py`
- `verification/archive/verify_phase23_*.py`

## 7. Canonical MCP References That Must NOT Be Deleted
The following canonical file contains strings matching the audit criteria (`ClientSession`, `stdio_client`) but is part of the new UCP architecture and must remain untouched:
- `services/connector/connectors/mcp/transport.py`

## 8. Exact Deletion Candidates
The 11 dead files listed in Section 5 are safe for immediate deletion.
However, `services/runtime/mcp/registry_provider.py` CANNOT be deleted yet.

## 9. Exact Files Requiring Migration Before Deletion
- **`services/capabilities/bootstrap.py`**: Must be refactored to remove the dependency on `JsonRegistryProvider` before `services/runtime/mcp` can be safely destroyed. (It should likely use standard JSON parsing or the canonical `ConnectorPlatformBootstrap` capabilities index).

## 10. Verdict
**NO-GO** — legacy production dependency still requires migration.
