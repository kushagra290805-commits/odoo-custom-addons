# PHASE 47.30 — HEADLESS API & CLIENT BACKEND BOUNDARY AUDIT REPORT

Date: 2026-09-06
Phase: 47.30 (AUDIT ONLY — no production code, schema, config, provider,
connector, generated-workspace, or frontend changes were made)

Classification legend:
✅ IMPLEMENTED + USED | 🟡 IMPLEMENTED + PARTIALLY USED | 🟠 IMPLEMENTED BUT
UNREACHABLE | 🔴 STUB / MISSING | ⚠️ DUPLICATE / OWNERSHIP CONFLICT |
⚪ DEFERRED

---

## 1. Executive Summary

Nexora today is a **frontend-generation system with an agency-only Odoo
backend**. The end-to-end path
`Requirement → AI content analysis → custom frontend generation →
deterministic validation` is real, exercised by fresh E2E runs (47.28/47.29),
and frozen under canonical ownership (ADR-0074/0078/0081).

The client-backend direction has **conceptual anchors already present** —
a client-provisioning controller with a REAL database-create primitive, a
template-store with backend-template and capability registries, a Fernet
secret store, and an accepted ADR declaring "one database per client" —
but the chain from `backend-required decision` through `module install`,
`client API`, and `frontend ↔ backend binding` is **stubs or absent**.

Two parallel `/api/v1` API surfaces exist (Odoo HTTP controllers and a
FastAPI BFF in `nexora-console/backend`), and the Console's Vite proxy
targets **Odoo directly (:8069)** while several Console features call
endpoints that only exist in the **not-currently-running FastAPI BFF** —
an ownership conflict that must be resolved before any client-backend work.

The single most important architectural conclusion: **the target direction
should be built on the Odoo-controller boundary + BuilderSessionService
orchestration + artifact-metadata injection precedent, not on a new
gateway, not inside the frozen pipeline, and not as a second capability
registry** — the existing `nexora.capability_registry` is a tool/MCP
registry and must not be repurposed; the ADR-0030-style *project*
capability model does not exist yet and is the genuine gap.

---

## 2. Current Architecture Diagram (verified from code)

```
┌──────────────────────────┐        ┌──────────────────────────────┐
│  Nexora Console (React)  │        │ FastAPI BFF                  │
│  nexora-console/src      │        │ nexora-console/backend       │
│  axios → /api/v1         │        │ 53 routes + /ws (JWT)        │
│  vite proxy → :8069 ─────┼───┐    │ JSON-RPC → Odoo              │
└──────────────────────────┘   │    │ NOT RUNNING (evidence:       │
                               │    │ :8000 = Docker backend)      │
                               ▼    └──────────────────────────────┘
                     ┌─────────────────────┐
                     │ Agency Odoo :8069  │  dbfilter=^nexora_studio$
                     │ nexora_studio      │
                     │ 18 controllers,    │
                     │ ~73 /api/v1 routes │
                     │ SSE /nexora/stream│
                     └─────────┬──────────┘
                               │ BuilderSessionService.run_generation
                               ▼
        GenerationCoordinator → GenerationRuntime → WebsiteGenerationPipeline
        → 19 engines → managed workspace (React/Vite) → build/preview/
        browser/mobile validation (ValidationEngine) → final acceptance
                               │
                               ▼
                    Generated frontend = STATIC SPA
                    (no fetch, no API client, no env config)
```

There is **no second database tier** today: `Agency Odoo DB only`.

---

## 3. Actual Runtime Path (proven)

- Console request path (live): `nexora-console/src/api/client.ts` →
  `baseURL '/api/v1'` → `vite.config.ts` proxy → `http://127.0.0.1:8069`
  → Odoo controllers (`nexora_studio/controllers/*`).
- Generation path (live): `BuilderSessionService.run_generation`
  (`services/builder_session_service.py:517`) → `GenerationCoordinator`
  (`services/generation/core/generation_coordinator.py`) →
  `WebsiteGenerationPipeline` → engines → `WorkspaceAdapter` writes →
  `PreviewEngine`/`ValidationEngine` (preview + browser + mobile + final
  acceptance). Verified by 47.28/47.29 E2E matrices.
