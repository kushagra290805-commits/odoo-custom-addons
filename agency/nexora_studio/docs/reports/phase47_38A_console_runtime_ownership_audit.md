# PHASE 47.38A — Console Surfaces + Production Runtime Ownership Audit

Date: 2026-04-15
Phase: 47.38A (verification-first, no implementation)
Baseline: Phase 47.37 ACCEPTED WITH FOLLOW-UPS (381 checks, 0 failures, 0 LLM calls)
Method: Source-authoritative audit. Graphify used only for bounded navigation; every ownership claim verified by direct file read. No source modified. No parallel architecture created.

---

## 1. Executive Verdict

**AUDIT COMPLETE — READY FOR NARROW 47.38 CONSOLE SURFACES; PRODUCTION RUNTIME DEFERRED.**

- **Console ownership is clear and singular.** One FastAPI BFF (`nexora-console/backend/main.py`), one transport (`adapters/odoo_client.py:OdooClient`), one auth boundary (Console JWT `security/auth.py:get_current_user` vs client bearer `api/client_routes.py:client_bearer`). No second BFF, no second transport, no second auth path. Extending Console to surface existing platform state is a narrow, safe change.
- **Client-environment facts are 80% already available through existing canonical owners but not surfaced.** The data lives in `nexora.client_environment` / `nexora.client_environment_service` and `services/design/capability_policy.py` + `services/design/module_policy.py`; the BFF has **zero** client-environment adapter or route today (verified). Surfacing them requires a single new thin adapter + read-only routes — no new storage, no new service.
- **No production runtime exists for generated apps.** Development is proven (`ViteLauncher` dev server + `vite.config.js` `server.proxy` injecting `NEXORA_CLIENT_API_TOKEN` server-side). All three launcher plugins (`vite_launcher.py`, `static_file_launcher.py`, `python_http_launcher.py`) are plain dev/static servers with no proxy and no secret capability. No nginx/Caddy/Traefik, no Docker/K8s definition, no SSR/Node entrypoint for generated apps exists in the repo. Token-in-browser is not an option.
- **Decision: OPTION D — defer production runtime to a dedicated deployment phase.** Console work (47.38) should not invent a production deploy plane. The minimal 47.38 scope is read-only Console visibility + safe lifecycle actions via the existing `ClientEnvironmentService`.
- **No ADR required in 47.38A.** This audit makes no architectural decision; it classifies ownership and defers the production-runtime decision. ADR-0061 should be created only when the deployment phase selects a runtime.

---

## 2. Architecture Inventory (as found)

### 2.1 Console Frontend (`nexora-console/src`)

| Concern | Location | Notes |
|---|---|---|
| App shell | `src/App.tsx` | `BrowserRouter` + `QueryClientProvider` + `AuthProvider` |
| Routes | `src/constants/routes.ts` | `PUBLIC: /login`, `PRIVATE: /dashboard, /projects, /projects/:id, /templates, /sessions, /workspace, /workspace/:sessionId, /settings, /ai-operations` |
| Auth | `src/providers/AuthProvider.tsx`, `src/api/client.ts` | Axios `baseURL: /api/v1`, JWT from `localStorage nexora_token` -> `Authorization: Bearer`, 401 evicts token |
| Query keys | `src/constants/queryKeys.ts` | `DASHBOARD, PROJECTS, TEMPLATES, SESSIONS, WORKSPACE, BUILDER_CONFIGURATIONS` |
| Features | `src/features/{dashboard,projects,sessions,templates,workspace,builder}` | `Projects.tsx` + `ProjectDetail.tsx` (10-tab placeholder), `Sessions.tsx`, `MissionControlView.tsx`, `WorkspaceView.tsx` |
| Repositories | `src/repositories/{projectRepository.ts, sessionRepository.ts}` | Thin wrappers over `apiClient.get/post/patch/delete` |
| Hooks | `src/hooks/queries/{useProjects.ts, useSessions.ts, useDashboard.ts, ...}` | `react-query` with `QUERY_KEYS` |
| Types | `src/types/{project.ts, session.ts, workspace.ts}` | `Project {id,name,status,client,createdAt}`; `Session {status: SessionLifecycleStatus, runtimeState, runtimeHealth}` with explicit tab-map |
| Vite proxy | `vite.config.ts` | `server.proxy: /api -> http://127.0.0.1:8000, /ws -> ws://127.0.0.1:8000` — Console BFF only |

### 2.2 Console Backend (`nexora-console/backend`)

| Concern | File | Notes |
|---|---|---|
| BFF app | `main.py` | Single `FastAPI` instance. `CORSMiddleware` allowlist from `config/settings.py`. `public_router` (login/health unauthenticated), `router` mounted with `Depends(get_current_user)` (every other `/api/v1` route requires JWT), `client_router` at `/api/v1/client` with its own bearer, `ws_router` |
| Auth | `security/auth.py` | `HTTPBearer` + `create_access_token`/`decode_token`/`get_current_user` (HS256, `JWT_SECRET`). Console JWT is the only agency credential |
| Transport | `adapters/odoo_client.py` | `class OdooClient` — single `JSON-RPC /web/dataset/call_kw/{model}/{method}` with `session_id` cookie. Singleton `get_odoo_client()`. No second client exists |
| Adapters | `adapters/{project,session,template,provider,ai_operations,dashboard,builder_configuration,workspace_file,preview,git,assistant,planner,execution}_adapter.py` | Each is a thin DTO mapper over `get_odoo_client()` |
| Routes | `api/routes.py` (agency) + `api/client_routes.py` (client, 4 routes) + `api/ws.py` | Agency: `public_router + router`; Client: `client_router.get /whoami,/health,/products + post /leads` |
| WebSocket | `api/ws.py` | `ConnectionManager` (only `register()`ed sockets receive broadcasts). `AUTH_TIMEOUT_SECONDS=10.0`, in-band `{"type":"AUTH","token":JWT}` validated via `decode_token` in executor. `nex_cli_*` structurally rejected (not a JWT) |
| Settings | `config/settings.py` | `ODOO_URL/DB/USERNAME/PASSWORD`, `JWT_SECRET` (random per-process fallback if missing) |

