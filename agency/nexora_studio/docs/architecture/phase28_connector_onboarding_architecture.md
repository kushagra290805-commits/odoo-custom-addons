# Phase 28 — Connector Onboarding Architecture

## Overview
Phase 28 establishes the **MCP Connector Onboarding Platform**, transforming the raw MCP Connector into an operator-facing system.

## Architectural Boundaries (ADR-0051)
- **Odoo ORM (Management)**: `nexora.mcp_server_config`, `nexora.mcp_credential`, `nexora.mcp_discovered_tool`.
- **Domain Aggregates (Translation)**: `McpOnboardingService` reads the Odoo models and constructs the `Connector` aggregate, wrapping `McpConnector` and `McpConfiguration`.
- **Runtime (Execution)**: The `ConnectorRuntime` is strictly decoupled from Odoo. It receives domain aggregates from the `ConnectorRegistrationPipeline`.
- **Synchronization**: `ConnectorRuntimeSynchronizer` listens to ORM state/credential changes and triggers runtime evictions/registrations.

## User Interface
- **Form Views**: Configured directly in `nexora.connector` via an MCP Server notebook tab.
- **Connection Tester**: Ephemeral runtime wizard that executes capability discovery before saving.

## Security
- Hardened HTTP endpoints via `_require_admin` and `_require_super_admin`.
- Credential storage uses Fernet encryption, inaccessible to non-super-admins.