- FastAPI BFF path: `nexora-console/backend/main.py` →
  `adapters/odoo_client.py` (JSON-RPC with a long-lived Odoo session) —
  **not deployed/not running**; no service definition found; port 8000 is
  occupied by Docker Desktop backend (netstat + process query).

---

## 4. Headless API Audit (Audit A)

### Surface 1 — Odoo HTTP controllers (CANONICAL, live)
- Owner files: `custom-addons/agency/nexora_studio/controllers/*.py`
  (auth_controller, ai_api, ai_analytics_api, audit_controller,
  builder_session_api, client_provisioning_api, project_api, provider_api,
  runtime_api, session_controller, spatial, streaming_controller,
  user_controller, workspace_api).
- Auth: Odoo sessions (`auth='user'`), group checks
  (`agency.group_agency_admin`, `base.group_system`).
  `auth_controller.py` + `services/auth_service.py` (login/logout/lockout/
  audit log, `nexora.auth.session` tracking) ✅ IMPLEMENTED + USED.
- SSE: `streaming_controller.py` (`/nexora/stream/<generation_id>`)
  wired to the pipeline event bus (47.29 added bounded composition
  metadata to EngineCompleted events) ✅.
- Limitations: response-shape inconsistency (some `type='json'`, some
  `type='http'`), no OpenAPI, no API-key auth, per-controller ad-hoc
  group checks; CSRF disabled per-route.

### Surface 2 — FastAPI BFF (`nexora-console/backend`) ⚠️ DUPLICATE / PARTIALLY UNUSED
- `backend/main.py` (FastAPI, CORS, /health, OpenAPI at /api/docs),
  `backend/api/routes.py` (53 routes), `backend/api/ws.py` (WS manager),
  `backend/security/auth.py` (JWT; login delegates password verification to
  Odoo XML-RPC), 13 adapters over `adapters/odoo_client.py`.
- Status: 🟠 code-complete but NOT the Console's live path (Vite proxy
  bypasses it) and NOT running. Several Console repositories call
  BFF-only endpoints (see §11 for the mismatch matrix).
- Dangerous defaults found (flagged, not changed):
  `config/settings.py` — default `JWT_SECRET="nexora-super-secret-jwt-2026"`,
  hardcoded Odoo login/password in source; `main.py` CORS
  `allow_origins + ["*"]` together with `allow_credentials=True`.

### Surface 3 — Odoo native JSON-RPC (`/web/dataset/call_kw`, `/xmlrpc/2/common`)
- Used by the BFF and by external scripts. Not used by the Console.

### Template-store API (shared addon)
- `custom-addons/shared/template_store/controllers/template_api.py` —
  template catalog/recommend/resolve/instantiate + generator jobs
  (`/api/v1/generator/job/*`). ✅ IMPLEMENTED, 🟡 PARTIALLY USED
  (used by template tooling/legacy orchestrator; not used by the 47.x
  pipeline).

**Canonical API boundary: the Odoo controllers.** ADR-0025's "API-first"
decision was implemented on the Odoo side; the FastAPI BFF is a second,
parallel interpretation of the same boundary ⚠️.

---

## 5. Client Database Isolation Audit (Audit B)

- **Topology today: Agency Odoo DB only.** `configs/dev.conf`:
  `dbfilter = ^nexora_studio$`, `db_name = nexora_studio`. No client DB
  records, no cross-DB code, no `Registry.new(<client_db>)` anywhere in
  production paths.
- Provisioning endpoint:
  `controllers/client_provisioning_api.py` (auth: `base.group_system`):
  - `create_database` ✅ REAL — calls `odoo.service.db.exp_create_database`
    (synchronous, blocks HTTP; `list_db` must be enabled for such flows).
  - `delete_database` ✅ REAL — `odoo.service.db.exp_drop` (⚠️ destructive,
    no confirmation/allowlist).
  - `install_modules`, `init_template_store`, `create_admin`, `backup`,
    `restore` 🔴 STUBS — service calls commented out; they return fake
    success messages (`'Modules ... scheduled for installation'`).
- The referenced `nexora.client_provisioning_service` **does not exist**
  (no model/service file; grep only finds the commented references).
- Client DB lifecycle is NOT represented in Odoo metadata: no model for
  client environments, no credentials record, no link from
  `nexora.builder_session`/`nexora.project` to any client DB.
