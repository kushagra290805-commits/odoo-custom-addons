# Generation Consolidation Report

## Unified Generation Architecture
As of Phase 18.3.2, the architectural directive mandates that exactly **one** generation orchestrator exists:

`BuilderSessionService` → `WebsiteGenerationPipeline` → `Generation Engines` → `WebsiteGenerationArtifact` → `Workspace` → `Preview`.

## Consolidation Rules Established
1. **Single Immutable Artifact**: The `WebsiteGenerationArtifact` is the only state carrier passed between engines. Unrelated mutations are forbidden.
2. **State Machine Transitions**: The pipeline operates as a formal state machine (`RequirementsCaptured` → `PlanningCompleted` → etc.) rather than a rigid sequential DAG.
3. **No Parallel Pipelines**: The `GenerationStageRegistry` and its legacy `nexora.ai_generation_stage` models are officially frozen. Their logic (specifically `stage_03` and `stage_06`) has been extracted into capabilities destined for the `WorkspaceGeneratorEngine` and `CodeGenerationEngine`.

## Implementation Mandates for Next Phase
When the Unified Pipeline is constructed:
- It must consume Penpot designs via `DesignOrchestrator`.
- It must copy scaffolding directly from `assets/frontend-templates`.
- It must construct the JSON Blueprint via Planning/Architecture engines.
- It must generate code via the `CodeGenerationEngine`.
