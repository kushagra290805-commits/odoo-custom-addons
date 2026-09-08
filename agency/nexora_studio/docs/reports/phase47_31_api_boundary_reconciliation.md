# PHASE 47.31 — FINAL API BOUNDARY RECONCILIATION REPORT

Date: 2026-09-06
Phase: 47.31 (ADR-0082)

---

## 1. Executive Summary

The dual `/api/v1` boundary (live Odoo controllers vs the undeployed
FastAPI BFF) is reconciled into **ONE canonical headless API boundary:
the FastAPI BFF** (`nexora-console/backend`), with every route delegating
to the existing canonical Odoo service owners. The Console's Vite proxy
now targets the BFF (:8000 for `/api` and `/ws`). The dead
`nexora.execution_engine_service` path was NOT resurrected — the
execution route now delegates to the canonical
`BuilderSessionService.run_generation` chain. A real-LLM E2E through the
new boundary produced a fully validated website with exactly **1 LLM
call**, proving the chain is intact end-to-end. No second gateway, no
duplicate orchestration, no Odoo controller rewrites, no schema changes.

## 2. Before Architecture (verified, Phase 47.30 + fresh evidence)

```
Console (axios /api/v1, JWT+cookie)
  → Vite proxy → Odoo :8069  ← WRONG TARGET (BFF bypassed)
  → ~40 of 62 Console calls had NO Odoo route (files/git/planner/
    assistant/execution/preview/ai-jobs/dashboard/ws)
  → auth/sessions Odoo routes used JSON-RPC envelopes (type='json')
    incompatible with the Console's plain-JSON axios client
FastAPI BFF (:8000) — complete, thin-adapter, NOT RUNNING (port owned
  by Docker); dead execution target; duplicate POST /sessions
  registration; wildcard CORS with credentials; committed secrets
```

## 3. Canonical API Decision

**B = the FastAPI BFF is canonical.** Odoo controllers remain the
internal API surface (scripts/tests/admin tooling) — unchanged, not
deprecated, not rewritten.

## 4. Why This Boundary Was Chosen (evidence)

1. **Console contract match**: the Console's implemented 62 calls —
   int-id session DTOs, JWT token store, workspace/git/planner/
   assistant/AI-operations routes — match the BFF's contracts, and ~40
   have no Odoo-controller equivalent (Console API-call inventory:
   `console_api_calls_4731.py` output vs Odoo route tables).
2. **Adapters are thin delegators** — every adapter calls an existing
   Odoo service owner (git_adapter → `nexora.git_service`,
   workspace_file_adapter → `nexora.workspace_file_service`, session
   lifecycle → `nexora.builder_session.action_*` →
   `nexora.builder_session_service`, planner → `nexora.project_planner_service`,
   assistant → `nexora.builder_assistant_service`). No business logic
   lives in the BFF.
3. **Documented intent**: Console ADR-0026/0027/0038 + Phase-11B report
   define the BFF as the Console backend; the Vite proxy drift to Odoo
   was an unrecorded regression, not a decision.
4. **JSON-envelope mismatch**: Odoo `auth`/`sessions`/`users`/`audit`
   routes are `type='json'` (JSON-RPC envelope), which the Console's
   axios client cannot consume — the BFF speaks plain JSON.

## 5. Endpoint Ownership Matrix (capability → canonical owner)