- Secrets today: MCP credentials are Fernet-encrypted
  (`services/connector/credentials/odoo_secrets_provider.py`,
  `models/connector/nexora_mcp_credential.py`, master key from
  `NEXORA_CONNECTOR_SECRET_KEY` env) ✅. Provider API keys live in
  `ir.config_parameter` values (readable via Odoo RPC by config
  administrators) ⚠️ acceptable for agency-internal but NOT a pattern to
  extend to client credentials.
- Dangerous assumption flagged: `admin_password` defaults to `'admin'`
  in the create-database controller.

---

## 6. Odoo Provisioning Audit (Audit C)

- There is **no provisioning plan** concept: no model, no engine, no
  service that decides what a client DB should contain.
- `nexora.template_backend` (shared template_store) has framework
  entries including `odoo` (`code='odoo_module'`) and `fastapi_service` —
  a template catalog concept for backend scaffolds 🟡 (registry rows
  exist: 2 backend templates; not consumed by the 47.x generation path).
- The 47.x pipeline never touches Odoo installation APIs; generation
  output is a frontend workspace only.

## 7. Module Installation Audit (Audit C cont.)

- **No real module installation exists.** Grep for `install_module(s)`
  across the addon returns only the stub controller method.
- `odoo.service.db.exp_create_database` installs only `base`; there is
  no follow-on `upgrade_modules`/registry-switch/install anywhere.
- No module allowlist, no capability→module mapping, no dependency
  handling. 🔴 STUB / MISSING (all of it).

---

## 8. Capability / Backend-Required Audit (Audit D)

How Nexora answers "does this client require an Odoo backend?" today:
**it does not ask the question.** (grep `backend_required|requires_backend|
needs_backend` → zero matches.)

What exists:

