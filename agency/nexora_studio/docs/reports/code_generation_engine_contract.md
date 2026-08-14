# CodeGenerationEngine Contract

## Purpose
The `CodeGenerationEngine` replaces the legacy `stage_06_ai_code_generation.py`. It serves as the critical bridge in the `WebsiteGenerationPipeline`, translating logical JSON Blueprints into physical codebase mutations.

## Inputs
- **WebsiteGenerationArtifact**: A single immutable artifact that encapsulates the entire state of the generation job.

## Outputs
- **Updated WebsiteGenerationArtifact**: The enriched artifact containing the modified `Workspace Metadata`, `Patch Report`, and `Generation Metadata`.

## Responsibilities
- **Artifact Immutability**: The engine must consume the artifact and return a strictly evolved (enriched) copy without mutating unrelated state.
- **Apply Blueprint**: Translates JSON component trees into React imports and JSX tags.
- **Generate Components**: Uses `ProviderManager` to write net-new code logic for custom requirements.
- **Modify Existing Files**: Uses `PatchEngine` to inject components into the `Frontend Templates` scaffold (e.g., updating `App.tsx` routes).
- **Create Missing Files**: Provisions entirely new directories and files as dictated by the `PlanningEngine`.
- **Preserve Boilerplate**: Explicitly avoids modifying core `vite.config.ts` or `package.json` unless requested by the Blueprint.
- **Emit Telemetry**: Dispatches granular metrics per file generated.
- **Trigger Validation**: Kicks off a fast-fail syntax check before saving state.
