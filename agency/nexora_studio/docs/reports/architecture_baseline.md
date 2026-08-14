# Architecture Baseline

## Current State Summary
The Nexora Studio system currently possesses a robust, production-ready foundation for AI integrations, session management, and sandbox runtime environments. However, the core website generation logic is fractured into multiple competing implementations. 

### Fully Functional (The Baseline)
Future development MUST leverage these existing implementations.
- **Provider & HTTP Layer:** `AIProviderManager`, `CostRouter`, and `BaseAIAdapter` handle all upstream LLM communications synchronously.
- **Telemetry Layer:** Async-friendly telemetry (`RuntimeEvents`, `TelemetryRecorder`) decouple logging from execution.
- **Runtime Environment:** `RuntimeService` provisions isolated filesystem workspaces, `ViteLauncher` for preview, and manages git integration natively.
- **Design Governance:** `DesignOrchestrator` integrates tightly with `PenpotDesignProvider` for design logic extraction and layout validation.

### Fractured (The Problem Area)
Website generation is currently caught between three implementations:
1. **Template Store (Legacy/Dead)**: Found in `shared/template_store`. Uses monolithic Odoo records and string replacement.
2. **GenerationStageRegistry (Transitional)**: Uses a 12-stage sequential array of scripts to clone Vite templates and mutate code (`stage_06_ai_code_generation`).
3. **WebsiteGenerationPipeline (Future)**: Uses intelligent `Engines` (Requirement, Architecture, Asset) to build high-fidelity JSON Blueprints, but completely lacks a Code Generation step to apply those blueprints to the filesystem.

### Missing (The Next Phases)
- **Agentic Runtime (Phase 8)**: No conversational memory, delegation, or multi-agent loop is currently implemented. The system operates entirely on procedural/single-shot execution.
- **Streaming (Phase 9)**: No Server-Sent Events (SSE) implemented for real-time UI streaming.
- **Deployment & Client Portal (Phase 12/13)**: No infrastructure logic exists to host the generated sites externally or gather client approvals.

## Architectural Directives
1. **No New Orchestrators**: Do not build a new pipeline. The existing `WebsiteGenerationPipeline` and `GenerationContext` must be used and extended to merge the physical code generation of the `GenerationStageRegistry`.
2. **No Custom HTTP Clients**: Do not use `requests.get` directly for LLMs. Use `AIProviderManager.chat_completion()`.
3. **No Legacy Templates**: The `Template Store` is dead. Penpot provides the design; `assets/frontend-templates` provides the execution scaffolding.
