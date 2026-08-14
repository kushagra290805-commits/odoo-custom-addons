# ADR 0053: Credential Persistence & Encryption Ownership

## Status
Accepted

## Context
During Phase 29.6 MCP validation, a security diagnostic revealed that GitHub Personal Access Tokens (PATs) were being stored in plaintext in the database (`nexora_mcp_credential.encrypted_value`). Furthermore, the global Windows Machine environment was incorrectly configured with `GITHUB_PERSONAL_ACCESS_TOKEN`, which allowed Docker containers to bypass the failing internal credential resolution via host environment inheritance.

To ensure secure execution of the ConnectorRuntime and MCP services, we must establish rigorous invariants for credential persistence, encryption, and runtime injection.

## Decisions

1. **Encrypted-At-Rest Invariant**: The database field `nexora_mcp_credential.encrypted_value` must NEVER contain plaintext.
2. **Canonical Encryption Service**: `OdooSecretsProvider` is the sole canonical owner of encryption and decryption logic. No second encryption system will be created. The Odoo model (`nexora.mcp_credential`) must intercept `create` and `write` operations to safely encrypt any plaintext input using `OdooSecretsProvider._encrypt()`.
3. **Runtime-Only Plaintext Resolution**: Credentials will only be decrypted in memory (via `OdooCredentialResolver`) during the `ConnectorRegistrationPipeline` and will be injected ephemerally into the `McpConfiguration.env`.
4. **No Host-Environment Bypass**: External/host environment variables (e.g., `GITHUB_PERSONAL_ACCESS_TOKEN` in the Windows registry) must not act as fallbacks for internal MCP credentials. This prevents bypassing the platform's security and telemetry pipelines.
5. **No Persistent Plaintext**: Passwords and keys must never appear in exceptions, test artifacts, logs, or UI elements. 

## Consequences
- The Odoo user interface for MCP credentials will remain write-only.
- If the master secret key (`NEXORA_CONNECTOR_SECRET_KEY`) is missing or rotated without re-encryption, the system will fail safely (raising `RuntimeError` during decryption) instead of falling back to plaintext usage or leaking the token.
