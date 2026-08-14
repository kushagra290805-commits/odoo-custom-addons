# ADR-0018: AI Website Generation Engine

## Status
Accepted

## Context
Phase 8B transitions Nexora Studio from architectural preparation to functional website generation. The goal is to transform a locked Project Configuration into a fully generated Builder Workspace using the existing runtime and capability platform. We need a structured, robust, and traceable way to orchestrate this generation.

## Decision

### 1. Stage-Based Generation Architecture
We will implement a formal stage execution framework (`AbstractGenerationStage`). Each stage executes a specific part of the generation lifecycle and must implement `validate()`, `execute()`, and `rollback()`.
Stages include: Workspace Preparation, Template Resolution, Materialization, Variable Injection, Dependency Resolution, AI Code Generation, Runtime Bootstrap, Validation, and Finalization.

### 2. Builder Workspace Lifecycle
The workspace will transition through explicit stages. Each stage execution acts on a shared `GenerationStageContext`.

### 3. AI Orchestration Boundaries
AI generation is strictly contained within the `06_ai_code_generation_stage.py` stage. It focuses solely on generating missing files, components, and placeholders without interfering with the deterministic stages (like materialization or variable injection).

### 4. Incremental Regeneration & Recovery Model
The `WebsiteGenerationService` supports modes: `FULL`, `PARTIAL`, `FILE`, `COMPONENT`, and `CONFIGURATION`. The system will only regenerate requested targets and never overwrite user modifications unless explicitly forced. If a stage fails, the service orchestrates a reverse traversal of executed stages, invoking their `rollback()` methods to ensure a clean recovery state.

### 5. Artifact Generation Strategy
Structured artifacts (`generation_report.json`, `workspace_manifest.json`, etc.) will be stored inside the Builder Workspace to maintain full traceability and audit history.

## Consequences
- **Positive:** Highly modular and testable generation pipeline.
- **Positive:** Robust error recovery and granular incremental regeneration.
- **Negative:** Increased orchestration complexity to maintain rollback state.
