# ADR-0084: Client Odoo Database Lifecycle

Date: 2026-09-07
Phase: 47.33
Status: Accepted

## Context

Phase 47.30 proved the platform is agency-DB-only (`dbfilter=^nexora_studio$`). The existing `client_provisioning_api.py` provides real `create_database`/`delete_database` primitives (`odoo.service.db.exp_create_database`, `exp_drop`) but no lifecycle owner, no state model, no credential storage, and no idempotency. Phase 47.32 established `RequirementModel.backend_required` but provisioning was deferred.

The target chain:
```
backend_required
    ↓
Client Environment
    ↓
isolated Client Odoo DB
    ↓
ready/failed/deleted
```

## Decision

1. **Canonical lifecycle owner**: `nexora.client_environment_service` (new AbstractModel), with `nexora.client_environment` (new Model) as the stateful persistent owner.
2. **Agency DB vs Client DB separation**: the agency DB (`nexora_studio`) remains the control-plane; client DBs are isolated by name (`nexora_<sanitized>`), never the agency DB.
3. **Database naming**: deterministic sanitization (`_sanitize_db_name`): replace invalid chars with `_`, deduplicate underscores, truncate to 20 chars, prefix `nexora_`.
4. **Lifecycle states**: `draft` → `provisioning` → `ready` / `failed`; deletion: `deleting` → `deleted` / `failed`.
5. **Idempotency**: `create_environment` checks `db_name` existence before creation; `action_provision` only runs from `draft`/`failed`; `action_delete` checks state.
6. **Credential storage**: admin password encrypted via existing `OdooSecretsProvider` (Fernet) and stored in `encrypted_admin_password`; plaintext never logged.
7. **Deletion**: prevents deleting the agency DB; uses `exp_drop`; state transitions to `deleted` only after success.
8. **API boundary**: reuse existing `client_provisioning_api.py` endpoints; no new gateway. Lifecycle service is called from the controller.
9. **Generation boundary**: no pipeline integration in this phase; the service is standalone.
10. **Capability relationship**: `backend_required` is policy input, not an execution command; provisioning is explicit.

## Security

- Fernet reused (`OdooSecretsProvider`) — no new secret system.
- Admin password is encrypted at rest; decrypted only for internal use.
- DB names are sanitized; user input never directly injected.
- Errors never leak secrets.

## Non-goals (Phase 47.33)

- Module installation (47.34)
- Capability → module mapping (47.34)
- Client API/auth (47.35)
- Frontend binding (47.36)
- Console UI (47.38)
- Backup/restore (deferred)

## Consequences

- One canonical client lifecycle owner.
- Real DB creation and deletion through the existing Odoo primitives.
- Idempotent, observable, secure.
- Agency DB remains isolated.
- No new orchestration/duplicate provisioning.

## Future

- Phase 47.34: module installation.
- Phase 47.35: client API.
- Phase 47.36: frontend binding.