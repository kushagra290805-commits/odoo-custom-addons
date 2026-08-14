# Connector Migration Roadmap
## Phase 26 — Universal Connector Platform Foundation

**Purpose:** Documents how every existing provider becomes a connector in future phases.  
**Constraint:** No actual migration in Phase 26. Architecture only.

---

## Migration Principles

1. **No forced migration.** Existing providers continue working until their connector counterpart is certified.
2. **Connector first.** The connector implementation is built and verified before the legacy provider is deprecated.
3. **Capability namespace continuity.** The capability namespace registered by the connector must exactly match the namespace currently used by the legacy provider (e.g., `mcp.search` stays `mcp.search`).
4. **Dark launch.** Each connector is registered in the registry and can be tested via `ConnectorRuntime.dispatch()` before the UCEL is configured to route to it.
5. **Rollback available.** Because connectors and legacy providers coexist until the switch, any failing connector migration can be rolled back by removing the connector from the registry.

---

## Migration Phase Map

### Connector Platform Phase 1 (CP Phase 1) — Foundation Hardening
**Target:** Phase 27

| Item | Action |
|------|--------|
| `SecretsProvider` implementation | Implement `OdooSecretsStore` backed by encrypted `nexora.connector_configuration` |
| `CapabilityResolver` hardcode removal | Replace hardcoded MCP map with registry-driven query |
| `ConnectorPlatformBootstrap` wiring | Complete startup wiring and hook into `post_init_hook` |
| `NullConfigurationAdapter` → real adapter | Wire real `ConfigurationRuntimeAdapter` to GenerationRuntime |

---

### Connector Platform Phase 2 (CP Phase 2)

| Provider | Current Model | Target Connector Type | Connector ID | Notes |
|----------|--------------|----------------------|-------------|-------|
| **GitHub** | `nexora.github_provider` | `repository` | `com.nexora.github` | OAuth2 auth, `github.*` namespace |
| **Git (local)** | `nexora.git_runtime` | `repository` | `com.nexora.git_local` | SSH key or none, `git.*` namespace |
| **MCP (all)** | MCP session in builder | `mcp` | `com.nexora.mcp.*` | Requires real MCP transport (PRE-004) |

**Prerequisite for MCP:** PRE-004 (complete MCP transport layer) must be resolved.

---

### Connector Platform Phase 3 (CP Phase 3)

| Provider | Current Model | Target Connector Type | Connector ID | Notes |
|----------|--------------|----------------------|-------------|-------|
| **Gosom** | `nexora.gosom_provider` | `rest` | `com.nexora.gosom` | API key, scraping REST |
| **Firecrawl** | `nexora.firecrawl_provider` | `rest` | `com.nexora.firecrawl` | API key, web crawl REST |
| **Tavily** | `nexora.tavily_provider` | `rest` | `com.nexora.tavily` | API key, search REST |
| **Context7** | `nexora.context7_provider` | `sdk` | `com.nexora.context7` | Python SDK wrapper |
| **Penpot** | `nexora.penpot_provider` | `design` | `com.nexora.penpot` | API key + OAuth2 |
| **Spline** | `nexora.spline_provider` | `design` | `com.nexora.spline` | REST |
| **REST APIs (generic)** | Direct requests in engines | `rest` | Dynamic | Per-API connector |
| **GraphQL APIs** | N/A | `graphql` | Dynamic | Per-API connector |
| **Python Packages** | `pip` calls in subprocess | `sdk` | Dynamic | Per-package connector |

---

### Connector Platform Phase 4 (CP Phase 4)

| Provider | Current State | Target Connector Type | Notes |
|----------|-------------|----------------------|-------|
| **Figma** | Not integrated | `design` | OAuth2 + REST |
| **Docker** | Not integrated | `docker` | Requires Docker daemon access |
| **CLI Tools** | subprocess calls | `cli` | Per-tool connector with env isolation |
| **Deployment targets** | N/A | `deployment` | Vercel, Netlify, S3 |

---

## Migration Execution Pattern

For each provider migration:

```
Phase N:
1. Implement ConnectorTypeDescriptor (already done in Phase 26 for all types)
2. Implement ConnectorExecutionAdapter for the specific type
3. Register connector in nexora.connector (via seed data or admin UI)
4. Implement credentials in OdooSecretsStore (API keys, OAuth2 tokens)
5. Run PIAT with connector active
6. Verify E2E generation with connector providing the capability
7. Dark launch: configure UCEL to route 5% of traffic to connector
8. Monitor for 48 hours
9. Switch UCEL to route 100% to connector
10. Deprecate legacy provider model (mark for Phase N+1 deletion)
```

---

## Backward Compatibility Contract

During migration phases:
- Legacy provider models remain in `models/` and continue to function
- Capability namespaces are not changed
- No generation engine is modified
- Connectors are additive — they extend, not replace, the execution path
- Legacy providers are only deprecated after connector certification
