# PHASE 47.35.x — RED-TEAM REMEDIATION COMPLETE

Date: 2026-09-08
Phase: 47.35.x (remediation of the independent Phase 47.35 review)
Status: COMPLETED — F1 CLOSED, F2 CLOSED, F3 DOCUMENTED, F4/F5 DEFERRED
LLM calls: 0

## Executive Summary

The independent red-team review of Phase 47.35 confirmed the client API
implementation as genuine and structurally sound, with two actionable
findings (F1 unauthenticated WebSocket, F2 unexercised real HTTP
transport) and one design constraint to formalize (F3 superuser service
layer). This remediation closed F1 with a minimum fail-closed fix inside
the existing canonical BFF (no second realtime service), closed F2 with a
real-transport E2E over a real uvicorn BFF, real OdooClient, real
HTTP/JSON-RPC, real Odoo server and a real disposable client DB, and
documented F3 as an enforced architecture invariant (ADR-0086 addendum +
regression tests). The generation architecture, module provisioning,
connectors, and all canonical owners are untouched.

```
F1: unauthenticated /ws/events            -> CLOSED (fail-closed 4401)
F2: real BFF->OdooClient->HTTP->Odoo chain -> CLOSED (22/22 real checks)
F3: superuser service-layer invariant      -> DOCUMENTED + 12 regression tests
F4: rate limiting                          -> DEFERRED (no concrete exploit)
F5: internal Odoo error logging            -> DEFERRED (no secret disclosure)
```

## F1 Root Cause

`nexora-console/backend/api/ws.py` accepted every TCP connection into
`ConnectionManager.active_connections` and periodically broadcast agency
operational data — all tenants' sessions (`SESSIONS_UPDATE`), AI job and
token-usage telemetry (`SYSTEM_HEALTH`, `AI_OPS_UPDATE`) — to every
connected socket, with no authentication or authorization anywhere on the
path. Any network-reachable client could consume the full agency event
stream.

## F1 Existing WebSocket Architecture (verify-first audit)

- One hub: `/ws/events` in the ONE FastAPI BFF (`main.py` mounts
  `ws_router` alongside the REST routers).
- Sole consumer: the agency Console frontend
  (`src/stores/webSocketStore.ts`), used by Dashboard,
  MissionControlView, WorkspaceView, EventConsole, EventTerminal,
  ProblemsPanel — all AGENCY views. No client application consumes it.
- The frontend only LISTENS: no `SUBSCRIBE_SESSIONS`/`SUBSCRIBE_AI_OPS`
  senders exist anywhere in the console source; those message types were
  server-side dead paths for direct requests. Realtime flows exclusively
  via periodic server broadcasts.
- Audience verdict: **A. Agency Console only.**

## F1 Fix

Component: `nexora-console/backend/api/ws.py` (existing owner; no new
service, no second gateway).

- `ConnectionManager.connect()` accepts the socket (protocol requirement)
  but NO LONGER registers it. `register()` is the only path into
  `active_connections` (the broadcast set).
- `_authenticate_console_socket()` (new, same file): within a 10s window
  the socket must send `{"type": "AUTH", "token": <Console JWT>}`. The
  token is validated by the canonical `security.auth.decode_token` (the
  same decoder `get_current_user` uses) executed via
  `run_in_executor` (worker-compatible). No second JWT implementation, no
  second validator, no second token store.
- Fail-closed: timeout, disconnect, malformed JSON, non-AUTH first
  message, missing token, invalid JWT, expired JWT → `close(4401)` with
  NO event payload ever sent. Unauthenticated sockets are structurally
  invisible to `broadcast()`/`send_to()`.
- No welcome/CONNECTION_ESTABLISHED frame before authentication.

Transport rationale (§4): browsers cannot set `Authorization` on a
WebSocket handshake. The JWT transits the first in-band frame over the
same-origin channel (`ws://<origin>/ws` — same host as the REST API the
token already authenticates). This is the smallest safe existing-compatible
mechanism; no query-string token (URL leakage) was introduced.

## F1 Authentication/Authorization

- Authentication: canonical Console JWT only. Client API tokens
  (`nex_cli_*`) are not JWTs and are rejected by the canonical decoder —
  the client credential class structurally cannot authenticate the agency
  stream.
- Authorization: all registered sockets are agency Console principals.
  The event stream (all sessions, AI ops, token usage) is agency
  operational data and remains agency-only. Client principals cannot
  reach it under any credential.
