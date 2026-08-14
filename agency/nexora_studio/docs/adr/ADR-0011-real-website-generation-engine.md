# ADR-0011: Real Website Generation Engine

## Status
Accepted

## Context
Up to Phase 7E, the website generation pipeline existed as a well-orchestrated but mock-driven process. The Pipeline Orchestrator correctly scheduled stages, tracked state, and invoked Builder Sessions, but the actual filesystem work (copying templates, replacing variables, generating configurations) was simulated.

We now need to implement the physical materialization of projects without violating the established domain boundaries:
- `template_store` manages templates and the generation rules.
- `nexora_studio` manages the workspace filesystem, Git repository, and runtime orchestration.

## Decision
We will upgrade the pipeline stages implemented in Phase 7E to perform real operations.

### 1. Filesystem & Template Cloning
The `Workspace Preparation Stage` and `Cloning Stage` will invoke a Filesystem Abstraction Service (living in `nexora_studio`'s workspace domain but interfaced via `GenerationContext`) to create project layouts (frontend, backend, shared) and securely copy template structures.

### 2. Intelligent Merge Strategy
When templates are cloned into a target workspace, an Intelligent Merge Engine will detect conflicts. By default, it will overwrite standard files unless marked as protected. A merge report will be generated and attached to the Execution Context.

### 3. Variable Engine 2.0
The `Variable Engine` will recursively scan all copied text-based files (JSON, YAML, HTML, CSS, JS, TS, Python, Markdown, ENV) and apply Mustache-style (`{{VARIABLE_NAME}}`) variable substitutions from the Generation Context. Binary files (images, compiled assets) will be detected via MIME types or extensions and explicitly ignored to prevent corruption.

### 4. Configuration Generator
A dedicated Configuration Generator will assemble baseline `.env`, `docker-compose.yml`, `.gitignore`, and `package.json`/`requirements.txt` based on the combined templates.

### 5. Git Bootstrap Integration
At the end of the generation pipeline, if a Git Runtime is associated, the Orchestrator will automatically initialize a Git repository, stage the generated files, and create an initial "Initial commit from Builder" commit.

### 6. Rollback Policy
Checkpoints will track exactly which files and folders were created by the generation job. A rollback will precisely remove only the artifacts tracked in the checkpoint, leaving user modifications and pre-existing Git history intact.

## Consequences
- **Positive**: Complete automation from template selection to fully runnable development environment.
- **Positive**: Reusability of the variable engine across different template stacks.
- **Negative**: High filesystem I/O load during large template generations.
- **Negative**: Care must be taken to ensure binary files aren't corrupted during variable substitution.