| Component | File | What it actually is | Status |
|---|---|---|---|
| RequirementAnalyzer | `services/design/requirement_analyzer.py` | Deterministic labeled-brief parser (business/category/location/services/audience, domain keyword routing, mobile/spline/3d detection). No backend concept. | ✅ USED (RequirementEngine → pipeline) |
| Page pattern catalog | `services/design/page_patterns.py` | Deterministic domain→section-sequence composition (47.24). Frontend-only. | ✅ USED |
| `nexora.capability_registry` (model) | `models/capability_registry.py` | **Tool/MCP capability registry** (17 rows: `mcp.tool.browser`, `mcp.github`, `mcp.tavily`…). Execution-plugin metadata, NOT business/project capabilities. | ✅ for its purpose; ⚠️ must NOT be conflated with project capabilities |
| `services/capabilities/resolver.py` + selection engine, router | UCP (Universal Connector/Capability Platform) | Provider/tool routing (used by connector runtime, provider manager). | ✅ for its purpose |
| `nexora.generator_capability` (template_store) | `models/generator_capability.py` | 4 rows: variable_substitution, dual_repo_merge, env_config_generation, transactional_rollback — **generation-pipeline mechanics**, not business capabilities. | 🟡 niche |
| Console ADR-0030 "Capability-Driven Project Generation" | `nexora-console/docs/adr/ADR-0030-...` | Describes exactly the desired model: project CapabilityRegistry (features with backend/database dependencies) + Resolver + "Odoo/Backend/Database never assumed". | ⚪ **NOT IMPLEMENTED anywhere in the agency backend** |
| IntelligentCapabilityPlanner | `services/planning/planner.py` | Builds an execution plan whose "capabilities" are UCP tool namespaces (consumed by PlanningEngine for trace only; the pipeline's actual composition comes from page_patterns). | 🟡 partially used |

Distance from the desired model
(`LLM → structured capability interpretation → Nexora-owned policy →
allowlisted capability → approved Odoo module mapping`):
- LLM interpretation layer: **absent** (the single generate_content call
  produces page copy, not capability intent; RequirementAnalyzer is
  deterministic keyword extraction).
- Nexora-owned policy/allowlist: **absent**.
- Capability→module mapping: **absent**.
- The desired "LLM proposes, platform disposes" separation has a strong
  existing precedent to follow: the 47.27/47.29 ContentEngine contract
  (LLM returns structured JSON; deterministic normalization + validation;
  allowlisted fields; explicit fallback reasons). A capability decision
  should be built the same way — NOT by letting an LLM emit module names
  into any executable path.

---

## 9. Client API Audit (Audit E)

- **No client-facing API exists.** All ~73 Odoo routes are agency-internal
  (Odoo session auth, agency/system groups). No API keys, no client token
  model, no public/external endpoint set, no CORS policy for client apps.
- There is no code that, given a client DB, would expose an application
  API on it (no controller generation, no client Odoo module template
  beyond the `template_backend` catalog entry `odoo_module`).
- The BFF is an agency operator API (login = Odoo users), not a client
  application API.
- Generated frontends therefore cannot consume any backend today — see
  §10. The concepts internal-agency-API / client-app-API / developer-
  console-API are currently collapsed into one boundary (Odoo `/api/v1`
  + BFF `/api/v1`). This conflation must be resolved, not extended.

---

## 10. Generated Frontend Integration Audit (Audit F)

Verified from the generated E2E workspaces (47.29, `scratch/e2e4729/*`)
and the generators:

- Scaffold: Vite + React SPA (`react_provider._generate_package_json`,
  `_generate_vite_config`); pages from `CodeGenerationEngine`; components
  from `ReactComponentLibrary` (28 organisms).
- **No API client**: zero `fetch`/`axios`/`process.env`/
  `import.meta.env` usage in generated sources (only the Spline scene
  URL and provider scaffold internals).
- **No environment configuration** (no `.env` emission, no proxy target
  for a backend).
- `ContactForm.jsx` (`react_component_library.py:1170`) — client-state
  only: `setStatus('success')`, optional `onSubmit` prop, **no
  persistence**.
- `ProductGrid` — consumes structured items materialized from the
  ContentArtifact into JSX data arrays (ADR-0079). Data is compile-time,
  not runtime-fetched.
- No authentication flows in generated output.
- No client-backend binding metadata anywhere in the artifact
  (`generation_context.py` fields: template/design/assets/…; nothing for
  backend URL/credentials/API shape).

**Answer:** the generated frontend architecture (Vite/React, prop-driven
organisms, deterministic scaffold) is *connectable* to a client backend
without a new frontend architecture — the connection points are exactly
(i) a small generated API-client module + env file, (ii) prop/data-source
substitution for ProductGrid/ContactForm data feeding (both already
prop-driven), (iii) build-time binding metadata on the artifact. But none
of that exists yet, and per phase rules none was added.

---

## 11. Nexora Console Audit (Audit G)

- Framework: React 19 + Vite + TypeScript, react-query + zustand +
  react-router; entry `nexora-console/src/App.tsx`; routes: Dashboard,
  Projects, ProjectDetail, Templates, Sessions, Mission Control
  (workspace), Workspace, Settings, AI Operations, Login.
- API client: `src/api/client.ts` — axios, `baseURL '/api/v1'`,
  `withCredentials: true` AND a Bearer JWT from localStorage (a dual-auth
  assumption matching neither boundary cleanly).
- Features vs live backend (Odoo proxy target):

| Console call (repository/service) | Exists in Odoo controllers? | Exists in FastAPI BFF? | Verdict |
|---|---|---|---|
| `POST /auth/login` (username/password) | ✅ `auth_controller` (session) | ✅ (JWT) | dual ⚠️ (different response shapes) |
| `GET/POST /sessions` (uuid-based) | ✅ `builder_session_api` (uuid) | ✅ (id-based DTOs) | dual, different id spaces ⚠️ |
| `PATCH /sessions/{id}` | ❌ | ❌ | broken on both 🔴 |
| `POST /sessions/{id}/resume|pause|terminate` | ❌ (has start/stop/restart/recover) | ✅ | BFF-only 🔴 vs live proxy |
| `POST /sessions/{id}/execution/start` | ❌ | ✅ → `nexora.execution_engine_service.start_execution` (which itself has **no other callers**) | BFF-only + dead backend target 🔴 |
| `POST /sessions/{id}/planner/start` | ❌ | ✅ | BFF-only 🔴 |
| `POST /sessions/{id}/assistant/execute` | ❌ | ✅ | BFF-only 🔴 |
| `GET /dashboard`, `/providers`, `/ai/*` | partial (`ai_analytics_api`, `provider_api`) | ✅ | overlapping duals ⚠️ |
| WebSocket `…/ws/events` (webSocketStore) | ❌ (Odoo has SSE `/nexora/stream`) | ✅ (`api/ws.py`) | BFF-only 🔴 vs live proxy |

- Console controls today (against Odoo): login/logout, session list/
  create/ lifecycle (via builder_session_api subset), workspace files/
  git/preview status (where endpoints exist), templates catalog, provider
  inspection, AI metrics.
- Console cannot yet control: **website generation itself** (no call to
  `POST /api/v1/ai/generate` or `run_generation` exists in the Console),
  composition-manifest/evidence views (durable runtime events exist but
  no Console view), provisioning (no UI), client environments (no
  concept), module installation (no concept).
- Backend-only capabilities with NO Console path: run_generation
  (`ai_api.trigger_generation`), provisioning endpoints, provider
  test/migrate, spatial API, SSE stream.

---

## 12. Security Boundary Audit (Audit J)

Intended trust chain: Agency Operator → Console → API → Agency Odoo →
Provisioning Control Plane → Client Odoo → Client Application.

Current reality:

| Boundary | Evidence | Status |
|---|---|---|
| Operator → Console → API | Odoo session auth (`auth_service.py`, audit log, lockout) | ✅ functional |
| BFF JWT boundary | `backend/security/auth.py` + default secret in source | 🟠 exists, not deployed, weak defaults |
| Agency Odoo → Client DB | none | 🔴 absent |
| Client DB credentials storage | none | 🔴 absent (should reuse Fernet `OdooSecretsProvider` + `nexora.mcp_credential` pattern — existing owner) |
| Client app credentials (API keys for generated frontends) | none | 🔴 absent |
| Privileged-credential exposure to generated frontends | not applicable today; **flag**: never emit Odoo credentials into generated workspaces — only per-client API tokens | risk flagged |

Existing secret owners to reuse (per DO-NOT-BUILD rules): Fernet
`OdooSecretsProvider` (`NEXORA_CONNECTOR_SECRET_KEY` master key),
`nexora.mcp_credential` model, `models/credential/` interfaces
(`credentials/interfaces.py`). No new secret-management system is needed.

Dangerous assumptions flagged (not fixed): BFF default JWT secret +
hardcoded Odoo credentials; CORS `*` + credentials; provisioning default
admin password `'admin'`; `exp_drop` exposed via API without allowlist;
provider keys in `ir.config_parameter`.

---

## 13. Generation Pipeline Integration Point (Audit K)

Frozen path verified intact: `BuilderSessionService.run_generation` →
`GenerationCoordinator` → `GenerationRuntime` → `WebsiteGenerationPipeline`
→ engines (ADR-0074 canonical ownership; U96 acceptance gates; retry×2 +
rollback via `GenerationStateManager`; workspace isolation via
`WorkspaceAdapter` + `nexora.workspace`).

Where backend provisioning should integrate — evidence-based:

- Inside `WebsiteGenerationPipeline` as an engine? **No.** Evidence:
  engines are seconds-scale, retry with same-input semantics, run inside
  the agency-DB `env`, and a pipeline engine failure rolls back the
  *website artifact* — provisioning is minutes-scale, cross-DB (needs
  `Registry.new(<client_db>)` outside the request cursor), and its
  failure semantics (half-installed DB) are not artifact-rollback shaped.
  `execution_engine_service.py`'s dead `run_loop` (thread + own registry +
  cursor) demonstrates why this class of work was kept out of request/
  pipeline flows.
