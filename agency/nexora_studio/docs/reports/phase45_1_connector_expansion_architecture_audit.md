# Phase 45.1 — Connector Expansion Architecture Audit (3D Sources & GitHub Repository Intelligence)

**Mode:** READ-ONLY audit (no code modified)
**Date:** 2025-08-25
**Scope:** nexora_studio @ D:\ODOO\custom-addons\agency\nexora_studio (dev runtime :8069 / DB nexora_studio). Certification instance nexora_cert (:8169) explicitly out of scope.
**Ground truth policy:** every claim below was verified against current source files (file:line citations). Documentation was treated as claims, not facts.
**Evidence sources:** direct reads of services/, models/, data/, config/, tests/; four parallel sub-audits (CSF/DIP core, capability/builder flow, integrations, doc conventions); targeted re-verification of the five load-bearing files.

---

## 1. Executive Summary

The existing architecture CAN absorb both planned capabilities without introducing any new framework:

- **GitHub repository intelligence** already has a fully working canonical path: the `github_mcp` connector (stdio, `data/connector_github_data.xml`) executes through `UniversalCapabilityRouter → ConnectorExecutionTarget → ConnectorRuntime`, and two CSF sources (`react_bits`, `shadcn`) already consume its tools declaratively via `McpSourceAdapter.config_json.capability_map`. New repo-intelligence tools are a **configuration + capability-map expansion**, not new architecture.
- **3D component sources** fit the same CSF shape: a 3D source is just another `nexora.source_registry` row (`adapter_class='McpSourceAdapter'` or a properly-loaded non-MCP adapter) whose normalization produces the existing `ComponentPackage` domain model. Rendering/validation for R3F+Spline already exists (ADR-0064, Phase 37.1 validators); what is missing is ingestion and code-gen surface — both pluggable into existing pipelines.

However, the audit found **one functional defect that would silently disable all of this at runtime**, plus **four parallel provider/adapter frameworks**, one of which (UCEL COMPONENT providers) overlaps the CSF source set almost exactly (shadcn + react_bits exist in BOTH). These must be consolidated as part of this phase, or we will in fact build a parallel architecture by accretion.

**Headline defect (F-01):** `SearchEngine.search()` filters adapters with `get_capable_providers('SEARCH')` (`services\source_framework\search_engine.py:19`), but `McpSourceAdapter.capabilities` returns *discovered MCP tool names* (`services\source_framework\adapters\mcp_source_adapter.py:80-93`), not the CSF token `'SEARCH'`. Result: both seeded MCP-backed sources are filtered out of federated search today; `ComponentDiscoveryEngine` returns zero candidates from them.

## 2. What Is Authoritative (verified against code, not docs)

| Plane | Authority | Evidence |
|---|---|---|
| Tool/connector execution | **MCP connector platform**: `ConnectorRuntime.dispatch` → `ConnectorDispatcher` → `McpConnector/McpTransport/McpProvider`; namespace contract `{connector_id}.{tool_name}` → `tools.call` (ADR-0069) | services\connector\runtime\connector_runtime.py:250-306; services\connector\integration\connector_executor.py:99-142 |
| Canonical routing | **`UniversalCapabilityRouter`** built identically in two places: GenerationRuntime internally and `build_canonical_router(env)` | services\generation\core\generation_runtime.py:109-116; services\connector\integration\bootstrap.py:298-341 |
| Source registration (CSF/DIP) | **`nexora.source_registry`** rows + `ProviderManager.load_from_registry()` → `McpSourceAdapter` | models\source_framework\source_registry.py:4-32; services\source_framework\provider_manager.py:18-30 |
| Component normalization | **`ComponentPackage`** dataclass (+ Provenance/DesignTokenPackage/etc.) | services\source_framework\domain_models.py:15-31 |
| Ranking | **`ComponentRankingPipeline`** (weights quality .3 / compatibility .3 / internal_preference .1) invoked inside `SearchEngine.search` | services\source_framework\component_ranking_pipeline.py:27-45; search_engine.py:46-49 |
| Generation consumption | **`ComponentDiscoveryEngine`** inside `WebsiteGenerationPipeline` — the ONLY production consumer of the CSF stack | services\generation\engines\component_discovery_engine.py:26-53 |