- Event scoping between agency principals was NOT introduced (single
  agency tenant, matching the REST boundary posture — Console JWT holders
  may read all sessions via REST today); the cross-tenant problem that
  F1 identified (unauthenticated + client-reachable) is closed.
- CORS was not used as the boundary (WebSocket is not CORS-protected).

## F1 Event Scope (§6 audit)

Event payloads contain project/session identifiers, job telemetry and
token-usage aggregates — agency operational data. Schemas unchanged;
authorization enforced at the registration/broadcast boundary (only
authenticated sockets are in the broadcast set).

## F1 Security Tests

`tests/test_phase47_35x_ws_auth.py` — 14 tests, all PASS (TestClient, real
WS protocol): unauthenticated timeout close, malformed JSON close,
non-AUTH first message close, client-token rejection, invalid JWT,
expired JWT, AUTH without token, 4401 close code, unauthenticated
sockets never registered, authenticated registration + cleanup,
broadcast reaches only registered sockets (isolation proof),
canonical-decoder-only (no `jwt.decode` in ws.py), valid JWT full
session (CONNECTION_ESTABLISHED + ping/pong), single-app mounting.

## F1 Real Verification (§8)

Real TCP against a real uvicorn BFF (dev authentication, disposable
account, no production credentials, no tokens printed):

- unauthenticated connect → server closes 4401 after the auth window, no
  frame received (`verify_phase47_35x.py` WS probe: `CLOSED:4401
  Unauthorized`)
- client `nex_cli_` token as AUTH → `CLOSED:4401 Unauthorized`, no frame
- valid Console JWT (real BFF login) → `CONNECTION_ESTABLISHED` then
  ping/pong
- broadcast regression (`scripts/verify_phase47_35x_ws_broadcast.py`):
  an authenticated Console socket receives a real periodic
  `SYSTEM_HEALTH` broadcast ≤15s — legitimate Console realtime remains
  functional.

## F2 Existing OdooClient Architecture (§9 audit)

`nexora-console/backend/adapters/odoo_client.py` (existing canonical
transport; unchanged):

- URL: `{ODOO_URL}/web/dataset/call_kw/{model}/{method}` (JSON-RPC 2.0
  envelope; Odoo `call_kw` route).
- Auth: one `/web/session/authenticate` with `ODOO_DB`,
  `ODOO_USERNAME`, `ODOO_PASSWORD` → session cookie reused for calls;
  singleton with lock; re-auth on demand when disconnected.
- DB selection: fixed `settings.ODOO_DB` (the agency DB) for the
  control-plane hop — the CLIENT DB is never selected by the BFF; it is
  resolved server-side by the Odoo owner from the client token.
- Timeout: per-call override (client routes: 30s).
- Errors: Odoo error envelope parsed and raised; client routes sanitize
  to 502 (type-only logging).
- Service credentials: process environment only
  (`config/settings.py`, Phase 47.31 posture — none committed, none
  printed; the E2E BFF logs contain no credentials).

## F2 Transport Path (verified)

```
BFF /api/v1/client/*  (real uvicorn :8100)
  -> OdooClient.call (real adapter, singleton)
  -> HTTP JSON-RPC over 127.0.0.1:8069 (real Odoo server)
  -> nexora.client_environment_service.client_api_* (real owner)
  -> token -> ClientEnvironment -> agency guard -> Registry(client_db)
  -> real disposable client DB
```

No ForwardingClient on any load-bearing operation (§10).

## F2 Real HTTP E2E (`scripts/verify_phase47_35x.py` — 22/22 PASS)

1. Agency DB identified (`nexora_studio`); before-snapshot captured
   (module name/state map, crm_lead table presence, env record count).
2. Disposable client environment created/provisioned through the
   canonical lifecycle; real `product` + `crm` modules installed
   (`state=provisioned`); client DB ≠ agency DB.
3. One product seeded directly in the client DB (setup only).
4. Disposable Odoo service account created via registry
   (`base.group_system` — see Service Account Evidence), deleted at the
   end; credentials transit process env only.
5. Client token issued (control plane).
6. Real uvicorn BFF started with the real service credentials.
7. `GET /client/whoami` → 200, server-derived identity+capabilities, no
   db_name. **Real HTTP.**
8. `GET /client/health` → 200 `ready`/`provisioned`/`client_db_available`.
9. `GET /client/products` → 200; the response contains the product
   seeded ONLY in the client DB.