- The coordinator already has a **pre-pipeline injection precedent**
  (`_inject_planner_blueprint`, P0-03): read-only artifact enrichment
  before `pipeline.run`.
- The codegen already has a **binding precedent**
  (`_renderer_page_binding`: deterministic provider → import/tag from
  artifact metadata) — the exact shape a future client-API binding
  should follow.
- `RequirementEngine` runs first in the pipeline and the artifact's
  `requirements`/`generation_metadata` is the natural carrier for a
  capability decision.

**Recommendation (for the next phase, not implemented here):**
**(C) a sibling provisioning workflow** coordinated at the
`BuilderSessionService`/`GenerationCoordinator` level — started by the
same session entry point, running BEFORE frontend generation so its
outputs (client DB id, module set, client API base URL + token scope) can
be injected into the artifact as metadata (the P0-03 injection shape),
and consumed by codegen through the renderer-binding precedent. The
pipeline itself stays untouched; frontend generation remains the
existing engines; validation gains an optional client-backend phase only
when a binding exists. This preserves pipeline ownership, deterministic
validation, retry/failure handling (provisioning gets its own
retry/runtime-event semantics like preview runtimes), workspace
isolation, and client isolation (cross-DB work never enters the request
cursor).

---

## 14. Ownership Matrix (Audit H)

