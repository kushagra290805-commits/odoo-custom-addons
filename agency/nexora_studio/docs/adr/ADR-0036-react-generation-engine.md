# ADR-0036: React Generation Engine Foundation & Provider-Neutral Render Model

**Status:** Approved & Implemented  
**Date:** July 2026  
**Decision Makers:** Nexora Studio Technical Steering Committee, Lead AI Architecture Team  
**Governing ADR:** [ADR-0035 (AI Planning Layer Frozen)](ADR-0035-ai-planning-layer-frozen.md)  

---

## 1. Context & Problem Statement

Following the formal freezing of the provider-neutral AI Planning Layer under **ADR-0035** (covering Phases 11C–11F: Design Blueprints, Design Systems, Layout Intelligence, Asset Planning, and Content Intelligence), Nexora Studio requires its first production-ready **Rendering Provider**. 

The goal of Phase 12A is to implement a **React Generation Engine** that translates validated AI planning blueprints into modular, production-ready React web applications. However, translating directly from complex AI planning models (`DesignBlueprint`, `LayoutTree`, `ContentPlan`, etc.) into target framework syntax (JSX, React Router, CSS) presents significant architectural risks:
1. **Domain Pollution:** Introducing framework-specific terms (e.g., `jsx`, `react`, `react_router`, `vite`, `nextjs`, `css`, `html`) into the planning layer violates provider-neutrality.
2. **Coupling:** Direct generation couples the orchestration layer to React, making future expansion to other rendering targets (e.g., static HTML/CSS, Flutter, native mobile, Odoo XML) difficult and error-prone.
3. **Inconsistent Routing & Structure:** Without a standardized rendering intermediary, downstream generators might produce monolithic, unstructured code rather than clean, modular component hierarchies.

---

## 2. Decision

We decide to implement the **React Generation Engine Foundation (`ReactGenerationEngine`)** in `services/design/react_generation_engine.py` as an authoritative `DesignProvider` implementation governed by a **Provider-Neutral Render Model (`render_domain.py`)**.

### Key Architectural Rules & Contracts:

1. **Provider-Neutral Render Model Intermediary:**
   Before synthesizing target-specific code, all rendering providers must transform frozen planning models into the standardized **Render Model** (`services/design/render_domain.py`). This domain model includes:
   - `RenderProject`: The root rendering aggregate.
   - `RenderPage` & `RenderRoute`: Page definitions and routing topologies.
   - `RenderLayout` & `RenderComponent`: Visual hierarchy and component packaging.
   - `RenderToken`, `RenderAsset`, & `RenderContent`: Data-bound styling, media, and copy.
   
   *Strict Governance:* The Render Model must NEVER reference JSX, React, React Router, CSS, HTML, Vite, Next.js, or any target-specific runtime keywords.

2. **Two-Stage Generation Pipeline:**
   The `ReactGenerationEngine` executes a two-stage process:
   - **Stage 1 (`build_render_project`):** Validates and converts the frozen `DesignBlueprint` (with 11D/11E/11F metadata) into a clean `RenderProject`.
   - **Stage 2 (`generate_react_project`):** Translates the `RenderProject` into a modular file payload containing `package.json`, `vite.config.js`, `index.html`, entry point scripts (`src/main.jsx`, `src/App.jsx`, `src/routes.jsx`), styling tokens (`src/styles/tokens.css`), data config (`src/config/assets.js`, `src/config/content.js`), layouts (`src/layouts/`), components (`src/components/`), and pages (`src/pages/`).

3. **Universal Archetype Support:**
   The engine natively supports all 6 required application archetypes: `landing`, `saas_dashboard`, `blog`, `ecommerce`, `contact`, and `auth`. Each archetype receives tailored layout wrapping and component synthesis.

4. **Zero Prohibited Runtime Engines:**
   Synthesized React projects must be lightweight and standards-compliant. The engine strictly forbids generating references to Three.js (`three`, `react-three-fiber`), runtime animation engines (`gsap`, `framer-motion`), or raw static HTML generation engines.

5. **No Invented Granular Payloads:**
   Granular intra-file mutations (`create_page`, `create_component`, `update_component`, `export_svg`, etc.) raise explicit `NotImplementedError`s and are classified under `unsupported_granular_operations_deferred`. This enforces compliance with our rule against inventing simulated canvas responses.

6. **Orchestrator Routing & 4-Tier Precedence:**
   The engine is integrated into `DesignOrchestrator.get_provider()` and registered as `nexora.react_generation_engine`. When invoked via `execute_blueprint(..., provider_name='react')`, the orchestrator executes the full 5-stage AI planning pipeline before routing to Stage 1 and Stage 2 of the React engine. Configuration resolution strictly follows the 4-tier precedence hierarchy (Explicit Config $\rightarrow$ Odoo System Parameter $\rightarrow$ Environment Variable $\rightarrow$ Localhost Default).

---

## 3. Consequences

### Positive
- **Architectural Isolation:** The AI Planning Layer remains 100% frozen and untouched. Adding React generation introduced zero breaking changes or framework leakage to existing domains.
- **Future-Proofing:** The `Render Model` is now established as the reusable contract for all future rendering engines (e.g., HTML/CSS, Flutter, Native Mobile).
- **Clean Modular Code:** Generated React code is production-ready, cleanly separated into reusable components and layouts, and styled with standards-compliant CSS variables.
- **100% Verified Quality:** Automated verification suite (`tests/test_react_generation_engine.py`) achieves 100% pass rate across all 33 tests alongside Phase 11C–11F regressions.

### Negative / Trade-offs
- **Deferred Granular Editing:** Interactive canvas-style editing (e.g., drag-and-drop component tweaking) is deferred to offline code renderer tools rather than handled in-memory by the React engine.

---

## 4. Compliance & Verification

Compliance is continuously enforced via `tests/test_react_generation_engine.py`:
```bash
python -m unittest tests/test_react_generation_engine.py tests/test_asset_content_engine.py tests/test_layout_engine.py tests/test_design_system_engine.py tests/test_design_blueprint_engine.py
```
Any PR that attempts to introduce React/JSX keywords into planning models or bypass the two-stage Render Model pipeline will fail code review and CI verification.
