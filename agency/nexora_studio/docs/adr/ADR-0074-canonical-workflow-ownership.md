# ADR 0074: Canonical Production Website-Generation Workflow and Ownership

## Status
Accepted

Ratified as part of Phase 47.8A closure. Required by Phase 47.1 audit of workflow-closure ownership gaps.

## Context

Phase 47.1 defined the canonical production website-generation workflow as ten units `U1`–`U10`. Units `U1`–`U7` are complete and verified. The Phase 47.1 audit recorded that no single document enumerated the end-to-end decision chain: which service owns which boundary, which invariants are mandatory, and what constitutes a valid generation run. This ADR consolidates those decisions into one authoritative reference so future work (U8–U10 and beyond) cannot silently drift the contract.

## Decision

The following 20 decisions are the canonical ownership and invariant rules for the production website-generation workflow in Nexora Studio. Any change to the workflow must amend or supersede this ADR.

### 1. Single Production Entry Point
`POST /api/v1/ai/generate` → `BuilderSessionService.run_generation()` is the sole production entry. No alternative endpoint, no direct `GenerationCoordinator` invocation, no manual `GenerationRuntime` construction from controllers.

### 2. Session Lifecycle Owner
`BuilderSessionService` is the sole owner of session state (`draft` → `preparing` → `generating` → `completed` / `failed`). `GenerationCoordinator` receives a session but never writes lifecycle state.

### 3. Workspace Precondition
`GenerationCoordinator.start_generation()` must verify a managed workspace exists (via `WorkspaceService.get_or_create_session_workspace`). No workspace → generation refused. This is a hard gate, not a soft warning.

### 4. Concurrency Gate
Exactly one generation per session at a time. `GenerationCoordinator` enforces this via `BuilderSessionService` state check (`generating` blocks new runs). No per-request locking; session state is the source of truth.

### 5. Explicit Environment
`GenerationRuntime` receives `env` explicitly in its constructor. It MUST NOT acquire `env` from `odoo.http.request` or any thread-local. Controllers pass `self.env`; tests pass a fake `env`. This is a structural invariant.

### 6. Single Universal Capability Router
Exactly one `UniversalCapabilityRouter` instance exists per `GenerationRuntime`. It is constructed in `GenerationRuntime.__init__` and exposed as `runtime.ucel_router`. `PlanningEngine` uses `runtime.orchestrator.execute_prepared_plan(plan)` — it MUST NOT construct a shadow router or call `build_canonical_router` directly.

### 7. Capability Scope Registry
`GenerationRuntime._registry` (`RuntimeScopeRegistry`) is the sole declaration of which engine receives which runtime capabilities (`tools`, `orchestrator`, `ai`, `env`, etc.). Engines declare their required scopes via `get_scoped_view(EngineClass)`. No engine may reach outside its declared scope.

### 8. Checkpoint Serialization
`GenerationStateManager` serializes full engine context (artifacts, decisions, intermediate state) to JSON. Checkpoint keys are `(session_id, generation_id, stage_name)`. Only successful stage boundaries produce checkpoints.

### 9. Strict Checkpoint Restore
`GenerationStateManager.load_checkpoint()` restores the exact prior context object graph. No partial restore, no merge. If the checkpoint is missing or corrupt, the generation is marked `failed` and a new run must start from `draft`.

### 10. Rollback Does Not Overwrite
A failed/interrupted generation does NOT overwrite the last valid checkpoint. The last successful boundary remains the source of truth for any subsequent resume or new run.

### 11. Progress Advances Only on Success
`GenerationStateManager.update_progress()` is called ONLY after a `StateTransitionCompleted` event for the stage. Failed stages do not increment `completed_stages` or `progress_percent`. Progress is monotonic and bounded by successful stages.

### 12. ContentEngine Single Execution
`ContentEngine` executes exactly once in the pipeline, between `ASSETS_GENERATED` and `WORKSPACE_PREPARED`. It is not invoked during planning, component discovery, or asset generation.

### 13. Requirement Preservation
All `BusinessRequirement` objects from `RequirementEngine` flow through `GenerationContext.requirements` unchanged. No engine may filter, re-rank, or mutate requirements; they are immutable input to the pipeline.

### 14. Workspace Output Truthfulness
Generated workspace output MUST be truthful:
- Real session workspace path returned (no temp/placeholder paths).
- Generated pages wired into existing `src/App.jsx` (React entry point).
- File-write failures fail the stage (no silent empty output).

### 15. Component Source Framework Semantics
`SearchEngine.search()` default operation remains `'SEARCH'` for backward compatibility. `ComponentDiscoveryEngine` explicitly uses `operation='COMPONENT_SOURCE'`. A source declaring both `COMPONENT_SOURCE` and `SEARCH` is invoked once via `discover_components()` in component-source mode.

