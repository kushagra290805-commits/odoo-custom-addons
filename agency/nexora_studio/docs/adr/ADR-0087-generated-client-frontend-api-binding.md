# ADR-0087: Generated Client Frontend ↔ Client API Binding

Date: 2026-09-08
Phase: 47.36
Status: Accepted

## Context

Phase 47.35 established the Client API (four routes inside the ONE
canonical FastAPI BFF) and the per-environment `nex_cli_*` bearer
credential (SHA-256 at rest, expiring, revocable, rotatable). Generated
client applications are public React 18 + Vite SPAs served by the
platform-managed Vite dev server (the canonical generated-app runtime —
`PreviewEngine` → `nexora.preview_service` → `ViteLauncher` →
`npm run dev`). Until this phase they were purely static: `ProductGrid`
rendered compile-time structured copy and `ContactForm` faked success.

The binding must connect backend-capable generated frontends to the
existing Client API **without exposing the environment credential to
public browsers** and without a second API contract, authentication
architecture, component registry, or generation pipeline.

## Decision

### 1. Authentication boundary: server-held credential

The Phase 47.35 token is an environment-level machine credential — NOT a
public browser credential. Embedding it in browser-delivered code
(VITE_*/NEXT_PUBLIC_*, source, localStorage, runtime config) is
architecturally forbidden; obfuscation is not secret storage.

The safe boundary reuses the established same-origin Vite-proxy
convention (Nexora Console, ADR-0041/0082):

```
Browser (public visitor, NO credential)
    -> relative same-origin fetch('/api/v1/client/*')
    -> generated-app runtime server (vite dev server, platform-managed)
       proxy injects: Authorization: Bearer $NEXORA_CLIENT_API_TOKEN
       (SERVER process environment ONLY — Node-side, never bundled;
        vite exposes only VITE_*-prefixed vars to client code)
    -> Phase 47.35 Client API (unchanged contract)
    -> authentication -> authorization -> ClientEnvironment
    -> Phase 47.34.x agency guard -> Client Odoo DB
```

The browser bundle contains zero credentials; the token transits only
the control-plane issuance → runtime server process environment → proxy
request header. The token never appears in generated source, built
output, or browser-visible configuration. The existing
`ViteLauncher.prepare()` already copies the platform process
environment into the dev server, so the runtime credential flows through
the canonical launcher without launcher changes.

This implements the Phase 47.36 objective's "Browser → generated
frontend → same-origin/server-side API call → Client API → environment
credential kept server-side" model on the EXISTING canonical runtime.
The missing platform piece — automatic session/project →
ClientEnvironment → token-issuance linkage at preview start — is a
deliberately deferred control-plane decision (see Future).

### 2. ONE canonical client API client module

The rendering provider scaffold (the canonical scaffold owner) emits
`src/lib/clientApi.js` — the single Client API client for generated
apps — reusing the exact Phase 47.35 contract: `GET
/api/v1/client/products` (explicit id/name/price/sku projection) and
`POST /api/v1/client/leads` (name/email/message whitelist — narrower
than the internal Odoo schema). Relative same-origin URLs only; bounded
timeout; sanitized deterministic errors (`CLIENT_NETWORK_ERROR`,
HTTP-status codes — never raw transport text, internals, or stack
traces). `useClientProducts()` provides the one products data hook
(single fetch per mount, cancellation-safe, no retry storm). No
duplicate ProductApi/LeadApi/BackendApi clients exist.

### 3. Capability-gated binding (server stays authoritative)

The binding derives ONLY from the Phase 47.32 Project Capability
Contract on the generation artifact, transported through the existing
process_blueprint kwargs → output_config contract
(`spline_scene_url` precedent):

```
RequirementModel.capabilities (deterministic, no LLM)
    -> DesignOrchestrationEngine.client_api_binding()
    -> provider output_config['client_api']
    -> scaffold: clientApi module + vite proxy (only when enabled)
    -> CodeGenerationEngine section builders (same artifact contract)
```

- `products` → MenuHighlights composes the native ProductGrid organism
  bound to `useClientProducts()` (live client-DB data replaces the
  static items; one canonical source — no ambiguous precedence).
- `leads` → the contact page (`/contact`) composes the native
  ContactForm organism with the real submit mode (`onSubmitLead` bound
  to `clientApi.createLead`).
