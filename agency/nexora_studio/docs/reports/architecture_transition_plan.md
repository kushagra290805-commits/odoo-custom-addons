# Architecture Transition Plan

## Vision
Migrate the system from a fractured, dual-orchestrator state into a singular, cohesive generation pipeline, maximizing the reuse of verified components while adhering to strict deprecation workflows.

## 1. The Starting State (Current)
- `WebsiteGenerationPipeline`: Generates high-fidelity JSON Blueprints, but stops short of filesystem mutation.
- `GenerationStageRegistry`: Mutates physical files based on raw prompts, oblivious to the JSON Blueprint.
- `Template Store`: Deprecated legacy Odoo models.

## 2. The Transition State (Pipeline Unification)
This phase focuses heavily on capability extraction and refactoring.

1. **Extract & Refactor**
   - Extract the `patch_engine` and `ai_provider_manager` logic from `stage_06_ai_code_generation`.
   - Implement the new `CodeGenerationEngine` contract, appending it to the `WebsiteGenerationPipeline` DAG immediately after `WorkspaceGeneratorEngine`.

2. **Route Unification**
   - Reroute `BuilderSessionService` to rely *exclusively* on `WebsiteGenerationPipeline`.
   - Detach `GenerationStageRegistry` from the primary execution path.

3. **Template Sourcing**
   - Point `WorkspaceGeneratorEngine` directly to the `assets/frontend-templates` directory for physical materialization, completely bypassing `nexora.template_frontend` database queries.

## 3. The Target State (Unified Pipeline as a State Machine)
The pipeline will transition from a sequential DAG to an Explicit State Machine where engines receive a specific state, advance it, and enrich the canonical `WebsiteGenerationArtifact`.

```text
Generation Session
        ↓
[State Machine]
        ↓
RequirementsCaptured
        ↓
PlanningCompleted
        ↓
ArchitectureCompleted
        ↓
DesignCompleted
        ↓
WorkspacePrepared
        ↓
CodeGenerationCompleted
        ↓
ValidationCompleted
        ↓
PreviewReady
        ↓
DeploymentReady
```
Each engine in this flow validates prerequisites, performs its logic on the `WebsiteGenerationArtifact`, emits telemetry, and cleanly transitions to the next state, enabling safe checkpoints and resumable multi-agent coordination.

## 4. Verification Gates
Before advancing to Phase 18.3.5 (Legacy Removal), the following criteria must be met:
- ✅ **Generation**: `GenerationStageRegistry` is no longer invoked in production paths.
- ✅ **Templates**: The system operates purely on Penpot Design + Frontend Template scaffolding.
- ✅ **Runtime**: The Builder provisions workspaces and previews using the single Unified Pipeline.
- ✅ **Dependencies**: Graphify confirms zero duplicate orchestration paths.