## 3. Actual Runtime Flow (traced end-to-end)

```
nexora.source_registry (XML-seeded: react_bits, shadcn → connector github_mcp)
  └─ ProviderManager.load_from_registry()            provider_manager.py:18-30   [MCP-only]
       └─ McpSourceAdapter(connector_id, env)        mcp_source_adapter.py:60-74
WebsiteGenerationPipeline (ARCHITECTURE_COMPLETED)
  └─ ComponentDiscoveryEngine.execute                component_discovery_engine.py:26-53
       └─ SearchEngine.search(query, ctx)            search_engine.py:18-51
            ├─ get_capable_providers('SEARCH')       provider_manager.py:35-40   ← F-01 filter kills MCP sources
            ├─ route_request(pid,'search',q)         provider_manager.py:42-55
            │    └─ McpSourceAdapter.search → _execute(intent)
            │         ├─ capability_map intent→tool  mcp_source_adapter.py:124-133 (config_json)
            │         └─ build_canonical_router().execute("{cid}.{tool}")
            │              └─ ConnectorExecutionTarget._build_request → tools.call
            │                   └─ ConnectorRuntime.dispatch → McpTransport (stdio/SSE)
            ├─ MetadataNormalizer.normalize_list     identity stub (metadata_normalizer.py:6-7)
            ├─ DependencyResolver.resolve_graph      appends {"resolved": True} (dependency_resolver.py:6-8)
            ├─ CompatibilityChecker                  always compatible (compatibility_checker.py:6-11)
            ├─ QualityScorer                         constant 0.95 (quality_scorer.py:6-7)
            └─ ComponentRankingPipeline.rank_components (real weights, real sort)
  → EngineExecutionResult.metadata["candidate_components"]
       └─ ComponentRankingEngine: pass-through ("ranking delegated")  component_ranking_engine.py:16-22
       └─ ComponentIntelligenceEngine: IGNORES candidates; fabricates nodes
          from modular_blueprint with placeholder code               component_intelligence_engine.py:26-46
```

**Verdict:** the flow is wired end-to-end mechanically, but (a) F-01 empties it at the first hop, and (b) downstream engines currently discard whatever survives. "Builder consumes CSF" is true only up to `candidate_components` metadata.

## 4. GitHub Repository Intelligence — Current State

- **Working canonical path:** `github_mcp` connector seeded declaratively (`data/connector_github_data.xml:5-36`, stdio docker `ghcr.io/github/github-mcp-server`, read-only flag, credential slot `GITHUB_PERSONAL_ACCESS_TOKEN`). Executed through the router like every other connector.
- **Existing consumers:** CSF sources `react_bits`/`shadcn` map intents to `search_code` / `get_file_contents` via `config_json.capability_map` (`data/source_registry_data.xml:4-57`); `_McpModelProviderMixin` (`models/mcp_model_providers.py:29-77`) exposes `nexora.provider.github`.
- **Stubs/dead:** `services/providers/github_provider.py` (REST stub, mock commit SHA), knowledge `GitHubProvider` (unimplemented), deprecated CSF `github_adapter.py` (MockTransport-fed, DeprecationWarning), dead root script `validate_github_mcp.py` (imports vanished `services.runtime.mcp` package), vestigial disabled JSON entry in `config/mcp_registry.json`.
- **Parallel path risk:** `services/providers/component/github_adapter.py:16-63` is a working direct-REST GitHub integration bypassing ConnectorRuntime — a second GitHub orchestration layer in miniature.

**Conclusion:** repository intelligence/tools = extend tool coverage consumed through the EXISTING github_mcp connector + capability maps. No new orchestration, no second REST client.

## 5. 3D — Current State

