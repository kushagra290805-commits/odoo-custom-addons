# ADR-0054: Persistent Encryption Key Management for Credentials

**Status:** Accepted
**Date:** 2026-08-10

## Context

In Phase 28 (ADR-0051), we introduced `OdooSecretsProvider` to encrypt MCP connector credentials using Fernet encryption. The master encryption key was specified to be loaded strictly from the `NEXORA_CONNECTOR_SECRET_KEY` environment variable.

During Phase 29.6 provider testing, we discovered that relying solely on environment variables introduced fragility in standard Odoo development environments (where the server is often started via generic wrappers, IDE tasks, or background services without custom environment variables). When the key was missing, Odoo failed safely (raising `ConfigurationException`) but prevented credential storage entirely. A temporary workaround involving raw SQL bypass resulted in a plaintext credential being stored, violating our security constraints.

We needed a persistent, restart-safe mechanism to supply the master encryption key to the Odoo process without compromising our security guarantees.

## Decision

1. **Key Source:** We will source the master encryption key primarily from Odoo's native configuration system (`odoo.tools.config`), falling back to the `NEXORA_CONNECTOR_SECRET_KEY` environment variable.
2. **Development Configuration Strategy:** The master key will be stored under the `nexora_connector_secret_key` key in the project's native `dev.conf` (or corresponding deployment `.conf` file). This mirrors how Odoo natively handles highly sensitive deployment secrets like `db_password` and `admin_passwd`.
3. **Encryption Ownership:** The `OdooSecretsProvider` remains the sole owner of encryption/decryption operations. The key must never be cached at the module level.
4. **Prohibition on Plaintext Persistence:** To prevent any future bypassing, the system strictly enforces that no plaintext credential may be saved as a fallback. If the encryption key is missing, the system must crash gracefully rather than allowing plaintext storage.
5. **Key Rotation Implications:** If the key in the configuration file is rotated, all existing credentials must be re-encrypted. If the key is lost, existing credentials become unrecoverable and must be re-entered by the user.

## Consequences

- **Positive:** Odoo server restarts seamlessly pick up the encryption key, resolving the `ConfigurationException` crashes during credential lifecycle operations.
- **Positive:** We leverage Odoo's existing configuration infrastructure rather than forcing a secondary `.env` file management layer.
- **Negative:** Infrastructure teams must ensure that Odoo configuration files (`*.conf`) are secured with restrictive file permissions (e.g., `chmod 600`), as they now contain the encryption master key in addition to database passwords.
