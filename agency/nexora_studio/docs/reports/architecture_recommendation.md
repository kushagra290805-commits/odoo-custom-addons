# Architecture Recommendation

## Recommendation: Option B (Merge Template Store into Penpot workflow)

Based on the architectural discovery, the legacy `Template Store` module should be deprecated and removed, shifting its design registry responsibilities into Penpot, and its materialization responsibilities directly to the `Frontend Templates` scaffolding.

### Advantages
- **Eliminates Dead Code**: Removes the duplicated orchestration logic (`generation_service.py` vs `website_generation_pipeline.py`) and redundant state machines.
- **Single Source of Truth**: Enforces Penpot as the undisputed master of design tokens, layouts, and components, removing the ambiguity of Odoo-based template records.
- **AI-Centric Pipeline**: Solidifies the shift from procedural generation (static regex replacements) to intelligent AI mutation (reading from a static scaffold and writing customized code).

### Disadvantages
- **No Procedural Fallback**: Removing the Template Store removes the ability to do basic, non-AI string-replacement generations. The system will be 100% dependent on the AI pipeline.
- **Test Breakage**: Legacy verification scripts (such as `verify_real_generation.py`) that explicitly create `nexora.template_frontend` records will break and require rewrites.

### Migration Effort
- **Medium**. 
- Delete the `custom-addons/shared/template_store` directory.
- Update `stage_03_template_materialization.py` (or `WorkspaceGeneratorEngine`) to load boilerplate paths directly from `assets/frontend-templates` or a configuration variable, rather than resolving them via `nexora.template_frontend` database lookups.
- Remove any Template Store menus and views (`template_frontend_views.xml`, `generation_job_views.xml`) from the console UI.

### Architectural Impact
This refactor establishes a clean triad for the generation ecosystem:
1. **Penpot**: Owns the Design (Tokens, Layouts, Blueprints).
2. **Frontend Templates**: Owns the Execution Environment (Vite, React, `package.json`).
3. **AI Generation Pipeline**: Owns the Implementation (Mutating the boilerplate to match the design).
