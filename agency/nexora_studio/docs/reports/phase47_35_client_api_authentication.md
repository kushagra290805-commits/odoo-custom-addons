# PHASE 47.35 — CLIENT API + AUTHENTICATION FINAL REPORT

Date: 2026-09-07
Phase: 47.35
Status: COMPLETED

## 1. Executive Summary

Phase 47.35 establishes the canonical authenticated client API inside the
existing FastAPI BFF. It does not create a second API gateway, auth service,
database resolver, or Odoo integration mechanism.

```
Client Principal
    → client bearer-token authentication
    → authorized ClientEnvironment
    → Phase 47.34.x agency DB safety guard
    → isolated Client Odoo DB
    → explicit capability/business operation
```

Implemented public client contract:

```
GET  /api/v1/client/whoami
GET  /api/v1/client/health
GET  /api/v1/client/products
POST /api/v1/client/leads
```

Client tokens are per-environment, SHA-256 hashed at rest, expiring,
revocable, and rotatable. The client API accepts no `db_name`, project ID,
selector.

## 2. Existing API/Auth Audit

| Component | File | Classification | Evidence |
|---|---|---|---|
| FastAPI BFF | `nexora-console/backend/main.py` | **CANONICAL** | one FastAPI app; existing routers, CORS, global boundary |
| Console JWT | `backend/security/auth.py` | **CANONICAL (agency Console)** | HS256 JWT, expiry, HTTPBearer dependency |
| Console login | `backend/api/routes.py:44` | CANONICAL | Odoo `common.authenticate` → JWT |
| BFF Odoo adapter | `backend/adapters/odoo_client.py` | **CANONICAL** | JSON-RPC/session adapter; existing adapters delegate through it |
| BFF CORS | `backend/main.py:22` | CANONICAL | explicit settings origins; no wildcard credentials |
| WebSocket | `backend/api/ws.py` | EXISTING | left untouched; no client realtime requirement |
| Odoo credential owner | `OdooSecretsProvider` / `OdooCredentialResolver` | CANONICAL CONNECTOR OWNER | not reused for client API tokens |
| Client DB lifecycle | `ClientEnvironmentService` | CANONICAL | reused and extended, no duplicate service |
| Client DB safety | `_is_agency_database` | CANONICAL | Phase 47.34.x owner reused |
| Client auth/token owner | `ClientEnvironmentService` | **NEW EXTENSION OF CANONICAL OWNER** | token lifecycle + client operations |
| Client route owner | `backend/api/client_routes.py` | NEW THIN ROUTER | mounted inside existing BFF, no second app |

The repository contained no existing client principal/token implementation.
The existing JWT is agency Console authentication, not a client-environment
credential, so a small distinct client-token credential class was necessary.

## 3. Canonical Boundary Decision

The existing FastAPI BFF remains the ONE canonical headless API boundary.
Client routes are mounted inside the same FastAPI app under `/api/v1/client`.

- Console routes retain the existing JWT dependency.
- Client routes use a distinct client-token dependency.
- Odoo remains the control-plane/service owner.
- The BFF remains a thin adapter and HTTP error-mapping layer.

No second FastAPI app, gateway, router stack, or auth architecture was
created.

## 4. Authentication Design

The client principal is a per-`ClientEnvironment` bearer token:

- prefix: `nex_cli_`
- random token generated with `secrets.token_urlsafe(32)`
- SHA-256 hash stored in `nexora.client_environment`
- plaintext returned once by control-plane issuance
- default TTL: 365 days, bounded to 1–3650 days
- rotation replaces the active hash and invalidates the old token
- revocation clears the hash/active state
- expiry is checked server-side
- malformed tokens fail closed

The existing agency Console JWT is not accepted as a client token. Client
tokens are not connector API keys, PATs, Odoo passwords, or Fernet-managed
secrets.

## 5. Authorization Design

Authentication resolves exactly one environment. Authorization then checks:

1. token is active and not expired
2. environment exists and is `ready`
3. environment is not deleted
4. environment is not agency-pointed
5. requested business capability exists in the approved Module Plan
6. corresponding approved Odoo module is actually installed

No client-supplied environment/project/database selector participates in this
chain.

## 6. Client Identity Resolution

The canonical relationship remains:

```
Client API token
    → ClientEnvironment
    → project_id / project identity
    → stored client DB identity
```

`ClientEnvironmentService._resolve_client_token()` is the only token→tenant
resolution owner. `whoami` returns project/environment names and server-derived
business capabilities, but not `db_name`, technical module names, credentials,
or agency metadata.

## 7. ClientEnvironment Resolution

