# Phase 33: Firecrawl MCP Integration Architecture Audit

## 1. Executive Summary
This audit validates the architectural readiness for integrating the Firecrawl MCP server (`@mendable/firecrawl-mcp`). The audit confirms that the Universal Connector Platform (UCP) established in Phase 32 contains all necessary generic abstractions (Transport, Authentication, Configuration) to support Firecrawl natively. **No parallel orchestration, custom adapters, or specific Firecrawl providers are required.**

A critical finding of this audit is that Firecrawl is an **Agentic Research/Utility Tool**, not a Component Source (like GitHub or Shadcn). Consequently, it will bypass the Source Framework/`source_registry` entirely. 

**Recommendation:** GO for implementation, adhering strictly to the generic UCP pattern.

## 2. Existing Architecture Ownership
The canonical Phase 32 UCP architecture completely governs MCP integrations:
- **`nexora.connector`**: Root entity representing the Firecrawl package.
- **`nexora.mcp_server_config`**: Transport (`stdio`), Command (`npx.cmd`), and Args.
- **`nexora.mcp_credential`**: Resolves `FIRECRAWL_API_KEY` securely.
- **`McpTransport`**: Handles `stdio` process lifecycle and JSON-RPC communication.
- **`ConnectorRuntime`**: Mounts the MCP tools into the Agent's context.

*Finding: Legacy references to `models/firecrawl_provider.py` exist but act merely as an Odoo execution wrapper. The integration should purely be an MCP connector.*

## 3. Firecrawl Current MCP Contract
- **Source**: `https://github.com/mendableai/firecrawl-mcp` (NPM package `firecrawl-mcp`)
- **Transport**: `stdio` (launched via `npx`).
- **Authentication**: Environment variable `FIRECRAWL_API_KEY`. (Optionally `FIRECRAWL_URL`).
- **Tools**: `scrape`, `crawl`, `search`, `map`, `extract`.
- **Read-Only Test Tool**: `search` is ideal for harmless integration testing.

## 4. Transport & Authentication Compatibility Analysis
**Transport Compatibility**: `PASS`
- Firecrawl uses `stdio`. The Phase 32 generic `McpTransport` natively supports `stdio` subprocess management. No generic transport extension is required.

**Authentication Compatibility**: `PASS`
- Authentication is handled via injected environment variables. `nexora_mcp_server_config` fully supports mapping `nexora.mcp_credential` keys (e.g., `FIRECRAWL_API_KEY`) into the `stdio` subprocess `env`. No HTTP header abstractions are needed for this specific `stdio` implementation.

## 5. Database Configuration Design
Firecrawl will be configured entirely via the database, avoiding hardcoded secrets or arbitrary Python constants:
- **Connector (`nexora.connector`)**: `connector_id = 'firecrawl_mcp'`
- **Config (`nexora.mcp_server_config`)**:
  - `transport_type = 'stdio'`
  - `command = 'npx.cmd'` (on Windows) or `npx`
  - `args_json = '["-y", "firecrawl-mcp"]'`
  - `env_vars_json = '{"FIRECRAWL_API_KEY": "__INJECT_VIA_NEXORA_MCP_CREDENTIAL__"}'`
- **Credential (`nexora.mcp_credential`)**: Holds the actual Firecrawl API key.

## 6. Source Framework Decision
**Decision: DO NOT REGISTER AS A COMPONENT SOURCE.**
Firecrawl does not satisfy the semantic `SEARCH/GET` contract for code components. It is an arbitrary web extraction utility. Registering it in `source_registry.xml` would conceptually pollute the architecture. It will be mounted directly by the `ConnectorRuntime` as raw MCP tools for the agent to use when web research/scraping is needed.

## 7. Security/SSRF Analysis (CRITICAL)
**Finding:** Firecrawl takes arbitrary URLs and fetches them.
- **SSRF Risk (Internal):** Mitigated. Because the official `firecrawl-mcp` routes requests to the Firecrawl Cloud API (`api.firecrawl.dev`), the HTTP request originates from MendableAI's infrastructure, not the local Odoo container. It cannot be used to scrape `localhost:8069` or internal AWS metadata (`169.254.169.254`) unless the user explicitly hosts a local open-source Firecrawl instance and modifies `FIRECRAWL_URL`.
- **Egress URL Policy:** Nexora currently lacks a generic Egress URL Allowlist for MCP tools. Since Firecrawl can scrape *any* public URL, the LLM agent could theoretically be coerced into scraping malicious external sites.
- **Architectural Action:** No Firecrawl-specific hack should be added. URL egress policy is a platform-level concern that should be addressed in a future ADR (e.g., `ConnectorEgressPolicy`), but it is not a blocker for Firecrawl Cloud integration since internal SSRF is structurally prevented by the cloud architecture.

## 8. Reuse Matrix

| Existing Component | Reuse? | Required Change | Reason |
|---------------------|--------|-----------------|--------|
| `McpTransport (stdio)` | YES | None | Generic subprocess RPC works as-is. |
| `McpOnboardingService` | YES | None | Can dynamically provision Firecrawl config. |
| `McpCredential` | YES | None | Environment variable injection is already generic. |
| `ConnectorRuntime` | YES | None | Discovers and exposes MCP tools generically. |
| `Source Framework` | NO | None | Firecrawl is not a component source. |

## 9. Modified/Untouched Files
**Files to Modify:**
- `data/connector_registry_data.xml` (To bootstrap Firecrawl config into the DB).

**Files NOT to Modify:**
- `mcp_registry.json` (Firecrawl is already there, but we rely on DB configuration).
- `services/source_framework/adapters/*` (Not a source adapter).
- `services/connector/sdk/mcp_transport.py` (No transport extension needed).

## 10. Test Strategy
1. **CI Tests (Deterministic)**: Mock `McpTransport` to simulate `firecrawl-mcp` `stdio` responses for `tools/list` and a dummy `search` operation. Verify config resolution.
2. **Failure Tests**: Verify missing `FIRECRAWL_API_KEY` credential fails cleanly.
3. **Integration Test (Optional)**: A standalone script (`verify_firecrawl_integration.py`) that uses real credentials (via `os.environ`) to perform a live `search` via Odoo shell.

## 11. Proposed ADR Summary
**Title:** ADR-0059 - Integration of Firecrawl as Native MCP Utility Connector
**Context:** Phase 33 introduces web scraping/research capabilities.
**Decision:** We integrate `@mendable/firecrawl-mcp` over `stdio` using generic Phase 32 UCP abstractions. Firecrawl is strictly registered as a `utility` connector, bypassing the Source Framework (which is exclusively for semantic component extraction). Egress URL security relies on Firecrawl Cloud isolation; a generic Egress Allowlist is deferred to a future platform ADR.

## 12. Explicit GO / NO-GO Recommendation
**GO.** 
The architecture is 100% ready. Firecrawl can be integrated entirely via generic data configuration (`nexora.connector`, `nexora.mcp_server_config`) without writing any Firecrawl-specific orchestration classes.
