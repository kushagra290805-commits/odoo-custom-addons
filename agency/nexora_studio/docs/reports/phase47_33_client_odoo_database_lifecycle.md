# PHASE 47.33 — FINAL CLIENT ODOO DATABASE LIFECYCLE REPORT

Date: 2026-09-07
Phase: 47.33
Status: ACCEPTED

## 1. Executive Summary

Phase 47.33 establishes a **secure, idempotent client Odoo database lifecycle** for Nexora Studio. The existing `client_provisioning_api.py` real primitives (`exp_create_database`, `exp_drop`) are now owned by a canonical lifecycle service (`nexora.client_environment_service`) with a persistent state model (`nexora.client_environment`). Database names are deterministic and sanitized, admin credentials are encrypted with the existing Fernet `OdooSecretsProvider`, and deletion prevents the agency DB from being dropped. The lifecycle is isolated from the frontend generation pipeline and does not install modules or create client APIs.

## 2. Existing DB Lifecycle Audit (re-verified)

| Component | File | Status | Evidence |
|---|---|---|---|
| `create_database` | `controllers/client_provisioning_api.py:48` | ✅ REAL | Calls `odoo.service.db.exp_create_database` |
| `delete_database` | `controllers/client_provisioning_api.py:124` | ✅ REAL | Calls `odoo.service.db.exp_drop` |
| `install_modules` | Same controller:64 | 🔴 STUB | Commented service call |
| `init_store` | Same controller:76 | 🔴 STUB | Commented service call |
| `create_admin` | Same controller:91 | 🔴 STUB | Commented service call |
| `backup`/`restore` | Same controller:102,113 | 🔴 STUB | Commented service calls |
| Client environment model | **NEW** `models/client_environment.py` | ✅ ADDED | Stateful owner |
| Lifecycle service | **NEW** `services/client_environment_service.py` | ✅ ADDED | Canonical owner |

No duplicate or dead lifecycle implementations exist.

## 3. Canonical Ownership Decision

**Owner:** `nexora.client_environment_service` (AbstractModel) with `nexora.client_environment` (Model).

**Why:** The existing controller primitives are raw (no state, no idempotency, no credential storage). The lifecycle service owns all state transitions and database operations. The controller routes now delegate to this service.

## 4. Client Environment Model (`nexora.client_environment`)

| Field | Type | Purpose |
|---|---|---|
| `project_id` | Many2one | Logical project owner |
| `name` | Char | Environment name |
| `db_name` | Char | Sanitized database name, unique |
| `status` | Selection | `draft` → `provisioning` → `ready` / `failed`; `deleting` → `deleted` / `failed` |
| `error_message` | Text | Safe diagnostic |
| `encrypted_admin_password` | Text | Fernet-encrypted admin password |
| `created_by` | Many2one | Audit |

Constraints: `db_name` unique and allowed characters `[a-zA-Z0-9_]`.

## 5. Database Naming

`_sanitize_db_name(name)`:
- Replace invalid characters with `_`
- Collapse multiple `_` to single
- Strip leading/trailing `_`
- Prefix with `nexora_`
- Truncate to 20 chars (plus prefix)

Deterministic, safe, collision-resistant.

## 6. Lifecycle State Machine

```
draft
  ↓ action_provision()
provisioning
  ↓ DB creation success → ready
  ↓ DB creation failure → failed
ready
  ↓ action_delete()
deleting
  ↓ exp_drop success → deleted
  ↓ exp_drop failure → failed
deleted (terminal)
failed (retryable → draft/provisioning)
```

Transitions are explicit and observable.

## 7. Creation Flow

1. `create_environment(project_id, name)` → checks project existence, sanitizes name, ensures uniqueness, creates `draft` record.
2. `action_provision()` (called from controller) → status `provisioning` → `exp_create_database(db_name, demo=False, lang='en_US', admin_password)`.
3. On success: status `ready`, encrypt and store admin password.
4. On failure: status `failed`, error_message set.

## 8. Initialization Flow

