# Generation Capability Matrix

This matrix evaluates the legacy `GenerationStageRegistry` stages not as obsolete files, but as architectural capabilities to be extracted, preserved, or removed.

| Legacy Stage | Capability | Primary Responsibility | Decision |
| :--- | :--- | :--- | :--- |
| `stage_01_workspace_preparation` | Workspace Initialization | Create physical directories (`src`, `public`, `config`) and init metadata. | **Merge** into `WorkspaceGeneratorEngine` |
| `stage_02_template_resolution` | Template Lookup | Resolve subfolder path from legacy Odoo template models. | **Remove** (Superseded by Penpot) |
| `stage_03_template_materialization`| Scaffold Materialization | Physical `shutil.copytree` of Vite/React boilerplate into workspace. | **Reuse** in `WorkspaceGeneratorEngine` |
| `stage_04_variable_injection` | Regex Variable Replacement | String substitution for `{{VAR}}` legacy tokens. | **Remove** |
| `stage_05_dependency_resolution` | Package Dependency Checks | Verify `package.json` coherence. | **Merge** into `ValidationEngine` |
| `stage_06_ai_code_generation` | AI Code Mutation | Build AI context, construct LLM prompts, trigger `ProviderManager`, and apply diff patches. | **Refactor** into `CodeGenerationEngine` |
| `stage_07_runtime_bootstrap` | Runtime Initialization | Install NPM packages and prep local server environment. | **Reuse** in `PreviewEngine` / Env Engine |
| `stage_08_validation` | Static Validation | Run ESLint / Prettier on the generated workspace. | **Merge** into `ValidationEngine` |
| `stage_09_ai_self_review` | Code Self-Review | LLM-based reflection on code quality. | **Refactor** (Multi-agent loop) |
| `stage_10_ai_bug_fix` | Automated Code Repair | AI applies patches based on linter/review failures. | **Refactor** (Multi-agent loop) |
| `stage_11_ai_quality_pass` | Design QA | Validates the code against the Design Blueprint tokens. | **Merge** into `ValidationEngine` |
| `stage_12_ai_security_review` | Security Analysis | Scans for vulnerable patterns. | **Merge** into `ValidationEngine` |
| `stage_09_finalization` | Version Checkpoint | Git commit and session state lock. | **Reuse** at Pipeline Conclusion |
