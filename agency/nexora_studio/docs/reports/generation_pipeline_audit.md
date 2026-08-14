# Generation Pipeline Audit

## 1. WebsiteGenerationPipeline (The Engines Path)
This is the modern orchestration system based on a DAG of Engines (`BaseGenerationEngine`), designed to construct a comprehensive `DesignBlueprint`.

### Current Inputs
- Raw client requirement strings.
- Odoo Session context (for DB access).

### Current Outputs
- A heavily typed `GenerationContext` containing `Requirements`, `WebsiteBlueprint`, `Architecture`, `Theme`, `ComponentTree`, `AssetPlan`, and `ContentPlan`.
- Serialized JSON blueprints on the filesystem.

### State Transitions
Managed by `GenerationStateManager`. DAG execution from `REQUIREMENTS_ANALYSIS` through 11 states, automatically checkpointing and handling recovery/rollback.

### Engine Sequence
`RequirementEngine` -> `PlanningEngine` -> `ArchitectureEngine` -> `ComponentDiscoveryEngine` -> `ThemeEngine` -> `AssetEngine` -> `ContentEngine` -> `WorkspaceGeneratorEngine` -> `OptimizationEngine` -> `ValidationEngine` -> `PreviewEngine`.

### Missing Responsibilities
- **Code Mutation**: The engine pipeline constructs the logical blueprint but has no engine that actually mutates or generates physical code on the filesystem. It delegates to JSON serialization in `WorkspaceGeneratorEngine`.

---

## 2. GenerationStageRegistry (The Stages Path)
This is the older, sequentially ordered system designed to clone boilerplates and mutate physical files.

### Stage Responsibilities & Sequence
- `01_workspace_preparation`: Initializes Git repository.
- `02_template_resolution`: Looks up legacy `template_store` records.
- `03_template_materialization`: Copies `assets/frontend-templates` via `shutil.copytree`.
- `04_variable_injection`: Legacy string replacement (`{{PROJECT_NAME}}`).
- `05_dependency_resolution`: Package dependency validation.
- `06_ai_code_generation`: Analyzes existing templates, prompts ProviderManager, applies patches via `patch_engine`.
- `07_runtime_bootstrap`: Installs NPM dependencies.
- `08_validation`: Static linting.
- `09_ai_self_review` / `10_ai_bug_fix` / `11_ai_quality_pass` / `12_ai_security_review`: AI automated loops.
- `finalization`: Git commit.

### Missing Responsibilities
- **Design Intelligence**: The stages lack the context of a `DesignBlueprint` (Theme, Architecture, Component tokens). They mutate blindly based on a raw prompt instead of a structured plan.

---

## 3. Comparison Matrix

| Responsibility | Unique to Engines | Unique to Stages | Duplicated | Missing entirely |
| :--- | :--- | :--- | :--- | :--- |
| **Requirements Parsing** | ✅ Yes | | | |
| **Blueprint / Sitemap** | ✅ Yes | | | |
| **Penpot Token Resolution**| ✅ Yes | | | |
| **Template Cloning** | | ✅ Yes | | |
| **AI Code Mutation** | | ✅ Yes (`stage_06`) | | |
| **Git Version Control** | | ✅ Yes (`stage_01`, finalization) | | |
| **Orchestration / DAG** | | | ✅ Yes | |
| **Odoo Context Management**| | | ✅ Yes | |
| **Multi-Agent Conversational Logic** | | | | ✅ Yes |

### Conclusion
The two systems perfectly complement each other in theory but are completely decoupled in practice. The **Engines** build the logical truth, while the **Stages** perform the physical execution. The stages must be converted into Engines to complete the `WebsiteGenerationPipeline`.
