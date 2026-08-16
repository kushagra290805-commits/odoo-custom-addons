# Phase 36.5: Legacy Reachability Audit

**Date**: 2026-08-16

## Objective
Search the repository for all references to the legacy `services/runtime/mcp/` architecture and classify them to prove that no production execution paths remain dependent on it.

## Audit Results

### 1. `McpRuntimeAdapter` / `mcp_runtime`
- `models/github_provider.py`: **[CLEARED]** Migrated to UCP.
- `models/context7_provider.py`: **[CLEARED]** Migrated to UCP.
- `models/tavily_provider.py`: **[CLEARED]** Migrated to UCP.
- `models/platform_service.py`: **[CLEARED]** Bootstrapping and registration removed.
- `verify_mcp_runtime.py`: **[HISTORICAL/TEST]** Script for adversarial certification. Dead.
- `verification/provider_conformance_suite.py`: **[TEST]** Used legacy check `mcp_runtime.health_status()`. Dead/must be updated to UCP.
- `verification/debug_mcp.py`: **[TEST]** Direct catalog access. Dead.
- `verification/archive/*`: **[HISTORICAL]** Old Phase 23 audit traces.

### 2. `McpToolRouter` / `execute_capability`
- `verify_phase21c.py` / `verify_phase21d.py`: **[HISTORICAL]** Validation scripts for Phase 21. Dead.
- `validate_github_mcp.py`: **[TEST]** Validation script. Dead.

### 3. `McpRuntimeManager` / `McpServerRegistry` / `McpCapabilityCatalog`
- `validate_github_mcp.py`: **[TEST]** Manual instantiation for tests. Dead.
- `verification/archive/*`: **[HISTORICAL]** Phase 23 prints. Dead.

### 4. `McpClient` / `ClientSession` / `stdio_client`
- `tests/test_runtime_health.py`: **[TEST]** Unit test targeting legacy health loops. Dead.
- `tests/test_platform_runtime_mcp_bootstrap.py`: **[TEST]** Unit test targeting legacy boot. Dead.
- `tests/test_mcp_sse_generic_transport.py`: **[TEST]** Mentions `ClientSession` mock. (Only relevant for testing the legacy).
- `tests/test_credential_injection.py`: **[TEST]** Mentions `stdio_client` mock.

## Conclusion

**Production Dependency State: ZERO**
There are **no remaining production code consumers** of the legacy MCP runtime (`services/runtime/mcp/`). All production integration points (`platform_service.py` and all three generation providers) have been successfully decoupled and migrated to the canonical `ConnectorRuntime`.

All remaining references are isolated strictly within:
1. Historical adversarial verification scripts (`verify_*.py`).
2. Unit tests explicitly designed to test the legacy runtime behavior (`test_runtime_health.py`, `test_platform_runtime_mcp_bootstrap.py`).

The legacy architecture is fully decoupled and ready for background thread audit followed by final deletion.