10. `POST /client/leads` (hostile extras `db_name`/`model`/`method`/
    `args` included) → 200 `lead_id`.
11. Real-TCP WS probes (see F1 Real Verification).
12. Failure semantics: BFF with WRONG service password → sanitized 502
    `Client backend unavailable` (no credential/exception leakage); BFF
    pointed at a dead port → sanitized 502, bounded at 4.1s.
13. Agency after-snapshot: module states identical; lead count in agency
    DB unchanged; control-plane +1 (the disposable env, then deleted).

## F2 Client DB Evidence

- Product provenance: the seeded widget exists only in the disposable
  client DB; its presence in the HTTP response proves the request served
  from that DB.
- Lead provenance: direct registry read of the disposable client DB finds
  the lead (`lead_id=1`, whitelisted email/phone intact); the agency DB
  has no new lead (and no `crm_lead` table at all).

## F2 Agency DB Evidence

- Agency identity confirmed before and after (`nexora_studio`).
- `ir_module_module` name/state snapshot identical before/after.
- No lead in the agency DB; agency DB never a target of any client
  request (token-keyed resolution + `_is_agency_database` reused,
  not duplicated).

## F2 Service Account Evidence (§11/§13)

- Source of credentials: process environment (`ODOO_USERNAME` /
  `ODOO_PASSWORD`) — the existing Phase 47.31 mechanism; nothing
  committed, printed, or stored in tests/reports. The BFF log files of
  the E2E runs contain no credentials (verified).
- Privilege model: the BFF service account is a REAL Odoo user with
  `base.group_system` — deliberately privileged, because the Nexora
  service layer (token auth → capability authz → agency guard → field
  whitelists) is the security boundary; the account is not superuser
  (`OdooBot`/`__system__`), and the E2E did not silently elevate it.
  Documented as part of the F3 invariant.
- The client credential never transits Odoo; Odoo never sees
  `nex_cli_*` values (verified: no such strings in the E2E BFF logs).
- Client API requests cannot retrieve the service password: the client
  routes return only the whitelisted business projections (whoami/health/
  products/leads) — no config, no credentials, no ir.config_parameter
  surface.

## F2 Error/Timeout Verification

- Invalid service credentials → every client route returns sanitized 502
  `Client backend unavailable` (type-only server-side logging).
- Odoo unavailable → connection failure surfaces within the per-call
  timeout (measured 4.1s, bounded by the 30s client-route timeout);
  response sanitized 502.
- No stack traces, DB names, credentials, or Odoo internals in any
  client response (re-asserted in both failure probes).

## F3 Superuser Security Boundary (§14)

Documented in the ADR-0086 addendum: client Odoo SUPERUSER operations are
an internal implementation detail behind the Nexora authorization
boundary, confined to the resolved Client DB, reachable only through the
four allowlisted `client_api_*` operations with fixed field/projection
whitelists. `Client → Odoo SUPERUSER` directly is forbidden and
impossible (the client credential never reaches Odoo; no generic
execution surface exists).

## F3 Future `client_api_*` Invariant (§15)

Hard rule (ADR-0086 §17): every future `client_api_*` operation MUST go
through the shared prelude (auth → env state → agency guard → capability),
resolve the environment server-side, pass `_is_agency_database`, execute
only an explicit allowlisted business operation, and sanitize the
response. Generic Odoo execution under the client API is architecturally
forbidden and now regression-enforced.

## F3 Test Coverage (§16)

`tests/test_phase47_35x_security_invariants.py` — 12 tests, all PASS:

- client requests never select the agency DB (structural: no
  db_name/environment selector in any client_api signature)
- agency guard invoked on the real client path (spy: the runtime call
  happens with the stored environment db_name)
- agency-pointed (corrupted) environment fails closed BEFORE any
  registry/superuser cursor opens
- superuser context confined to the resolved client DB (registry opened
  only for the stored environment db_name)
- no generic RPC surface (client_api bodies contain no
  execute_kw/call_kw/model/method dispatch)
- hostile lead payload yields only the whitelisted vals (SQL/RPC/domain
  injection inert)
- credential-class separation both directions (Console-JWT-shaped string
  rejected as client token; client token cannot decode as JWT; tampered
  tokens never resolve)
- future-operation enforcement (every client_api method uses the
  prelude; prelude order auth → state → guard → capability)

