# ADR-0039: Provider Interface & Multi-Renderer Foundation

**Status:** Accepted  
**Date:** 2026-07-26  
**Phase:** Phase 12C — Provider Interface & Multi-Renderer Foundation  

---

## 1. Context & Problem Statement

In Phase 12A and Phase 12B, Nexora Studio established a robust React Generation Engine capable of synthesizing full, production-ready React 18 applications powered by a reusable Component Library and design token bindings. However, the synthesis logic was coupled directly to the `ReactGenerationEngine` class. 

As Nexora Studio expands toward multi-channel and multi-framework design generation (e.g., Vue 3, Angular 17, Flutter Web, Vanilla HTML5, and 3D WebGL via React Three Fiber), the architecture required a clean abstraction boundary that isolates target-specific rendering engines from the upstream AI planning layer.

To prevent architectural degradation and maintain strict separation of concerns, this phase required an authoritative **Provider Interface** and **Multi-Renderer Foundation** without modifying or destabilizing the existing AI planning engines or frozen contracts established in previous phases.

---

## 2. Architectural Constraints & Governance

To ensure system stability, Phase 12C strictly adhered to the following architectural directives:

1. **Frozen Upstream Contracts (ADR-0035, ADR-0037, ADR-0038):** The Requirements Engine, Builder Session, Blueprint Engine, Design System Engine, Layout Intelligence Engine, Asset Planning Engine, Content Intelligence Engine, Render Model (`RenderProject`), and Component Manifest (`ComponentManifest`) must remain untouched.
2. **Strict Rendering Separation:** No specific rendering framework syntax (JSX, React Router, Vue Composition API, Dart widgets) may bleed into domain models or the provider registry.
3. **Phase 12C Scope Limitation:** Only the provider abstraction layer and the React provider migration were permitted. Future targets (`vue`, `angular`, `flutter`, `html`, `react_three_fiber`) must be registered as architectural stubs raising `NotImplementedError` upon invocation.

---

## 3. Decision & Technical Architecture

We have implemented a comprehensive Provider Abstraction Layer consisting of five core architectural pillars:

### 3.1. Authoritative `RenderingProvider` Interface (`rendering_provider.py`)

We defined an abstract base class (`RenderingProvider`) that enforces a modular, granular generation contract across all target implementations:
- `get_metadata() -> ProviderMetadata`: Exposes provider identity, display names, capabilities, versioning, and supported features.
- `generate_project(context: RenderingContext) -> Dict[str, Any]`: Orchestrates full project generation, returning structural code dictionaries.
- `generate_layouts(context: RenderingContext) -> Dict[str, str]`: Synthesizes hierarchical layout containers.
- `generate_components(context: RenderingContext) -> Dict[str, str]`: Synthesizes atomic, molecule, and organism UI components.
- `generate_pages(context: RenderingContext) -> Dict[str, str]`: Synthesizes page views composing section components and layouts.
- `generate_routes(context: RenderingContext) -> Dict[str, str]`: Synthesizes modular routing tables and root application containers.
- `generate_assets(context: RenderingContext) -> Dict[str, str]`: Synthesizes asset registries and static binding configurations.
- `generate_design_tokens(context: RenderingContext) -> Dict[str, str]`: Synthesizes authoritative CSS token stylesheets.

### 3.2. Expanded 5-Part Validation Contract

Replacing a single, monolithic output check, every provider must implement a 5-part validation contract that spans the entire software lifecycle:
1. `validate_manifest(context)`: Verifies that the upstream `ComponentManifest` satisfies provider-specific prop and slot requirements.
2. `validate_project(context, project_structure)`: Verifies structural integrity, required file presence, module syntax health, and absence of prohibited dependencies.
3. `validate_build(context, build_output)`: Validates compile-time bundling health (e.g., Vite/esbuild production builds).
4. `validate_runtime(context, runtime_info)`: Validates server execution, HTTP responsiveness (200 OK), and DOM hierarchy health.
5. `validate_artifacts(context, artifacts)`: Validates visual evidence and accessibility compliance (e.g., Playwright headless browser screenshots).

