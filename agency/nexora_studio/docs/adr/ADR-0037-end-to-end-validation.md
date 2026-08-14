# ADR-0037: Phase 12A.1 End-to-End Integration & Runtime Validation

**Status:** Accepted  
**Date:** 2026-07-25  
**Deciders:** Nexora Studio Architecture Board  
**Technical Area:** AI Generation Pipeline, Rendering Layer, Automated Quality Assurance  

---

## 1. Context & Architectural Challenge

With the formal adoption of **ADR-0035 (AI Planning Layer Frozen)** and the introduction of the first production rendering provider in **Phase 12A (React Generation Engine)**, the Nexora Studio architecture split into two decoupled domains:
1. **The AI Planning Layer (Phases 11C–11F):** A provider-neutral domain producing `DesignBlueprint`, `DesignTokenSet`, `LayoutTree`, `AssetCollection`, and `ContentBundle`.
2. **The Rendering Layer (Phase 12A):** A provider-specific synthesis domain consuming a provider-neutral `RenderProject` to generate production target applications (e.g., React JSX, Vite config, CSS).

Prior to Phase 12A.1, each engine was validated independently through unit tests and mock harnesses. However, without full end-to-end runtime integration validation, critical failure modes could remain undetected:
- **Pipeline Bypassing:** Risk of rendering engines consuming raw requirements or blueprints while bypassing intermediate intelligence engines (Design System, Layout, Asset, or Content).
- **Data Leakage & Bounded Context Violation:** Risk of target-specific vocabulary (`jsx`, `react`, `vite`) leaking back into provider-neutral domain models.
- **Synthesized Code Build Failures:** Risk of generated JSX or CSS containing subtle syntax errors, unescaped brace literals, or missing imports that cause bundlers (Vite/Esbuild/Rollup) to fail during production compilation.
- **Client-Side Runtime Exceptions:** Risk of applications compiling successfully but failing at runtime in the browser due to blank DOM rendering, broken routing, or missing asset bindings.

---

## 2. Decision

We mandate and implement **Phase 12A.1 (End-to-End Integration & Runtime Validation)** as a permanent, automated validation gate required for all current and future rendering providers. 

The validation framework establishes four non-negotiable auditing stages across all six canonical web application archetypes (`landing`, `saas_dashboard`, `blog`, `ecommerce`, `contact`, `auth`):

### Stage 1: Render Model & Planning Contract Verification
- Every rendering engine must implement a two-stage transformation: `Planning Models ➔ Render Model (RenderProject) ➔ Code Synthesis`.
- The intermediate `RenderProject` must be serialized and audited to confirm **zero dropped planning properties** (100% token, route, layout, and content preservation) and **zero target runtime terms** in domain keys or metadata.

### Stage 2: Workspace Management & Code Synthesis Audit
- Generated project filesystem dictionaries must be synthesized into isolated temporary workspaces (`.tmp_val_workspace/{project_name}`).
- To eliminate repetitive network overhead during QA cycles, all workspace projects must link to a shared dependency cache (`shared_cache/node_modules`) via directory junctions or symlinks.

### Stage 3: Runtime Toolchain & Live Server Verification
- Every generated project must undergo live Node.js toolchain execution via `npm run build`. Compilers must exit with code `0` and generate valid static bundles in `dist/`.
- Every project must boot a live local web server (`npm run preview` on dynamic local ports) and verify that HTTP GET requests return status `200 OK` with valid HTML root mount points (`<div id="root">`).

### Stage 4: Playwright Headless Visual & Browser Health Audit
- An automated browser automation harness using the **Playwright Python API (`sync_playwright`)** must connect to the live preview servers and navigate primary application routes.
- The harness must attach real-time runtime listeners to assert **zero browser console errors** (`msg.type == "error"`), **zero unhandled page exceptions**, and **zero network asset loading failures**.
- The harness must assert non-blank DOM rendering and capture full-page visual screenshot artifacts for regression reporting.

---

## 3. Consequences

### Positive
- **Guaranteed Production Readiness:** Nexora Studio guarantees that generated applications not only conform to architectural contracts but actually build and run in real web browsers without client-side errors.
- **Regression Proofing:** By executing the 56-test regression suite and Playwright visual audits against canonical golden references, any future modifications to planning or rendering engines will be caught immediately if they alter visual layouts or introduce build warnings.
- **Clean Architecture Enforcement:** ADR-0035 compliance is mechanically enforced; developers cannot introduce framework-specific hacks into planning domain models without failing the Stage 1 neutrality audit.

### Negative / Trade-offs
- **Test Suite Execution Overhead:** Executing Node.js builds (`vite build`) and launching headless Chromium instances across six archetypes adds ~20 seconds of runtime execution time to the full validation suite. This is mitigated by our `WorkspaceManager` shared caching and asynchronous subprocess management.
- **Environment Toolchain Dependency:** Running the runtime validation suite requires Node.js, `npm`, and Playwright Chromium browsers to be installed in the local validation environment.

---

## 4. Compliance & Verification

Compliance with ADR-0037 is verified by running the complete automated validation suite:
```bash
# 1. Execute Domain Engine Regression & Stage 1 Render Model Audit
python -m unittest tests/test_design_blueprint_engine.py tests/test_design_system_engine.py tests/test_layout_engine.py tests/test_asset_content_engine.py tests/test_penpot_live_integration.py tests/test_react_generation_engine.py tests/test_end_to_end_pipeline.py tests/test_render_model_validation.py

# 2. Execute Stage 2 & Stage 3 Runtime Build and Server Audit
python -m unittest tests/test_runtime_validation.py

# 3. Execute Stage 4 Playwright Headless Visual & Browser Audit
python -m unittest tests/test_playwright_validation.py
```

All suites must exit with status `OK` (0 errors, 0 failures) before marking any generation milestone complete.
