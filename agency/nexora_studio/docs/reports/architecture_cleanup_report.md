# Architecture Cleanup Report

## Executive Summary
Phase 18.3.2 focused exclusively on consolidating the fractured generation pipelines without introducing new capabilities or physically deleting files. The architectural governance policy was strictly followed: legacy systems were identified, capabilities extracted, and deprecated code was transitioned into a `Freeze → Read-only → Archive` lifecycle.

## Actions Taken
- **Capability Extraction**: Analyzed 13 legacy `generation_stages` and assigned them to either `Reuse`, `Refactor`, `Merge`, or `Remove` paths for the future `WebsiteGenerationPipeline`.
- **Contract Definition**: Established the `WebsiteGenerationArtifact` and the `CodeGenerationEngine` interface to strictly define how future code mutation will occur.
- **State Machine Formalization**: Updated the transition plan to move the pipeline from a sequential DAG to an explicit State Machine capable of resumability and multi-agent coordination.

## Status of Cleanup Candidates
| Component | Status | Next Steps |
| :--- | :--- | :--- |
| `custom-addons/shared/template_store` | Frozen / Archived | Deferred physical deletion to Phase 18.3.5. |
| `GenerationStageRegistry` | Frozen / Read-only | Awaiting replacement by Unified Pipeline. |
| Legacy XML / Tests | Frozen / Archived | Do not run in modern CI; delete in 18.3.5. |
