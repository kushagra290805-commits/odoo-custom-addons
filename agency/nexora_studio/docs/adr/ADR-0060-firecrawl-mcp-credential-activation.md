# ADR-0060: Firecrawl MCP Credential Activation

## Status
Proposed

## Context
In Phase 34, we stabilized the Connector Registry Health subsystem, resolving race conditions and false-positive degradation states. The canonical `firecrawl_mcp` connector has been integrated using the Universal Connector Platform (UCP) through the `stdio` MCP transport mechanism, running `npx -y firecrawl-mcp`. It currently registers as HEALTHY.

However, the Firecrawl MCP server requires authentication (via the `FIRECRAWL_API_KEY` environment variable) to perform actual operations against the Firecrawl API. 

The goal of Phase 35 is to activate a real Firecrawl API key and prove an end-to-end authenticated operation without compromising the UCP architecture, avoiding bespoke credential storage, bespoke connector types, or bespoke Python providers.

## Decision
We will adhere strictly to the existing canonical UCP credential architecture to supply the Firecrawl API key:

1. **Storage Mechanism:** We will utilize `nexora.mcp_credential` to store the secret. The key will be `FIRECRAWL_API_KEY`.
2. **Encryption:** The secret will be encrypted using `OdooSecretsProvider`, utilizing Fernet symmetric encryption with the master key provided by the environment.
3. **Resolution:** During runtime execution, the `ConnectorCredentialResolver` will resolve and decrypt the credential, passing it securely in memory.
4. **Transport Consumption:** The UCP `McpTransport` (stdio) will inject the resolved secret into the environment variables of the `npx -y firecrawl-mcp` child process.
5. **No Architectural Bypass:** No custom Python code, alternative API key models, or manual overrides will be created to bypass this flow.

## Consequences
- **Positive:** We prove that the UCP architecture natively supports secure, dynamic secret injection for arbitrary MCP servers without requiring bespoke integration code.
- **Positive:** We maintain a single source of truth for credentials (`nexora.mcp_credential`) and connector definitions.
- **Negative:** None, as this uses the designed architecture precisely as intended.

## Architecture & Ownership Audit
- **Canonical Connector Record:** `nexora.connector` (connector_id: `firecrawl_mcp`).
- **Configuration Record:** `nexora.mcp_server_config` (command: `npx`, args: `["-y", "firecrawl-mcp"]`).
- **Credential Ownership:** `nexora.mcp_credential` mapped to the canonical connector. (Currently has two keys: `FIRECRAWL_API_KEY` and the legacy typo `FIRECRAWL__API_KEY` which will be cleaned up).
- **Resolver Path:** `OdooSecretsProvider` -> `ConnectorCredentialResolver` -> `McpConfiguration` env injection.
