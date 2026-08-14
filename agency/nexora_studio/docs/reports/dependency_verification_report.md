# Dependency Verification Report

## Verification Methodology
Dependencies were verified via Graphify analysis, import tracing, and Odoo XML reference searches.

## Key Findings
1. **`shared/template_store` dependencies**:
   - The module is referenced by `agency/nexora_studio/__manifest__.py`.
   - Referenced by `client_provisioning_api.py`.
   - Referenced by legacy tests `verify_template_store.py` and `verify_real_generation.py`.
   - *Status*: Validated as technically entangled, but practically dead code. Frozen for Phase 18.3.5 removal.

2. **Orchestration Dependencies**:
   - `BuilderSessionService` currently depends on **both** `WebsiteGenerationPipeline` and `GenerationStageRegistry`.
   - *Status*: This duplicate dependency has been documented. The transition plan mandates pruning the `GenerationStageRegistry` dependency once the unified pipeline is ready.

3. **Provider Platform Dependencies**:
   - All AI execution paths correctly route through `AIProviderManager`.
   - No hardcoded `requests` or independent LLM clients were found active in the generation stages.

## Conclusion
The dependency graph confirms the architectural fracture identified during discovery. The freeze/archive rules established in Phase 18.3.2 will safely decouple these dependencies during Phase 18.3.5.
