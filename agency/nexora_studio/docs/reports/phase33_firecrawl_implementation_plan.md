# Phase 33: Firecrawl MCP Integration Implementation Plan

## 1. Goal
Integrate Firecrawl as a native MCP connector using the existing Universal Connector Platform (UCP). Do so entirely through database configuration, avoiding hardcoded provider abstractions. Delete any dead/legacy Firecrawl wrappers.

## 2. Prerequisites (from Architecture Audit)
- The canonical Phase 32 `McpTransport` natively supports the `stdio` transport required by `@mendable/firecrawl-mcp`.
- The canonical `McpOnboardingService` supports credential injection into `stdio` environment variables (`FIRECRAWL_API_KEY`).
- Firecrawl is an Agentic Utility, not a Component Source, and will not be added to the `source_registry`.

## 3. Implementation Steps

### Step 1: Purge Legacy Code
Delete the existing bespoke Firecrawl execution wrapper, as UCP handles tool routing transparently now.
- **[DELETE]** `models/firecrawl_provider.py`
- **[MODIFY]** `models/__init__.py` (remove `from . import firecrawl_provider`)
- **[DELETE]** `verification/archive/verify_phase23_6_firecrawl.py` (obsolete scratch script)

### Step 2: Database Configuration (XML)
Inject the Firecrawl configuration into the database using Odoo XML data files. This connects the existing `firecrawl_mcp` registry entry to the UCP runtime.
- **[MODIFY]** `data/connector_registry_data.xml`
  - Add `<record id="connector_firecrawl_mcp" model="nexora.connector">`
  - Link it to a `utility` connector type.
  - Add `<record id="mcp_config_firecrawl" model="nexora.mcp_server_config">`
    - `transport_type = 'stdio'`
    - `command = 'npx.cmd'` (or 'npx' for linux)
    - `args_json = '["-y", "firecrawl-mcp"]'`
    - `env_vars_json = '{"FIRECRAWL_API_KEY": "__INJECT_VIA_NEXORA_MCP_CREDENTIAL__"}'`
    - `startup_policy = 'lazy'`

### Step 3: Implement Deterministic CI Tests
Write a fast, mocked unit test to prove the UCP can resolve and bootstrap the Firecrawl connector correctly without needing network access.
- **[NEW]** `tests/test_firecrawl_connector.py`
  - Mock `McpTransport._start_stdio_process`
  - Assert that `FIRECRAWL_API_KEY` is correctly extracted from the `nexora.mcp_credential` table and injected into the subprocess `env`.
  - Assert that missing credentials raise the appropriate canonical validation error.
  - Run a mock `tools/call` for `search` to prove end-to-end execution path.

### Step 4: Implement Live Integration Test (Optional / Scratch)
Write a standalone verification script (similar to Phase 32) that uses real credentials to prove the integration works against the actual NPM package.
- **[NEW]** `scripts/verify_firecrawl_integration.py`
  - Reads `FIRECRAWL_API_KEY` from `os.environ`.
  - Injects the credential into Odoo DB.
  - Starts the ConnectorRuntime.
  - Calls the `search` tool with a benign query.

### Step 5: Odoo Verification
- Run `odoo-bin -u nexora_studio --stop-after-init` to ensure the XML loads perfectly without CDATA/formatting errors.
- Run `python run_ci.py` to ensure all tests pass and there are no sibling regressions.

## 4. Rollback Plan
If integration fails or causes regression:
1. Revert `data/connector_registry_data.xml`.
2. Delete the new test files.
3. The legacy `models/firecrawl_provider.py` can remain deleted since it has no production caller in the current UCP architecture.

## 5. Egress Security Note
As identified in the audit, URL Egress Policy is out of scope for Phase 33 because it requires a platform-wide ADR for the Connector Framework. The immediate integration is secured from internal SSRF by the Firecrawl Cloud API architecture.
