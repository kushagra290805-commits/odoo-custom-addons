# ADR-0042 – Generation Architecture Constitution

## Status
Accepted

## Context
As Nexora Studio evolved through various phases, the generation architecture suffered from severe fragmentation. Multiple orchestration paths, competing template systems, and overlapping state mechanisms were introduced, leading to an architectural baseline that was difficult to maintain, trace, or extend (particularly for multi-agent workflows and streaming). 

To ensure the integrity of the generation subsystem moving forward, this document establishes the unalterable constitutional rules for the architecture. It strictly prohibits the introduction of parallel paths and defines a rigid governance model for any future architectural changes.

## Core Principles

Every architectural decision and component within the generation ecosystem must strictly adhere to the following principles:

1. **Single Orchestration Path**: There is exactly one path for generation execution.
2. **Immutable Artifact**: All generation state is encapsulated in a singular, immutable `WebsiteGenerationArtifact`. Engines consume it, enrich it, and return a new instance. Engines must never mutate unrelated state.
3. **State Machine Execution**: The generation pipeline is a formal state machine (`RequirementsCaptured` → `PlanningCompleted` → etc.), not a fragile procedural script.
4. **Capability Reuse**: If a capability exists, it must be reused. Do not reinvent existing mechanics (e.g., HTTP clients, telemetry).
5. **Penpot = Design Source**: Penpot is the exclusive source of truth for design tokens, layouts, and component blueprints.
6. **Frontend Templates = Execution Scaffold**: The `assets/frontend-templates` directory is the exclusive source of truth for the physical Vite/React boilerplate execution environment.
7. **BuilderSessionService = Entry Point**: The `BuilderSessionService` is the only valid entry point for a user or agent to initiate a generation session.
8. **WebsiteGenerationPipeline = Orchestration**: The `WebsiteGenerationPipeline` is the exclusive orchestrator of generation engines.
9. **One Responsibility Per Subsystem**: No two systems may share or duplicate a core responsibility.

## Forbidden Patterns

To prevent the recurrence of the architectural fractures observed in earlier phases, the following patterns **must never be introduced again**:

- **Parallel Generation Pipelines**: (e.g., maintaining both an Engine DAG and a Stage Registry).
- **Multiple Template Systems**: (e.g., using both Odoo models and physical frontend templates simultaneously).
- **Multiple Orchestrators**: (e.g., `generation_service.py` vs `BuilderSessionService`).
- **Multiple Provider Managers**: All AI requests must route through the single `AIProviderManager`.
- **Multiple Runtime Managers**: All sandboxes must be managed by the single `RuntimeService`.
- **Multiple Telemetry Systems**: All events must route through the single `TelemetryRecorder`.
- **Duplicate State Stores**: The state must live solely in the Odoo DB and the `WebsiteGenerationArtifact`.
- **Duplicate Filesystem Abstractions**: All filesystem mutations must use the established `WorkspaceService`.

## Required Decision Process

Every future architectural proposal (including new phases, ADRs, or Implementation Plans) **must explicitly answer** the following questions. If these questions are not answered—or if the answers violate the Core Principles—the proposal **should not proceed**.

1. **What existing component owns this responsibility?**
2. **Why can't it be extended?**
3. **Does this introduce another source of truth?**
4. **Does this introduce another orchestration path?**
5. **Can this capability be extracted instead?**

## Consequences
By adhering to this constitution, the Nexora Studio generation pipeline remains a singular, cohesive, and highly observable state machine. This enables immediate support for advanced capabilities like Agentic Runtimes, Streaming responses, and dynamic QA loops without fighting underlying structural entropy.