### 3.3. Unified `RenderingContext` Encapsulation

We introduced `RenderingContext` as the sole data payload passed into provider generation and validation methods. It encapsulates:
- `render_project`: Authoritative `RenderProject` domain tree.
- `manifest`: Resolved `ComponentManifest` describing props, slots, and design bindings.
- `metadata`: Optional target `ProviderMetadata`.
- `tokens` & `assets`: Authoritative collections of design tokens and media assets.
- `output_config` & `feature_flags`: Target directory specifications and toggleable capabilities (e.g., accessibility generation, dark mode).

### 3.4. Dynamic `RenderingProviderRegistry` (`provider_registry.py`)

We implemented a centralized, lazy-loading registry responsible for target discovery and resolution:
- **Capability Querying (`ProviderCapabilityModel`):** Exposes boolean capability flags (`layouts`, `routing`, `forms`, `animations`, `design_tokens`, `accessibility`, `static_export`, `ssr`) allowing upstream planners to query target features before generation.
- **Provider Versioning (`ProviderVersioning`):** Tracks `provider_version`, `api_version`, and `manifest_version` for future compatibility grading.
- **Lazy Resolution:** Eliminates circular import penalties by resolving provider classes on-demand via `get_provider(provider_id)`.
- **Deferred Target Stubs:** Registers authoritative metadata and capabilities for future targets (`vue`, `angular`, `flutter`, `html`, `react_three_fiber`) while enforcing a clean `NotImplementedError` barrier upon execution.

### 3.5. React Provider Delegation & Refactoring (`react_provider.py`)

We migrated the synthesis logic from `ReactGenerationEngine` into `ReactRenderingProvider` implementing the full `RenderingProvider` contract. `ReactGenerationEngine.generate_application()` was refactored into an orchestration facade that delegates 100% of code generation to `RenderingProviderRegistry.get_provider("react")`. Furthermore, barrel export generation (`src/components/index.js`) was unified to eliminate duplicate symbol export build failures.

---

## 4. Verification & Validation Evidence

The Multi-Renderer Foundation was verified via an automated test suite and regression testing:
1. **Interface Contract Verification (`tests/test_provider_interface.py`):** Verified ABC instantiation rules, 5-part validation method presence, capability model defaulting, versioning serialization, and `RenderingContext` factory encapsulation.
2. **Registry Discovery & Resolution (`tests/test_provider_registry.py`):** Verified support querying across all 6 registered targets, dynamic registration of custom provider subclasses, type safety enforcement, and deferred `NotImplementedError` assertion for stubs.
3. **React Provider Synthesis & Validation (`tests/test_react_provider.py`):** Verified modular granular generators, clean barrel exports without symbol duplication, 100% compliance with the 5-part validation contract, and full project synthesis for React 18 applications.
4. **Full Architectural Regression (`tests/test_*.py`):** Executed comprehensive regression suites across all 16 core planning, design, and rendering modules (87 automated tests), achieving a 100% pass rate with zero regressions across all 6 application archetypes.
5. **Visual Validation (`test_playwright_validation.py`):** Confirmed headless browser visual rendering and screenshot evidence generation across all archetypes.

---

## 5. Consequences & Future Roadmap

### Positive Consequences
- **Unlocking Multi-Target Design:** Upstream AI planning engines can now design interfaces for web, mobile, and 3D canvas targets using a single, unified workflow.
- **Zero Regression Migration:** Existing React generation pipelines continue operating seamlessly with zero external API changes.
- **Enhanced Testability:** Granular generation methods allow targeted unit testing of components, layouts, or tokens in isolation without synthesizing entire projects.

### Future Roadmap
- **Phase 13:** Implement `VueRenderingProvider` (Vue 3 + Vite + Pinia + Composition API).
- **Phase 14:** Implement `FlutterRenderingProvider` (Flutter Web + Material 3 widget trees).
- **Phase 15:** Implement `R3FRenderingProvider` (React Three Fiber 3D WebGL scene synthesis).