## F4 Rate Limiting Status

DEFERRED. No concrete exploitable path found: all client routes
authenticate server-side before any expensive operation; 401s are hash
lookups over 256-bit tokens. No rate-limit infrastructure was added (per
scope guard). Recorded as a future operational hardening item.

## F5 Error Logging Status

DEFERRED (audit outcome). `OdooClient` logs exception text server-side
(internal logs), but no secret/credential disclosure was found: the Odoo
owner returns error dicts (not raised exceptions) for client routes, and
the sanitization of externally visible responses was re-verified under
invalid-credentials and Odoo-down probes. Internal log hardening remains
a low-priority follow-up.

## Files Changed

| File | Owner | Change | Why minimal |
|---|---|---|---|
| `nexora-console/backend/api/ws.py` | FastAPI BFF (canonical boundary) | F1: authenticate-before-register; `register()`; `_authenticate_console_socket()`; 4401 close | Same hub, same app; no new service |
| `nexora-console/src/stores/webSocketStore.ts` | Console frontend store | F1: send AUTH frame with the existing `nexora_token` JWT on open | Same store, same token, one frame |
| `custom-addons/.../tests/test_phase47_35x_ws_auth.py` | new test file | F1: 14-test WS auth matrix | tests only |
| `custom-addons/.../tests/test_phase47_35x_security_invariants.py` | new test file | F3: 12-test invariant suite | tests only |
| `custom-addons/.../tests/__init__.py` | test registry | register the invariants suite | one line |
| `custom-addons/.../scripts/verify_phase47_35x.py` | new E2E script | F2 real HTTP + F1 real TCP WS | script only |
| `custom-addons/.../scripts/verify_phase47_35x_ws_broadcast.py` | new script | F1 broadcast regression | script only |
| `custom-addons/.../scripts/run_4735x_regressions.py` | new script | standalone generation regression runner | script only |
| `docs/adr/ADR-0086-...` | ADR | addendum §14-17 (WS boundary, real transport, superuser invariant, future rule) | doc only |
| `docs/reports/phase47_35_client_api_authentication.md` | report | remediation addendum §37 | doc only |

Callers/impact: `ws.py` is called only by `main.py` (router mount) and
the frontend store (WS client). The REST surface, client routes,
ClientEnvironmentService, module policy, generation chain, and
connectors are untouched.

## Tests Added/Changed

- `test_phase47_35x_ws_auth.py` — 14 (new, BFF/WS)
- `test_phase47_35x_security_invariants.py` — 12 (new, Odoo-side)
- `verify_phase47_35x.py` — 22 real checks (new, E2E)
- `verify_phase47_35x_ws_broadcast.py` — 1 real broadcast check (new)
- No existing test was modified.

## Complete Regression Results (§24)

| Suite | Count | Result |
|---|---:|---|
| 47.31 API boundary (standalone) | 17 | Ran 17, OK |
| 47.32 capability contract (standalone) | 20 | Ran 20, OK |
| 47.3x Odoo combined via odoo-bin (47.33: 8, 47.34: 39, 47.34.x: 24, 47.35: 27, **47.35x invariants: 12**) | **110** | `0 failed, 0 error(s) of 110 tests` |
| 47.35 BFF client routes (standalone) | 19 | Ran 19, OK |
| 47.35x WS auth (standalone, new) | 14 | Ran 14, OK |
| Generation regressions (47_5 behavior 8 + 47_7 artifacts 30) | 38 | Ran 38, OK |
| Real HTTP + WS E2E | 22 checks | all PASS |
| Real broadcast regression | 1 | PASS |
| Frontend TS check (`tsc -b`) | — | `webSocketStore.ts` clean (11 pre-existing errors in untouched files, unchanged) |

Known pre-existing environment failures OUT OF SCOPE (fail identically
with and without this remediation, in the full-module odoo-bin run):
`test_lifecycle_integrity` (connector runtime environment) and
`test_phase16_autonomous_generation` (template path environment).

## Agency DB Before/After Evidence (§26)

- Before: agency identity `nexora_studio`; module name/state map
  captured; `crm_lead` table present but EMPTY (lead count captured);
  env record count captured.
- After: identity unchanged; module map identical (dict equality); lead
  count unchanged (no client lead in the agency DB); env count +1 (the
  disposable E2E environment, deleted through `action_delete` in the
  same run — the two earlier development-iteration orphans
  `nexora_e2ehttp_010434`/`010419` were also cleaned through the same
  canonical lifecycle; the agency DB was never a target).