| Capability | Odoo /api/v1 | FastAPI BFF | Console caller | Actual runtime | Canonical owner |
|---|---|---|---|---|---|
| auth login/session | ✅ (json-envelope) | ✅ JWT | authService | BFF now | **BFF /auth/login** → Odoo authenticate (password source of truth stays Odoo) |
| builder sessions CRUD/lifecycle | ✅ (uuid, json-envelope mix) | ✅ (int-id DTOs) | sessionRepository/service | BFF | **BFF** → `nexora.builder_session` actions → builder_session_service |
| generation execution | `ai_api /ai/generate` (internal) | ✅ execution/start → **dead** target | PlanningWorkspace | BFF (fixed) | **BFF** → `action_run_generation` → `BuilderSessionService.run_generation` |
| planner | ❌ | ✅ → project_planner_service | PlanningWorkspace | BFF | `nexora.project_planner_service` |
| assistant | ❌ | ✅ → builder_assistant_service | AIAssistantPanel | BFF | `nexora.builder_assistant_service` |
| workspace files/git | ❌ | ✅ → git/workspace_file services | workspace/git repos | BFF | `nexora.git_service` / `nexora.workspace_file_service` |
| preview status | ❌ | ✅ (read-only) | PreviewPanel | BFF | `nexora.runtime`/`preview_runtime` (startup owner: `nexora.preview_service`, unchanged) |
| runtime events feed | ❌ (service existed, no route) | ➕ NEW thin route | useRuntimeEvents | BFF | storage: `nexora.runtime_event` (producer: pipeline, unchanged) |
| templates / dashboard / ai-jobs / providers | partial (json-envelope) | ✅ | templates/dashboard/ai hooks | BFF | **BFF** (aggregation) over Odoo models |
| SSE generation stream | ✅ `/nexora/stream/<id>` | ❌ | — (scripts/tests) | Odoo internal | **Odoo SSE** (producer: pipeline event bus) — unchanged |
| WebSocket `/ws/events` | ❌ | ✅ | webSocketStore | BFF now | **BFF WS hub** (delivery only) |
| provisioning (stubs) | ✅ (internal, admin) | ❌ | — | Odoo internal | unchanged (Phase 47.30 audit outcome; future work) |

## 6. Files Changed

**Console (consumer migration):**
- `nexora-console/vite.config.ts` — proxy `/api`+`/ws` → `127.0.0.1:8000` (BFF).

**BFF (canonical boundary hardening — existing app, no rewrite):**
- `backend/main.py` — CORS wildcard removed; routers split:
  `public_router` (login, health) unauthenticated, `router` mounted with
  `dependencies=[Depends(get_current_user)]` (JWT on ALL other routes).
- `backend/api/routes.py` — `public_router` added; login/health moved to
  it; NEW `GET /sessions/{id}/events` (thin projection over
  `nexora.runtime_event`, since_id + bounded limit); dead duplicate
  `POST /sessions` registration removed.
- `backend/adapters/execution_adapter.py` — re-pointed from the dead
  `nexora.execution_engine_service.start_execution` (zero callers) to the
  canonical `nexora.builder_session.action_run_generation` with a
  per-call 1200s timeout (full generation is minutes-scale).
- `backend/adapters/odoo_client.py` — optional per-call `timeout`
  parameter on `execute_kw`/`call` (long delegations no longer die at the
  10s default while the Odoo owner keeps running).
- `backend/config/settings.py` — no committed secrets: `JWT_SECRET`
  falls back to a random per-process key (warning logged); Odoo
  service-account credentials env-only (empty defaults + warning).

**Odoo addon (additive, owner-preserving):**
- `models/builder_session.py` — `action_run_generation()` thin record
  wrapper (exact `action_start_runtime` precedent) delegating to
  `nexora.builder_session_service.run_generation(record)`. No service
  changes, no pipeline changes, no schema changes.

**Docs/tests:**
- `docs/adr/ADR-0082-canonical-headless-api-boundary.md` (new).
- `tests/test_phase47_31_api_boundary.py` (new, 17 tests).
- `custom-addons/agency/scratch/e2e_boundary_4731.py` + evidence.

## 7. ADR-0082

Created (`docs/adr/ADR-0082-canonical-headless-api-boundary.md`): documents
the canonical boundary and why, Odoo-controller role (internal API),
BFF role (thin adapter), compatibility strategy, authentication boundary,
SSE/WS ownership (generation = producer, API = delivery),
BuilderSessionService/GenerationCoordinator relationships, the
API-boundary ≠ orchestration-boundary prohibition, Console relationship,
future client-API separation, migration invariants, and explicit
non-goals.

