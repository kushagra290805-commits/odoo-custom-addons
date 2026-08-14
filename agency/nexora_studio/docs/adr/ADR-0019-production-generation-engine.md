# ADR-0019: Production Generation Engine

## Status
Accepted

## Context
Phase 8C elevates the AI Website Generation Engine from a framework with placeholders to a fully functional production system. This requires eliminating mocked template copies, rudimentary string replacements, and hardcoded AI stubs. We must implement true incremental generation, advanced variable injection, authentic AI provider integration, dependency orchestration, and robust runtimes (Git, Preview, IDE).

## Decision

### 1. Provider Abstraction
We introduce `ai_provider.py` as an abstract interface, with `ai_provider_factory.py` orchestrating concrete implementations (`openai_provider`, `gemini_provider`, `openrouter_provider`, `ollama_provider`). The stages will never contain provider-specific logic.

### 2. Template & Variable Engine
Materialization will correctly recursively copy files, respecting ignore rules and preserving binary files. Variable injection will utilize `VariableInjectionService`, supporting complex templating (potentially Jinja2-like syntax) across multiple file types.

### 3. Incremental Generation & Artifact Manifest
A `generation_diff_service.py` uses SHA-256 to track file states, allowing the engine to skip unchanged files and preserve user modifications. `artifact_manifest_service.py` provides a ledger of what was generated, by whom, and when.

### 4. Resume & Orchestration Support
Stages will persist checkpoints, enabling partial execution recovery. The `WebsiteGenerationService` will interpret these checkpoints to resume interrupted processes safely.

### 5. Runtime & Git Integration
`RuntimeBootstrapStage` will trigger actual subsystem allocation (e.g., dynamic port allocation for Preview, `git init`/`commit` for checkpoints). A strict Validation Pipeline ensures readiness before the `FinalizationStage` locks the artifact.

## Consequences
- **Positive:** A production-ready, idempotent generation orchestrator capable of full application synthesis.
- **Positive:** Granular rollback and resume protect against AI latency or network interruptions.
- **Negative:** Increased complexity in the orchestration lifecycle and the diff engine.