### 2.3 Agency (Odoo) Models Relevant to Console

| Model | File | Fields relevant to this audit |
|---|---|---|
| `nexora.project` | `models/project_management.py` | `name, partner_id, status {draft,active,paused,closed}` — **no** `capabilities`, `backend_required`, or `client_environment` link |
| `nexora.builder_session` | `models/builder_session.py` | `name, builder_configuration_id!, session_uuid, status {14 values}, runtime_state {6}, runtime_health, project_name (Char, not FK), lifecycle_phase (compute), workspace_id, event_ids` — **no** `project_id` FK, **no** `client_environment_id`, **no** `capabilities`/`backend_required` |
| `nexora.client_environment` | `models/client_environment.py` | `project_id (Many2one nexora.project, required, cascade, index)`, `name, db_name (unique), status {draft,provisioning,ready,failed,deleting,deleted}`, `module_provisioning_state {none,provisioning,provisioned,partial,failed}`, `module_plan (Text JSON), module_provisioning_result, module_provisioning_error`, `client_api_token_* (hash/active/expiry)`, `_sql_constraints db_name_uniq`, `@api.constrains _check_db_name` (regex + `_is_agency_database` fail-closed) |
| `nexora.workspace` | `models/builder_session.py` via relation, plus workspace modules | `workspace_path, status, health` |
| `nexora.runtime` | `models/runtime.py` | `builder_session_id (cascade), runtime_type {workspace,git,ide,preview,mcp,ai,deployment,docker,custom}, status, health, endpoint, port, process_id, metadata_json` |
| `nexora.runtime_event` | `models/runtime_event*` | `builder_session_id, runtime_type, event_type, message, timestamp` — pipeline subscribers + `BuilderSessionService._emit_event` write here; BFF reads via `GET /sessions/{id}/events` |
| `nexora.builder_configuration` | `models/builder_configuration.py` | `name, configuration_uuid, semantic_version, status {draft,locked,archived}, environment {development,testing,production}` |

---

## 3. Audit Objective A — Console Architecture

**Current Console application structure**

- Frontend is a standard Vite + React 19 + TanStack Query + React Router app. Routing is flat under `AppLayout`. `Projects` and `Sessions` are the two primary domain surfaces; `ProjectDetail` is a 10-tab shell where 9 tabs are placeholder Cards ("This enterprise module is fully integrated but awaits concrete data population.").
- Backend is a single FastAPI BFF. Every agency route is `Depends(get_current_user)` (JWT). `/api/v1/client/*` is separately authenticated via `client_bearer`. WebSocket is JWT-authenticated in-band. No Console surface today touches `nexora.client_environment`.

**Routing / adapters / BFF routes / WS consumption**

- `ROUTES.PRIVATE`: `DASHBOARD, PROJECTS, PROJECT_DETAIL, TEMPLATES, SESSIONS, MISSION_CONTROL, WORKSPACE, SETTINGS`. No `/environments`, `/client-environments`, or `/deployments` route exists.
- `api/routes.py`: ~30 agency routes across projects/sessions/templates/builder-configurations/files/git/assistant/planner/execution/preview/providers. `GET /sessions/{id}/events` is the only event feed (caps `limit 1..500`, reads `nexora.runtime_event`).
- `api/client_routes.py`: exactly 4 client routes — `GET /whoami`, `GET /health`, `GET /products?limit`, `POST /leads` — all delegating to `nexora.client_environment_service` via `get_odoo_client().call(CLIENT_SERVICE, method, [token,...])` with `CLIENT_ERROR_STATUS` mapping.
- Console WS consumer: none of the Console features currently subscribe to WS for provisioning/environment status; WS is used for `SYSTEM_HEALTH` / `SESSIONS_UPDATE` / `AI_OPS` style broadcasts (see §7).

**Existing project/session/environment surfaces**

- `ProjectAdapter` (`nexora.project`, fields `id,name,status,partner_id,create_date,write_date`) — list/search/status filter + CRUD. DTO is `{id,name,description:'',status,client,clientId,createdAt,updatedAt}` — no capabilities.
- `SessionAdapter` (`nexora.builder_session`, fields `id,name,session_uuid,status,project_name,runtime_state,runtime_health,lifecycle_phase,started_at,closed_at,last_activity,create_date,write_date,builder_configuration_id`) — same tab-group mapping as frontend. `project_name` is a plain `Char` (not a FK to `nexora.project`), so sessions are not relationally joined to projects today.
- **No environment surface exists.** `grep nexora.client_environment` across `nexora-console/backend/adapters` returns **0 hits** (verified). The BFF has never read `nexora.client_environment`.

**Canonical owner per responsibility**

| Responsibility | Canonical owner | Evidence |
|---|---|---|
| Project list/detail | `adapters/project_adapter.py:ProjectAdapter` -> Odoo `nexora.project` | DTO mapping `FIELDS`/`DETAIL_FIELDS` |
| Session list/detail/lifecycle | `adapters/session_adapter.py:SessionAdapter` -> Odoo `nexora.builder_session` + `nexora.builder_session_service` actions | `create/read/search_read/unlink` + `call MODEL action_*` |
| Builder configuration | `adapters/builder_configuration_adapter.py:BuilderConfigurationAdapter` -> `nexora.builder_configuration` | `MODEL = nexora.builder_configuration` |
| Project capability/backend_required | `services/design/capability_policy.py:CAPABILITY_VOCABULARY/BACKEND_REQUIRED_CAPABILITIES + infer_capabilities/backend_required` consumed by `services/generation/engines/requirement_engine.py` | `RequirementEngine.execute -> capability_policy.infer_capabilities` |
| Client environment lifecycle | `services/client_environment_service.py:ClientEnvironmentService` (`create_environment, _provision, _delete, _is_agency_database`) + model `client_environment.py` | `_is_agency_database` fail-closed at every boundary |
| Module planning + installation | `services/design/module_policy.py:build_module_plan/CAPABILITY_MODULE_ALLOWLIST` + `services/client_environment_service.py:provision_modules -> _install_modules_in_client_db -> Registry.new` | Pure allowlist, privileged installer |
| Client API (agency-to-Odoo) | `services/client_environment_service.py:client_api_*` (whoami/health/list_products/create_lead) | Token is sole selector |
| Frontend binding | `services/generation/engines/design_orchestration_engine.py:client_api_binding` + `services/design/providers/react_provider.py:_generate_client_api_js/_generate_vite_config` | Capability-gated `src/lib/clientApi.js` + vite proxy |
| Managed dev runtime | `services/launchers/vite_launcher.py:ViteLauncher` (plus `static_file_launcher.py`, `python_http_launcher.py`) | `validate/prepare/start/stop/health/detect_project` |

