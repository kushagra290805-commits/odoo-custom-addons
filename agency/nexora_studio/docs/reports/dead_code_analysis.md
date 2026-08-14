# Template Ecosystem Dead Code Analysis

## 1. Shared Template Store (`custom-addons/shared/template_store`)

**Module Status: Deprecated / Dead**
This entire module represents a legacy procedural generation architecture that has been superseded by the `nexora_studio` Builder AI pipeline.

### Unused Models
- `nexora.template_frontend`: **Deprecated**. Used by `verify_real_generation.py` but not in the modern AI `WebsiteGenerationPipeline`.
- `nexora.template_backend`: **Deprecated**. Same as above.
- `nexora.template_metadata`: **Dead**. Superseded by AI `GenerationContext` and `DesignBlueprint`.
- `nexora.template_version`: **Dead**.

### Unused Services
- `generation_service.py`: **Dead**. Duplicate responsibility of `nexora_studio`'s `WebsiteGenerationPipeline`.
- `pipeline_service.py`: **Dead**. Duplicate responsibility of `GenerationStateManager`.
- `workspace_preparation_service.py`: **Dead**. Replaced by `WorkspaceGeneratorEngine`.
- `variable_engine.py`: **Dead**. Procedural string replacement is obsolete. AI uses `context` injection.
- `services/stages/*` (cloning, config, finalize, merge, prepare, validate, variable): **Dead**. Replaced by `nexora_studio/services/generation/engines/*`.

### Duplicate Responsibilities
- `template_store` tries to manage pipeline stages procedurally.
- `nexora_studio` manages pipeline states (DAG) intelligently via AI Engines.

## 2. Frontend Templates (`assets/frontend-templates`)

**Module Status: Active (but evolving)**
- The static template files themselves remain **Active** because `stage_03_template_materialization.py` and the `WorkspaceGeneratorEngine` use them to initialize Vite/React projects before AI mutation. However, they function as "dumb boilerplates" rather than smart templates.
