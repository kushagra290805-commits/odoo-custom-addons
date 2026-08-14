# Template Ecosystem Dependency Graph

## 1. Template Store (`custom-addons/shared/template_store`)

**Incoming Dependencies:**
- *Legacy tests / Validation scripts*: (`verify_real_generation.py`)
- *User Interface*: Menus and views (`generation_job_views.xml`, `template_frontend_views.xml`)

**Outgoing Dependencies:**
- `nexora.filesystem_service`
- `nexora.pipeline_service`
- `nexora.validation_service`
- `nexora.variable_engine`

**Models:**
- `nexora.template_frontend`
- `nexora.template_backend`
- `nexora.template_metadata`
- `nexora.template_version`

**Services:**
- `nexora.generation_service`
- `nexora.merge_service`
- `nexora.pipeline_service`
- `nexora.validation_service`
- `nexora.variable_engine`
- `nexora.workspace_preparation_service`

**Builder References:**
- **NONE**. The modern `BuilderSessionService` and `WebsiteGenerationPipeline` in `nexora_studio` do not import or use `template_store` models.

**Generation References:**
- Orchestrated via `nexora.generation_service.execute_job()` and stages (`cloning_stage.py`, `merge_stage.py`).

**Registry References:**
- Local template registry (`template_metadata`, `template_version`).

---

## 2. Frontend Templates (`assets/frontend-templates` or local template directories)

**Who reads them:**
- `template_store/services/stages/cloning_stage.py` (Reads template folders for copying).
- `stage_06_ai_code_generation.py` (AI analyzes the existing template via `template_analyzer`).

**Who writes them:**
- Developers authoring boilerplates.

**Who clones them:**
- `nexora.filesystem_service` via `cloning_stage.py` (legacy).
- `stage_03_template_materialization.py` (current AI pipeline).

**Dependencies:**
- *Runtime*: React, React-DOM.
- *Build*: Vite, TypeScript.
- *Deployment*: Static hosting artifacts (`index.html`, bundles).

---

## 3. Penpot Integration

**Current Usage:**
- **Adapters**: `PenpotAdapter` (`services/source_framework/adapters/penpot_adapter.py`) implemented for the Design Intelligence Platform (DIP).
- **Services**: `PenpotDesignProvider` (`services/design/penpot_provider.py`), `PenpotAPIClient`, `PATAuthenticator`.
- **Provider Registry**: Registered as a primary Design Provider via `DesignOrchestrator` (`services/design/design_orchestrator.py`).
- **Builder**: The Builder's generation pipeline (`ArchitectureEngine`, `LayoutEngine`, `AssetEngine`) routes blueprints to `DesignOrchestrator.execute_blueprint(..., provider_name="penpot")`.
- **Template Generation**: Penpot acts as the *source of truth* for design tokens, layouts, and components, displacing static templates as the origin for design metadata.
