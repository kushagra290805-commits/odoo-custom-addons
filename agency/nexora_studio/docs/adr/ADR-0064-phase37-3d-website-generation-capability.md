# ADR-0064: Phase 37 3D Website Generation Capability Expansion

## Context & Problem Statement
Phase 37 introduces 3D website generation capabilities into Nexora Studio. The challenge is introducing complex spatial, WebGL, and Three.js capabilities without violating the established Universal Connector Platform (UCP) constraints or creating parallel architectural stacks. We need a 3D solution that operates strictly within the existing AI orchestration and capability resolution bounds, using only verified no-key UCP connections.

## Decision

1. **Existing Architecture Reused:** 
   We will completely reuse the existing `GenerationPipeline` and `ConnectorPlatform`. 3D component synthesis will be treated as standard component generation managed by the existing `core.orchestration` runtime, not a separate pipeline.

2. **Canonical Integration Point:** 
   The multi-renderer `RenderingProviderRegistry` already contains a stub for `react_three_fiber`. We will implement this target (or extend the standard `react_provider.py`) rather than bypassing the provider layer. The restriction blocking `three` in `react_provider.py` will be modified or isolated to allow authorized 3D rendering profiles.

3. **Approved Capability Sources:** 
   We will rely exclusively on the Phase 37 Safe Connector Set: `tavily_mcp.tavily_search` and `tavily_mcp.tavily_extract`. No other external API connectors will be invoked.

4. **Tavily's Exact Role:** 
   Tavily will ONLY be used for necessary real-time web research regarding 3D library syntax (e.g., retrieving up-to-date `@react-three/fiber` or `@react-three/drei` documentation/examples) to ground the AI generation. It will NOT be used to scrape 3D models or act as a generic tool demonstration.

5. **Why No New Connector Architecture is Required:** 
   The UCP already supports arbitrary tool execution via `McpCapabilityDiscoveryService` and `ConnectorRuntime.dispatch()`. The generation pipeline already supports AI orchestration via `execute_workflow`. 3D code generation is fundamentally just text/AST generation; it does not require a bespoke orchestration layer, merely the correct React Three Fiber context.

6. **3D Technology Choice:** 
   Based on existing repository traces (`react_three_fiber` stub, `three` prohibitions in React provider), the technology of choice is **React Three Fiber (R3F) + Drei**. 
   We explicitly reject the legacy `spline_provider.py` approach as it relies on a local node sandbox bypassing standard generation ASTs and UCP MCP orchestration.

7. **Data/Control Flow:**
   User Requirement -> `RequirementAnalyzer` (identifies 3D) -> `PlanningWorkflow` -> `PlatformRuntime` (AI Orchestrator) -> AI uses `tavily_mcp` for context -> AI generates R3F React components -> `DesignTranslator` -> `react_three_fiber` Rendering Provider -> Generated Artifacts.

8. **Generated Artifact Ownership:** 
   All synthesized `.jsx` and `.css` files remain owned by the standard DocumentModel / Project Workspace. The generated website artifacts are indistinguishable from 2D artifacts from a storage and lifecycle perspective.

9. **Security Boundaries:** 
   No new boundaries. The AI executes within the existing sandbox environment, and Tavily operates via the locked-down UCP standard I/O.

10. **Credential Boundaries:** 
    Execution is strictly anonymous/no-key. No API keys are required for R3F generation, and Tavily operates in its verified keyless mode.

11. **Testing Strategy:** 
    Verification will pass standard React layout validations, specifically checking that R3F components cleanly mount without throwing unhandled exceptions in the validation AST parser.

12. **Explicit Non-Goals:** 
    - No direct GLTF/GLB binary synthesis (AI generates declarative R3F scenes, not raw binary models).
    - No integration of credential-gated platforms like Spline or PlayCanvas.
    - No creation of a bespoke "3D Capability Router".

13. **Rollback Strategy:** 
    If R3F generation destabilizes standard React output, we revert the `RenderingProviderRegistry` back to the stub and restore the "prohibited `three`" block in `react_provider.py`.

## Implementation Addendum (Phase 37.1)

- **Canonical 3D Renderer**: React Three Fiber is explicitly designated as the canonical 3D renderer via the `react_three_fiber` RenderingProvider.
- **Companion Libraries**: Drei (`@react-three/drei`) is an approved companion library where appropriate.
- **Scope**: 3D mode is explicitly scoped to the `react_three_fiber` provider. 
- **Standard Mode Validation**: Standard React generation remains subject to its existing validation policy (strict 2D bounds). There is no global relaxation of React security/validation rules.
- **Enrichment**: Tavily is optional enrichment only. Generation must proceed without it if capability discovery falls back.
- **Legacy Path**: Spline remains non-canonical/legacy. It is not deleted yet, but the primary Phase 37 path does not depend on it.

## Implementation Addendum (Phase 37.2) — Multi-3D Renderer Support

### Decisions

1. **Dual 3D Renderers**: React Three Fiber and Spline are both supported 3D rendering technologies under the canonical `RenderingProviderRegistry`.
2. **Peer Providers**: They are independent peer providers (`react_three_fiber` and `spline`), not parent/child or wrapper/wrapped.
3. **R3F Role**: R3F is the canonical procedural/code-generated 3D provider (Three.js scenes constructed via JSX).
4. **Spline Role**: Spline is the canonical embedded/scene-based 3D provider (pre-authored scenes referenced by URL).
5. **Coexistence**: Both may coexist in one generated website. A project may contain R3F components and Spline components simultaneously.
6. **React Integration**: Spline integration uses the official React package (`@splinetool/react-spline`) rather than the legacy Node sandbox provider (`models/spline_provider.py`).
7. **Legacy Path**: `models/spline_provider.py` remains legacy and is NOT part of the canonical generation path. It is referenced only by historical verification/test scripts.
8. **Tavily**: Tavily remains optional enrichment only. No Tavily dependency exists in either 3D provider.
9. **Credential Policy**: No Spline API credential is required merely to render a Spline scene whose scene URL is already supplied by the project/user. The `@splinetool/react-spline` package loads scenes client-side via public URLs.

### Scene Source Security Policy

- Remote scene URLs must use HTTPS
- Remote scene URLs must reference approved Spline hosting domains (`prod.spline.design`, `draft.spline.design`, `app.spline.design`, `my.spline.design`)
- Remote scene URLs must have valid Spline extensions (`.splinecode`, `.spline`)
- Local/relative paths to `.splinecode` assets are supported for self-hosted scenes
- `javascript:` and `data:` URI schemes are explicitly rejected
- Scene URLs are NOT hard-coded by the provider; they come from validated project/generation input

### Provider-Aware Validation

| Provider Mode      | `three` | `@react-three/*` | `@splinetool/*` | `playcanvas` | `babylon` |
|--------------------|---------|-------------------|-----------------|--------------|-----------|
| `react` (standard) | ❌      | ❌                | ❌              | ❌           | ❌        |
| `react_three_fiber`| ✅      | ✅                | ✅ (peer)       | ❌           | ❌        |
| `spline`           | ✅ (peer)| ✅ (peer)        | ✅              | ❌           | ❌        |
