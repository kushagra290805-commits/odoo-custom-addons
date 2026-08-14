# ADR 0030: Live Penpot RPC Integration & Schema Boundaries

**Status**: Accepted  
**Date**: 2026-07-25  
**Context**: Nexora Studio Architecture — Phase 11B Live Penpot Integration  

---

## 1. Context & Problem Statement

In Phase 8A, Nexora Studio established the vendor-neutral **Design Provider Framework** (`DesignProvider`, `DesignOrchestrator`) and eradicated all dependencies on proprietary desktop design tools (Figma). A stubbed `PenpotDesignProvider` was introduced to prepare for self-hosted, open-source design federation.

In Phase 11B, the framework required runtime integration with the live, self-hosted Penpot instance running at `http://localhost:9001`. To ensure production readiness, maintainability, and architectural cleanliness, four key challenges needed to be addressed:
1. Preventing hardcoded server locations across environments (development, staging, production).
2. Avoiding tight coupling to a single authentication scheme (such as Personal Access Tokens).
3. Maintaining system stability when interacting with Penpot's internal RPC-style architecture, where granular intra-file mutations (`update-file`) rely on undocumented, frontend-internal changeset schemas.
4. Protecting Builder Session workflows against transient network glitches or backend restarts.

---

## 2. Decision

We adopt the following architectural design for live Penpot runtime integration:

### 1. 4-Tier Configuration Precedence
The base URL, connection timeouts, and read timeouts are resolved dynamically through a strict 4-tier hierarchy:
- **Tier 1 (Explicit)**: Dictionary parameter passed directly to method/provider (`config.get('url')`).
- **Tier 2 (Database/Odoo)**: Odoo system parameter (`ir.config_parameter.sudo().get_param('nexora.penpot_url')`).
- **Tier 3 (OS Environment)**: Environment variable (`PENPOT_PUBLIC_URI` or `PENPOT_URL`).
- **Tier 4 (Default)**: Fallback to `http://localhost:9001`.

### 2. Authentication Abstraction (`penpot_auth.py`)
We decouple authentication from the HTTP transport by introducing the abstract `PenpotAuthenticator` interface.
- We implement `PATAuthenticator` for programmatic Personal Access Token workflows (`Authorization: Token <key>`).
- We define `SessionAuthenticator` as an architectural stub to support future cookie-based web login (`penpot-session`) and enterprise SSO federation without modifying provider logic.

### 3. Strict Schema Compliance (Prohibition of Invented Payloads)
We establish a strict boundary between stable top-level RPC endpoints and internal file mutation engines:
- **Supported Top-Level Operations**: Methods mapping to stable, verified RPC endpoints (`authenticate`, `create_workspace`, `list_projects`, `create_project`, `get_project`, `export_svg`, `export_png`, `export_pdf`, `export_assets`, `validate_design`) are fully implemented and executed via `PenpotAPIClient`.
- **Unsupported Granular Mutations**: In accordance with the rule *"If a capability is unavailable through supported interfaces, report it explicitly instead of implementing a brittle workaround"*, all granular intra-file mutation methods (`create_page`, `create_frame`, `create_component`, `update_component`, `delete_component`, `create_design_tokens`, `apply_theme`, `import_assets`, `sync_project`) raise a descriptive `NotImplementedError`. Inventing undocumented `update-file` changeset payloads is strictly prohibited.

### 4. Resilient Transport Engine (`penpot_client.py`)
We encapsulate all HTTP communication inside `PenpotAPIClient`, featuring:
- Automatic interception of transient HTTP errors (500, 502, 503, 504) and timeouts.
- Exponential backoff retry engine (up to 3 retries starting at 0.5s).
- Pre-flight connection reachability and health validation (`validate_connection()`).
- Structured logging via Python's standard `logging` module.

---

## 3. Consequences

### Positive
- **Zero Lock-in / Environmental Agility**: The system seamlessly transitions between localhost development and enterprise Odoo/Docker deployments via database or environment configuration.
- **Enterprise Extensibility**: New auth schemes (OAuth, SAML, Cookie sessions) can be plugged in by creating a new `PenpotAuthenticator` subclass.
- **High Reliability**: Builder Session generation is resilient against transient network blips during design asset retrieval or project creation.
- **Architectural Safety**: Prohibiting invented mutation payloads guarantees that Nexora Studio will not break when Penpot updates its internal frontend-backend synchronization schema.

### Negative / Limitations
- Granular creation of design canvas elements (pages, frames, components) directly from code remains unsupported via the standard RPC client until Penpot publishes an official, stable API specification or MCP server integration for granular file mutations.