- No capability / `backend_required = false` → static behavior is
  preserved byte-identically; no clientApi module, no proxy, no bound
  sections. A section named ContactForm without the leads capability is
  truthfully skipped (Gallery precedent).
- Unsupported capabilities (orders, bookings, …) bind nothing — only
  capabilities with an existing Phase 47.35 operation.
- The frontend never claims capabilities; the server-side 47.35
  authorization chain (token → environment → module plan → installed
  module) remains authoritative. Technical Odoo module names never reach
  the frontend contract.

### 4. Component contract preservation

`ProductGrid` is unchanged (zero visual redesign); the binding lives in
the deterministic section builder with explicit states:
loading (`role="status"`), error (`role="alert"` — never masked as live
data and never silently falling back to static content), empty, and
success. `ContactForm` gains one optional async `onSubmitLead` prop:
field capture (name/email/message only), length caps mirroring the
server whitelist, duplicate-submit protection (disabled + aria-busy
while submitting), sanitized error messages keyed on the stable
Phase 47.35 error codes, and legacy demo behavior when unbound. The
component library remains byte-identical across projects (ADR-0077);
sections own the binding decision.

### 5. Error semantics

The clientApi module normalizes failures to a stable, sanitized
contract (status + code). ContactForm maps the stable codes to
deterministic friendly messages; a missing runtime credential yields
401 → the products error state ("temporarily unavailable"), never
fabricated data. No raw Odoo errors, DB names, internal URLs, or stack
traces are surfaced.

## Consequences

- Fresh generations deterministically embed the binding (proved
  byte-identical across two independent fresh generations of the same
  brief); no manual artifact patching.
- The browser cannot select environments, databases, models, methods,
  or capabilities; it holds no credential of any class.
- Token rotation/revocation does not require regenerating the frontend
  (the credential is runtime-supplied, not compiled in).
- Static projects remain fully static — no backend dependency is forced.
- CORS architecture is untouched: the browser makes same-origin
  requests only.

## Security analysis

- Public browser exposure of `nex_cli_*` tokens: structurally
  impossible through this binding (no token in source, bundle, HTML,
  runtime config; scanned in E2E including built dist/).
- Agency/Odoo-service credentials: never reach the frontend; the
  generated app is outside the control-plane trust boundary.
- Arbitrary RPC: no model/method/db selector exists anywhere in
  browser-delivered code; only the two allowlisted business operations
  are callable.
- Tenant isolation: the token (not the browser) selects the tenant; the
  E2E proves the same app + tenant-B credential yields only tenant-B
  data.

## Non-goals

- automatic session/project → environment → token linkage at preview
  start (token-distribution flow — deferred, see Future)
- production deployment of generated apps (the same-origin proxy
  contract carries to whatever reverse proxy serves the built app)
- client-user login/OIDC sessions
- new API endpoints (the Phase 47.35 contract is consumed unchanged)
- whoami/health frontend consumption (no component consumer; server
  stays authoritative)
- rate limiting (documented operational follow-up from 47.35)

## Future

1. **Token-distribution decision (Phase 47.37+)**: the platform flow
   that automatically resolves a generated app's ClientEnvironment at
   preview/deployment start and issues/rotates its runtime credential
   (e.g. session/project ↔ environment linkage). Until then the
   credential is operator/E2E-supplied through the runtime process
   environment — the boundary this phase established.
2. Production deployment contract: a reverse proxy owning the same
   `/api/v1/client` → BFF forwarding + server-side Authorization
   injection for the static build.
3. Rate limiting and lead-abuse controls on the Client API.

## Evidence

`scripts/verify_phase47_36.py` — 51/51 checks PASS, LLM calls 0: real
brief → real engine chain (AI mocked for hero/content copy only) →
fresh generation ×2 (byte-identical binding) → npm install + vite build
→ token scan (source + dist clean) → real vite dev servers + real
uvicorn BFF with disposable service account + real disposable client
DBs → real browser (Playwright): client-DB product renders in
ProductGrid, same-origin-only API requests, zero console errors, lead
submission creates a verified `crm.lead` in Client DB A (absent from
agency DB and Client DB B), no-token error state, empty-catalog empty
state, tenant-B isolation → agency DB module snapshot identical.
