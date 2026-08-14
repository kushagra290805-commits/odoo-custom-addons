# Legacy Archival Plan

## Objective
Implement a strict "Freeze → Read-only → Archive" lifecycle for deprecated generation components in accordance with Architectural Governance Policy. Physical deletion is strictly prohibited during Phase 18.3.2.

## Components to Archive

### 1. Template Store (`custom-addons/shared/template_store`)
- **Action**: Freeze.
- **State**: Deprecated & Read-only.
- **Constraint**: Do not delete the module. Do not remove it from Odoo dependencies yet. Stop writing new code against its models.

### 2. Generation Stage Registry (`services/generation/generation_stage_registry.py`)
- **Action**: Freeze.
- **State**: Deprecated & Read-only.
- **Constraint**: Do not delete the stage classes. The `BuilderSessionService` will continue calling this path temporarily while the Unified Pipeline is constructed. 

### 3. Legacy Template Views (`views/template_frontend_views.xml`, etc.)
- **Action**: Freeze.
- **State**: Deprecated.
- **Constraint**: Leave the menus active in the UI, but mark them visually as "(Legacy)" if practical, or leave them untouched until final removal.

### 4. Legacy Tests (`verify_template_store.py`, `verify_real_generation.py`)
- **Action**: Freeze.
- **State**: Archived.
- **Constraint**: Preserve the tests to act as reference implementations for the logic being extracted, but do not execute them in modern CI pipelines.

## Future Removal (Phase 18.3.5)
These components will only be physically deleted from the repository during **Phase 18.3.5 – Legacy Removal**, contingent upon the successful validation and freeze of the Unified `WebsiteGenerationPipeline`.