### 16. Component Ranking Failure Isolation
`ComponentRankingPipeline` failure does not halt the pipeline. It logs a warning, returns an empty ranked list, and the pipeline proceeds with a fallback (first-discovered package). The failure is recorded in `generation_metadata['ranking_warnings']`.

### 17. Non-Component Artifact Consumers (U7)
`BusinessData` → `BusinessResearchEngine` → `artifact.research['business_data']` with provenance.  
`RepositoryArtifact` + `KnowledgeDocument` → `KnowledgeEnrichmentEngine` → `artifact.knowledge['implementation_context']` + `artifact.knowledge['knowledge_documents']` with provenance.  
`DesignAsset` → `AssetEngine` → `artifact.assets` (images/icons/fonts buckets) with provenance; unmapped types deferred to `generation_metadata['design_assets_deferred']`.  
`ComponentPackage` → `ComponentTree` → `CodeGenerationEngine` handoff re-verified.

### 18. Capability Classification Authority
`nexora.capability_registry` is the authoritative store for platform policy (`implementation_model`, `supports_local`, `supports_remote`, `enabled`, `state`). `mcp_registry.json` is the authoritative bootstrap source (ADR-0068/0070). `_derive_target_type` derives `ExecutionTargetType.CONNECTOR` when `implementation_model == 'connector'`. Remote-only rows (no local support, not connector) resolve to `REMOTE` which has NO registered executor — `GenerationRuntime` refuses to boot.

### 19. Penpot Classification
`mcp.penpot` is a registry-backed MCP connector. Its capability row MUST have `implementation_model='connector'`, `supports_local=false`, `supports_remote=false` → `CONNECTOR`. A stale REMOTE row is a boot-blocking defect corrected by Phase 47.8A migration.

### 20. Migration Mechanism
Controlled DB corrections use the existing Odoo migration mechanism (`migrations/<version>/post-migrate.py`). Module version bump triggers the migration on `-u nexora_studio`. `post_init_hook` runs ONLY on install, not upgrade, so a migration applied via upgrade does NOT re-trigger `execute_bootstrap()` and its full registry re-sync side effects.

### 21. Final Acceptance Gate (U9.6)
`ValidationEngine` is the sole owner of the final acceptance decision. At the end of its browser phase it computes `final_acceptance` (`accepted`/`failed`) by aggregating the EXISTING build (`build_acceptance`), preview (preview runtime contract), browser (`browser_validation`) and renderer (`browser_validation.renderer_runtime`) evidence. Rules:
- build must pass, preview must be healthy, browser must pass, and renderer must pass when renderer != `react`; `react` is `not_applicable` and never blocks.
- a missing/unknown renderer identity fails (`renderer_identity_missing`/`renderer_identity_unknown`) — never guessed.
- the gate scopes blocking aggregation to the acceptance layers (build/preview/browser/renderer); seo/design/dynamic-validation issues remain observable but non-gating (preserving pre-U9.6 behaviour).
- warnings never block; the decision is deterministic, side-effect free (never executes npm/build/preview/browser/connector/DB work), and stored in `ValidationReport.final_acceptance` + context metadata.
- no new pipeline state: `BROWSER_VALIDATED` remains the last validation state and is only reached when the final gate accepts.

## Consequences

- `U8` (Plan-and-Execute) must use `runtime.orchestrator.execute_prepared_plan(plan)` and declare its scope via `RuntimeScopeRegistry`.
- `U9` (Preview Runtime) must wire the preview server to the session workspace path and respect the single `ContentEngine` boundary.
- `U10` (Delivery & Verification) must use the final checkpoint as the source of truth for deployment artifacts.
- Any new capability surface must declare its `implementation_model` in `mcp_registry.json` and its policy in `nexora.capability_registry`; ad-hoc rows are forbidden.
- The `nexora_cert` database is off-limits for all workflow-closure phases.
- Existing six connectors remain disabled (`state='disabled'`, `health_status='unknown'`) as steady state.

## Verification Evidence

| Evidence | Source |
| --- | --- |
| `U1`–`U7` test suites pass (129 tests) | `tests/test_phase47_*_*.py` |
| `GenerationRuntime` boot passes with corrected penpot row | `tests/test_phase47_8a_runtime_boot.py` (6/6) |
| DB integrity: connectors=6 (all disabled), sources=6, credentials=5, configs=6 | Read-only probe against `nexora_studio` |
| Stale adapter tests rewritten to canonical router contract | `tests/test_mcp_source_adapter_mappings.py` (10/10) |
| Phase 45/46 regression including architecture integrity | 57/57 OK |
| `git diff --check` clean, `py_compile` clean | CI gate |

## Related ADRs
- ADR-0068 (MCP Platform Hardening) — CONNECTOR classification authority
- ADR-0070 (Authoritative Capability Store) — three-store model
- ADR-0072 (Connector Expansion via Existing Source Framework) — CSF normative vocabulary
- ADR-0073 (Business Location Intelligence via Gosom MCP Shim) — Gosom integration