The base Odoo environment is initialized by `exp_create_database` (which runs `_initialize_db`). No further initialization is performed in this phase; module installation is deferred to 47.34.

## 9. Credential Handling

- Admin password is **encrypted at rest** using the existing `OdooSecretsProvider` (Fernet, master key from `NEXORA_CONNECTOR_SECRET_KEY`).
- Plaintext is never logged or returned in API responses.
- Decryption only occurs internally for credential use (future phases).

## 10. Idempotency

- `create_environment` checks `db_name` uniqueness before creation.
- `action_provision` only runs from `draft` or `failed` states.
- `action_delete` only runs from `ready`; prevents duplicate deletion.
- The service does not automatically recreate or retry without explicit action.

## 11. Concurrency

Odoo transactional locking (standard ORM savepoints) prevents concurrent provisioning of the same environment. The model uses `db_name` uniqueness as a database-level guard.

## 12. Failure/Recovery

| Failure | Behavior |
|---|---|
| Invalid DB name | ValidationError, no DB created |
| DB already exists | Duplicate key error, no DB created |
| `exp_create_database` failure | Status → `failed`, error_message set |
| `exp_drop` failure | Status → `failed`, error_message set |
| Agency DB deletion attempt | ValidationError, status unchanged |
| Process interruption | DB may exist without record; operator reconciliation required (future phase) |

## 13. Deletion

- `action_delete()` prevents deleting the agency DB (`db_name == config['db_name']`).
- Calls `odoo.service.db.exp_drop(db_name)`.
- On success: status → `deleted`.
- On failure: status → `failed`, error_message set.

## 14. API Boundary

The existing `POST /api/v1/provisioning/databases` and `DELETE /api/v1/provisioning/databases/<db_name>` endpoints now delegate to the lifecycle service. No new API routes were added. Phase 47.31 BFF remains the sole Console boundary.

## 15. Capability Contract Relationship

Phase 47.32's `RequirementModel.backend_required` is policy input, not an execution command. Provisioning is explicit (via API trigger), not automatic.

## 16. Generation Boundary

No integration with `WebsiteGenerationPipeline`. The lifecycle service is a standalone sibling workflow, consistent with Phase 47.30 evidence.

## 17. Security Boundary

- Fernet encryption reused (`OdooSecretsProvider`).
- DB names sanitized; user input not directly interpolated.
- Agency DB deletion guarded.
- Admin password encrypted at rest.
- Errors never leak secrets.

## 18. ADR-0084

Created: `docs/adr/ADR-0084-client-odoo-database-lifecycle.md`

Documents the client environment concept, agency vs client DB separation, canonical owner, creation/deletion ownership, lifecycle states, idempotency, concurrency, credential ownership, Fernet reuse, initialization semantics, failure/recovery, API boundary, relationship to BuilderSessionService and GenerationCoordinator, relationship to Phase 47.32 capability contract, separation from module provisioning, explicit non-goals, and security boundary.

## 19. Files Changed

| File | Change |
|---|---|
| `models/client_environment.py` | New model |
| `services/client_environment_service.py` | New service |
| `models/__init__.py` | Import `client_environment` |
| `services/__init__.py` | Import `client_environment_service` |
| `controllers/client_provisioning_api.py` | `create_database` and `delete_database` now delegate to the service |
| `docs/adr/ADR-0084-client-odoo-database-lifecycle.md` | New ADR |
| `tests/test_phase47_33_client_lifecycle.py` | New tests (TransactionCase, all pass) |

## 20. Tests

| Test | Result |
|---|---|
| `test_sanitize_db_name` | PASS |
| `test_create_environment` | PASS |
| `test_provision_success` | PASS |
| `test_provision_failure` | PASS |
| `test_delete_success` | PASS |
| `test_delete_agency_db_fails` | PASS |
| `test_idempotent_create` | PASS |
| `test_encryption` | PASS |

All tests ran under Odoo TransactionCase (`--test-tags=post_install`) and passed.

## 21. Real DB E2E Evidence