`services/client_environment_service.py` owns all client API resolution and
operations. It reuses the existing environment model, lifecycle state, Module
Plan, `_is_agency_database`, and client registry access pattern.

## 8. Database Resolution

The client API has no `db_name` or `environment_id` argument. The service reads
only the stored `ClientEnvironment.db_name`, then applies the existing
fail-closed Phase 47.34.x agency guard before opening:

```
Registry(client_db_name)
    → context-managed cursor
    → SUPERUSER Environment
    → explicit operation
```

The agency DB cannot be selected through a client request.

## 9. Agency DB Protection

`_is_agency_database` remains the canonical safety owner. Client API methods
re-check it before serving client operations. Corrupted/legacy environment
records pointing at the agency DB return `CLIENT_ENV_NOT_READY` and do not
open or mutate the agency DB.

## 10. Token Lifecycle

Implemented in `services/client_environment_service.py`:

- `issue_client_api_token(env_id, ttl_days=None)`
- `revoke_client_api_token(env_id)`
- `_resolve_client_token(token)` (internal, underscore-prefixed)

Model fields added to `models/client_environment.py`:

- `client_api_token_hash`
- `client_api_token_issued_at`
- `client_api_token_expires_at`
- `client_api_token_active`

Issuance and revocation require system/admin privilege. The model actions
`action_issue_client_api_token()` and `action_revoke_client_api_token()` are
control-plane operations; no Console UI was added.

## 11. Credential Storage

Client API tokens use SHA-256 hashing because the plaintext token is only
needed at issuance and never recovered. `OdooSecretsProvider`,
`OdooCredentialResolver`, `nexora.mcp_credential`, and connector credentials
remain separate and untouched.

No token/password/PAT/API-key value is logged or returned by client routes.

## 12. Odoo Access Mechanism

The BFF reuses `adapters/odoo_client.py` and its existing service-account
JSON-RPC delegation pattern. Existing BFF adapters already call Odoo
AbstractModel services such as `nexora.builder_assistant_service`; Phase 47.35
follows that established ownership pattern.

Client DB business operations use the proven in-process Odoo `Registry` and
context-managed cursor pattern established by Phase 47.34.

## 13. API Contract

### `GET /api/v1/client/whoami`

Returns `project`, `environment`, and server-derived `capabilities`.

### `GET /api/v1/client/health`

Returns environment status, module provisioning state, and client DB
availability. It does not return the database name.

### `GET /api/v1/client/products?limit=1..100`

Requires the server-derived `products` capability and installed `product`
module. Returns an explicit product projection: `id`, `name`, `price`, `sku`.

### `POST /api/v1/client/leads`

Requires the server-derived `leads` capability and installed `crm` module.
Accepts only `name`, `email`, `phone`, and `message`; creates an explicit
`crm.lead` projection. Model/method/db/args fields are ignored and never
reach Odoo.

## 14. Capability Authorization

Capabilities are read from the approved Phase 47.34 Module Plan and filtered
through `CAPABILITY_MODULE_ALLOWLIST`. The client cannot submit or override
capabilities. Technical module names are not part of the public API response.

## 15. Error Semantics

The BFF maps stable Odoo-service codes:

| Code | HTTP |
|---|---:|
| `CLIENT_AUTH_INVALID` | 401 |
| `CLIENT_AUTH_EXPIRED` | 401 |
| `CLIENT_ENV_DELETED` | 410 |
| `CLIENT_ENV_NOT_READY` | 503 |
| `CLIENT_CAPABILITY_UNAVAILABLE` | 403 |
| `CLIENT_DB_UNAVAILABLE` | 503 |
| `CLIENT_REQUEST_INVALID` | 422 |
| `CLIENT_BACKEND_ERROR` | 502 |

Unexpected transport errors are sanitized. No raw Odoo stack trace or DB
connection detail is returned.

## 16. CORS/Security

`settings.CORS_ORIGINS` and the existing explicit-origin, credential-capable
CORS configuration remain unchanged. No wildcard credential CORS was added.
No rate-limiting service exists in the repository; rate limiting is deferred
as an operational follow-up rather than adding disproportionate infrastructure.

## 17. Tenant Isolation

Tenant isolation is structural: the client API has no tenant selector.
Token A always resolves to environment A; token B resolves to environment B.
The E2E proves two real client databases, cross-capability rejection, agency
DB isolation, and client DB identity.

## 18. BFF Relationship

The FastAPI BFF remains the sole headless boundary. `api/client_routes.py` is
a thin router and error mapper; it does not contain Odoo business logic,

