# ADR-0010: Website Generation Orchestrator

## Status
Accepted

## Context
With the foundational elements of Nexora Studio (Builder Session, Runtime Plugins, Workspace generation) and the Template Store established, the system requires a mechanism to combine these independent domains into a fully automated website generation lifecycle.

Previously, `PipelineService` in `template_store` contained hardcoded conditionals for various stage types. Additionally, `template_store` was overly burdened with knowing how to orchestrate generation.

We need an orchestration layer that:
1. **Preserves Domain Boundaries**: `template_store` manages templates and the metadata of generation pipelines. `nexora_studio` handles Builder Sessions and Runtimes. The Orchestrator must bridge these without introducing reverse dependencies.
2. **Abstracts Stage Execution**: Pipeline stages must not be hardcoded strings. They need an object-oriented registry model that supports `execute()`, `rollback()`, and context-passing.
3. **Persists Context & Enables Resumption**: A generation job may be interrupted. The Orchestrator must construct an Execution Context and track progress deterministically so that a job can resume safely.
4. **Feeds the Timeline**: Operations must emit events directly into the `nexora.runtime_event` Timeline.

## Decision
We will implement the **Generation Orchestrator** in `nexora_studio` (`nexora.generation_orchestrator`) as the single entry point for all generation jobs.

### 1. Domain Separation
- **`template_store`**: Owns `generation_job`, `generation_pipeline`, `generation_stage`.
- **`nexora_studio`**: Owns the `GenerationOrchestrator`, which receives a `generation_job`, constructs the execution context, delegates stage execution back to registered Stage implementations, and upon success, automatically creates the `Builder Session` and delegates to the `RuntimeService`.

### 2. Stage Registry
We will introduce `nexora.stage.base` in `template_store`. All stages (e.g., `nexora.stage.validation`, `nexora.stage.preparation`) will inherit from this base and register themselves. The Orchestrator will resolve stages dynamically based on their `stage_type` mapping.

### 3. Execution Context
A standard `GenerationContext` object/dictionary will be passed through every stage. It will store variables, template version pointers, and partial metadata, eliminating global state dependence.

### 4. Progress and Status (Idempotent Upgrade)
We will **not** replace the existing `status` field on `generation_job`. Instead, we will map legacy states automatically during module upgrades or abstract them behind a newly added computed `progress` percentage based on `completed_stages / total_stages`. The existing `status` field choices will be gracefully extended or mapped to ensure backward compatibility.

### 5. Timeline Events
All orchestrator steps will emit standardized events using `_emit_event` into the `nexora_studio` timeline.

## Consequences
- **Positive**: Strict separation of concerns. `template_store` does not know what a Builder Session is, but an automated generation pipeline seamlessly triggers one.
- **Positive**: Hardcoded stage loops are eliminated, making new generation stages plug-and-play.
- **Negative**: Increased complexity in context passing between loosely coupled stages.

