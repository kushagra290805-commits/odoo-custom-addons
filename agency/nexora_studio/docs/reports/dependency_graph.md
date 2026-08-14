# Architectural Dependency Graph

This graph maps the dependencies derived from Graphify analysis and code traces.

## 1. Platform & Provider Layer
The bedrock of the application, completely isolated from generation logic.

- **`ProviderManager`** depends on:
  - `ProviderRegistry`
  - `CostRouter` (Cost Ledger)
  - `AIModelCatalog`
  - `NexoraAIAuditLog` (Telemetry)
- **`RuntimeService`** depends on:
  - `IDE Launcher`
  - `Preview Launcher`
  - `Git Runtime`
  - `MCP Registry`

*Validation:* Clean dependencies. No circular references. Production ready.

## 2. Session & Workspace Layer
- **`BuilderSessionService`** connects everything together. (Graphify God Node: 39 edges).
  - Depends on `WorkspaceService` for filesystem provisioning.
  - Depends on `AuthService` for security boundaries.
  - *Duplicate Dependency:* It invokes **both** `WebsiteGenerationPipeline` and `GenerationStageRegistry`, causing architectural fracture.

## 3. Design Layer
- **`DesignOrchestrator`** depends on:
  - `PenpotDesignProvider` (Integration)
  - `DesignSystemEngine` (Phase 11D)
  - `LayoutEngine` (Phase 11E)
  - `AssetPlanningEngine` (Phase 11F)
  - `ContentIntelligenceEngine` (Phase 11F)
  - `BlueprintValidator`

## 4. Generation Layer (The Fractured Core)

### Path A: The Engine Pipeline (Active, JSON-only)
- **`WebsiteGenerationPipeline`**
  - -> `RequirementEngine`
  - -> `PlanningEngine`
  - -> `ArchitectureEngine`
  - -> `WorkspaceGeneratorEngine`
  - *Issue:* Stops at JSON Serialization. Never modifies physical files.

### Path B: The Stage Registry (Legacy/Active, Physical Mutation)
- **`GenerationStageRegistry`**
  - -> `stage_03_template_materialization`
  - -> `stage_06_ai_code_generation`
  - *Issue:* Actually writes code, but uses older `AbstractGenerationStage` architecture and ignores the Engine blueprints.

### Path C: The Template Store (Dead)
- **`generation_service.py`**
  - -> `cloning_stage.py`
  - -> `variable_stage.py`
  - *Issue:* Dead service. Not connected to modern Builder paths.

## Validation Results
- **Circular Dependencies**: Only harmless `__init__.py` imports. No major structural cycles detected.
- **Duplicate Orchestration**: **CRITICAL**. Paths A, B, and C all attempt to orchestrate website generation using different architectural paradigms.
- **Dead Services**: Entire `template_store` module is detached from the `BuilderSessionService`.