## 8. Authentication Boundary

- Console → BFF: the EXISTING JWT mechanism (`security/auth.py`);
  passwords verified against Odoo (`common.authenticate`) — Odoo remains
  the identity provider (ADR-0027 preserved).
- BFF → Odoo: shared service-account session (documented limitation
  from 47.30, unchanged this phase; per-user propagation = future work).
- No new auth system. No Odoo admin credentials exposed to the
  Console/frontend; BFF service-account credentials are env-only now.
- Future client-application API auth remains a SEPARATE boundary
  (per-client tokens) — explicitly out of scope.

## 9. SSE/WebSocket Boundary

- Generation remains the event PRODUCER (pipeline event bus → runtime
  events → SSE `/nexora/stream/<id>` — unchanged, Odoo-internal).
- BFF `/ws/events` = delivery-only hub (existing); new
  `GET /sessions/{id}/events` = thin read of the SAME
  `nexora.runtime_event` storage. No new event/telemetry subsystem.

## 10. Console Integration

- All 62 Console calls now resolve through one boundary (BFF). The
  previously BFF-only paths (files, git, planner, assistant, execution,
  preview, events, WS) are served; the auth mismatch (json-envelope) is
  gone. No Console UI/code changes required (client.ts unchanged).
- `PATCH /sessions/{id}` and `PATCH /projects/{id}` remain absent on
  the BFF (broken before on BOTH surfaces — unchanged; documented in
  Remaining Gaps rather than inventing semantics).

## 11-12. Generation Chain Before/After + Chain-Integrity Proof

BEFORE (broken for ~40 calls):
```
Console → Vite proxy → Odoo :8069 (json-envelope mismatch / 404s)
BFF :8000 (correct owner wiring) — unreachable
```

AFTER (proof per changed route):
| Route | Previous consumer | New route | Service owner | Orchestration owner | Duplicate path? | Required dependency reachable? |
|---|---|---|---|---|---|---|
| ALL Console calls | Console axios | same paths via BFF :8000 | each route's existing Odoo service (see matrix) | unchanged (BuilderSessionService/GenerationCoordinator/pipeline) | NO (one boundary) | YES (E2E) |
| POST /sessions/{id}/execution/start | PlanningWorkspace (was → dead execution_engine_service) | same route | `nexora.builder_session.action_run_generation` (new wrapper) | `BuilderSessionService.run_generation` → GenerationCoordinator → GenerationRuntime → WebsiteGenerationPipeline | NO | YES (real E2E below) |
| GET /sessions/{id}/events | useRuntimeEvents (no backend) | new thin route | `nexora.runtime_event` storage | pipeline subscribers (producer, unchanged) | NO | YES |
| auth/sessions/etc. | Odoo json-envelope | BFF routes (existing) | Odoo services | unchanged | NO | YES |

## 13. Duplicate-Orchestration Proof

- No new orchestrator/coordinator/engine classes exist. Grep + static
  test (`test_30_adapters_have_no_orchestration_mechanics`) prove the
  BFF adapters contain no threading/subprocess/pipeline internals.
- `execution_engine_service` remains caller-free (NOT resurrected);
  `GenerationOrchestrator.generate_website` remains a deprecated
  compatibility wrapper only.
- `run_generation` remains the single generation entry (chain verified
  by suites 47.18/47.24/47.26/47.27/47.28/47.29/47.5-pipeline — all OK).

## 14. Tests

- `test_phase47_31_api_boundary.py` — **17/17 OK**: JWT posture over the
  full OpenAPI surface (404-proof: >40 protected operations 401 without
  token), public login/health, wrong-password 401, events-route
  thinness/bounds, execution delegation target, dead-target absence,
  model-wrapper content, adapter thinness, single POST /sessions
  registration, Vite proxy targets, no committed secrets, no
  wildcard-CORS, router dependency.
