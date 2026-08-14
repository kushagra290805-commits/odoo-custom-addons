# Template Ecosystem Responsibility Matrix

## 1. Template Store (`custom-addons/shared/template_store`)

*Actual Current Responsibility:* **Legacy Monolithic Registry**

- **Template Registry?** Yes. Maintains `nexora.template_frontend` and `nexora.template_backend` records.
- **Metadata?** Yes. Maintains `nexora.template_metadata` and `nexora.template_version` for versioning static files.
- **Reusable Components?** No. It operates on entire repository structures (cloning folders).
- **Code Storage?** No. It stores paths to physical directories on disk (e.g., `subfolder_path`).
- **AI Knowledge?** No. Purely procedural string replacements (via `variable_engine.py`).

## 2. Frontend Templates (`assets/frontend-templates`)

*Actual Current Responsibility:* **Starter Kit Scaffolding**

- **Source Code?** Yes. They contain raw React/Vite boilerplate files.
- **Deployment Artifacts?** No. They are uncompiled source.
- **Starter Kits?** Yes. They provide the initial `package.json` and basic directory structure so the AI pipeline (`stage_06_ai_code_generation.py`) has a foundation to parse and modify rather than starting from absolute zero.

## 3. Penpot (`nexora_studio/services/design/penpot_provider.py`)

*Actual Current Responsibility:* **Dynamic Design Source of Truth**

- **Design Source?** Yes. The `DesignOrchestrator` translates `DesignBlueprints` into Penpot projects.
- **Design Tokens?** Yes. Used by the `DesignSystemEngine` to enforce visual consistency.
- **Mockups?** Yes. The LayoutEngine uses it for layout representation.
- **Runtime Dependency?** No. It is an API used during the *generation* phase, not when the generated website is actually deployed.

## 4. Builder (`nexora_studio/services/generation/pipeline/website_generation_pipeline.py`)

*Actual Current Responsibility:* **AI Generation Orchestrator**

- **Orchestration?** Yes. It drives the `WebsiteGenerationPipeline` DAG.
- **Cloning?** Yes. Through `WorkspaceGeneratorEngine` and early stages, it copies the initial scaffold.
- **Modification?** Yes. AI Code Generation heavily mutates the cloned templates based on client requirements.
- **Generation?** Yes. It is the primary engine building the final output.