**Can Console's existing project/environment abstraction naturally own the required fields?**

| Required datum | Natural owner if surfaced? | Gap |
|---|---|---|
| `backend_required` | `nexora.builder_session` or `nexora.project` — but neither field exists today | Inference lives only in transient `GenerationContext.requirements.backend_required`; no persisted column on `project` or `session` |
| `capabilities` | Same as above | Inference lives in `RequirementModel.capabilities` (artifact); not persisted relationally |
| `ClientEnvironment` record | `nexora.client_environment` (exists, FK to `nexora.project`) | No adapter/route surfaces it to Console |
| Provisioning state | `nexora.client_environment.{status, module_provisioning_state, module_plan, module_provisioning_result/error}` | Exists, not surfaced |
| Module status | `module_plan` JSON + `module_provisioning_result` | Exists, not surfaced |
| Client API availability | `client_api_token_active/expires_at` (+ `status==ready`) not exposed; `GET /api/v1/client/health` is a client-credential probe, not an agency status read | Needs an agency-readable availability projection (not the token itself) |
| Runtime/deployment status | `nexora.runtime` + `nexora.preview_runtime:preview_url` via `preview_adapter` | Preview status exists (`GET /sessions/{id}/preview`); no deployment or client-runtime status |

**Conclusion A:** Do not create a second project/environment store. `nexora.project` is the existing client record (FK target of `client_environment`), `nexora.builder_session` is the existing lifecycle record. The missing piece is Console visibility over `nexora.client_environment` and the transient capability decision — both should be projected through existing owners, not re-stored.

---

## 4. Audit Objective B — Client Environment Data Surface

**What is already available (source-verified)**

On `nexora.client_environment` (model `client_environment.py:5-83`):

- `project_id` (Many2one `nexora.project`, cascade, indexed)
- `name` (Char)
- `db_name` (Char, unique, `@constrains` regex + `_is_agency_database` guard)
- `status` (Selection: `draft,provisioning,ready,failed,deleting,deleted`, default `draft`, required, indexed)
- `error_message` (Text), `encrypted_admin_password` (Text, Fernet-encrypted via `odoo_secrets_provider`), `created_by`
- `module_provisioning_state` (Selection: `none,provisioning,provisioned,partial,failed`, default `none`, indexed)
- `module_plan` (Text JSON — `{"schema_version","capabilities","modules":[{name,source_capabilities,reason}],"unresolved_capabilities","supported"}`)
- `module_provisioning_result` (Text JSON — `{installed,skipped,post_states,unresolved_capabilities}`), `module_provisioning_error` (Text)
- `client_api_token_hash` (Char SHA-256), `client_api_token_issued_at/expires_at` (Datetime), `client_api_token_active` (Boolean)

On services:

- `services/client_environment_service.py`: `_is_agency_database(db_name)` (fail-closed, checks `odoo.tools.config['db_name']` list + `cr.dbname`), `_agency_database_names()`, `create_environment(project_id, name)`, `_provision`, `_delete`, `provision_modules(env_id, capabilities)`, `issue_client_api_token/revoke_client_api_token` (control plane, `base.group_system`), `_resolve_client_token(token)`, `_client_api_prelude`, `client_api_whoami/health/list_products/create_lead`.
- `services/design/capability_policy.py`: `CAPABILITY_VOCABULARY` (14 values), `BACKEND_REQUIRED_CAPABILITIES`, `infer_capabilities(business_category, services, features, goals, raw_input)`, `backend_required(capabilities)`.
- `services/design/module_policy.py`: `CAPABILITY_MODULE_ALLOWLIST` (10 mapped, 4 explicitly unmapped), `build_module_plan`.

**Classification of each required Console datum**

| Conceptual datum | Availability | Source / exposure today |
|---|---|---|
| Environment identity (`id`, `name`, `db_name`, `project_id`) | **1 — already available** (not surfaced to Console) | `nexora.client_environment` fields; no BFF route today |
| Lifecycle state (`status`, `error_message`) | **1 — already available** | Same model; no BFF route |
| `backend_required` | **2 — available through existing owner but not persisted/surfaced** | `capability_policy.backend_required(infer_capabilities(...))` is computed during generation and stored only in `GenerationContext.requirements`; no column on `nexora.project` or `nexora.builder_session` |
| `capabilities` (inferred) | **2** | Same inference; same transient storage |
| Requested module plan | **1 — already available** | `module_plan` JSON (deterministic, `sort_keys=True`) |
| Installed modules | **1 — already available** | `module_provisioning_result` JSON (`installed`/`skipped`/`post_states`) |
| Provisioning error/status | **1 — already available** | `module_provisioning_state` + `module_provisioning_error` |
| Client API availability (safe) | **2 — available via existing owner, needs projection** | `client_api_token_active` + `client_api_token_expires_at` + `status==ready` can be projected as `{available: bool, reason: string}` without exposing the token, hash, or DB name internals. The client-facing `GET /api/v1/client/health` is not appropriate for Console (requires `nex_cli_*`) |
| Runtime/deployment status | **4 — should remain internal as defined OR 2 if preview qualifies** | `nexora.runtime` + `nexora.preview_runtime.preview_url` already surfaced via `GET /sessions/{id}/preview` (`preview_adapter`). Deployment status for generated apps does not exist (see §5). Generated-app runtime is `ViteLauncher` dev-only; no deployment status to surface |

**Do-not-surface (internal):** `encrypted_admin_password`, `client_api_token_hash`, plaintext `nex_cli_*` (never stored), `db_name` should be treated as internal identifier (Console may display `name` + `status` but need not expose raw `db_name` unless operator role requires it — see security §9).

