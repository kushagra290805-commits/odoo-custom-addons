# Duplication Analysis

| Duplication Area | Components Involved | Classification | Notes |
| :--- | :--- | :--- | :--- |
| **Generation Orchestration** | 1. `WebsiteGenerationPipeline`<br>2. `GenerationStageRegistry` | Active | **Critical.** The Pipeline builds a JSON blueprint. The Registry mutates the physical files. They operate on separate interfaces and state machines. |
| **Legacy Generation** | 3. `nexora.generation_service` | Planned for removal | The legacy `template_store` procedural generation service. Dead code. |
| **Template Sourcing** | 1. `Template Store` (Odoo Models)<br>2. `assets/frontend-templates`<br>3. `Penpot` (Design tokens) | Active / Planned for removal | `Template Store` is dead. Penpot provides designs. `assets/frontend-templates` provides scaffolding. |
| **HTTP Clients** | 1. `requests` (in older scripts)<br>2. `_request()` (Shared HTTP Abstraction in `BaseAIAdapter`) | Removed | Phase 18.3.1 successfully consolidated all AI providers to use the shared abstraction. No duplicates remain. |
| **Provider Managers** | 1. `AIProviderManager` | Active | Only one provider manager exists. Duplication was avoided in Phase 18.2. |
| **Cost Ledgers** | 1. `ProviderCostLedger` | Active | Unified cost tracking exists in a single model. |
