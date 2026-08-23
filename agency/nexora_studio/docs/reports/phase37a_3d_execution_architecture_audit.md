# Phase 37A — 3D Execution Architecture Audit

**Date:** 2026-08-17
**Objective:** Perform a read-only trace of the existing architecture to determine owners, callers, and reuse opportunities for the 3D website generation vertical slice.

## Component Trace

### 1. AssetPlanningEngine
- **Responsibility:** Determines which assets a project requires based on project type/domain.
- **Current Owner:** `AssetPlanningEngine` (Design Service)
- **Callers:** `RequirementAnalyzer`, `Planner`
- **Inputs:** `ProjectObjective`, `ComponentArchetypes`
- **Outputs:** `AssetRequirement` definitions (e.g., `3d_asset` with format `glb`).
- **Missing Behavior:** Actual asset resolution logic is missing; currently it only *plans* the requirement.
- **Reuse Opportunity:** Keep as the absolute authority for declaring 3D requirements.

### 2. BlueprintValidator
- **Responsibility:** Validates design blueprints against constraints (payload limits, accessibility).
- **Current Owner:** `BlueprintValidator`
- **Callers:** `Planner`, `DesignOrchestrator`
- **Inputs:** `DesignBlueprint`
- **Outputs:** Validation warnings/errors.
- **Missing Behavior:** Lacks explicit validation rules for WebGL capabilities (e.g., max polygon count, DRACO compression flags).
- **Reuse Opportunity:** Extend existing payload size constraints for GLB files.

### 3. ComponentIntelligence
- **Responsibility:** Maps user intent to structural component archetypes and variants.
- **Current Owner:** `ComponentIntelligence`
- **Callers:** `Planner`
- **Inputs:** Semantic keywords.
- **Outputs:** Supported component definitions (e.g., `hero-product` optionally requiring `generic_3d_asset`).
- **Missing Behavior:** No R3F component equivalents exist.
- **Reuse Opportunity:** Seamlessly integrates 3D requirements at the component level without changing layout algorithms.

### 4. provider_registry
- **Responsibility:** Maintains available rendering implementations.
- **Current Owner:** `RenderingProviderRegistry`
- **Callers:** `WorkspaceGeneratorEngine`
- **Inputs:** Provider ID string (`"react"`, `"react_three_fiber"`).
- **Outputs:** Instantiated `RenderingProvider` class.
- **Missing Behavior:** `react_three_fiber` is currently a metadata stub with no backing implementation class.
- **Reuse Opportunity:** Canonical entry point for instantiating the new 3D provider.

### 5. RenderingProvider & react_provider
- **Responsibility:** Base contract for code generation, and the React-specific implementation.
- **Current Owner:** `RenderingProvider`, `ReactRenderingProvider`
- **Callers:** `WorkspaceGeneratorEngine`
- **Inputs:** `DesignBlueprint`, Workspace Paths.
- **Outputs:** Synthesized file system structure (React `.jsx`/`.tsx` files).
- **Missing Behavior:** `ReactRenderingProvider` explicitly prohibits 3D canvas references to prevent hallucinations.
- **Reuse Opportunity:** `ReactThreeFiberProvider` can inherit `RenderingProvider` and reuse React's baseline component syntax generation while adding `<Canvas>` semantics.

### 6. react_three_fiber provider/stub
- **Responsibility:** R3F-specific React code generation.
- **Current Owner:** `provider_registry` (Stub)
- **Callers:** None yet.
- **Inputs:** `DesignBlueprint`.
- **Outputs:** R3F code.
- **Missing Behavior:** The entire implementation class is missing.
- **Reuse Opportunity:** It will be built strictly as an extension of `RenderingProvider`.

### 7. AssetContentEngine
- **Responsibility:** Resolves and validates asset content and metadata.
- **Current Owner:** `AssetContentEngine`
- **Callers:** `DesignOrchestrator`
- **Inputs:** `AssetRequirement`
- **Outputs:** `AssetDefinition` with real paths.
- **Missing Behavior:** Has no logic to execute an external MCP call to download a `.glb`.
- **Reuse Opportunity:** Can be wired to `ConnectorRuntime` to fetch assets, keeping the domain model clean.

### 8. WorkspaceGeneratorEngine
- **Responsibility:** Materializes the project template and invokes the renderer.
- **Current Owner:** `WorkspaceGeneratorEngine`
- **Callers:** `GenerationEngine`
- **Inputs:** `GenerationSession`, `DesignBlueprint`
- **Outputs:** Generated workspace on disk.
- **Missing Behavior:** Fully capable, but needs `react_three_fiber` registered to succeed.
- **Reuse Opportunity:** Canonical orchestrator; requires ZERO structural changes.

### 9. Existing Browser Verification
- **Responsibility:** Playwright-based MCP tool for rendering HTML and taking snapshots.
- **Current Owner:** `mcp.playwright`
- **Callers:** Verification scripts.
- **Inputs:** URL, action (`snapshot`).
- **Outputs:** Playwright execution results.
- **Missing Behavior:** Not currently invoked automatically to verify WebGL context or R3F `<Canvas>` mounting.
- **Reuse Opportunity:** Extend Playwright MCP capabilities to include `page.waitForSelector('canvas')` and WebGL context assertions.

### 10. ConnectorRuntime, Dispatcher & CapabilityIndex
- **Responsibility:** Canonical Universal Connector Platform for executing external tools.
- **Current Owner:** UCP
- **Callers:** Verification scripts (currently), `AssetContentEngine` (future).
- **Inputs:** `ConnectorExecutionRequest`
- **Outputs:** Tool result (e.g., downloaded file path, LLM code).
- **Missing Behavior:** Lacks 3D-specific tool schemas (e.g., `asset.acquire.glb`).
- **Reuse Opportunity:** Absolute canonical path for acquiring external assets and generating code via `Context7`.
