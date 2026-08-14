# Architecture Roadmap Baseline

## Purpose
This document establishes the verified baseline of the Nexora Studio architecture as of the Phase 18.3.1 Telemetry Freeze. **Every future phase MUST build upon this baseline rather than creating parallel implementations.**

## 1. The Baseline Stack
- **Provider & LLM Access**: `BaseAIAdapter`, `AIProviderManager`, `CostRouter`. (Completed). *Rule: Do not bypass the manager.*
- **Telemetry & Auditing**: `TelemetryRecorder`, `NexoraAIAuditLog`. (Completed). *Rule: Emit events asynchronously, never block.*
- **Runtimes & Workspace**: `WorkspaceService`, `RuntimeService`, `ViteLauncher`. (Completed). *Rule: Do not build custom filesystem handlers.*
- **Design Intelligence**: `DesignOrchestrator`, `PenpotDesignProvider`. (Completed). *Rule: Penpot is the primary design truth.*

## 2. Permanent Architectural Rules

### 1. Single Source of Truth
Every responsibility must have exactly one owner. No secondary owners are permitted.
- Penpot → Design
- Frontend Templates → Scaffolding
- WebsiteGenerationPipeline → Orchestration
- RuntimeService → Runtime
- ProviderManager → AI
- TelemetryRecorder → Observability

### 2. Immutable Artifact Rule
Engines should not mutate unrelated state. Each generation engine receives the canonical `WebsiteGenerationArtifact`, enriches it, and returns the updated `WebsiteGenerationArtifact`.

### 3. Architecture Decision Gate
Before any new phase begins, the following must be answered:
1. Does this already exist?
2. Can this be extended?
3. Does it introduce another orchestration path?
4. Does it create another source of truth?

*If any answer indicates duplication, the phase must be redesigned before implementation.*

## 3. The Architectural Fracture (The Core Problem)
Currently, generation is split into two disjointed systems:
1. **The Engine Pipeline** (`WebsiteGenerationPipeline`): Produces intelligent JSON Blueprints but never modifies code.
2. **The Stage Registry** (`GenerationStageRegistry`): Modifies actual React code but relies on legacy string replacement and basic procedural checks.
3. **The Template Store**: Legacy monolith that is now deprecated and dead.

## 4. The Future Roadmap (What to Build)

### Immediate Next Steps: The Unification Phase
- **Deprecate** the old `Template Store` and remove `shared/template_store`.
- **Merge** the Engine Pipeline and the Stage Registry. The `WebsiteGenerationPipeline` must be extended with a genuine `CodeGenerationEngine` that consumes the `DesignBlueprint` and dynamically writes Vite/React code into the workspace, relying on `Frontend Templates` for the static Vite scaffolding.

### Following Steps
1. **Phase 9: Streaming (SSE)**. Patch `BaseAIAdapter` to support async chunked generators for UI streaming.
2. **Phase 8: Agent Runtime**. Introduce multi-agent conversational capabilities (e.g. `PlannerAgent`, `CoderAgent`, `QAAgent`) into the `WebsiteGenerationPipeline`, replacing the current single-shot Engine logic.
3. **Phase 12: Deployment**. Introduce a `DeploymentEngine` to push generated workspaces to live hosting (Vercel/AWS).
4. **Phase 13: Client Portal**. Build an Odoo Portal frontend for clients to review and approve Generated Websites.

## Guiding Constraint
**No parallel architecture.** If a capability matrix shows "Implemented", use it. Do not rebuild authentication, provider management, or runtimes. Address the gaps identified in `gap_analysis.md`.