**No new API contract is genuinely required for the environment facts themselves** — a thin read-only `GET /projects/{id}/environments`-style or `GET /client-environments?project_id=` projection over the existing model suffices. The only "new" contract is the BFF adapter/route that projects the already-stored rows.

---

## 5. Audit Objective C — Existing Deployment / Runtime Ownership

### 5.1 Generated-app runtime mechanisms found

| Mechanism | File | Type | Proxy? | Secret-capable? | Used by generated apps? |
|---|---|---|---|---|---|
| `ViteLauncher` | `services/launchers/vite_launcher.py` | `nexora.preview_launcher_vite` (`_inherit: nexora.preview_launcher`) | No — `prepare()` returns `cmd=[npm run dev -- --port --host 127.0.0.1]`, `env={'PORT':port}` only. Proxy is NOT in the launcher; it is in the **generated** `vite.config.js` (`ReactRenderingProvider._generate_vite_config` injects `server.proxy /api/v1/client -> process.env.NEXORA_CLIENT_API_URL` + `proxyReq.setHeader('Authorization','Bearer '+token)`) | Token injected into launched `env` by 47.36 E2E harness at launch time (`NEXORA_CLIENT_API_TOKEN`), but the launcher itself never sets `NEXORA_CLIENT_API_*` |
| `StaticFileLauncher` | `services/launchers/static_file_launcher.py` | `nexora.preview_launcher_static_file` | No | No |
| `PythonHttpLauncher` | `services/launchers/python_http_launcher.py` | `nexora.preview_launcher_python_http` | No | No (`python -m http.server`) |
| `AntigravityLauncher` / `PythonHttpLauncher` variants | `services/launchers/` | Same contract | No | — |
| `Runtime` model + `PreviewLauncher` polymorphism | `models/runtime.py`, `services/runtime_service.py`, `services/runtime_plugin.py` | `nexora.runtime` (`runtime_type {workspace,git,ide,preview,mcp,ai,deployment,docker,custom}`) dispatched to plugin | No proxy semantics | No |
| `preview_runtime` | `models/preview_runtime.py` (via `adapters/preview_adapter.py`) | Stores `preview_url` for a `runtime_id` | No | — |
| Artifact serving / deployment services | — | — | — | — | No deployment service found. `grep -R deployment` across `custom-addons/agency/nexora_studio` returns only `BuilderSession.status deploy→completed` + placeholder comments |
| Reverse proxies | — | — | — | — | No `nginx`/`Caddy`/`Traefik` config for generated apps. Only `Penpot/compose/docker-compose.yaml` exists and is unrelated. Console `vite.config.ts` proxies only `/api` + `/ws` to the Console BFF |
| Container / K8s | — | — | — | — | No `Dockerfile`/`docker-compose.yaml`/`k8s/` for generated apps |
| SSR / Next.js / Node entrypoint | — | — | — | — | Generated output is a Vite+React SPA (`package.json: type module, scripts dev/build/preview`) with no server entrypoint |
| Static hosting adapter | — | — | — | — | No adapter; `vite build` emits `dist/` (proven in 47.37 `build_a1.log`) |
| Console deployment surface | `ProjectDetail.tsx` | Hardcoded `Deployment Target: Vercel (Production)` + `Deploy` button (no handler) | — | Placeholder |
| Env vars for generated apps | `services/design/providers/react_provider.py: _generate_vite_config` | `NEXORA_CLIENT_API_URL`, `NEXORA_CLIENT_API_TOKEN` (server-only, `process.env`) | — | — |

### 5.2 Answers to the 9 deployment questions

1. **Is there a production runtime capable of server-side proxying?** No. All three launchers are dev/static servers without proxy. `ViteLauncher` dev proxy is useful, but `vite preview` (the production static server) does not run the `vite.config.js` `server.proxy` path.
2. **Who owns it?** Would be `ViteLauncher` / `PreviewLauncher` family if extended — but their contract today is process-launch + health on a local port, not production hosting.
3. **Is it already used by generated applications?** Only in development (`npm run dev`). Production (`npm run build` -> `dist/` -> `vite preview` or `python -m http.server`) is not integrated.
4. **Does it already have access to environment-scoped secrets?** The 47.36 E2E harness injects `NEXORA_CLIENT_API_TOKEN` into the vite process env at spawn; `ClientEnvironmentService` stores only the SHA-256 hash. No production secret-distribution mechanism exists.
5. **Can it preserve same-origin `/api/v1/client/*`?** In dev yes (vite `server.proxy`). In prod no — `dist/` served statically has no proxy; would need a server component.
6. **Can it inject `NEXORA_CLIENT_API_TOKEN` server-side?** In dev yes (launcher env). In prod no server exists to do so.
7. **Can it route to the canonical BFF without exposing BFF internals?** Yes in principle — BFF is a single FastAPI at `http://127.0.0.1:8000` (dev). Prod would need a target URL (`NEXORA_CLIENT_API_URL`) per environment, which the dev proxy already parameterizes.
8. **Does production need a new narrow adapter or is an existing owner sufficient?** A narrow production adapter IS needed — but it belongs to a deployment phase, not to Console UI. Options: (a) Vite `preview` subclass that adds a tiny Node proxy (e.g. `vite preview --proxy` shim), (b) a platform-managed reverse proxy (nginx/Caddy sidecar), (c) an SSR/Next.js server if that strategy is chosen. Any of these is a new runtime concern.
9. **If no production runtime exists, is this a separate deployment phase rather than Console work?** Yes — the required change is a runtime/deployment decision (hosting + proxy + secret injection), not a Console component. Console can own the *status* of that runtime once it exists, but not the runtime itself without an ADR.

**IMPORTANT outcome:** Do not implement a production runtime during this audit — done. No code changed.

---

## 6. Audit Objective D — Console ↔ Backend Boundary

Verified canonical path remains:

```
Console (React, /api/v1 via vite proxy) 
  -> FastAPI BFF (main.py: router + public_router + client_router + ws_router)
  -> adapters/odoo_client.py:OdooClient (single JSON-RPC transport, session_id cookie)
  -> Odoo (nexora.* services/models)
  -> existing Nexora services/models (builder_session_service, client_environment_service, runtime_service, etc.)
```

