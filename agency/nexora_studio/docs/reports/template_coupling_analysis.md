# Template Ecosystem Coupling Analysis

## 1. Template Store ↔ Builder
**Classification: Dead**
- The modern `BuilderSessionService` in `nexora_studio` utilizes `WebsiteGenerationPipeline` and `GenerationContext` (a DAG-based state machine).
- The `Template Store` uses a completely isolated orchestration path (`nexora.generation_service` and `nexora.pipeline_service`) that is not referenced by the Builder.

## 2. Template Store ↔ Frontend Templates
**Classification: Legacy**
- The Template Store was built around `cloning_stage.py` and `variable_stage.py` to copy static templates from `subfolder_path` into the workspace and perform regex variable injection.
- This is an older procedural approach superseded by AI generation.

## 3. Template Store ↔ Penpot
**Classification: Non-existent / Dead**
- There is zero coupling. The Template Store relies on static file models (`nexora.template_frontend`). It has no integration with dynamic design providers, tokens, or live APIs like Penpot.

## 4. Builder ↔ Frontend Templates
**Classification: Optional / Transitional**
- The Builder's generation pipeline includes `stage_03_template_materialization.py` which copies a base template if `template_path` is provided.
- `stage_06_ai_code_generation.py` uses `nexora.template_analyzer` to read the existing template and instructs the AI to "Modify existing template files".
- It serves as a scaffolding base, but the AI handles the heavy lifting, making the templates loosely coupled boilerplates.

## 5. Builder ↔ Website Generation
**Classification: Required**
- Highly coupled. The Builder strictly relies on `WebsiteGenerationPipeline` to progress through states (`REQUIREMENTS_ANALYSIS` -> `ARCHITECTURE` -> `PREVIEW`).

## 6. Penpot ↔ Website Generation
**Classification: Required**
- The `WebsiteGenerationPipeline` leverages `ArchitectureEngine`, `AssetEngine`, and `ContentEngine` which route `DesignBlueprints` into the `DesignOrchestrator`.
- The `DesignOrchestrator` sets `PenpotDesignProvider` as the primary default provider for component validation, token retrieval, and design generation.