| Stage | Existing owner (file/class) | Real runtime path | Status | Missing dependency |
|---|---|---|---|---|
| Requirement intake | `RequirementEngine` + `services/design/requirement_analyzer.py` | pipeline 1st engine | ✅ | — |
| Requirement → capability interpretation | — | none | 🔴 | LLM structured-capability step (ContentEngine-contract style) |
| Backend-required decision | — | none | 🔴 | policy owner + allowlist |
| Capability→module mapping | — | none | 🔴 | approved mapping registry |
| Provisioning plan | — | none | 🔴 | plan model/service |
| Client DB provisioning | `controllers/client_provisioning_api.py::create_database` (`odoo.service.db.exp_create_database`) | HTTP only, sync, admin-only, no callers in console/generation | 🟡 real primitive, unused | async orchestration, lifecycle records, credentials |
| Module installation | same controller `install_modules` | none (stub) | 🔴 | registry-switch + install + allowlist |
| Backend configuration | `template_store` `template_backend` catalog (`odoo_module` row) | catalog only | 🟡 data only | instantiation + config generation |
| Client API | — | none | 🔴 | client-facing auth + routes on client DB |
| Frontend generation | `CodeGenerationEngine` (+ engines) | pipeline | ✅ | — |
| Frontend↔backend binding | — | none | 🔴 | binding metadata + generated API client/env |
| Validation | `ValidationEngine` (build/preview/browser/mobile/final) | pipeline | ✅ | optional backend-phase later |
| Console visibility | Console sessions/workspace views; runtime-event timeline; 47.29 composition summary event | live | 🟡 | generation trigger UI, provisioning UI, client-env views |

---

## 15. Existing vs Missing Capabilities

**Exists and is canonical:** agency REST boundary (Odoo controllers),
Odoo-session auth + audit, generation pipeline (frozen), content/asset/
codegen engines, deterministic validation chain, managed workspaces,
preview runtimes, runtime events + composition-manifest evidence (47.29),
Fernet secret provider, template store registries, real DB create/drop
primitives.

**Exists but partially used / unreachable:** FastAPI BFF (complete,
undeployed, duplicated surface), `nexora.execution_engine_service`
(zero callers), `GenerationOrchestrator` + template-store job pipeline
(legacy, Phase 20A-renamed context), `IntelligentCapabilityPlanner` UCP
trace, `nexora.project*` models (client/project records exist but nothing
generates from them).

**Missing entirely (the actual gap chain):** backend-required decision →
provisioning plan → client DB lifecycle model → module install (allowlist)
→ client API (auth + routes) → frontend API client/env generation →
frontend↔backend binding metadata → backend-aware validation → Console
surfaces for all of the above.

---

## 16. Dead / Legacy / Duplicate Implementations

| Item | Class | Evidence |
|---|---|---|
| FastAPI BFF vs Odoo `/api/v1` | ⚠️ duplicate boundary | vite proxy → 8069; BFF not running; overlapping routes with different id-spaces/shapes |
| `nexora.execution_engine_service.start_execution` | 🟠 unreachable | only reference is the BFF route (BFF itself unreachable); no Odoo caller |
| `services/generation_orchestrator.py` (LegacyJobContext) | legacy | explicit Phase 20A header; template-store job pipeline, not the 47.x path |
| `nexora.project_blueprint` / `ExecutionPlan` / `GenerationManifest` models | 🟡 partially used | blueprint injection works (P0-03); execution plan/manifest only via dead execution service |
| Console `PATCH /sessions`, resume/pause/terminate vs Odoo routes | 🔴 mismatch | route tables in §11 |
| `client_provisioning_api` stub methods | 🔴 stub | commented service calls |
| `nexora.capability_registry` (tool registry) | ✅ canonical *for MCP tools* | must not be conflated with project capabilities |

---

## 17. ADR Consistency Review (Audit I)

