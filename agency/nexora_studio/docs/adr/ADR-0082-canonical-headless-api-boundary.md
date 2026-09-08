# ADR-0082: Canonical Headless API Boundary (BFF over Odoo Services)

Date: 2026-09-06
Phase: 47.31
Status: Accepted

## Context

Phase 47.30 proved the platform had TWO parallel `/api/v1` surfaces:

1. **Odoo HTTP controllers** (`nexora_studio/controllers/*`) — live via the
   Console's Vite proxy (→ :8069), Odoo-session auth, JSON-envelope
   (`type='json'`) mixed with plain-JSON (`type='http'`) routes.
2. **FastAPI BFF** (`nexora-console/backend`) — 55 routes + WS hub, JWT
   auth, thin adapters delegating to Odoo services via JSON-RPC — but NOT
   deployed (port 8000 occupied by an unrelated process; Vite proxy
   bypassed it).

Meanwhile the Console's implemented contract matches the BFF: 62 API
calls, of which ~40 (files, git, assistant, planner, execution, preview,
AI jobs, dashboard aggregation, WS events) have **no Odoo-controller
equivalent at all**, and several Odoo controllers (auth, sessions) use the
JSON-RPC envelope the Console's plain-JSON axios client cannot speak.
Console ADR-0026/0027/0038 document the BFF as the intended Console
backend ("FastAPI layer", "session commands via the FastAPI layer",
"POST /auth/login"), and `implementation_report_phase11b` wired it end
to end before the proxy drifted to Odoo.

## Decision

**The FastAPI BFF (`nexora-console/backend`) is the ONE canonical
headless external API boundary** for the Nexora Console and for future
client-backend-facing workflows. The Vite dev proxy routes `/api` and
`/ws` to it (:8000).

1. **Why it is canonical (evidence)**: it is the only surface that serves
   the Console's implemented contract (int-id session DTOs, JWT+cookie,
   workspace/git/planner/assistant/AI-operations routes); its adapters
   are thin delegators to the canonical Odoo service owners — no business
   logic and no orchestration live in the BFF; WS `/ws/events` matches
   the Console store; OpenAPI docs ship with it.
2. **Odoo controllers' role**: they remain the INTERNAL API surface for
   server-side scripts, tests, admin tooling, SSE generation-stream
   debugging, and direct integrations that speak Odoo session auth. They
   are not removed and not rewritten. They are no longer the Console's
   boundary.
3. **API boundary ≠ orchestration boundary.** The BFF never orchestrates.
   Every state-changing route delegates to an existing canonical Odoo
   owner:
   - session lifecycle → `nexora.builder_session.action_*` →
     `nexora.builder_session_service`;
   - generation → `nexora.builder_session.action_run_generation` (new thin
     record wrapper, the `action_start_runtime` precedent) →
     `BuilderSessionService.run_generation` → `GenerationCoordinator` →
     `GenerationRuntime` → `WebsiteGenerationPipeline` → engines;
   - files → `nexora.workspace_file_service`; git → `nexora.git_service`;
     planner → `nexora.project_planner_service`; assistant →
     `nexora.builder_assistant_service`; preview → read-only queries over
     `nexora.runtime`/`nexora.preview_runtime` (ownership stays with
     `nexora.preview_service`).
4. **Dead orchestration is not resurrected.** The former BFF target
   `nexora.execution_engine_service.start_execution` (zero callers,
   legacy Phase-44/45 pipeline) is NOT revived. `POST
   /sessions/{id}/execution/start` now delegates to the canonical
   `BuilderSessionService.run_generation` — the same owner the planner's
   blueprint feeds (P0-03 injection), preserving the Console's
   plan→execute UX without a second execution engine.
5. **Compatibility/deprecation strategy**: no Odoo controller routes were
   removed or changed; existing scripts/tests keep working. The duplicate
   dead `POST /sessions` registration inside the BFF itself (shadowed by
   route-order) was removed. `GET /sessions/{id}/events` was added as a
   thin read-only projection over the EXISTING `nexora.runtime_event`
   storage (the Console's event feed previously had no backend on either
   surface).
6. **Authentication boundary**: the EXISTING mechanisms only. BFF JWT
   (`security/auth.py`) with password verification delegated to Odoo;
   `public_router` (login, health) is unauthenticated, every other route
   requires the JWT via router-level dependency. Default credentials are
   no longer committed: `JWT_SECRET` falls back to a random per-process
   key with a warning; Odoo service-account credentials come from the
   environment only. CORS uses the explicit allow-list (wildcard +
   credentials removed). Known limitation (documented, unchanged): the
   OdooClient holds one shared service-account Odoo session — per-user
   identity propagation to Odoo is future work; WS `/ws/events` accepts
   connections without a token (Console store limitation). Future CLIENT
   API authentication (per-client tokens for generated applications) will
   be a SEPARATE boundary from this agency-console authentication and is
   explicitly out of scope here.
7. **SSE/WebSocket ownership**: generation remains the event PRODUCER
   (pipeline event bus → `nexora.runtime_event` + SSE
   `/nexora/stream/<id>`). The BFF only DELIVERS: `/ws/events` broadcasts
   aggregated health/session snapshots (existing behavior), and the new
   events route polls the existing storage. No new event/telemetry
   subsystem.
8. **Relationship to BuilderSessionService / GenerationCoordinator**: they
   remain the single generation entry and orchestration owners. The BFF
   is an HTTP adapter in front of them; the frozen pipeline is untouched
   (verified by the 47.31 regression suites and a real-LLM E2E through
   the new boundary).
9. **Console relationship**: one API base (`/api/v1`), one auth token
   store, one proxy target. No Console UI changes.
10. **Future client-backend API relationship**: client application APIs
    (on provisioned client DBs) will be a THIRD, clearly separated
    surface — never this agency boundary, never the internal Odoo
    controllers. This ADR reserves that separation.

### Migration invariants

- No route may be added to the BFF that contains business logic or
  orchestration; it must delegate to an existing Odoo service owner.
- No second gateway; no second event bus; no parallel capability or
  provider registry at the API layer.
- The frozen generation chain (`run_generation → GenerationCoordinator →
  GenerationRuntime → WebsiteGenerationPipeline → engines`) is the only
  generation path reachable from the boundary.
- Odoo controllers remain internal-only; new Console capabilities get
  BFF routes delegating to canonical owners.

### Explicit non-goals (Phase 47.31)

Client DB provisioning, module installation, client API authentication,
frontend-backend binding, LLM/provider changes, connector/MCP changes,
Graphify changes, Console UI work.