- DB accessible and schema healthy throughout (server served all
  requests).

### Agency DB `crm` note (forensic clarification)

The agency DB carries `crm` in `ir_module_module.state = 'installed'
since 2026-07-10` (pre-dating Phase 47.x; the state row's write_date is
untouched by this phase) with an EMPTY `crm_lead` table. Forensics
(dev.log + module-row write_dates) confirmed: every "module crm:
creating or updating database tables" line produced during this
remediation belonged to a DISPOSABLE client DB install
(`nexora_e2ehttp_*`); the agency table was already present at the E2E
before-snapshot, and the E2E explicitly verified the agency lead count
identical before/after the real HTTP client operations. No client API
path can install modules into or write data to the agency DB (agency
guard + capability authorization), and none did.

Separately (standard Odoo behavior, not client-API related): each
`odoo-bin -u nexora_studio` regression run performs the module upgrade's
usual auto-install/dependency state reconciliation (e.g.
`auth_totp_portal`, `http_routing` write_dates refresh to the last `-u`
run). This is the same upgrade side effect every prior regression run in
this repository produced, occurs only in the separate odoo-bin process
(not via any client route), and did not occur within the E2E's
before/after snapshot window.

## Connector Status (§19)

Not modified. All six connectors (context7_mcp, firecrawl_mcp, github_mcp,
gosom_mcp, penpot_mcp, tavily_mcp) remain as restored/verified; no
configuration, credential, enable/disable, or MCP architecture change.

## LLM Call Count

0 (no AI provider, routing, or generation code touched).

## Architecture/Ownership Audit

- ONE canonical headless API boundary: unchanged (client routes + WS in
  the same FastAPI app; no second app/gateway).
- ONE authentication owner: canonical JWT decoder for Console (REST +
  WS); client tokens validated Odoo-side by ClientEnvironmentService —
  unchanged; the WS fix reuses the canonical decoder (no second
  validator).
- ONE authorization model: server-derived capabilities (unchanged).
- ONE client identity resolution path: `_resolve_client_token`
  (unchanged).
- ONE client DB lifecycle owner: `ClientEnvironmentService`
  (unchanged; E2E cleanup used `action_delete`).
- ONE database safety owner: `_is_agency_database` (reused, never
  duplicated).
- ONE module provisioning owner: unchanged.
- Generation chain (BuilderSessionService → GenerationCoordinator →
  GenerationRuntime → WebsiteGenerationPipeline): untouched; generation
  regressions green.

## Duplicate Architecture Audit

No WebSocketGateway/ClientWebSocketGateway/EventGateway/
ClientRealtimeService was created (the existing hub was extended). No
second API service, auth system, authorization system, secrets store,
database service, or Odoo client exists after this change.

## Remaining Follow-ups

- F4 rate limiting (operational hardening; no current exploit path).
- F5 internal Odoo exception-text logging in `OdooClient` (no secret
  disclosure found; low priority).
- Cross-principal event scoping within the agency Console (single-tenant
  agency model today; relevant only if the Console ever becomes
  multi-principal).
- Client realtime (Phase 47.36+ scope, if ever required) must be
  separately scoped per tenant; the agency hub must not be reused for it.

## Explicitly Deferred Phase 47.36 Work

- generated frontend binding to the client API
- frontend API client generation
- browser-side client-token delivery/storage decisions
- generated component API calls
- full-stack frontend/backend validation
- client realtime channels

## Final Security Verdict

| Finding | Status |
|---|---|
| F1 unauthenticated cross-tenant WebSocket | **CLOSED** (fail-closed 4401; client tokens structurally rejected; authenticated Console realtime verified over real TCP) |
| F2 real BFF→OdooClient→HTTP→Odoo transport | **CLOSED** (22/22 real-transport checks; correct client DB proven; agency DB untouched; failure semantics bounded+sanitized) |
| F3 superuser service-layer invariant | **DOCUMENTED** (ADR-0086 addendum §16-17; 12 regression tests; no arbitrary Odoo access introduced) |
| F4 rate limiting | **DEFERRED** (no concrete exploit; recorded) |
| F5 error-logging hardening | **DEFERRED** (no secret disclosure found) |

All acceptance criteria of §30 are met. Phase 47.36 was NOT started.
