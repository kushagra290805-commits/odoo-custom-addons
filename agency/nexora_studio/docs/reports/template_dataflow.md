# Template Ecosystem Data Flow

## Modern Generation Data Flow (WebsiteGenerationPipeline)

```
Client Requirements (Domain/Text)
        ↓
RequirementEngine / PlanningEngine (Builder)
        ↓
DesignBlueprint (JSON structure)
        ↓
DesignOrchestrator
        ↓
PenpotDesignProvider (Validates tokens, creates/modifies Penpot project)
        ↓
WorkspaceGeneratorEngine (Serializes Blueprint to JSON / workspace metadata)
        ↓
AICodeGenerationStage (Reads Blueprint/Penpot context & mutates codebase)
        ↓
Generated Website
```

## Legacy Generation Data Flow (AbstractGenerationStage)

```
Generation Job
        ↓
Stage 02: Template Resolution (Locates template path)
        ↓
Stage 03: Template Materialization (shutil.copytree to workspace)
        ↓
Stage 04: Variable Injection (String replacement)
        ↓
Generated Website
```

## Deprecated Data Flow (`template_store` module)

```
nexora.generation_job
        ↓
nexora.generation_service (Orchestrator)
        ↓
cloning_stage.py (Copies frontend/backend subfolders)
        ↓
variable_stage.py (Replaces {{VAR}} with job values)
        ↓
Generated Website
```

> **Note:** The data flows explicitly show that Penpot acts as an intermediate design compilation target in the modern workflow, completely bypassing the physical copying of `template_store` structures.