## 19. Generation Relationship

No generation code changed. The frozen chain remains:

```
BuilderSessionService → GenerationCoordinator → GenerationRuntime
    → WebsiteGenerationPipeline
```

No generation engine gained API/authentication responsibility.

## 20. Module Provisioning Relationship

Client API/authentication does not install modules and accepts no module
identifiers. It consumes the verified Phase 47.34 Module Plan and installed
module state only.

## 21. Files Changed

| File | Change |
|---|---|
| `models/client_environment.py` | Client token fields + issue/revoke actions |
| `services/client_environment_service.py` | Token lifecycle, auth resolution, identity/health/products/leads operations |
| `nexora-console/backend/api/client_routes.py` | New thin client routes within existing BFF |
| `nexora-console/backend/main.py` | Mounts client router in same FastAPI app |
| `tests/test_phase47_35_client_api.py` | New Odoo-side auth/authz/API tests |
| `tests/test_phase47_35_bff_client_routes.py` | New BFF route contract/security tests |
| `tests/__init__.py` | Registers Odoo-side Phase 47.35 tests |
| `scripts/verify_phase47_35.py` | Real client API/auth E2E |
| `docs/adr/ADR-0086-client-api-authentication.md` | New ADR |
| `docs/reports/phase47_35_client_api_authentication.md` | This report |

## 22. Tests

- Odoo TransactionCase suites: **98 tests, 0 failures, 0 errors**
  - Phase 47.33: 8
  - Phase 47.34: 39
  - Phase 47.34.x: 24
  - Phase 47.35 Odoo-side: 27
- BFF client route tests: **19 tests, all pass**
- Phase 47.31 boundary tests: 17 OK
- Phase 47.32 capability tests: 20 OK
- Generation regressions: 38 OK

## 23. Real Client DB E2E

`scripts/verify_phase47_35.py` completed with **31/31 checks PASS** and
`LLM calls: 0`.

Real flow:

1. Environment A created/provisioned in `nexora_e2e475a_*`.
2. Real `product` and `crm` modules installed.
3. Product seeded in Client DB A.
4. Client token issued.
5. Real BFF routes exercised through a forwarding OdooClient transport to the
   real Odoo service and real client registry.
6. Product read returned the product from Client DB A.
7. Lead write created a record in Client DB A.
8. Lead was verified directly in Client DB A.
9. Lead was absent from the agency DB.
10. Both disposable client DBs were dropped through the canonical lifecycle.

The BFF transport was forwarded in-process only to avoid requiring unknown
external BFF service-account environment variables; the BFF route, Odoo
service, token resolution, capability checks, registry access, and real DB
operations were exercised.

## 24. Cross-Client Rejection E2E

Environment B received a distinct token and had no provisioned modules:

- Token B resolved only to Tenant B.
- Products request with Token B → 403 capability unavailable.
- Leads request with Token B → 403 capability unavailable.
- Tenant A product/lead data was not exposed to Tenant B.
- No environment ID or database selector existed in the route/service
  contract.

## 25. Agency DB Rejection E2E

- Console JWT supplied to client route → 401.
- Client token supplied to Console `/api/v1/auth/me` → 401.
- Client operations resolved only through ClientEnvironment records.
- Agency DB module snapshot remained unchanged before/after.
- Lead was not present in the agency DB.

## 26. Arbitrary Odoo Access Rejection E2E

- `/api/v1/client/execute` → 404
- `/api/v1/client/rpc` → 404
- `/api/v1/client/odoo` → 404
- `/api/v1/client/sql` → 404
- `/api/v1/client/models/res.partner` → 404
- Hostile `model`, `method`, `args`, and `db_name` fields in lead payloads
  never reached Odoo; only the explicit lead whitelist was persisted.

## 27. Agency DB Before/After Evidence

The E2E compared the agency `ir_module_module` name/state snapshot before and
after client API activity: identical. Agency control-plane record counts
changed only by the two expected disposable environment audit records.

## 28. Client DB Evidence

- Client DB A: `nexora_e2e475a_*`, product and CRM modules installed; product
  read and lead write verified directly through its registry.
- Client DB B: `nexora_e2e475b_*`, no CRM/product capability; capability
  requests rejected before business operation.
- Both disposable databases were deleted through `action_delete`; the agency
  DB remained accessible.

## 29. Regression Results

All required regressions passed:

- 47.31 boundary: 17
- 47.32 capability: 20
- 47.33 lifecycle: 8
- 47.34 provisioning: 39
- 47.34.x safety: 24
- 47.35 Odoo API/auth: 27
- BFF client routes: 19
- generation: 38

