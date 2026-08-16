# ADR-0059: Firecrawl MCP Integration via Universal Connector Platform

## Context
Phase 33 introduces web scraping and research extraction capabilities via Firecrawl. The architectural goal is to integrate Firecrawl without creating a bespoke orchestration layer, bespoke adapters, or bespoke clients, strictly adhering to the Universal Connector Platform (UCP) established in Phase 26/32.

Firecrawl exposes an official MCP server package (`firecrawl-mcp`). It is an agentic utility that provides tools like `search`, `scrape`, `crawl`, etc.

## Decision
1. **Native MCP Utility Connector:** Firecrawl will be integrated natively via the UCP using the existing `nexora.connector` and `nexora.mcp_server_config` abstractions.
2. **Not a Component Source:** Firecrawl does not satisfy the semantic `SEARCH/GET` contract for software components. Therefore, it will NOT be registered in the `source_registry`.
3. **Transport Choice:** We deliberately choose the LOCAL `stdio` transport (`npx -y firecrawl-mcp`) because it requires zero new architecture extensions and maximizes reuse of the generic `McpTransport` abstraction.
4. **Credential Ownership:** The `FIRECRAWL_API_KEY` will be managed securely by `nexora.mcp_credential` and injected into the subprocess environment by the `McpOnboardingService`.
5. **Failure Isolation:** Missing credentials, startup timeouts, and invocation failures will map cleanly to the canonical `ConnectorLifecycleState` (e.g., `FAILED`, `DEGRADED`) without requiring Firecrawl-specific exception handling in the core runtime.

## Security Boundary (Egress Policy)
The default Firecrawl Cloud deployment places web fetching outside Nexora's local network boundary, reducing local SSRF exposure. A self-hosted Firecrawl deployment changes that trust boundary and should eventually be governed by a generic Connector Egress Policy.

We do not implement a bespoke Firecrawl URL allowlist in Phase 33 to preserve the generic abstraction.

## Rejected Alternatives
- **Parallel Provider Architecture:** Rejected. Building a `FirecrawlProvider` or `FirecrawlAdapter` duplicates UCP responsibilities.
- **Hosted MCP (SSE):** Rejected for initial implementation to prioritize zero-architecture-change reuse of the `stdio` mechanism.
- **Source Registry Mapping:** Rejected. Forcing `search`/`scrape` into the `SEARCH`/`GET` component semantics violates the Source Framework's intent.