- No Console direct `xmlrpc/2/common` — only `api/routes.py:login` uses `xmlrpc.client` for the `authenticate(username,password)` side-effect to mint a JWT; all data paths go through `get_odoo_client()`.
- No second BFF: `main.py:app = FastAPI(...)` is the single instance; `api/client_routes.py:client_router` is mounted **within** it on `/api/v1/client`, not a separate service.
- No new API gateway: Console `vite.config.ts` proxies `/api` and `/ws` only to the BFF; generated-app `vite.config.js` proxies `/api/v1/client` only to the BFF with the client bearer.
- No client DB credentials in Console: `adapters/*` never touches `nexora.client_environment.encrypted_admin_password` or `client_api_token_hash`; Console holds only the JWT in `localStorage`.
- No client bearer in Console: `src/api/client.ts` sets `Authorization: Bearer <JWT>` (from `nexora_token`), not `nex_cli_*`; `api/client_routes.py:client_bearer = HTTPBearer(auto_error=False)` is isolated to `/api/v1/client`.

**Verdict: Boundary intact. Console remains an agency-only client of the BFF.**

---

## 7. Audit Objective E — Existing Realtime Architecture

**WebSocket remediation (47.35.x) as found**

- `api/ws.py:ConnectionManager` — `active_connections: Set[WebSocket]` only holds **registered** sockets. `connect()` does `accept()` but deliberately does NOT register.
- `_authenticate_console_socket(ws)` — `await asyncio.wait_for(ws.receive_text(), 10s)`, parse JSON, require `{"type":"AUTH","token":str}`, then `await loop.run_in_executor(None, decode_token, token)`. Any failure (timeout, JSON error, missing AUTH, bad JWT, client token) returns `False`; caller closes with `4401 Unauthorized` before any event is sent.
- `decode_token` is the same function used by `get_current_user` — single credential class (Console JWT). `nex_cli_*` tokens are not JWTs and are structurally rejected.
- After registration, `broadcast_system_health()` (every 15s if any connections), plus `SESSIONS_UPDATE`, `AI_OPS`, etc., are broadcast only to `active_connections`.

**Can provisioning/environment status reuse this channel?**

- Yes in principle. The channel is a generic `manager.broadcast({"type": str, "payload": dict})` — adding a new type such as `ENVIRONMENTS_UPDATE` or `PROVISIONING_UPDATE` would reuse the same auth and connection manager with no new bus or WebSocket.
- Today no such type is emitted. `BuilderSessionService._emit_event` writes `nexora.runtime_event` rows; `GET /sessions/{id}/events` polls them (limit 500). Pipeline subscribers (`PipelineEventBus` -> `ProgressSubscriber`, etc.) write `runtime_event` entries; no subscriber writes a client-environment event.
- **Minimum missing contract (deferred):** Either (a) have `ClientEnvironmentService` emit `runtime_event`s on state transitions (e.g. `client_environment.provisioning_started/completed/failed`, `client_environment.module_provisioning_update`) tied to the owning `project_id` or `builder_session_id` (requires a policy for which session to attribute), or (b) expose a pollable endpoint and let Console `refetchInterval` cover it (simpler, matches `useSessions({refetchInterval:30000})` pattern). Both reuse the existing authenticated channel; (b) requires no WS change at all.

---

## 8. Audit Objective F — Duplicate / Dead Architecture Audit

| Candidate | Location | Callers | Live / Dead | Canonical owner | Recommendation |
|---|---|---|---|---|---|
| Second BFF | — | — | None found | `nexora-console/backend/main.py` | No action |
| Second `OdooClient` | — | — | None found (`grep class OdooClient` -> 1 hit + `get_odoo_client` singleton) | `adapters/odoo_client.py` | No action |
| Second client API client | — | — | `src/lib/clientApi.js` is generated per project; Console has no client API client at all | `services/design/providers/react_provider.py:_generate_client_api_js` (generated side) | No action |
| Second client DB resolver | — | — | None — only `_resolve_client_token` + `_client_api_prelude` | `services/client_environment_service.py` | No action |
| Second provisioning owner | `controllers/client_provisioning_api.py` vs `services/client_environment_service.py` | Controller `create_database/install_modules/delete_database` previously called `odoo.service.db.exp_*` directly — now delegates to `ClientEnvironmentService` (`create_environment/action_provision`, `provision_modules`, `action_delete`) with `_is_agency_database` guard | **Migrated**: controller is now a thin HTTP wrapper over the canonical service; direct `exp_drop` fallback removed (47.34.x) | `services/client_environment_service.py` | Keep controller as thin wrapper; if Console needs agency provisioning UI, route through the same service — no new owner |
| Second module mapper | — | — | None — `grep capability.*module` hits only `capability_policy.py` -> `module_policy.py` chain | `services/design/module_policy.py` | No action |
| Second project capability model | `GenerationContext.requirements.{capabilities,backend_required}` vs hypothetical persisted project field | `RequirementEngine` (inference) -> `GenerationContext` (transient) is the only writer; `nexora.project` has no capabilities column; `nexora.builder_session` has no capabilities column | Transient vs persisted gap (see §3) is the only duplication risk — currently no duplication, just missing projection | `services/design/capability_policy.py` | In 47.38, project the transient decision to Console via a derived read (no new model needed unless persistence is required for history — defer) |
| Second deployment runtime | `services/launchers/{vite,static_file,python_http,antigravity}_launcher.py` | All inherit `nexora.preview_launcher`, dispatched by `runtime_service` based on `detect_project()` priority | Vite is canonical for generated apps; static/python are fallbacks for static workspaces | `services/launchers/vite_launcher.py` | No second runtime to remove; production case needs a new narrow adapter (see §5), not a duplicate to delete |
| Duplicate environment stores | `nexora.client_environment` vs hypothetical `nexora.project_environment` | No second store exists | — | `models/client_environment.py` | No action |
| Dead `execution_engine_service` | `services/execution_engine_service.py` (`nexora.execution_engine_service`) | `grep` across `nexora-console/backend` -> 0 callers; `adapters/execution_adapter.py` used to call it, now comments: "The previous target (nexora.execution_engine_service) had ..." and calls `nexora.builder_session` `action_*` methods | **Dead path** — superseded by `BuilderSessionService.run_generation -> GenerationCoordinator -> WebsiteGenerationPipeline` (Phase 47.33-47.37). Still importable but not on any live Console path | `services/builder_session_service.py` + `services/generation/*` | **Do not delete in this audit** (per rules). Flag for removal / archival in a follow-up after confirming no Odoo cron/UI action still references it (verified: no BFF adapter calls it). Safe to annotate as deprecated today |
| Old Console/Odoo direct API paths | `api/routes.py:login` XML-RPC `common.authenticate` | Login only | Intentional narrow exception for JWT bootstrap; all other data via `OdooClient` | `security/auth.py + OdooClient` | No duplication — keep as is |
| Duplicate auth paths | `security/auth.py:bearer_scheme` (Console JWT) vs `api/client_routes.py:client_bearer` (client token) | Mounted on disjoint router prefixes (`/api/v1` vs `/api/v1/client`) | Live, separate, intentionally disjoint — Console JWT cannot auth client routes and vice versa | Both are canonical for their class | No action |

