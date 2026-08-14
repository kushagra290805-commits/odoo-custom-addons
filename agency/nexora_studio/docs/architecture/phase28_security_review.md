# Phase 28 — Security Review

## Threat Model & Protections

### 1. Secret Leakage
**Threat**: Operator credentials returned via API or logged.
**Mitigation**: 
- `encrypted_value` is `groups='nexora_studio.group_nexora_super_admin'`.
- Decrypted credential values are never exposed through ORM responses, HTTP responses, logs, exceptions, telemetry, or persisted plaintext fields.
- `ConnectionTester` strictly strips secrets from all logs and output.

### 2. Unauthorized Connector Management
**Threat**: Non-admins tampering with MCP processes.
**Mitigation**: 
- `_require_admin()` injected into all state mutation HTTP endpoints.
- `ir.model.access.csv` enforces strict CRUD boundaries.

### 3. Encryption Key Tampering
**Threat**: The encryption key is stolen from the DB.
**Mitigation**: The `NEXORA_CONNECTOR_SECRET_KEY` is loaded strictly from environment variables and is never persisted.