The E2E was conducted in the test environment (isolated database). The lifecycle was exercised end-to-end:
1. Environment created (`draft`)
2. Provisioned (`ready`) with real `exp_create_database`
3. Encrypted admin password stored
4. Deleted (`deleted`) with real `exp_drop`
5. Agency DB remained intact

Logs and test output confirm no module installation, no client API, no generation pipeline modification.

## 22. Agency DB Isolation Evidence

- `configs/dev.conf` still has `dbfilter=^nexora_studio$`.
- The service explicitly checks `db_name != config['db_name']` before deletion.
- Creation uses `nexora_` prefix and sanitization, preventing collision with agency DB.
- The controller and service never modify the agency DB's schema or data beyond control-plane metadata.

## 23. Chain-Integrity Proof

The existing generation chain remains:
```
Console
  ↓
FastAPI BFF
  ↓
existing service owners
  ↓
BuilderSessionService.run_generation()
  ↓
GenerationCoordinator
  ↓
GenerationRuntime
  ↓
WebsiteGenerationPipeline
```

The lifecycle service is a separate control-plane workflow, not inserted into the pipeline. No engine, state, or registry changes.

## 24. Duplicate-Orchestration Proof

- Exactly one lifecycle owner: `nexora.client_environment_service`.
- Exactly one DB creation primitive: `odoo.service.db.exp_create_database` (called only from the service).
- Exactly one DB deletion primitive: `odoo.service.db.exp_drop` (called only from the service).
- No new orchestrator (`ClientProvisioningOrchestrator`, `EnvironmentOrchestrator`) created.
- No duplicate controller or service.

## 25. Dead/Legacy Implementation Classification

| Implementation | Status |
|---|---|
| `client_provisioning_api.py` primitives (`exp_create_database`, `exp_drop`) | CANONICAL (now wrapped) |
| `install_modules`, `init_store`, `create_admin`, `backup`, `restore` | STUB (deferred) |
| `nexora.client_provisioning_service` (referenced in comments) | MISSING (now replaced by `nexora.client_environment_service`) |

The stubs remain in place (not removed) to avoid breaking potential callers; they are documented as deferred.

## 26. Remaining Gaps

1. **Backup/restore** still stubbed (deferred to future phase).
2. **Admin/service account creation** still stubbed (deferred to Phase 47.35).
3. **Module installation** absent (deferred to Phase 47.34).
4. **Capability → module mapping** absent (deferred to Phase 47.34).
5. **Client API** absent (deferred to Phase 47.35).
6. **Frontend binding** absent (deferred to Phase 47.36).
7. **Console UI** absent (deferred to Phase 47.38).

## 27. Explicitly Deferred Work

- Module installation and allowlist (47.34)
- Capability → Odoo module mapping (47.34)
- Client API and authentication (47.35)
- Frontend ↔ client backend binding (47.36)
- Full-stack validation (47.37)
- Console provisioning UI (47.38)

## 28. Architecture Invariant Confirmation

- One canonical client environment owner ✅
- Real DB creation works ✅
- Real DB deletion works ✅
- Lifecycle states explicit ✅
- Failures observable ✅
- Retries safe ✅
- Duplicate creation prevented ✅
- Agency DB remains isolated ✅
- Fernet/OdooSecretsProvider reused ✅
- No plaintext credentials ✅
- No credentials returned to frontend ✅
- No privileged operations exposed to LLM ✅
- DB names safely controlled ✅
- Errors do not leak secrets ✅
- No duplicate provisioning service ✅
- No duplicate DB lifecycle primitive ✅
- No new orchestration layer ✅
- No generation pipeline modification ✅
- FastAPI BFF remains the one headless boundary ✅
- No API gateway duplication ✅
- Capability contract separate from provisioning ✅
- No module installation ✅
- No capability → module mapping ✅
- No client API ✅
- No frontend binding ✅
- No Console UI ✅
- No provider/model/connector changes ✅
- No Graphify changes ✅
- ADR-0084 created ✅
- Tests pass ✅
- Agency DB integrity verified ✅

---

*End of Phase 47.33 report.*