**Nothing is deleted in this phase (per audit rules).** Duplicates are absent; the one dead path (`execution_engine_service`) is correctly orphaned and should be formally deprecated, not revived.

---

## 9. Audit Objective G — Proposed 47.38 Console Surfaces (minimum, not yet implemented)

All surfaces are read-only projections over existing owners plus thin lifecycle actions that already exist on `ClientEnvironmentService`. No new storage, no new credential handling, no `nex_cli_*` in the browser.

| # | Conceptual surface | Existing owner | Existing data source | Existing BFF API | Missing contract | Console location (proposed) | Implementation required? |
|---|---|---|---|---|---|---|---|
| 1 | **Project backend status** (`backend_required` + `capabilities` summary) | `services/design/capability_policy.py` + `services/generation/engines/requirement_engine.py` | `GenerationContext.requirements.{capabilities,backend_required}` (transient) and `ClientEnvironment.module_plan.capabilities` (persisted per env) | None — no project-level capabilities endpoint | Derived read: `GET /projects/{id}/capabilities` or extend `GET /projects/{id}` to include `backendRequired` + `capabilities` computed from the latest `client_environment.module_plan` or last generation artifact if available. If no env exists, return `{backendRequired:false,capabilities:[],resolved:false}`. No new model unless history is needed | `Projects.tsx:ProjectCard` badge + `ProjectDetail.tsx` Overview tab "Backend" card | Yes — narrow |
| 2 | **Client environment status** (identity, lifecycle `status`, error) | `models/client_environment.py` + `services/client_environment_service.py` | `nexora.client_environment` rows (FK `project_id`) | None — no `client_environment` adapter/route in `adapters/` | `GET /projects/{id}/environments` (list) + `GET /client-environments/{id}` (detail). Fields: `id, name, status, errorMessage, createdAt, projectId`. **Never** return `db_name` raw to non-operator roles, never `encrypted_admin_password`, never tokens/hashes | `ProjectDetail.tsx` new `Environments` card/section (or dedicated tab) | Yes |
| 3 | **Capability summary** (human-readable) | `services/design/capability_policy.py:CAPABILITY_VOCABULARY` | Same as #1 (`capabilities` array) mapped to vocabulary descriptions | Same as #1 | Same endpoint as #1 includes `capabilityLabels: [{id,label,description}]` derived from `CAPABILITY_VOCABULARY` | Same card as #1 | Yes (same call) |
| 4 | **Module provisioning status** (plan, installed/skipped, error) | `services/design/module_policy.py` + `services/client_environment_service.py:provision_modules` | `module_provisioning_state`, `module_plan`, `module_provisioning_result`, `module_provisioning_error` | None | Included in #2 detail: `moduleProvisioning: {state, plan, result, error}` where `plan/result` are JSON-parsed safe projections (module names only, no server paths) | Environments detail expand / provisioning tab | Yes |
| 5 | **Client API status** (available / unavailable / reason) | `services/client_environment_service.py:{status, client_api_token_active, client_api_token_expires_at}` | `status==ready` + `client_api_token_active==True` + `expires_at` after now => `available:true`; token itself never returned | `GET /api/v1/client/health` is client-credential only — not usable for Console | Projection on #2: `clientApi: {available: boolean, reason: string}` computed server-side from the three fields above; maps to `CLIENT_AUTH_*`/`CLIENT_ENV_*` style reasons without exposing codes to the browser beyond display strings | Same environments card (status chip) | Yes |
| 6 | **Runtime/deployment status** | `models/runtime.py` + `models/preview_runtime.py` | `GET /sessions/{id}/preview` already returns `previewUrl/status/health`; generation status via `GET /sessions/{id}` (`status`, `runtimeState`, `runtimeHealth`, `progressPercent`) | `GET /sessions/{id}/preview`, `GET /sessions/{id}/events` | No new contract for preview. For generated-app deployment (production), status would be a new `deployment` runtime type once that runtime exists — **defer** (see §10) | `ProjectDetail: Generation` tab already shows `GenerationMonitor`; environments card can show preview link when available | No (reuse existing) for preview; defer deployment |
| 7 | **Safe lifecycle actions** (provision, retry, delete, revoke/rotate token via operator) | `models/client_environment.py: action_provision/action_delete/action_provision_modules/action_issue/revoke_client_api_token` delegating to `services/client_environment_service.py` | Existing model methods | `controllers/client_provisioning_api.py` has agency `POST/DELETE /api/v1/provisioning/databases/**` (admin `base.group_system` gated) but BFF has no Console-facing wrapper | Thin BFF `POST /client-environments/{id}/provision`, `POST .../provision-modules`, `DELETE ...`, plus optional operator-only `POST .../issue-token` (returns token once, shown to operator — never stored in Console/browser). All gated to authenticated Console users; token issuance additionally requires `base.group_system` if exposed | Action buttons in environments detail (with confirm + error display) | Yes — narrow, gated |
| 8 | **Failure/error presentation** | Same as 2/4/5 | `status==failed`, `module_provisioning_state==failed`, `error_message`, `module_provisioning_error`, client API `reason` | Error payloads already sanitized (`CLIENT_ERROR_STATUS` map) on client side; Console errors come from `error_message` fields | No new contract — formatter maps states to chips/messages (`StatusChip` precedent) | Inline in environments / provisioning cards | Yes (formatter) |
| 9 | **Generated-project integration status** (is the workspace's `src/lib/clientApi.js` + proxy in sync with the environment's capabilities?) | `services/generation/*` (generation completeness) + `services/design/providers/react_provider.py` (binding) | `GenerationContext.state==COMPLETED` + `artifact.design` can be inferred from `BuilderSession.status==completed` and workspace file existence (`GET /sessions/{id}/files`) | `GET /sessions/{id}/files` + `GET /sessions/{id}/files/content?path=...` exist | No new contract for a first pass: compare `capabilities` vs workspace `src/lib/clientApi.js` existence (indirect). A dedicated `GET /sessions/{id}/capability-binding` check can be added later if drift detection is required — defer | Environments card footer / workspace header | Defer — use existing file-tree check if needed |

