# PHASE 47.36 — GENERATED CLIENT FRONTEND BINDING COMPLETE

Date: 2026-09-08
Phase: 47.36 (ADR-0087)
Status: COMPLETED

---

## 1. Executive Summary

Phase 47.36 connects the **generated client React/Vite frontend** to the
Phase 47.35 Client API through a **server-held credential boundary**:
the browser application carries NO credential, calls only relative
same-origin `/api/v1/client/*` URLs, and the canonical generated-app
runtime server (the platform-managed Vite dev server) forwards those
requests to the BFF with the per-environment `nex_cli_*` token injected
from its SERVER process environment. The token never appears in
generated source, browser JavaScript, or build output.

```
Browser (public visitor — NO credential)
    -> relative same-origin /api/v1/client/*
    -> generated-app runtime (vite dev server, platform-managed)
       [server-side proxy: Authorization injected from process env]
    -> Phase 47.35 Client API (unchanged)
    -> authentication -> authorization -> ClientEnvironment
    -> Phase 47.34.x agency guard -> isolated Client Odoo DB
```

The binding is **capability-gated** by the Phase 47.32 Project
Capability Contract, deterministic, platform-owned (LLM calls: 0), and
reproduced automatically by every fresh generation — no manual artifact
patching.

```text
PHASE 47.36 E2E: 51/51 checks PASS in 184.8s (LLM calls: 0)
```

## 2. Existing Generated-Frontend Audit (verify-first)