- Generation regressions: 47.18 (36) OK, 47.24 (35) OK, 47.26 (18) OK,
  47.27 (18) OK, 47.28 (17) OK, 47.29 (33) OK, 47.5 pipeline (8) OK,
  47.20B AI repair (21) OK.

## 15. Real E2E Evidence (through the canonical boundary)

`scratch/e2e_boundary_4731.py` → `scratch/e2e4731/e2e_result.json`:
- BFF health OK (odoo connected); anonymous GET /sessions → **401**.
- BFF login (dedicated E2E user; password verified by Odoo) → JWT.
- Builder configurations (19) read; session **1373** created via BFF.
- **execution/start → 200 success** → `action_run_generation` →
  `BuilderSessionService.run_generation` → full pipeline:
  - **LLM calls: exactly 1** (`openrouter / minimax-minimax-m3:free`,
    success) — no additional LLM call introduced.
  - session status `ai_reviewing` (pipeline COMPLETED incl. build,
    preview, browser validation — 3 route screenshots — final
    acceptance).
  - Runtime events via the boundary feed: 5 events; **composition
    event present** ("Page pattern…" summary).
  - Generated home present with native Hero; zero manual workspace
    patching; workspace evidence preserved.
  - `mobile_viewport=false` is correct: the brief did not request
    responsive/mobile, so the in-pipeline mobile phase was not
    required (same behavior as pre-phase).
  - Session DELETE (500) correctly surfaced the owner's workspace
    guard (ValidationError) — errors propagate, not masked. E2E
    records cleaned afterwards.

## 16. Regression Results

All suites listed in §14 pass. No Odoo schema changes; no provider/model
changes; OpenRouter/MiniMax path untouched (E2E used the existing
registry default model).

## 17. Dead/Legacy Paths Retained or Removed

- REMOVED: duplicate `POST /sessions` BFF registration (dead second
  registration); committed default secrets; wildcard-with-credentials
  CORS; BFF→`execution_engine_service` wiring (dead target).
- RETAINED (documented, not removed): Odoo controllers as internal API;
  `nexora.execution_engine_service` (dead, untouched — not part of the
  boundary); `GenerationOrchestrator` legacy wrapper; Odoo
  json-envelope routes (scripts/tests may use them).

## 18. Remaining Gaps

1. `PATCH /sessions/{id}` and `PATCH /projects/{id}` — requested by
   Console services but never implemented on any surface (documented;
   NOT invented this phase).
2. WS `/ws/events` accepts connections without a token (Console store
   sends none); channel-level auth is future hardening.
3. BFF→Odoo shared service account (no per-user propagation) — carried
   from 47.30, now documented in ADR-0082.
4. Session DELETE blocked by workspace guard is correct but the BFF
   returns 500; a 409 mapping would be nicer (cosmetic).
5. BFF deployment still manual (uvicorn); no service manager — startup
   strategy is deployment work, out of scope.

## 19. Explicit Deferred Work

Client DB provisioning, module installation, client API auth, frontend-
backend binding, per-user Odoo identity propagation, PATCH endpoints, WS
auth, BFF service deployment, Console UI for composition evidence — all
explicitly out of scope per phase constraints.

## 20. Architecture Invariant Confirmation

- ONE canonical external API boundary (BFF); no second gateway ✅
- No duplicate business logic (all routes delegate; adapters thin) ✅
- GenerationCoordinator canonical; BuilderSessionService = entry;
  no new execution/planning orchestrator; API layer ≠ orchestration ✅
- No legitimate Console capability lost (62-call inventory resolved) ✅
- SSE/runtime events intact; preview/validation intact; service
  ownership intact ✅
- No privileged Odoo credentials to Console; existing auth reused; no
  new secret system ✅
- ADR-0082 written ✅
- No new provider/model/connector; no Odoo schema changes; no client
  provisioning; no module installation; no frontend binding; no
  Graphify/OpenCode changes ✅

— End of Phase 47.31 report.
