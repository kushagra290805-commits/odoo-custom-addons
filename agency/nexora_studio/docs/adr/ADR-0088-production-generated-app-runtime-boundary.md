# ADR-0088: Production Generated-App Runtime Boundary

## Status
Accepted

## Context
Phase 47.38A ownership audit verified that no production runtime exists for generated applications. Development is served via `ViteLauncher` launching `npm run dev` with `vite.config.js` `server.proxy` injecting `NEXORA_CLIENT_API_TOKEN` server-side from `process.env`. All launcher plugins (`vite_launcher.py`, `static_file_launcher.py`, `python_http_launcher.py`) are development or static servers with no proxy and no secret capability. No nginx, Caddy, Traefik, Docker/K8s definition, SSR entrypoint, or static-hosting edge proxy exists for generated apps. Phase 47.38 is scoped to narrow Console operator surfaces only.

## Decision
1. **Vite `server.proxy` is development/runtime infrastructure, not production deployment architecture.** The existing Vite development proxy in generated `vite.config.js` remains unchanged and is exclusively for development preview.

2. **Production serving is intentionally deferred.** No production proxy infrastructure, static-hosting edge proxy, SSR, nginx, Caddy, or Traefik is introduced by Phase 47.38.

3. **`nex_cli_*` is never a browser credential.** The client bearer token remains server-side only. Generated `src/lib/clientApi.js` contains no `nex_cli_*` reference; injection occurs only via `process.env.NEXORA_CLIENT_API_TOKEN` inside the Node proxy layer.

4. **Future production runtime must preserve server-side token injection.** Any production host must obtain and inject the client API token without exposing it to browser JavaScript or `dist/` artifacts.

5. **Console does not become the production deployment/runtime owner.** Console surfaces observe environment and provisioning state; they do not host, proxy, or deploy generated apps in production.

6. **Future production runtime must reuse the existing Client API / BFF / auth contract.** The canonical path remains `generated app -> server-side proxy (Authorization: Bearer nex_cli_*) -> FastAPI BFF /api/v1/client/* -> OdooClient -> nexora.client_environment_service`. No second BFF, no second OdooClient, no second client DB resolver.

7. **No generic reverse proxy is introduced by 47.38.** Phase 47.38 adds no wildcard routing, no arbitrary model/method/SQL forwarding, and no generic Odoo RPC.

8. **A dedicated future deployment phase will make the production runtime decision.** That phase will select the runtime (e.g., platform-managed reverse proxy, Node SSR/edge function host, or Vite preview-subclass with proxy) and answer per-environment hosting, secret distribution, same-origin preservation, and lifecycle questions identified in the 47.38A audit.

## Consequences
- Positive: Production runtime remains a deliberate architectural decision with proper secret and routing design, not an ad-hoc Console addition.
- Positive: Existing development proxy and `nex_cli_*` secrecy guarantees are preserved.
- Positive: Console scope stays narrow and ownership-clean.
- Negative: Generated apps have no production hosting path until the deployment phase executes; Console shows production deployment as unavailable/not configured.

## References
- docs/reports/phase47_38A_console_runtime_ownership_audit.md (Option D)
- services/design/providers/react_provider.py (`_generate_vite_config`, `_generate_client_api_js`)
- services/launchers/vite_launcher.py
- nexora-console/backend paths (BFF remains Console-only)