- **Exists:** ADR-0064 names React Three Fiber the canonical 3D renderer; R3F validation provider implemented (`services/design/providers/react_three_fiber_provider.py`, registered lazily `provider_registry.py:182-184`); Spline validation + sandbox smoke provider (`services/design/providers/spline_provider.py`, `models/spline_provider.py`, conformance PASS in verification/conformance_dashboard.json:50-57); `three_d_scene` flags in design intelligence; glb/gltf format strings in asset planning.
- **Missing:** 3D source ingestion (no 3D entries in `nexora.source_registry`; only disabled `lifecycle:"planned"` JSON blocks for spline_mcp/threejs_docs_mcp/r3f_docs_mcp/drei_docs_mcp in `config/mcp_registry.json` — vestigial), GLB/GLTF acquisition/serving pipeline (AssetContentEngine has none), R3F scene/code-gen emission.
- **Doc drift:** `docs/reports/template_dependency_graph.md:60-67` cites `penpot_adapter.py` and `design/penpot_provider.py` — neither file exists.

**Conclusion:** 3D sources plug into CSF exactly like react_bits/shadcn (registry row + capability_map + ComponentPackage normalization). The rendering side is governed by ADR-0064 and the DesignProvider stack — out of scope for source expansion beyond consuming what CSF delivers.

## 6. Duplicates That MUST Be Consolidated (anti-parallel-architecture)

| # | Duplication | Disposition required this phase |
|---|---|---|
| D-01 | **Four adapter/provider frameworks**: CSF BaseProviderAdapter; UCEL BaseProvider+DI container (shadcn/magic_ui/aceternity/react_bits/21st.dev/internal_template — real HTTP implementations); legacy services\adapters ComponentAdapter; DesignProvider/RenderingProviderRegistry | Do NOT create a fifth. This phase extends CSF as THE source-discovery plane. UCEL COMPONENT providers stay as-is (separate mandate); declare CSF↔UCEL boundary in ADR; forbid new direct-HTTP source clients (retire pattern of github_adapter.py-in-UCEL for new work) |
| D-02 | **shadcn + react_bits registered in BOTH CSF (source_registry over github_mcp) and UCEL (direct HTTP/scrape)** | Pick one plane per source in ADR; document CSF rows as authoritative for generation-time discovery |
| D-03 | **Three UniversalCapabilityRouter wirings** (GenerationRuntime, build_canonical_router, PlanningEngine throwaway LOCAL-only router that can never succeed — planning_engine.py:54-66) | Leave the two legitimate ones (acknowledged duplication, bootstrap.py:303-310); delete/neutralize PlanningEngine throwaway in this phase's consolidation unit |
| D-04 | **Two generation architectures** (engine pipeline vs DB-stage legacy) with incompatible stage.execute signatures (orchestrator calls execute(job,stage,ctx); numbered stages define execute(ctx) → latent TypeError) | Out-of-scope to fix wholesale; ADR must pin which pipeline the new capabilities target (engine pipeline Path A) and record the signature hazard |
| D-05 | Model zoo overlap: nexora.component vs nexora.component_index; nexora.capability vs nexora.capability_registry vs nexora.capability_definition | No new models; reuse component_index as the single cache/index if persistence is needed (currently zero production writers) |

## 7. Incomplete / Dead Inventory (verified)

**Incomplete (declared but inert):** ProviderManager non-MCP loading (`pass` branch, provider_manager.py:28-30); `adapter_class` string never dynamically resolved anywhere; `nexora.component_index` written by nothing in production (tests only, test_dip_orm.py:32-47); MetadataNormalizer/DependencyResolver/CompatibilityChecker/QualityScorer are identity/constant stubs; ranking weights reference unused dimensions (performance/reliability/ai_confidence declared, absent from formula); ComponentReplacementEngine has no production caller.