- Console **ADR-0025 (Headless API Gateway)** — REST-first on Odoo:
  implemented ✅; "One Database per Client": ⚪ deferred (only the create/
  drop primitives exist); SSE/bus abstraction: implemented
  (`streaming_controller` + pipeline event bus).
- Console **ADR-0030 (Capability-Driven Generation)** — ⚪ NOT implemented
  in the agency backend; remains valid as the target model for the
  capability layer and matches the desired LLM→policy→allowlist shape.
- Agency **ADR-0074 (Canonical Workflow Ownership)** + **ADR-0078
  (Deterministic/LLM boundary)** + **ADR-0081** — consistent with code;
  the 47.29 composition-manifest surfacing matches them.
- **ADR-0029 (unified provider platform, agency docs)** — describes the
  BFF as "Presentation & Experience Layer"; drifted: the live Console
  bypasses it.
- Agency **ADR-0042 (generation architecture constitution)** — pipeline
  ownership frozen; any provisioning work must respect §13's conclusion.

**Recommendation:** before implementation, create a NEW ADR (e.g.,
ADR-0082 "Client Backend Provisioning & API Boundary") that: (a) declares
the Odoo controllers the canonical API boundary and retires or re-scopes
the FastAPI BFF (decision required — see §20), (b) adopts ADR-0030's
capability model as a *project-capability* registry distinct from
`nexora.capability_registry` (tools), (c) fixes the sibling-workflow
integration point from §13, (d) mandates Fernet/OdooSecretsProvider reuse
for client credentials, (e) states that generated frontends receive only
per-client API tokens, never Odoo credentials. Amend ADR-0025's client-DB
section by reference rather than rewriting history.

---

## 18. Recommended Target Architecture (validated against the repo)

The proposed target diagram is directionally correct but should be
grounded on existing owners:

```
Console (React) ──► Odoo /api/v1 (canonical boundary; JWT/session per
                    existing AuthService) ──► Agency Odoo (nexora_studio)
                              │
        ┌─────────────────────┼───────────────────────────┐
        ▼                     ▼                           ▼
 Capability Decision    Generation System            Client Lifecycle
 (LLM structured        (frozen pipeline,            (sibling workflow:
  interpretation +      unchanged)                    plan → DB → modules
  Nexora policy +                                     → client API config)
  allowlist → module                                  │
  mapping; ADR-0030          │                        │
  model)                     ▼                        ▼
                    Custom Frontend ◄── binding metadata (artifact
                    (existing generators +            injection, P0-03
                     generated API client/env)         precedent)
                              │
                              ▼
                    Client API (new, on Client Odoo; API-token auth)
                              │
                              ▼
                    Full-stack validation (ValidationEngine + backend phase)
```

Validate: use the **existing orchestration boundary**
(BuilderSessionService/GenerationCoordinator) — NOT a new gateway, NOT a
new pipeline.

## 19. Recommended Implementation Sequence (evidence-based)

1. **Resolve the API-boundary conflict first** (it blocks everything
   client-facing): decide Odoo-controllers-canonical; align the Console's
   broken repositories (§11) or re-point the Vite proxy at a deployed
   BFF — but do not build a new gateway. (Why first: every later Console
   feature and any client-app pattern depends on one stable boundary.)
2. **Project-capability model + backend-required decision** (ADR-0030
   shape; LLM proposes structured capabilities via a ContentEngine-style
   contract; deterministic policy + allowlist decide). (Why next: it is
   the input to every provisioning stage; cheap, no infra.)
3. **Client DB lifecycle records + provisioning service** reusing
   `exp_create_database`/`exp_drop` behind a real service (the missing
   `nexora.client_provisioning_service` name is already referenced by the
   stubs), async with runtime events, credentials via Fernet provider.
4. **Allowlisted module installation** (registry-switch install; mapping
   from step 2; allowlist is a hard gate).
5. **Client API on the client DB** (client-facing auth — per-client API
   tokens; separate from agency auth).
6. **Frontend binding**: artifact metadata + generated API client/env +
   prop-driven data substitution in existing organisms (ContactForm/
   ProductGrid already prop-driven) + renderer-binding precedent.
7. **Backend-aware validation phase** (optional, when binding exists).
8. **Console surfaces** (generation trigger, provisioning, client envs,
   composition evidence) — last, on the resolved boundary.

## 20. Risks / Architectural Decisions Required