## 30. LLM Call Count

Client API/authentication adds **0 LLM calls**. No AI provider, routing, or
generation code changed.

## 31. Performance/Connection Observations

- BFF transport uses the existing OdooClient singleton and per-call timeout.
- Client registry cursors are context-managed and released after every
  operation.
- Registry caching uses Odoo's existing registry cache; no second connection
  pool was created.
- Products and lead operations are bounded by explicit payload/limit caps.
- No rate-limit infrastructure currently exists; deferred.

## 32. ADR/Report Changes

- Added `docs/adr/ADR-0086-client-api-authentication.md`.
- Added this report.

## 33. Dead/Duplicate Implementation Audit

- No existing client auth/token owner existed.
- Existing Console JWT remains canonical for agency Console traffic.
- Existing FastAPI BFF remains canonical; no duplicate API gateway.
- Existing ClientEnvironmentService remains canonical for environment,
  token, DB, and client operation ownership.
- Existing OdooClient remains canonical for BFF→Odoo transport.
- Connector credential infrastructure was not reused or changed.
- No generic RPC/model endpoint was created.

## 34. Remaining Gaps

- Client connectors are not exposed through this API.
- Client user/password/OIDC identity is deferred; Phase 47.35 uses
  per-environment machine/client tokens.
- Rate limiting is deferred.
- Token issuance UI was not added; the control-plane model action/service is
  available to the operator.
- BFF production service-account environment configuration remains an
  operational deployment concern; the E2E used an in-process forwarding
  transport while preserving the real route/service/DB path.

## 35. Explicitly Deferred Phase 47.36 Work

- generated frontend binding
- frontend API client generation
- browser-side token delivery/storage decisions
- generated component API calls
- full-stack frontend/backend validation

## 36. Architecture Invariant Confirmation

- ONE canonical headless API boundary ✅
- ONE Console JWT owner; distinct client token class ✅
- ONE client identity/environment resolution path ✅
- ONE client DB lifecycle owner ✅
- ONE database safety owner ✅
- ONE module provisioning owner ✅
- client identity before DB identity ✅
- authorization before client DB resolution ✅
- no trusted client-supplied db_name/environment selector ✅
- agency DB access rejected ✅
- no raw Odoo RPC/model/method/SQL exposure ✅
- no connector changes ✅
- no credential values printed or logged ✅
- no generation changes ✅
- no LLM calls ✅
- tenant crossing tested with real client DBs ✅
- agency DB before/after integrity verified ✅
- Phase 47.31/32/33/34/34.x/generation regressions green ✅
- no Phase 47.36 work implemented ✅

---

*End of Phase 47.35 report.*

---

## 37. Phase 47.35.x Remediation Addendum (2026-09-08)

Scope: close the two verification/action findings of the independent
red-team review (F1, F2) and formally document the accepted design
constraint (F3). No client API redesign; no second gateway, auth system,
DB resolver, Odoo client, or realtime service was created.

### F1 — WebSocket isolation: CLOSED

Root cause: `/ws/events` (backend/api/ws.py) accepted any TCP connection
and broadcast agency operational data (all sessions, AI ops, token
usage) to it.

Audience determination (verify-first): the sole consumer is the agency
Console frontend (`src/stores/webSocketStore.ts` — dashboard/workspace
live panels). No client application consumes the hub; the frontend only
listens (no SUBSCRIBE_* senders exist in the console code).

Fix (minimum, within the ONE BFF): in-band first-message authentication
reusing the canonical Console JWT decoder (`security.auth.decode_token`
— no second validator). Browsers cannot set an Authorization header on
a WS handshake; the JWT transits the same-origin first frame (10s auth
window). Fail-closed: unauthenticated sockets are never registered for
broadcasts and receive nothing; malformed/invalid/absent credentials and
client `nex_cli_*` tokens close the socket with 4401. The Console
frontend store now sends `{"type": "AUTH", token}` on open.

Event scope: unchanged (agency-only operational stream); enforcement is
at the registration/broadcast boundary — only authenticated sockets are
in the broadcast set. CORS was not used as the boundary.

Security tests (backend/api tests, real WS over TestClient): 14/14
(§7 matrix: unauth/malformed/non-AUTH/client-token/invalid-JWT/expired-
JWT/no-token rejections, 4401 close code, registration isolation,
broadcast reachability, canonical-decoder-only, route-monting
regression). Real TCP verification against the running BFF is included
in the 47.35.x E2E below (unauth→4401, client token→4401, valid
JWT→CONNECTION_ESTABLISHED→ping/pong).