**Dead/removable:** deprecated `source_framework/adapters/github_adapter.py`; entire legacy `source_framework/transport/*` package (LEGACY banners + DeprecationWarnings; only consumer is the deprecated GitHubAdapter); `services/providers/component/figma_adapter.py` (+ import in component/__init__.py:1) contrary to ADR-0029 eradication; phantom capability seed `mcp.figma → nexora.provider.figma` pointing at a nonexistent model (capability_providers_service.py:83-91); root `validate_github_mcp.py`; `scripts/run_piat.py:59-60` referencing nonexistent providers `nexora.provider.threejs_docs`/`.r3f_docs`; stale tests mocking `adapter._runtime.dispatch` (test_mcp_source_adapter.py:56) which no longer exists post-44.2 refactor.

**Missing governance:** `nexora.source_registry` and `nexora.component_index` have no ACL rows and no views.

## 8. Where New Functionality Plugs In (audit conclusion)

1. **GitHub repository intelligence tools** → extend the existing `github_mcp` connector usage:
   - New/extended CSF source rows (or expanded capability_map on existing rows) declaring intents → github_mcp tools;
   - Optionally one thin `AbstractModel` following `_McpModelProviderMixin` if an ORM-level service surface is needed (pattern precedent: Tavily/Github/Context7 providers);
   - Execution automatically inherits transport/session/credential/security infrastructure. Zero new transport code.
2. **3D component/source connectors** → new `nexora.source_registry` rows (MCP-backed where an MCP server exists, e.g., drei/r3f docs-style servers) normalized into `ComponentPackage` (extended_metadata carrying `three_d_scene`/format hints aligned with ADR-0064 vocabulary), flowing through SearchEngine → ComponentDiscoveryEngine. Non-MCP 3D adapters become reachable only after implementing the ProviderManager non-MCP branch (currently `pass`) — a prerequisite consolidation unit, not new architecture.
3. **Prerequisite fixes without which expansion is invisible:** F-01 capability-vocabulary reconciliation (CSF tokens vs discovered tool names) and the ProviderManager non-MCP branch decision (implement dynamic resolution of `adapter_class`, or restrict the registry contract to MCP-backed sources and say so in the ADR).

## 9. Feasibility Statement (mandated by task)

Both GitHub repository intelligence AND 3D component/source connectors are representable by the existing CSF/DIP abstractions (`BaseProviderAdapter`/`McpSourceAdapter`/`ComponentPackage`/`SearchEngine`/`ComponentRankingPipeline`/`nexora.source_registry`) plus the canonical MCP routing contract (ADR-0069) **without** a second DIP, CSF, provider registry, ranking engine, or duplicate GitHub orchestration layer. The audit found no requirement that the existing architecture cannot support.

## 10. Risk Register (top)

| ID | Risk | Mitigation direction |
|---|---|---|
| R-A | F-01 leaves expansion functionally dead even after perfect configuration | Fix capability reconciliation as W-item 0 in the plan; add a regression test proving an MCP source participates in federated search |
| R-B | Consolidation scope creep into the four-framework problem | ADR draws a hard line: CSF = source-discovery authority; UCEL untouched except boundary documentation; no migrations of UCEL providers this phase |
| R-C | Downstream discard (candidate_components ignored by enrichment) makes E2E value invisible | Include a builder-integration unit that actually consumes ranked packages in ComponentIntelligenceEngine input path, else acceptance stays synthetic |
| R-D | Legacy stage-signature TypeError trap (D-04) if anyone reruns Path B | Documented hazard only; no repair in this phase |
| R-E | cert/dev drift temptations | Implementation targets dev only; cert remains acceptance-only |

---

### Verdicts

- 3.1 Authoritative planes identified … **PASS**
- 3.2 Runtime flow traced with evidence … **PASS**
- 3.3 Reusable inventory established (MCP platform, CSF stack, ComponentPackage, ranking, github_mcp) … **PASS**
- 3.4 Incomplete/dead/duplicated catalogued (F-01, D-01…D-05, §7) … **PASS**
- 3.5 Plug-in points defined for 3D + GitHub without new architecture … **PASS**
- 3.6 Consolidation prerequisites explicit before implementation … **PASS**

**Audit status: COMPLETE. Next step: Phase 2 — ADR-0072 (proposed number; highest existing is ADR-0071).**
