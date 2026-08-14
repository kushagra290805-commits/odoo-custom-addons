# Responsibility Matrix

| Subsystem | Current Responsibility | Planned Responsibility | Missing Responsibility | Duplication Risk |
| :--- | :--- | :--- | :--- | :--- |
| **Provider Manager** | Synchronous HTTP request routing and execution. | Streaming, Server-Sent Events, Agentic function calling execution. | Streaming | Low |
| **Cost Router** | Tier-based fallback logic for cost governance. | Enforce real-time spending limits. | Real-time budget termination | Low |
| **Telemetry** | Non-blocking execution logging and metric aggregation. | Extended tracing for streaming and multi-agent thoughts. | Streaming event capture | Low |
| **WebsiteGenerationPipeline (Engines)** | Consumes Client Requirements, outputs serialised JSON `DesignBlueprints`. | Full orchestrator for end-to-end multi-agent execution. | Actually mutating the codebase. | **High** (Clashes with Stages) |
| **GenerationOrchestrator (Stages)** | Mutates codebase via 12-stage procedural steps (`stage_03`, `stage_06`). | Deprecation / Merge into Pipeline Engines. | Dynamic orchestration | **High** (Clashes with Engines) |
| **Template Store** | Dead legacy registry. | Complete Removal. | N/A | **High** (Clashes with Penpot) |
| **Penpot Integration** | Design System origin, tokens, layouts validation. | Direct component syncing to frontend template workspace. | Continuous sync | Low |
| **Frontend Templates** | Physical base directory copy (`assets/frontend-templates`). | Reduced to pure boilerplate config. | Dynamic dependency resolution | Low |
| **Runtime Service** | Manages IDE, Git, Preview, MCP plugin lifecycles. | Secure sandboxing, resource limits. | Network isolation | Low |
| **Deployment** | None. | Pushing generated code to staging/production infrastructure. | The entire subsystem | None |
| **Client Portal** | None. | Interface for client feedback, QA, and signoff. | The entire subsystem | None |

### Key Responsibility Overlap
The most significant duplication risk is in the **Generation Orchestration Layer**. 
1. `WebsiteGenerationPipeline` uses "Engines" (Phase 11 architecture) to build logical JSON blueprints.
2. `GenerationStageRegistry` uses "Stages" (Phase 7-10 architecture) to perform physical filesystem mutations.
3. `Template Store` (Legacy) uses its own custom stages to copy legacy directories.