**Non-goals (not implemented):** client portal UI, client user accounts, billing, payments/orders/inventory/bookings APIs, generic CRUD/RPC, public token distribution, OAuth, rate-limit/observability infrastructure.

---

## 10. Audit Objective H — Production Runtime Decision

### Explicit Decision: OPTION D — Defer production runtime to a dedicated deployment phase

**Chosen: D** (with a note that OPTION B could be misread as applicable — it is not, for the reasons below).

| Option | Description | Applicable? | Why |
|---|---|---|---|
| **A — existing runtime can own production proxy** | `ViteLauncher` already does this for prod | No | `ViteLauncher` proxy lives in the **generated** `vite.config.js` `server.proxy` (dev-server only). `vite preview` and `python -m http.server` / static file servers do not execute that proxy. No existing runtime is production-capable with proxy + secrets. |
| **B — existing BFF/deployment infra can be extended narrowly** | Add a small proxy endpoint to the existing BFF so prod `dist/` can be served through it | Tempting but **out of scope for a Console UI phase** | The Console BFF (`nexora-console/backend`) is a Console-only service today. Turning it into a multi-tenant generated-app host (routing `/client/{envId}/api/v1/client/*` or per-env origins, serving each `dist/`, injecting per-env tokens) is a new deployment concern (routing, hosting density, per-env secret scope, static asset origin) that requires an ADR and is not a Console component. A narrow BFF addition without that design would violate the `DO NOT invent a generic reverse proxy` rule. |
| **C — new deployment/runtime architecture is genuinely required** | True that new infra is required, but declaring C alone would suggest 47.38 must build it | Type-C is descriptively true, but prescriptively the safe action is to **stop implementation planning for that part** and defer to its own phase (i.e., D) rather than design a runtime inside a Console-surface audit. |
| **D — production runtime should be deferred to a dedicated deployment phase** | **SELECTED** | Document the gap, preserve the token boundary, and implement Console visibility now | Matches 47.37's own handoff ("production deployment is not yet defined: document the gap. Do NOT invent a deployment platform in 47.37."). 47.38A reaffirms the gap with evidence. The deployment phase will ADR one of: (a) platform-managed reverse proxy (nginx/Caddy/Traefik sidecar per env), (b) Node SSR/edge function host, or (c) Vite `preview`-subclass Node server with proxy. Each must satisfy the 7 proxy questions in §5.2. |

**If C had been selected, 47.38 would have been required to STOP** rather than invent architecture — D is the safe articulation of that stop. No code is written, no generic proxy is added, no `nex_cli_*` is exposed.

**What the deployment phase must answer (handoff):**

- Which runtime serves `dist/` for generated apps (per-env origin or shared host with per-env routing)?
- How does it obtain `NEXORA_CLIENT_API_TOKEN` per environment without exposing it to the browser (secret store vs BFF delegation vs sidecar injection)?
- How does it preserve same-origin `/api/v1/client/*` (so `src/lib/clientApi.js` remains unchanged)?
- How does it route to the canonical BFF (`NEXORA_CLIENT_API_URL`) without exposing BFF internals?
- What is the lifecycle (create on `client_environment.status==ready`, teardown on `action_delete`)?

---

## 11. Security Invariants (reaffirmed)

All remain true; none is weakened by surfacing environment facts:

- `nex_cli_*` never enters browser JS — generated `vite.config.js` reads `process.env.NEXORA_CLIENT_API_TOKEN` in Node, not `import.meta.env`; `_generate_client_api_js` asserts no `nex_cli_/Bearer/Authorization/localStorage/VITE_/process.env` in emitted `clientApi.js` (test `TestClientApiModule`).
- `nex_cli_*` never appears in `dist/` — `verify_phase47_36.py` scans every file under `gen_*/dist` for `nex_cli_` (0 hits).
- No Odoo credentials (`ODOO_PASSWORD`, etc.), no service credentials, no `fernet` in generated output — same scan.
- No `db_name` selector from the client — client routes accept only `Authorization: Bearer <token>`; `_resolve_client_token` -> `_client_api_prelude` derives `db_name` from the matched `nexora.client_environment`.
- No `environment_id` / `model` / `method` / `SQL` / generic RPC / arbitrary module installation in `api/client_routes.py` or `clientApi.js` — verified (field-whitelist validators on `LeadInput` / `client_api_create_lead`).
- No agency DB targeting — every privileged op calls `_is_agency_database(db_name)` fail-closed (`raise ValidationError` on non-string/empty/ambiguous, membership test on `set(odoo.tools.config['db_name'] list + cr.dbname)`).
- Tenant identity remains server-derived — token hash lookup, single active token per env.
- Console JWT (`security/auth.py:decode_token`, HS256 `JWT_SECRET`) and client bearer (`api/client_routes.py:client_bearer`) remain disjoint (different `HTTPBearer` instances, disjoint router prefixes).
- All client DB lifecycle (`exp_create_database`/`exp_drop`) and module installation (`Registry.new`) remain under `ClientEnvironmentService` with the same guards.
- No second BFF, no second `OdooClient`, no `exec_kw` wildcard.