| Component | File | Finding |
|---|---|---|
| Generated app shape | React 18 + Vite SPA; template `assets/frontend-templates/vite-react` | Static browser bundle; canonical runtime = Vite dev server (`PreviewEngine` → `nexora.preview_service` → `ViteLauncher` → `npm run dev -- --port N --host 127.0.0.1`) |
| Component source owner | `services/design/react_component_library.py` | 27-component native library, byte-identical per project (ADR-0077); ProductGrid/ContactForm templates live here |
| Scaffold owner | `services/design/providers/react_provider.py` | vite.config.js, package.json, src/config/*, src/lib/* — materialized by `WorkspaceGeneratorEngine` |
| Section composition owner | `services/generation/engines/code_generation_engine.py` | deterministic pattern builders (MenuHighlights→ProductGrid, ContactCTA…); assembler-owned import whitelist |
| Data flow before 47.36 | static structured ContentEngine copy embedded as `const products = [...]`; ContactForm fake-success | No API client, no fetch, no credentials anywhere |
| Page patterns | `services/design/page_patterns.py` + `DOMAIN_TEMPLATES` | MenuHighlights only in restaurant pattern; `/contact` page only in SaaS/Agency domains |
| Existing API client | none | created (ONE canonical module) |
| Same-origin proxy precedent | `nexora-console/vite.config.ts` proxies `/api` → BFF (ADR-0041/0082) | reused for generated apps |
| BuilderSession linkage | NO `project_id` (only `project_name` Char); no environment link anywhere | automatic token linkage impossible with existing architecture — deferred (see §29) |

## 3. Canonical Source Owner

The binding lives entirely in the canonical generation sources:

| Change | File | Owner |
|---|---|---|
| clientApi module + vite proxy scaffold | `services/design/providers/react_provider.py` | rendering provider (scaffold owner) |
| capability → binding transport | `services/generation/engines/design_orchestration_engine.py` (`client_api_binding()`) | renderer bridge (blueprint kwargs precedent) |
| products section binding | `code_generation_engine.py` (`_menuhighlights_api_bound`) | deterministic section builder owner |
| leads section builder | `code_generation_engine.py` (`_pattern_contactform`) | same |
| contact-page composition | `services/generation/engines/architecture_engine.py` | composition metadata owner |
| ContactForm real-submit mode | `services/design/react_component_library.py` | component library owner |
| identifiers/imports allowlist | `code_generation_engine.py` (`_CLIENT_API_IDENTIFIERS`, `_SCAFFOLD_COMPOSED`) | assembler contract |

No generated artifact was manually patched; fresh generations (×2,
byte-identical binding output) prove source-of-truth.

## 4. API Client Ownership

ONE canonical module: `src/lib/clientApi.js` (generated scaffold file)
— `clientApi.products(limit)`, `clientApi.createLead({name, email,
message})`, `useClientProducts(limit)` hook. Exact Phase 47.35 routes;
no alternative endpoints (`/frontend/*`, `/website/*`, `/public/*`
rejected); no duplicate ProductApi/LeadApi/BackendApi clients.
`whoami`/`health` are deliberately NOT emitted — no component consumer
exists; the server remains authoritative (§17 of the mandate).

## 5. Authentication Architecture (the critical gate)

**Decision**: the environment bearer token is NOT a public browser
credential. Verified against ADR-0086 (per-environment machine token;
"plaintext returned once by control-plane issuance") — no existing
security design makes it public. Therefore:

- Browser code: no token, no `Authorization`, no `VITE_*`/`NEXT_PUBLIC_*`
  env vars, no localStorage/sessionStorage, no absolute URLs.
- Runtime server (vite dev server — the canonical generated-app runtime,
  platform-managed, already forwards its process environment via
  `ViteLauncher.prepare()`): `server.proxy['/api/v1/client']` forwards
  to the BFF (`NEXORA_CLIENT_API_URL`, default the canonical local BFF)
  and injects `Authorization: Bearer ${NEXORA_CLIENT_API_TOKEN}` from
  `process.env` inside the Node-side proxy handler — never
  browser-readable (vite only exposes `VITE_*`-prefixed vars to client
  code).
- CORS untouched: the browser makes same-origin requests only; the BFF
  explicit-origin credential-capable CORS configuration is unchanged.
- Token rotation/revocation does not require regenerating the frontend —
  the credential is runtime-supplied, not compiled.

This is the mandate's "Browser → generated frontend → same-origin/
server-side API call → Client API → environment credential kept
server-side" architecture on the EXISTING canonical runtime and the
established repo proxy convention. No new authentication system, gateway,
secret store, or credential class was created.

## 6. Token Exposure Analysis (§32/§49 verification)

Scanned (marker values never printed) across generated source AND built
`dist/` for: `nex_cli_`, `ODOO_PASSWORD`, `ODOO_USERNAME`, `JWT_SECRET`,
`fernet`/`Fernet` — **zero hits** in both fresh generated apps; the
browser-delivered page HTML contains no token; the built JS bundle
contains the relative `/api/v1/client` paths and the sanitized error
vocabulary only. Expected safe result achieved: **no client environment
bearer token in browser-delivered output**.

## 7. Capability-to-Binding Mapping

| Project capability (47.32) | Phase 47.35 operation | Frontend binding |
|---|---|---|
| `products` | `GET /api/v1/client/products` | MenuHighlights section → native ProductGrid via `useClientProducts()` |
| `leads` | `POST /api/v1/client/leads` | `/contact` page → native ContactForm with `onSubmitLead` |
| (any other) | — | none (no API surface emitted) |
| none (`backend_required=false`) | — | static behavior preserved byte-identically |

Mapping derived only from `artifact.requirements.capabilities`
(deterministic RequirementEngine inference — no LLM), transported via
`DesignOrchestrationEngine.client_api_binding()` through the existing
process_blueprint kwargs → `output_config['client_api']` contract
(spline_scene_url precedent). Frontend never claims capabilities;
server-side authorization (Module Plan + installed module + agency guard)
stays authoritative. Capability ≠ module: no Odoo module identifiers
anywhere in browser code.

## 8. ProductGrid Binding

`_pattern_menuhighlights` emits the API-bound variant when the products
capability exists: explicit projection `name→title`, `price→price`,
`sku→badge` (nothing else — no `description`/`list_price`/
`default_code`/Odoo fields); deterministic states:

- **loading** — `role="status"` status block
- **error** — `role="alert"` ("temporarily unavailable"), never masked
  as live data and never silently falling back to static content
- **empty** — "menu is being updated"
- **success** — native `<ProductGrid products={products}/>` (component
  unchanged — zero visual redesign)

Single canonical source: with the capability, the API replaces the
static items array (no dual-source precedence). Without the capability
the static composition is byte-identical to Phase 47.27-47.29 behavior
(regression-guarded by the existing suites, which all pass).

## 9. ContactForm / Lead Binding

- Library `ContactForm` gains ONE optional async prop `onSubmitLead`:
  captures name/email/message (length caps 200/200/4000 mirroring the
  server whitelist), duplicate-submit protection (`disabled` +
  `aria-busy` while submitting), success alert + form reset, sanitized
  error alert keyed on the stable Phase 47.35 codes
  (CLIENT_CAPABILITY_UNAVAILABLE / CLIENT_REQUEST_INVALID /
  CLIENT_NETWORK_ERROR), and preserves the legacy demo behavior when
  unbound. The component library remains byte-identical across
  projects.
- `ArchitectureEngine` appends the ContactForm section to the `/contact`
  page only when the `leads` capability exists (other pages/static
  projects unchanged); `_pattern_contactform` composes
  `<ContactForm onSubmitLead={clientApi.createLead}/>`, and a
  ContactForm section without the capability is truthfully skipped
  (Gallery precedent).
- Only the allowlisted fields are submitted; the payload is narrower
  than the internal Odoo schema; no model/method/db/company/stage/user
  fields exist anywhere in browser code. Server-side validation
  remains authoritative.

## 10. Static vs Backend Behavior

`backend_required = false` (or no supported capability): NO clientApi
module, NO vite proxy, NO bound sections — verified byte-level in the
E2E's static generation (portfolio brief → zero API surface). The
native library still ships its components (inert without binding) per
ADR-0077.

## 11. API Error Handling

`clientApi` normalizes every failure into `{status, code}`:
network/timeout → `CLIENT_NETWORK_ERROR` (15s AbortController timeout);
HTTP errors → status + stable detail code. Raw transport text, internal
URLs, DB names, and stack traces are never surfaced. ContactForm maps
codes to deterministic friendly messages. Backend failure is never
presented as successful live data (explicit error/empty states).

## 12. Loading / Empty / Error States

All three states are explicit, deterministic, and accessible
(`role="status"`/`role="alert"`). No request loops (single fetch per
mount, cancellation-guarded), no duplicate submissions (submit lock),
no state-management framework introduced.

## 13. Deployment / Base-URL Behavior

Browser code uses relative same-origin paths only — no `localhost`,
`127.0.0.1`, `:8000`, `:8069`, or any absolute URL (test-enforced). The
dev-server proxy target is `process.env.NEXORA_CLIENT_API_URL ||
'http://127.0.0.1:8000'` — runtime server configuration, not
production frontend code, and overridable by the platform. For future
production deployments the same contract carries to the reverse proxy
that serves the static build (documented as the deployment contract;
no production deployment mechanism exists yet in the repository).

## 14. Browser / Network Evidence (E2E)

Real Playwright browser against the real vite dev server + real uvicorn
BFF + real Odoo + real disposable client DBs:

- client-DB product ("Trattoria Special <ts>") rendered in ProductGrid ✓
- every API request was same-origin
  `http://127.0.0.1:517x/api/v1/client/*` ✓ (no `:8069`, no direct BFF
  origin from the page, no arbitrary model/method/db payload)
- zero browser console errors; no unexpected failed requests (the
  no-credential variant's single 401 is the expected deterministic
  error-state path) ✓
- no `nex_cli_` in delivered page content ✓
- lead form submission → success state ✓
- no-token runtime → deterministic error state, no fake data ✓
- empty-catalog environment → deterministic empty state ✓
- same app + tenant-B token → tenant-B product only (tenant-A data not
  exposed) ✓

## 15. Client DB Provenance

- Lead "E2E Lead <ts>" verified by **direct registry read in Client DB
  A** (`nexora_e2e4736a_*`) — not merely HTTP 200 ✓
- Product data verified in Client DB A (≥1 product) ✓
- Lead absent from Client DB B (tenant isolation) ✓

## 16. Agency DB Evidence

Before/after snapshots across the full E2E: `ir_module_module`
name/state snapshot identical; zero new `crm_lead` rows; control-plane
record delta = exactly the 3 disposable environment audit records (all
soft-deleted through `action_delete`, DBs dropped); disposable BFF
service account removed. The Phase 47.34.x safety owner
(`_is_agency_database`) was reused, not duplicated.

## 17. Tenant-Isolation Evidence

Client A and Client B each provisioned with product+crm modules and
seeded with distinct products. The SAME generated app served with
tenant B's runtime credential rendered tenant B's product and did NOT
expose tenant A's product — the frontend binding is credential-keyed;
server-side 47.35 authorization remains authoritative.

## 18. Fresh-Generation Proof (source-of-truth)

Two independent fresh generations of the same restaurant brief produced
byte-identical `src/lib/clientApi.js`, `vite.config.js`,
`src/pages/index.tsx`, and `src/components/ContactForm.jsx`. A third
(agency) brief produced the leads binding; a fourth (portfolio) brief
produced zero API surface. All through the REAL engine chain
(RequirementEngine real capability inference → PlanningEngine →
ArchitectureEngine → DesignOrchestrationEngine over the real Odoo
service → TemplateResolution → Content → WorkspaceGenerator →
CodeGenerationEngine) — AI mocked ONLY for hero/content copy (the
LLM-free deterministic paths are real). LLM calls: 0.

## 19. Build Proof

`npm install` + `npm run build` (canonical toolchain) succeeded for the
products-bound app and the leads-bound app; the built `dist/` contains
the binding (relative API paths + sanitized error vocabulary) and zero
secrets.

## 20. Browser Proof

§14 above, executed with the repository's Playwright mechanism on the
canonical runtime (exact ViteLauncher command line, host binding, port
semantics).

## 21. Tests Added

`tests/test_phase47_36_frontend_binding.py` — 41 tests (standalone
suite, the 47.27-47.29 convention; not registered in `tests/__init__.py`
because it re-parses Odoo config at import — same reason 47.27-47.29
are unregistered):

- capability transport (4): binding derivation incl. unsupported
  capabilities bind nothing
- clientApi module (8): exact endpoints/methods, same-origin-only,
  zero credentials/selectors, explicit projections, narrow lead
  payload, hook states/single-fetch, sanitized errors, gated emission
- vite proxy (4): proxy present only when enabled, token only from
  server process env (never `import.meta.env`/VITE_*), config shape
- ProductGrid binding (7): API-bound generation, projection, states,
  single-source, section validation, static-path regression guard,
  leads-only project guard
- ContactForm (8): real-submit contract, duplicate protection,
  allowlist, sanitized errors, length caps, legacy mode, codegen
  section + truthful skip
- ArchitectureEngine composition (4)
- capability gating + security scan (5): static project zero surface,
  no credentials/hosts in any generated file, no generic RPC surface,
  fresh-generation determinism ×2

Runners: `scripts/run_4736_tests.py` (suite),
`scripts/run_4736_touched_suites.py` (touched suites),
`scripts/run_4736_regressions.py` (regression matrix),
`scripts/verify_phase47_36.py` (real E2E).

## 22. Regression Results (exact counts)

| Suite | Count | Result |
|---|---:|---|
| 47.3x Odoo focused matrix (odoo-bin post_install: 47.33=8, 47.34=39, 47.34.x=24, 47.35=27, 47.35x=12) | 110 | all PASS |
| 47.31 boundary (standalone) | 17 | PASS |
| 47.32 capability (standalone) | 20 | PASS |
| 47.35 BFF client routes | 19 | PASS |
| 47.35x WS auth | 14 | PASS |
| Generation regressions (47.5 behavior + 47.7 artifacts) | 38 | PASS |
| **Phase 47.36 new suite** | **41** | **PASS** |
| Touched library/provider/codegen suites (component synthesis, manifest, react provider ×2, interaction ×2, 47.25, 47.27, 47.28, 47.29, 47.32) | 179 | PASS |
| Full-module odoo-bin post_install run | 183 ran | 1 failed + 6 errors, ALL pre-existing documented environment failures (`TestLifecycleIntegrity` ×5, `TestPhase16GenerationPipeline` ×2 — identical to the Phase 47.35.x addendum's known-failure list; both before and after this phase; neither suite touches the frontend binding) |

## 23. LLM Call Count

**0** (E2E + all tests). The capability→binding decision is purely
deterministic from the Phase 47.32 contract; the binding sections are
the existing deterministic no-LLM pattern-builder class (ADR-0078/0079).
The E2E mocked AI only for hero/content copy (test-harness convention —
no real provider call).

## 24. Files Changed

| File | Change |
|---|---|
| `services/design/providers/react_provider.py` | `_client_api_binding`, `_generate_client_api_js` (ONE canonical client), capability-gated emission in `_synthesize_structure`, vite same-origin proxy with server-side token injection in `_generate_vite_config` |
| `services/generation/engines/design_orchestration_engine.py` | `client_api_binding()` + transport through existing kwargs contract |
| `services/generation/engines/code_generation_engine.py` | `_client_api_capabilities`, `_menuhighlights_api_bound`, `_pattern_contactform`, `_CLIENT_API_IDENTIFIERS`, ContactForm in `_PATTERN_SECTIONS`/`_SCAFFOLD_COMPOSED`, validation call-site identifiers |
| `services/generation/engines/architecture_engine.py` | capability-gated ContactForm composition on `/contact` |
| `services/design/react_component_library.py` | ContactForm real-submit mode (optional `onSubmitLead`; states, caps, duplicate protection, sanitized errors) |
| `tests/test_phase47_36_frontend_binding.py` | new (41 tests) |
| `scripts/run_4736_tests.py`, `run_4736_touched_suites.py`, `run_4736_regressions.py`, `verify_phase47_36.py` | new runners + real E2E |
| `docs/adr/ADR-0087-generated-client-frontend-api-binding.md` | new ADR |
| `docs/reports/phase47_36_frontend_binding.md` | this report |

Console frontend: **zero changes** (`nexora-console/src/**` untouched;
BFF `main.py`/`client_routes.py`/`ws.py` untouched). Client API:
**zero changes**. Module provisioning, environment lifecycle,
generation pipeline registry: **zero changes** (one additive kwarg
transport + one additive deterministic section).

## 25. Existing Owner Reuse

- ONE BFF (`nexora-console/backend`) — reused untouched
- ONE Client API (`/api/v1/client/*`) — consumed, not redesigned
- ONE authentication architecture (47.35 tokens) — reused; boundary
  moved server-side
- ONE client identity/DB resolution path (token → ClientEnvironment →
  agency guard) — untouched
- ONE scaffold owner (react provider), ONE component library owner,
  ONE section-builder owner, ONE composition owner — extended in place
- ONE runtime (Vite dev server via preview service/launcher) — reused;
  existing env passthrough already transports the credential
- Console vite-proxy convention — applied to the generated scaffold

## 26. Duplicate Architecture Audit

No second API client, gateway, auth system, secret store, component
registry, provider registry, renderer, generation phase, or
orchestration path was created. `clientApi.js` is the single generated
API module; ProductGrid/ContactForm remain single-source; the binding
decision has exactly one derivation (artifact capabilities) and one
transport (blueprint kwargs).

## 27. Security Assessment

- Environment token in public browser output: **structurally excluded**
  (scanned: source + dist + delivered HTML clean)
- Agency credentials (Console JWT, Odoo service username/password,
  connector keys, PATs, Fernet key, MCP credentials, internal BFF
  credentials): never generated into frontend code
- Frontend cannot select environment/DB/project, claim capabilities,
  choose models/methods, execute SQL or generic RPC — no such surface
  exists in browser code (test-enforced)
- Browser never targets Odoo :8069 or the agency DB; all API traffic is
  same-origin, credential-injected server-side
- Input treated as hostile: client-side validation mirrors the server
  whitelist but server-side validation remains authoritative

## 28. Remaining Gaps / Deferred Decisions

1. **Automatic token-distribution flow** (the §49-adjacent
   architectural decision): today the runtime credential is supplied by
   the operator/E2E through the preview server's process environment
   (`NEXORA_CLIENT_API_TOKEN`/`NEXORA_CLIENT_API_URL` — the
   ViteLauncher already forwards the platform environment). The
   platform flow that automatically resolves a generated app's
   ClientEnvironment at preview/deployment start (session/project ↔
   environment linkage; issuance/rotation semantics at restart) does
   not exist in the current architecture (BuilderSession has no
   project FK) and is **deferred to Phase 47.37+** as the
   token-distribution decision. No security risk arises from the
   deferral: without the env var the binding degrades to the explicit
   401 error state.
2. Production deployment of generated apps (reverse proxy owning the
   same `/api/v1/client` → BFF forwarding + header injection for the
   static build) — no deployment mechanism exists yet.
3. Rate limiting / lead-abuse controls on the Client API (47.35
   follow-up, unchanged).
4. Multi-page product surfaces (only MenuHighlights/ProductGrid exists
   in the current pattern vocabulary; Ecommerce `/products` pages are
   Content sections today — out of scope per "do not automatically
   convert static generated content into API data").

## 29. Explicitly Deferred Phase 47.37 Work

- session/project ↔ ClientEnvironment linkage + preview/deployment
  token-issuance flow (the token-distribution decision)
- full-stack frontend/backend validation hardening
- production deployment contract
- anything touching the Console (47.38)

## 30. Final Architecture Invariant Confirmation

- GENERATED CLIENT FRONTEND ≠ NEXORA CONSOLE (zero console changes) ✅
- ONE canonical Client API consumed unchanged ✅
- ONE authentication architecture; browser holds no credential ✅
- ONE client identity path (token → environment) ✅
- ONE client DB resolution path; ONE database safety owner reused ✅
- ONE module provisioning owner (untouched) ✅
- NO duplicate orchestration; NO new pipeline phase ✅
- NO generic Odoo RPC; NO arbitrary database selection ✅
- NO agency/Odoo-service credentials in client frontend ✅
- NO client environment bearer token in public browser output ✅
- SERVER-SIDE AUTHORIZATION REMAINS AUTHORITATIVE ✅
- CAPABILITY ≠ MODULE ≠ API ENDPOINT (frontend contract exposes
  neither module names nor endpoint vocabulary) ✅
- LLM calls: 0 ✅
- no connector / provider / Graphify / Console changes ✅
- fresh generation reproduces the binding deterministically ✅
- real client DB provenance + agency DB untouched proven ✅

---

*End of Phase 47.36 report.*
