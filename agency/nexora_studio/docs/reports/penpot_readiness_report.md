# Penpot Readiness Report

## Executive Summary

Based on dependency graphs, coupling, and dataflow analysis, **Penpot currently REPLACES the Template Store but merely COMPLEMENTS Frontend Templates.**

## Evidence: Replacement of Template Store

The legacy `template_store` module (`custom-addons/shared/template_store`) was designed to act as a monolithic registry for pre-built websites.
Penpot replaces this responsibility entirely:
1. **Design System Engine**: `nexora.design_system_engine` utilizes `DesignBlueprints` and sends them to `DesignOrchestrator`.
2. **Provider Delegation**: The orchestrator defaults to `PenpotDesignProvider` (`design_orchestrator.py:41` - "Penpot is the primary default provider").
3. **No Legacy Calls**: The modern Builder (`WebsiteGenerationPipeline`) makes **zero** calls to `nexora.generation_service` or `nexora.template_metadata`. All design logic flows through Penpot blueprints instead of static Odoo model paths.

*Conclusion:* Penpot is fully ready to assume the role of the Template Store. The old Odoo-based Template Store is dead architecture.

## Evidence: Complementation of Frontend Templates

While Penpot replaces design metadata, it **does not** replace raw technical scaffolding (Frontend Templates).
1. **Asset & Content Planning**: The pipeline relies on Penpot for colors, typographies, and layout tokens, but Penpot cannot generate a functional `vite.config.ts` or `package.json`.
2. **Materialization Base**: The system still utilizes starter folders (`stage_03_template_materialization.py` / `verify_real_generation.py`) to copy boilerplate React code into the workspace.
3. **AI Mutation Target**: `stage_06_ai_code_generation.py` uses `nexora.template_analyzer` to read the scaffolding and instructs the AI to "Modify existing template files". The AI needs a base React tree to mutate.

*Conclusion:* Penpot complements the Frontend Templates. Penpot provides the visual intelligence and design tokens, while the Frontend Templates provide the execution environment (Vite/React boilerplate) that the AI subsequently writes code into.
