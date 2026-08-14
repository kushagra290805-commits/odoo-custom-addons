# Actual E2E Pipeline Map

This documents the *actual implemented flow* currently executing in the system, ignoring intended architecture.

```text
Client Requirement (Domain/Text)
        ↓
[BuilderSessionService]
        ↓
[WebsiteGenerationPipeline] (Engines Path)
        ↓
✅ RequirementEngine (Extracts Domain & Features)
        ↓
✅ PlanningEngine (Builds Deterministic Sitemap)
        ↓
✅ ArchitectureEngine (Maps abstract Components)
        ↓
✅ ThemeEngine (Selects Colors/Typography)
        ↓
✅ AssetEngine (Routes through DesignOrchestrator to Penpot)
        ↓
✅ ContentEngine (Routes through DesignOrchestrator to Penpot)
        ↓
⚠️ WorkspaceGeneratorEngine (Writes JSON blueprint metadata to disk)
        |
        | [Pipeline stops mutating code here. Returns JSON to BuilderSessionService]
        ↓
[BuilderSessionService] switches context to [GenerationStageRegistry] (Stages Path)
        ↓
✅ stage_01_workspace_preparation (Initializes Git)
        ↓
✅ stage_03_template_materialization (shutil.copytree 'assets/frontend-templates' to Workspace)
        ↓
✅ stage_06_ai_code_generation (Analyzes copied template and mutates React code based on requirements)
        ↓
⚠️ stage_08_validation (Placeholder / Linter runs)
        ↓
❌ stage_10_tests (Missing/Placeholder)
        ↓
✅ PREVIEW (Vite Launcher starts)
        ↓
Generated Website
```

### Highlights
- **Implemented Stages**: Planning, Architecture, Asset, Content, Workspace Prep, Template Materialization, AI Code Generation, Preview.
- **Placeholder Stages**: WorkspaceGeneratorEngine (Only writes JSON), Validation, Testing.
- **Missing Stages**: Code Generation Engine (missing from the `Engines` pipeline entirely), Deployment, Client QA Approval.