### F2 — Real BFF → OdooClient → HTTP → Odoo transport: CLOSED

Audit (§9): `OdooClient` (backend/adapters/odoo_client.py) builds
`{ODOO_URL}/web/dataset/call_kw/{model}/{method}` JSON-RPC envelopes,
authenticates once via `/web/session/authenticate` using the
service-account env vars `ODOO_USERNAME`/`ODOO_PASSWORD` (never printed,
never committed; source: process environment only), reuses the
`session_id` cookie, per-call timeout (30s client routes), parses the
Odoo error envelope, and is the existing canonical transport — no
second Odoo client was created.

Real HTTP E2E (scripts/verify_phase47_35x.py, 22/22 PASS, LLM calls: 0):
real uvicorn BFF with a REAL disposable service account
(`base.group_system` by design — the Nexora service layer is the
security boundary; created/deleted through the registry, credentials
transit process env only) → REAL disposable client DB
(nexora_e2ehttp_*, modules product+crm really installed) →
product read + lead create over REAL HTTP → verified directly in the
client DB registry → agency DB module snapshot identical, no lead in
agency DB → disposable client DB + service account deleted. Failure
semantics: invalid service credentials → sanitized 502; Odoo
unavailable → sanitized 502 bounded at 4.1s.

DB-target evidence: the response product (seeded in the client DB only)
and the created lead (verified by direct client-DB registry read, absent
from agency DB) prove the HTTP request resolved to the correct client
DB through the canonical token → ClientEnvironment → agency-guard chain
(`_is_agency_database` reused, not duplicated).

### F3 — Superuser invariant: DOCUMENTED

ADR-0086 addendum §16-17 now states the invariant (client Odoo superuser
operations are an internal implementation detail confined to the
resolved client DB, reachable only through the four allowlisted
`client_api_*` operations) and the hard rule for future `client_api_*`
operations (shared prelude, agency guard, allowlisted operation, no
generic RPC). Regression coverage added:
`tests/test_phase47_35x_security_invariants.py` (12 tests: superuser
confinement to the resolved client DB, agency-pointed record fails
closed before any registry open, no generic RPC surface in
`client_api_*` bodies, hostile payload whitelist, credential-class
separation both directions, prelude-order enforcement).

### F4 (rate limiting) / F5 (internal Odoo error logging): DEFERRED

No concrete exploitable path was found during this remediation: client
401s are authenticated server-side before any expensive operation, and
no secret/credential disclosure was observed in error paths (the 502
sanitization was re-verified under invalid-credentials and Odoo-down
conditions). Both remain recorded future operational hardening items.

### Files changed (47.35.x only)

| File | Change |
|---|---|
| `nexora-console/backend/api/ws.py` | F1: in-band JWT auth before registration/broadcast; 4401 fail-closed close |
| `nexora-console/src/stores/webSocketStore.ts` | F1: send AUTH frame with canonical JWT on open |
| `tests/test_phase47_35x_ws_auth.py` | F1: 14-test WS auth/isolation matrix |
| `tests/test_phase47_35x_security_invariants.py` | F3: 12-test invariant suite |
| `tests/__init__.py` | register the 47.35x invariants suite |
| `scripts/verify_phase47_35x.py` | F2/F1: real HTTP + real TCP WS E2E |
| `scripts/verify_phase47_35x_ws_broadcast.py` | F1: real-TCP broadcast regression (authenticated Console socket still receives agency events) |
| `scripts/run_4735x_regressions.py` | standalone generation-regression runner |
| `docs/adr/ADR-0086-...` | addendum: WS boundary, real transport, superuser invariant, future client_api_* rule |
| `docs/reports/phase47_35_client_api_authentication.md` | this remediation addendum |

### Regression results (47.35.x)

| Suite | Count | Result |
|---|---:|---|
| 47.3x Odoo combined (odoo-bin, focused tags) | 110 | 0 failed, 0 errors |
| — of which new 47.35x invariants | 12 | all PASS |
| 47.35 BFF client routes | 19 | OK |
| 47.35x WS auth (new) | 14 | OK |
| 47.31 boundary | 17 | OK |
| 47.32 capability | 20 | OK |
| Generation regressions (47_5 behavior + 47_7 artifacts) | 38 | OK |
| Real HTTP + WS E2E (verify_phase47_35x.py) | 22 checks | all PASS |

Known pre-existing environment failures (unchanged by this phase, out of
scope): `test_lifecycle_integrity` (connector runtime env) and
`test_phase16_autonomous_generation` (template path env) fail in the
full-module odoo-bin run both before and after this remediation.