1. **API boundary dual** (Odoo vs FastAPI BFF) — must be decided before
   any client-backend work; both shapes are 50+ routes deep.
2. **Client-DB provisioning needs elevated Postgres rights and
   `list_db`-style database management** — deployment/security posture
   decision (ADR-0025 already flags it).
3. **Cross-DB execution semantics** — no production precedent for
   request-scoped work touching a second registry; the sibling-workflow
   pattern (own cursor + runtime events) must be designed deliberately.
4. **Cost/duration** — DB init + module install is minutes-scale; the
   Console UX needs async job semantics (runtime events exist to build
   on).
5. **Capability-registry conflation risk** — `nexora.capability_registry`
   (tools) vs ADR-0030 project capabilities; naming/ownership must be
   explicit to avoid a parallel registry (audit rule).
6. **Secret hygiene** — BFF defaults, config-parameter keys, default
   admin password must be fixed as part of (not after) provisioning work.

## 21. Explicit "DO NOT BUILD" List (for the next phase)

- A new API gateway (extend the Odoo controllers / decide the BFF).
- A second client-provisioning controller — extend
  `client_provisioning_api.py` + create the missing service behind it.
- A parallel capability registry — build the project-capability model
  alongside (clearly named), never inside `nexora.capability_registry`.
- A second DB-lifecycle manager, auth system, secret store, frontend
  scaffold, component registry, or orchestration path.
- Any new engine inside `WebsiteGenerationPipeline` for provisioning.
- Any LLM-driven direct module installation (mapping must be
  deterministic/allowlisted).

## 22. Evidence Appendix (keyed to sections)

- Console proxy/API: `nexora-console/vite.config.ts` (proxy → 8069),
  `src/api/client.ts` (baseURL /api/v1, JWT+cookie dual), `src/services/
  authService.ts`, `src/repositories/{session,execution,planner,
  assistant}Repository.ts`.
- BFF: `nexora-console/backend/main.py`, `api/routes.py` (53 routes),
  `api/ws.py`, `security/auth.py`, `config/settings.py` (default secret,
  hardcoded creds), `adapters/odoo_client.py` (JSON-RPC).
- Odoo API: `controllers/*.py` (route tables in §11),
  `services/auth_service.py`, `models/nexora_auth_session.py`,
  `controllers/streaming_controller.py` (SSE).
- Provisioning: `controllers/client_provisioning_api.py:48` (real create),
  `:64/:76/:91/:102/:113` (stubs), `:124` (real drop, default password
  `:41`).
- Capability/requirements: `services/design/requirement_analyzer.py`,
  `services/design/page_patterns.py`, `models/capability_registry.py`
  (+ DB rows), `services/capabilities/resolver.py`,
  `services/planning/{planner,orchestrator}.py`,
  `services/execution_engine_service.py` (no callers),
  `services/generation_orchestrator.py` (legacy header),
  `models/project_planner.py` (blueprint/plan/manifest models),
  `models/project_management.py` (client project records),
  shared `template_store/models/{template_backend,generator_capability,
  generation_job}.py` (+ DB rows: 2/4/9).
- Generated frontend: `services/design/react_component_library.py:1170`
  (ContactForm state-only), `react_provider.py` (package.json/vite
  emission, no env), 47.29 workspaces `scratch/e2e4729/*` (no fetch/env),
  `code_generation_engine.py` `_renderer_page_binding` (binding
  precedent), `generation_coordinator.py` `_inject_planner_blueprint`
  (injection precedent).
- Secrets: `services/connector/credentials/odoo_secrets_provider.py`
  (Fernet, `NEXORA_CONNECTOR_SECRET_KEY`),
  `models/connector/nexora_mcp_credential.py`, `ir.config_parameter`
  keys (openrouter/pexels) via DB query.
- Config/topology: `configs/dev.conf` (`dbfilter=^nexora_studio$`),
  netstat/process checks (port 8000 = Docker backend, not FastAPI).
- ADRs: console `ADR-0025`, `ADR-0030`; agency ADR-0074/0078/0081,
  ADR-0029 (BFF drift), ADR-0042.

— End of Phase 47.30 audit report. No production behavior was changed;
no DB/schema/config/provider/connector/generated-workspace/frontend
modifications were made; ADRs were reviewed but not modified.
