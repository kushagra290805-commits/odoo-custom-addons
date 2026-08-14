# Phase 16 Architecture Reference

## Architecture Overview
The Autonomous Website Generation Engine is a deterministic state machine orchestrating AI capabilities through strict, isolated operational stages. 

## Generation Lifecycle
The pipeline utilizes an immutable GenerationContext passed sequentially across individual BaseGenerationEngine descendants. Data flows monotonically downwards until WorkspaceGeneratorEngine freezes the context into the physical database. 

## State Machine & Pipeline Stages
1. **REQUIREMENTS_ANALYSIS**: Domain identification and structure parsing.
2. **PLANNING**: Core sitemap generation.
3. **ARCHITECTURE**: Layout structural bounds resolution.
4. **COMPONENT_DISCOVERY**: Design Intelligence search queries.
5. **THEME_GENERATION**: Design token and palette creation.
6. **ASSET_GENERATION**: SVG/Imagery discovery.
7. **CONTENT_GENERATION**: Copywriting population.
8. **WORKSPACE_GENERATION**: Direct binding into the Odoo ORM (
exora.builder_session).
9. **OPTIMIZATION**: Node-pruning on persisted payloads.
10. **VALIDATION**: Structural bounds validation against persisted configurations.
11. **PREVIEW**: Generates final UI snapshots reflecting the exact Builder payload.

## Provider Integration
Phase 16 does NOT communicate with external networks directly. It securely interfaces with the Phase 15 Unified Provider Platform via the ExecutionOrchestrator interface.
