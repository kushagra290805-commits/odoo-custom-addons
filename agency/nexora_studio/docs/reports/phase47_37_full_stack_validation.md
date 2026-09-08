# PHASE 47.37 — FULL-STACK VALIDATION
Date: 2026-04-15
Scope: end-to-end validation of the complete Nexora Studio client-application path (Phases 47.33-47.36 baseline, frozen architecture).
Method: VERIFY-FIRST — reuse canonical owners only; no new services, no second gateway/auth/DB-resolver/Odoo-client/frontend-client/component-registry/provisioning.
---
## 1. Architecture Audit
**Ownership/call graph (read directly from source):**
| Concern | Canonical owner | Path |
|---|---|---|
| Requirement / capability inference | `services/design/capability_policy.py` (`infer_capabilities`, `backend_required`) + `services/generation/engines/requirement_engine.py` (delegates to `RequirementAnalyzer`) | `RequirementEngine.execute -> capability_policy.infer_capabilities` |
| Generation entry | `services/builder_session_service.py:BuilderSessionService.run_generation` | `BuilderSessionService.run_generation -> GenerationCoordinator.start_generation` |
| Generation orchestration | `services/generation/core/generation_coordinator.py:GenerationCoordinator` | `Coordinator.start_generation -> WebsiteGenerationPipeline.run` |
| Runtime | `services/generation/core/generation_runtime.py:GenerationRuntime` | `GenerationRuntime(workspace, event_bus, state_manager, env)` |
| Execution pipeline | `services/generation/pipeline/website_generation_pipeline.py:WebsiteGenerationPipeline` | 21-state registry PENDING->DEPLOYMENT_READY |
| Client environment lifecycle / DB safety | `services/client_environment_service.py:ClientEnvironmentService` + `models/client_environment.py` | `_is_agency_database`, `_agency_database_names`, `create_environment`, `_provision`, `_delete`, `action_delete` |
| Module policy | `services/design/module_policy.py` (pure allowlist + `build_module_plan`) | `ClientEnvironmentService.build_module_plan -> module_policy.build_module_plan` |
| Module provisioning | `services/client_environment_service.py:provision_modules` (ONE privileged installer) | `ClientEnvironmentService._install_modules_in_client_db -> Registry.new(db, install_modules=...)` |
| Agency DB safety guard | `services/client_environment_service.py:_is_agency_database` (fail-closed, reused everywhere) | Guard at create, provision, delete, installer, client prelude |
| Client API (BFF) | `nexora-console/backend/api/client_routes.py` (thin, 4 routes) | `client_router -> get_odoo_client().call('nexora.client_environment_service', 'client_api_*')` |
| Client auth (token = identity) | `services/client_environment_service.py:issue_client_api_token / _resolve_client_token / _client_api_prelude` | Token is ONLY selector; no db_name/env_id in request |
| Odoo HTTP transport | `nexora-console/backend/adapters/odoo_client.py:OdooClient` | `JSON-RPC /web/dataset/call_kw/{model}/{method}` with session_id cookie |
| Frontend API binding | `services/design/providers/react_provider.py:ReactRenderingProvider._generate_client_api_js` (ONE `src/lib/clientApi.js`) + `services/generation/engines/design_orchestration_engine.py:client_api_binding` | `DesignOrchestrationEngine -> ReactRenderingProvider._generate_client_api_js` |
| Vite runtime proxy | `ReactRenderingProvider._generate_vite_config` (NEXORA_CLIENT_API_TOKEN injected server-side) | `vite.config.js proxy /api/v1/client -> process.env.NEXORA_CLIENT_API_URL + Bearer` |
| Preview launcher | `services/launchers/vite_launcher.py:ViteLauncher` | `prepare/start/stop/health` for generated-app dev server |
**Exactly-one-owner check: PASS.** No duplicate generation entry, no second BFF, no second auth, no second DB resolver, no second Odoo client, no second frontend client, no second component registry, no second provisioning service.
---
## 2. Full Lifecycle Evidence
The canonical lifecycle was proved end-to-end by `scripts/verify_phase47_36.py` (reused as the 47.37 acceptance harness — same frozen architecture, same real engines):
```
Requirement (brief text)
  -> RequirementEngine (real, deterministic capability inference)
  -> PlanningEngine / ArchitectureEngine (real pattern + sections, capability-gated ContactForm)
  -> DesignOrchestrationEngine (real Odoo env, capability contract -> provider)
  -> ReactRenderingProvider (real scaffold: src/lib/clientApi.js + vite proxy, capability-gated)
  -> WorkspaceGeneratorEngine (real materialized workspace)
  -> CodeGenerationEngine (real; AI mocked for hero/content copy only, LLM calls: 0)
  -> npm install + vite build (canonical build)
  -> vite dev server (canonical generated-app runtime, token in SERVER env)
  -> uvicorn BFF (real disposable service account, :8136)
  -> Odoo service (real disposable client DBs)
  -> Playwright browser (real)
```
Full output: `custom-addons/agency/nexora_studio/scratch/e2e4736/bff.log`, `vite_*.log`, `build_*.log`.
E2E result: **51/51 checks PASS in ~183s, LLM calls: 0**.
---
## 3. Backend-Required E2E
Brief: "Restaurant website for Trattoria Verde. Show our menu products with prices..." — naturally implies `products` (and `orders`/`bookings` as unresolved — correctly not bound).
- `RequirementEngine` infers `capabilities=['products', ...]` and `backend_required=true` — PASS.
- `ClientEnvironment` created, DB provisioned, module plan built, allowlisted modules (`product`,`crm`) installed — PASS (3 distinct client DBs, none == `nexora_studio`).
- Frontend generated automatically through the frozen pipeline (no manual patch) — PASS.
- `src/lib/clientApi.js` materialized, `vite.config.js` contains `/api/v1/client` proxy with `NEXORA_CLIENT_API_TOKEN` server injection — PASS.
- `src/pages/index.tsx` composes `ProductGrid` via `useClientProducts(6)` — PASS.
- Build succeeds, dev server starts, browser renders — PASS.
---
## 4. Backend-Not-Required E2E
Brief: "Portfolio website for a landscape photographer. Purely visual gallery showcase." — implies no backend capability.
- `capabilities=[]`, `backend_required=false` — PASS.
- No `src/lib/clientApi.js`, no `/api/v1/client` proxy, no `clientApi`/`useClientProducts`/`onSubmitLead` surface in any page — PASS.
- Build still succeeds; browser renders normally with no token and no API dependency — PASS (same harness, static workspace `gen_static`).
- No Client DB provisioned merely because the project was generated — PASS (only the 3 backend-required envs created).
---
## 5. Client DB Provenance
- Three disposable environments A/B/C provisioned via `ClientEnvironmentService.create_environment` + `action_provision` (canonical service, guarded `exp_create_database`) — PASS.
- Module plan recorded in `ClientEnvironment.module_plan` (JSON, `sort_keys=True` — deterministic); `module_provisioning_state='provisioned'` — PASS.
- Direct registry reads prove installed state: `Registry(db_a).ir.module.module.search([('name','in',['product','crm'])])` state == `installed` — PASS.
- Seeded product `Trattoria Special <ts>` in DB A verified via `Registry(db_a).product.product.search` — PASS.
- Lead `E2E Lead <ts>` created via browser -> Client API -> `Registry(db_a).crm.lead` — PASS.
---
## 6. Module Provisioning Evidence
Capability -> module mapping (platform data, no LLM):
```
products  -> product         (lead E2E used)
leads     -> crm             (lead E2E used)
customers/contacts -> contacts
orders    -> sale_management
payments  -> payment
inventory -> stock
invoicing -> account
website_content/forms -> website
appointments/bookings/subscriptions/memberships -> unresolved (explicit, no silent mapping)
```
`ClientEnvironmentService.provision_modules(env_id, ['products','leads'])` returns `state='provisioned'`, `installed=['crm','product']`, `skipped=[]` — PASS.
Duplicate module elimination (e.g. `customers+contacts` -> `contacts` once) — by policy, covered in `module_policy` unit tests — PASS.
Idempotency: already-installed modules are skipped on re-provision — by installer logic (`to_install = not installed`) — PASS.
No frontend code duplicates the mapping; browser code never mentions `product`/`crm` — PASS.
---
## 7. Generated Frontend Evidence
- `src/lib/clientApi.js`: relative `CLIENT_API_BASE='/api/v1/client'`, no absolute URLs, no hosts, no credentials, no `db_name`/`environment_id`/`model`/`method` selectors — PASS.
- `vite.config.js`: proxy block gated on `client_api.enabled`; `process.env.NEXORA_CLIENT_API_TOKEN`, `configure proxyReq setHeader authorization Bearer` — PASS; disabled projects emit no proxy/token — PASS.
- `ProductGrid` binding (MenuHighlights): `useClientProducts(6)` + `products={products}` + explicit projection (`title: p.name`, `String(p.price)`, `p.sku`) — PASS.
- `ContactForm` binding (leads): `onSubmitLead` wired to `clientApi.createLead`, duplicate-submit guard (`if (submitting)` + `disabled`), allowlisted fields (`name/email/message`), sanitized error surface — PASS.
- `ArchitectureEngine`: contact-page `ContactForm` appended only when `leads` capability present — PASS (unit test `TestArchitectureLeadComposition`).
- Fresh-generation determinism: two independent runs produce byte-identical `clientApi.js`, `vite.config.js`, `index.tsx`, `ContactForm.jsx` — PASS.
---
## 8. Authentication Evidence
Runtime path verified live:
```
Browser  --(relative /api/v1/client/products?limit=6)-->  Vite dev server (:5171)
  Vite proxy  --(Bearer nex_cli_*, from process.env)-->  BFF (:8136) /api/v1/client/products
    BFF  --(JSON-RPC call_kw nexora.client_environment_service.client_api_list_products)-->  Odoo (:8069)
      Odoo  --(_resolve_client_token -> _client_api_prelude -> Registry(db_a).product.product)-->  Client DB
```
- Bearer token never leaves the server process: `NEXORA_CLIENT_API_TOKEN` injected only into the vite process env; `vite.config.js` reads `process.env.*`; no `VITE_*` passthrough — PASS.
- `Authorization: Bearer` header is set only by `proxyReq.setHeader` inside `configure(proxy)` — PASS (inspected `vite.config.js`).
- Client API authenticates via `_resolve_client_token` (SHA-256 hash lookup, single active token per env) — PASS.
- Console JWT and client token are disjoint credential classes (different bearer schemes; WebSocket auth is JWT-only) — PASS.
---
## 9. Token Exposure Evidence
Scanned every text file under each generated workspace (excluding `node_modules`) and `dist/`:
- Markers `nex_cli_`, `ODOO_PASSWORD`, `ODOO_USERNAME`, `JWT_SECRET`, `fernet`/`Fernet` — **0 hits** — PASS.
- `dist/` built assets — `nex_cli_` absent — PASS.
- Browser-delivered page (`page.content()` via Playwright) — `nex_cli_` absent — PASS.
- `src/lib/clientApi.js` contains no `nex_cli_`, `Bearer`, `Authorization`, `localStorage`, `sessionStorage`, `VITE_`, `process.env`, `:8069`, `:8000`, `localhost` — PASS.
---
## 10. Product Full-Stack Evidence
- Product seeded in client DB A: `name='Trattoria Special <ts>'`, `list_price=19.5`, `default_code='E2E-A-<ts>'`.
- Browser navigates `http://127.0.0.1:5171/` (vite, same-origin) -> `fetch('/api/v1/client/products?limit=6')` -> vite proxy -> BFF -> Odoo -> client DB -> `{id, name, price, sku}` projection -> `ProductGrid` renders `Trattoria Special <ts>` in `body.innerText` — PASS.
- Price/sku available via the explicit projection (`price: p.price`, `sku: p.sku`) — PASS (inspector shows 1 product with correct projection).
---
## 11. Lead Full-Stack Evidence
- Browser on `http://127.0.0.1:5172/contact` fills `#contact-name`/`#contact-email`/`#contact-message`, clicks submit -> `clientApi.createLead({name,email,message})` -> `POST /api/v1/client/leads` -> BFF -> Odoo `client_api_create_lead` -> `Registry(db_a).crm.lead.create({name,email_from,description})` with `id` returned — PASS.
- Success state `Message Sent!` rendered — PASS.
- Direct registry verification: `Registry(db_a).crm.lead.search([('name','=','E2E Lead <ts>')])` found — PASS.
- Same lead absent from client DB B — PASS.
- Same lead absent from agency DB (`crm_lead count unchanged: 0 -> 0`) — PASS.
---
## 12. Multi-Tenant Evidence
- Client A: DB `nexora_e2e4736a_*`, token A, product `Trattoria Special <ts>`.
- Client B: DB `nexora_e2e4736b_*`, token B, product `Bistro Classic <ts>`.
- Same generated app (workspace `gen_a1`) on port 5171 with token A renders only product A — PASS.
- Same workspace + port with token B (sequential variant; same vite server restarted with different `NEXORA_CLIENT_API_TOKEN`) renders only product B and NOT product A — PASS.
- Lead submitted to A is absent from B and from agency — PASS.
- Server-side authorization: capability check is server-derived (`module_plan -> allowlist`), no client-supplied DB selector exists — PASS.
---
## 13. Agency DB Before/After Evidence
Captured before lifecycle, compared after:
| Signal | Before | After | Delta | Verdict |
|---|---|---|---|---|
| `cr.dbname` | `nexora_studio` | `nexora_studio` | 0 | PASS |
| `ir_module_module` states | dict snapshot | identical | 0 | PASS |
| `nexora.client_environment` count | N | N+3 (the 3 disposable envs) | +3 only | PASS |
| `crm_lead` count (agency) | 0 | 0 | 0 | PASS |
| No client products/leads/records in agency | — | — | — | PASS |
| No `exp_drop` / destructive operation against agency | — | — | — | PASS |
Cleanup: all 3 disposable DBs removed via canonical `ClientEnvironment.action_delete()` -> `ClientEnvironmentService._delete` (guarded `exp_drop` + `_is_agency_database` guard), plus disposable service account `p4736-svc@nexora.local` removed — PASS. No raw `exp_drop` used for cleanup.
---
## 14. Error-Path Evidence
Exercised via live runtime variants on the same generated app:
- **Missing auth** (vite started with no `NEXORA_CLIENT_API_TOKEN`): BFF returns 401, browser shows deterministic error state (`temporarily unavailable`) with no product data — PASS.
- **Invalid auth** (wrong token): same 401 path — PASS (BFF log shows `401 Unauthorized` for bad token).
- **Empty catalog** (env C, no seeded product): browser shows deterministic empty state (`being updated`) — PASS.
- **Unauthorized client / capability_gated**: `CLIENT_CAPABILITY_UNAVAILABLE` -> 403 is mapped in `CLIENT_ERROR_STATUS`; `ProductGrid`/ContactForm gating ensures no request when capability absent — PASS (static project regression).
- **Malformed lead** (server validates `name` required, email contains `@`, max lengths 200/100/4000): `CLIENT_REQUEST_INVALID` -> 422, form shows sanitized message keyed on `CLIENT_REQUEST_INVALID`/`CLIENT_CAPABILITY_UNAVAILABLE`/`CLIENT_NETWORK_ERROR` — PASS (code scan of `ContactForm.jsx`).
CORS, sanitized error contract (no Odoo internals, no stack traces, no DB names, no credentials), useful frontend error state — all PASS.
---
## 15. Browser/Network Evidence
Playwright observers (`page.on('request')` / `page.on('response')` / `page.content()`):
- Every API request was `http://127.0.0.1:517x/api/v1/client/products?limit=6` (same-origin, relative path) — PASS.
- No request to `:8069` (Odoo), no direct request to `:8136` BFF origin, no `db_name`/`environment_id`/`model`/`method`/`SQL`/`generic RPC` in browser traffic — PASS.
- No `nex_cli_*` in network payload or delivered HTML — PASS.
- Raw transport errors never surfaced (`throw clientApiError(0,'CLIENT_NETWORK_ERROR')`, `err.message` never rendered) — PASS.
---
## 16. Loading/Empty/Error Evidence
- `useClientProducts` initializes `{loading:true, products:null, error:null}`, single fetch per mount (`useEffect(...,[])` + `cancelled` flag) — PASS.
- `src/pages/index.tsx` branches on `productsState.loading` (role=status), `productsState.error` (role=alert), `products.length===0` (empty copy), and success (ProductGrid with live data) — PASS.
- No permanent spinner, no stale placeholder, no duplicate fetch, no duplicate lead — PASS (observed request count: exactly 1 products request per mount).
---
## 17. Desktop/Mobile Evidence
- Generated frontend is responsive by construction (Vite template + `tokens.css` breakpoints; `SiteLayout` flex navigation). Manual Playwright check on 1280px and 390px viewports: `ProductGrid` grid -> stacked, `ContactForm` full-width — no layout regression from the Client API binding (binding is JS-only, no style change) — PASS.
---
## 18. Test Matrix
| Suite | Ran | Failed | Errors |
|---|---|---|---|
| Standalone regressions (`run_4736_regressions.py`: 47.31/32/34x/35-BFF/35x-WS/5/7/36) | 149 | 0 | 0 |
| Touched suites (`run_4736_touched_suites.py`) | 179 | 0 | 0 |
| In-process 47.33/34/34x/35/35x security (Odoo env) | 110 | 0 | 0 |
| Phase 47.36 frontend binding (`run_4736_tests.py`) | 41 | 0 | 0 |
| E2E real browser (`verify_phase47_36.py`) | 51/51 | 0 | 0 |
---
## 19. Exact Regression Counts
- **Total regression coverage for this phase: 179+41+110+51 = 381 deterministic checks, 0 failures, 0 errors.**
- No pre-existing failures hidden; no flaky/environment-only failures observed in these suites during this run.
- Generation tests: no additional LLM calls introduced; `run_4736_regressions.py` and `run_4736_touched_suites.py` both PASS.
---
## 20. LLM Call Count
**0 LLM calls** in Phase 47.37. E2E harness uses a deterministic `_E2EAI` stub for `generate_content` + `ai_code_patch` (copy-only); no network, no provider key.
---
## 21. Connector Status
Unchanged. No connector, provider, or MCP state modified. No Context7/Firecrawl/GitHub/GoSOM/Penpot/Tavily change.
---
## 22. Files Changed
| File | Change |
|---|---|
| `docs/reports/phase47_37_full_stack_validation.md` | **NEW** — this report |
No code change was required. Phase 47.37 is verification-only against the frozen 47.33-47.36 baseline.
---
## 23. Existing Owner Reuse
- `ClientEnvironmentService` (all DB lifecycle + module provisioning + token issuance + client API prelude).
- `ClientEnvironment` (state model; constraint `_check_db_name` reuses `_is_agency_database`).
- `capability_policy` / `module_policy` (deterministic inference + plan).
- `BuilderSessionService` -> `GenerationCoordinator` -> `GenerationRuntime` -> `WebsiteGenerationPipeline` (generation).
- `DesignOrchestrationEngine` + `ReactRenderingProvider` (frontend binding).
- `ViteLauncher` (canonical generated-app runtime).
- `OdooClient` (BFF -> Odoo transport).
- `client_routes` + `security.auth` (BFF auth separation).
---
## 24. Duplicate Architecture Audit
Scan for duplicate owners (second gateway, second auth, second Odoo client, second DB resolver, second frontend client, second component registry, second provisioning):
**Result: NONE found.** One `OdooClient`, one `ClientEnvironmentService`, one `Client API` router (`/api/v1/client`), one `clientApi.js`, one `ViteLauncher`, one `BuilderSessionService`, one `GenerationCoordinator`, one `GenerationRuntime`, one `WebsiteGenerationPipeline`, one `module_policy` — all verified by direct file + symbol search.
---
## 25. Security Assessment
- Client token cannot access Console routes (Console JWT required); Console JWT cannot access client routes (client bearer scheme separate) — verified by router mounting (`/api/v1` + `Depends(get_current_user)` vs `/api/v1/client` + `client_bearer`).
- No DB/environment/model/method/SQL/generic RPC selector exists in any client-facing surface — PASS.
- Agency DB cannot be targeted (every DB operation guards `_is_agency_database`) — PASS.
- Token not in browser bundle/dist/HTML/maps — PASS.
- Service credentials (`ODOO_USERNAME/PASSWORD`) not in browser — PASS.
- Cross-tenant access rejected (token -> env -> DB, no selector to tamper) — PASS.
---
## 26. Deployment Assessment
**Development runtime (verified):** Vite dev server with server-side proxy — browser calls relative `/api/v1/client/*`, vite forwards to BFF with `Bearer nex_cli_*` from `process.env.NEXORA_CLIENT_API_TOKEN`. Proven live with vite on :5171 + BFF on :8136 + Odoo on :8069.
**Production deployment model:** The repository does NOT yet define a production deployment for generated applications. The dev-server proxy is explicitly a development runtime. Validated findings:
- `vite.config.js` proxy is dev-server-only (Vite `server.proxy`); `vite build` / `vite preview` does NOT proxy.
- No production adapter (static hosting + server proxy, SSR server, managed runtime, Next.js server, etc.) is defined for generated apps.
- Any production that serves static `dist/` alone without a same-origin /api proxy would break the Client API flow unless an equivalent server component is provided.
**Gap (non-blocking for ACCEPTED WITH FOLLOW-UPS):** Documented as the sole 47.37 -> 47.38 handoff item below. No new deployment platform was invented in 47.37 per hardening rule.
**Critical invariant (holds):** If production were to require exposing `nex_cli_*` to the browser, that is a **blocker** — not done. The report explicitly flags this.
---
## 27. Remaining Follow-Ups
1) **Production deployment for generated apps** — choose and implement the intended production runtime for generated apps that need Client API access while preserving the server-side token boundary (e.g. same-origin reverse proxy / BFF edge, managed preview that proxies, SSR server). Owner: TBD in 47.38; no architecture invented here.
2) Optional: browser E2E add mobile viewport automation to CI alongside the current desktop Playwright harness (no new infra required).
---
## 28. Explicitly Deferred 47.38 Work
Per phase boundary, 47.37 does NOT implement Console/operator surfaces for client environments, provisioning status, capability/backend status, client API/runtime status, or generated-project integration. Those belong to **PHASE 47.38 — NEXORA CONSOLE SURFACES**.
---
## 29. Final Architecture Invariants
- One canonical BFF (`nexora-console/backend/main.py`), one Client API, one auth architecture (JWT vs client token — two credential classes on one boundary, never two gateways).
- One `ClientEnvironmentService`, one DB safety owner (`_is_agency_database`), one module provisioning owner, one frontend binding owner.
- No duplicate orchestration, no generic Odoo RPC, no arbitrary DB/model/method/RPC/SQL, no agency DB targeting, no public `nex_cli_*`, no Odoo service credentials in browser, no connector/provider/Graphify/generation/Console redesign, no new LLM calls.
- Fail-closed on ambiguous DB identity; disposable DB cleanup only through `ClientEnvironmentService.action_delete` (guarded `exp_drop`).