Surfacing `nexora.client_environment` to Console as `{id,name,status,moduleProvisioningState,clientApiAvailable}` does **not** require exposing `db_name`, `encrypted_admin_password`, `client_api_token_hash`, or the plaintext token. The BFF adapter will project only safe fields.

---

## 12. Validation Performed

| Check | Result |
|---|---|
| Direct source read of Console `src/{App,constants/{routes,queryKeys},api/client,features/{projects,sessions,workspace},repositories/{project,session},types/{project,session},layouts,components,providers,stores}` | Structure, routing, query keys, auth flow confirmed |
| Direct source read of BFF `backend/{main,api/{routes,client_routes,ws},adapters/*,security/auth,config/settings}` | Single BFF, single transport, disjoint auth, 4 client routes, WS JWT in-band auth confirmed |
| Direct source read of Odoo `models/{project_management,client_environment,builder_session,builder_configuration,runtime,runtime_event_constants}`, `services/{client_environment_service,design/{capability_policy,module_policy},generation/{core/*,engines/*,pipeline/*},launchers/*}`, `controllers/client_provisioning_api.py` | Ownership, field sets, safety guards, provisioning path, capability chain confirmed |
| Grep `nexora.client_environment` across `nexora-console/backend/adapters` | 0 hits — no existing Console surface over client environments |
| Grep `nginx|Caddy|Traefik|docker-compose|Dockerfile|SSR|Next.js|vercel|netlify` across repo (excl. Penpot compose) | No production runtime for generated apps |
| Grep `class OdooClient|class FastAPI|HTTPBearer|_resolve_client_token` | Single instances |
| Read `services/launchers/{vite,static_file,python_http}_launcher.py` | All dev/static only, no proxy, no secret handling |
| Read `services/execution_engine_service.py` + `adapters/execution_adapter.py` | Dead path vs canonical `BuilderSessionService.run_generation` confirmed |
| No source modifications during audit | Verified (`git status`-equivalent: only this report added) |

No large test suite was run indiscriminately (per instructions). The audit is a read-only ownership classification; functional regressions remain those proven in 47.37 (381 checks, 0 failures).

---

## 13. Files Examined (representative)

`nexora-console/src/App.tsx`, `src/constants/routes.ts`, `src/constants/queryKeys.ts`, `src/api/client.ts`, `src/features/projects/{Projects,ProjectDetail}.{tsx}`, `src/features/sessions/Sessions.tsx`, `src/features/workspace/{MissionControlView,WorkspaceView}.tsx`, `src/repositories/{project,session}Repository.ts`, `src/hooks/queries/{useProjects,useSessions}.ts`, `src/types/{project,session}.ts`
`nexora-console/backend/main.py`, `backend/api/{routes,client_routes,ws}.py`, `backend/adapters/{odoo_client,project_adapter,session_adapter,preview_adapter,builder_configuration_adapter,execution_adapter,workspace_file_adapter,git_adapter,assistant_adapter,planner_adapter}.py`, `backend/security/auth.py`, `backend/config/settings.py`, `vite.config.ts`
`custom-addons/agency/nexora_studio/models/{project_management,client_environment,builder_session,builder_configuration,runtime,runtime_event_constants}.py`, `services/client_environment_service.py`, `services/design/{capability_policy,module_policy}.py`, `services/generation/{core/{generation_coordinator,generation_runtime,generation_context},engines/{requirement,design_orchestration,code_generation}_engine,pipeline/website_generation_pipeline}.py`, `services/launchers/{vite,static_file,python_http}_launcher.py`, `services/launchers/__init__.py`, `services/{builder_session_service,runtime_service,runtime_plugin,execution_engine_service}.py`, `controllers/client_provisioning_api.py`

---

## 14. Remaining Gaps and 47.38 Implementation Boundary

**Gaps (non-blocking for Console surfaces):**

1. Persistence of `capabilities`/`backend_required` on `nexora.project` or `nexora.builder_session` for historical audit — currently transient (artifact only). Console can derive the current view from `client_environment.module_plan.capabilities`; history requires a follow-up if desired.
2. Attribution of `client_environment` to a `builder_session` — `client_environment.project_id` exists but no `builder_session_id`; WS/provisioning attribution policy is open.
3. Production deployment for generated apps — deferred to dedicated phase (see §10).

**47.38 boundary (next phase):**

- Implement the minimum Console surfaces in §9 rows 1-8 (safe, gated, read-only + existing-action buttons). Each surface reuses the owners identified here.
- Do not invent the production runtime in 47.38; defer to `PHASE 47.39 — GENERATED-APP PRODUCTION RUNTIME` (or the repo's next deployment-track phase) with an ADR selecting the runtime and its secret/same-origin strategy.
- Keep `services/design/*`, `services/generation/*`, `security/auth.py`, `api/client_routes.py`, `services/client_environment_service.py`, `services/launchers/*` frozen except for the narrow BFF adapter/route addition.

---

## 15. Final Architecture Invariants (47.38A reaffirmation)

- One canonical BFF (`nexora-console/backend/main.py`), one Client API (`/api/v1/client`), one auth architecture (JWT vs client bearer — two classes on one boundary).
- One `ClientEnvironmentService`, one DB safety owner (`_is_agency_database`), one module provisioning owner (`module_policy + ClientEnvironmentService`), one frontend binding owner (`DesignOrchestrationEngine + ReactRenderingProvider`), one dev runtime owner (`ViteLauncher`).
- No duplicate orchestration, no generic Odoo RPC, no arbitrary DB/model/method/SQL, no agency targeting, no public `nex_cli_*`, no Odoo credentials in browser, no connector/provider/Graphify/generation/Console redesign, no new LLM calls.
- Fail-closed on ambiguous DB identity; disposable lifecycle only via `ClientEnvironmentService.action_delete`.
- Console is an agency-only observer of `nexora.client_environment` (hashed/token-free projection) and never holds client bearer credentials.

---

*Report produced by Phase 47.38A ownership audit. No source modified. Next: Phase 47.38 Console Surfaces (narrow BFF adapter + read-only views + gated lifecycle actions). Production runtime is a separate deployment-phase concern.*
