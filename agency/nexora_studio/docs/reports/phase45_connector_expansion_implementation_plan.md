# Phase 45 Connector Expansion Implementation Plan (Rev 2) — 3D Sources & GitHub Repository Intelligence

**Architecture Basis:** ADR-0072 (amended post-review) + ADR-0027/0028 + ADR-0052 + ADR-0064 + ADR-0068/0069
**Audit Basis:** docs/reports/phase45_1_connector_expansion_architecture_audit.md
**Target:** nexora_studio / dev (:8069) ONLY. nexora_cert is certification-only and MUST NOT be touched. CG-01…CG-40 out of scope.
**Status:** Rev 2 — reworked per pre-implementation review. NOT approved for coding until explicitly approved.
**Additive Guarantee:** no new models, no new frameworks, no second CSF/DIP/registry/ranking engine, no GitHub REST client, no dynamic plugin loading.
**Rollback:** per-unit git revert; data-row caveats documented in-unit.

---

## 0. Verified Runtime Contracts (grounding for every unit below)

| Contract | Verified fact | Source |
|---|---|---|
| Ranking is component-typed | `rank_components` reads `item["package"]` as `ComponentPackage` (compatibility_report, provenance.provider) | services\source_framework\component_ranking_pipeline.py:31-36 |
| Canonical repo-artifact model already exists | `RepositoryArtifact(artifact_id, path, content, type, metadata, provenance)` | services\source_framework\domain_models.py:78-85 |
| Metadata bus between engines | pipeline merges `result.metadata` → `context.metadata`; engines receive only `artifact`; `ComponentIntelligenceEngine` reads `artifact.generation_metadata["modular_blueprint"]` | website_generation_pipeline.py:131-135; component_intelligence_engine.py:26 |
| Discovery output today | candidates placed only in `result.metadata["candidate_components"]` → unreachable by enrichment engines | component_discovery_engine.py:58-62 |
| Enrichment behavior today | ignores candidates; fabricates nodes from blueprint with placeholder code | component_intelligence_engine.py:21-46 |

Consequences: (a) repository intelligence artifacts = **`RepositoryArtifact`**, never forced into `ComponentPackage`, and deliberately NOT routed through the component ranking pipeline (no type abuse, no second engine); (b) builder integration requires a two-line-class change pair: discovery publishes ranked candidates on the artifact bus, enrichment consumes them — verified as the genuine missing boundary.

## 0b. Semantic Capability Vocabulary (normative)

`SEARCH` · `FETCH` · `COMPONENT_SOURCE` · `REPOSITORY_INTELLIGENCE`

Declared on `nexora.source_registry.capabilities` (CSV). `McpSourceAdapter.capabilities` returns these tokens; concrete MCP tool names are internal to execution and validated against discovered tools at call time.

---

## U1 — F-01 semantic capability reconciliation  *(first unit, unchanged priority)*

**Extend:** `services/source_framework/adapters/mcp_source_adapter.py`
- `capabilities` property (lines 80–93) → parse declared tokens from linked `nexora.source_registry.capabilities` CSV (via `_ensure_config_loaded`).
- NEW private `_discovered_tools()` → exact current tool-name logic moved verbatim (discovered tools, fallback connector capability_ids).
- `_execute` guard (lines 155–161) → validate against `_discovered_tools()`.
- New adapter method `fetch_repository_artifacts(intent, params) -> List[RepositoryArtifact]` for `REPOSITORY_INTELLIGENCE` sources: resolves intent→tool via capability_map, executes through the same `_execute` router chain, normalizes MCP results into `RepositoryArtifact` (artifact_id/path/content/metadata/provenance).

**Untouched:** `SearchEngine`, `ProviderManager` (they operate on semantic tokens and start working unchanged).

**Tests:** (1) source declaring `SEARCH` is returned by `get_capable_providers('SEARCH')`; (2) source whose discovered tools include e.g. `search_code` but declares NO semantic token is NOT discoverable (tool names ≠ capabilities); (3) `_execute` still rejects intents resolving to undiscovered tools; (4) existing react_bits/shadcn behavior preserved after their rows gain declarations.

**Rollback:** revert commit. No data dependency.

## U2 — GitHub repository intelligence via existing github_mcp

**Extend:** `data/source_registry_data.xml` — new noupdate row:
- `technical_name='github_repo_intelligence'`, `adapter_class='McpSourceAdapter'`, `connector_id=connector_github_mcp`
- `capabilities="REPOSITORY_INTELLIGENCE,FETCH"`
- `config_json.capability_map`: `{"repo_search": "search_repositories", "code_search": "search_code", "fetch_file": "get_file_contents"}` (+ payload_mapping/normalization for `RepositoryArtifact` shaping)
Also add `capabilities="SEARCH"` to existing react_bits/shadcn rows.

**Flow:** github_mcp → UniversalCapabilityRouter (`tools.call`) → McpSourceAdapter → `RepositoryArtifact`s. NO REST client, NO separate orchestration/registry. Artifacts bypass component-ranking by design (contract 0, row 1); ordering inherited from tool results.

**Tests:** mapping tests (router-path mocks per Phase 44.2 reality); `RepositoryArtifact` shaping test; negative test asserting no ComponentPackage fabrication for this source.

**Rollback:** revert XML; manual unlink of inserted row if desired (noupdate caveat).

## U3 — canonical 3D artifact ingestion/normalization contract

**Extend:** normalization logic inside `McpSourceAdapter` (config-driven `normalization` map + structural heuristics, lines 201–267 region) and module-level constants for ADR-0064 metadata keys (new small constants block — location: `domain_models.py` bottom, no schema change).

**Contract (implemented + tested here):**
```
discovery intent (SEARCH over source)
→ candidate identification (config-driven filters: path/extension/name patterns)
→ source/artifact retrieval (FETCH via get_file_contents)
→ normalization → ComponentPackage ONLY if qualifying:
     actual component/scene code or scene asset present (e.g., imports @react-three/fiber,
     .glb/.gltf asset reference) — bare repository metadata NEVER becomes a package
→ provenance (Provenance: repo/commit/path/license) + dependencies (parsed from
     retrieved package.json when present)
→ renderer metadata attached only to qualifying packages:
     three_d_scene=True, asset_format=glb|gltf (when applicable),
     renderer_expectation=react_three_fiber|spline
→ validation at normalization time: required deps present (three, @react-three/fiber)
     else candidate rejected with logged reason
→ existing SearchEngine scoring/ranking/resolution unchanged
```

No ThreeDRegistry / ThreeDComponentService / separate discovery engine / separate ranking / separate provider registry.

**Tests:** qualifying vs non-qualifying payloads; dependency-validation rejection; metadata-key constants usage.

**Rollback:** revert commit.

## U4 — one real high-value 3D source end-to-end

**Extend:** `data/source_registry_data.xml` — new noupdate row `threed_component_library`:
- `adapter_class='McpSourceAdapter'`, `connector_id=connector_github_mcp`
- `capabilities="SEARCH,FETCH"`
- `config_json`: discovery config targeting the pmndrs ecosystem (drei/R3F example repositories) via `search_repositories`/`search_code`; retrieval config pulling actual `.tsx/.glb` artifacts via `get_file_contents`; normalization config per U3 contract.

**End-to-end proof (dev):** federated search returns a REAL generation-relevant 3D `ComponentPackage` (code present, ADR-0064 metadata attached, provenance populated) — not a repository-metadata shell. Live `github_mcp` round-trip through ephemeral runtime.

**Rollback:** revert XML; manual row removal if desired.

## U5 — generation integration (only after U2/U4 prove the artifact contract)

Verified gap: candidates travel in `result.metadata` which never reaches enrichment engines (contract table). Smallest fix:

**Extend (two spots):**
1. `services/generation/engines/component_discovery_engine.py` — additionally publish ranked candidates on the artifact bus: `artifact.evolve(generation_metadata={**artifact.generation_metadata, "candidate_components": [...]})` (one-line-class change).
2. `services/generation/engines/component_intelligence_engine.py` — before fabricating blueprint-derived nodes, match section types against `candidate_components` from `artifact.generation_metadata`; matched sections use the candidate's identity/metadata; unmatched keep current placeholder behavior.

The builder gains NO search/rank/resolve/match machinery of its own — it only consumes already-ranked candidates.

**Tests:** engine-pair test (discovery metadata → intelligence node selection + fallback path).
**Rollback:** revert both commits independently.

## U6 — tests, integration verification, architecture-integrity checks

1. Focused unittests after every unit (standalone runner pattern from Phase 44.2): refreshed `test_mcp_source_adapter*.py`, new reconciliation/artifact/normalization/integration test modules listed per-unit above; regression: `test_dip_orm.py`, `test_provider_registry.py`.
2. Integration (dev): federated-search probe returning MCP-backed + 3D candidates; live `github_mcp` round-trip via canonical non-persisting tester.
3. Log safety: cert-style scan on dev log proving zero credential values written during verification runs.
4. Architecture-integrity assertions (committed as tests/greps):
   - exactly ONE source-registration write path for generation-time discovery (`nexora.source_registry`)
   - exactly TWO sanctioned `UniversalCapabilityRouter` construction sites (GenerationRuntime, build_canonical_router)
   - no new direct-HTTP clients under `services/source_framework/`
   - single ranking pipeline; single federated search entry (`SearchEngine.search`)
   - single generation consumption boundary for CSF (`ComponentDiscoveryEngine`) + the one enrichment consumer (U5)
5. Negatives: nexora_cert untouched; CG-01…CG-40 not executed; no manual DIP/CSF registration edits.

---

## Deferred to future consolidation phase (explicitly OUT of this phase)

- ProviderManager dynamic adapter resolution (non-MCP branch remains stubbed; limitation recorded)
- PlanningEngine throwaway-router consolidation
- UCEL COMPONENT-provider migration / CSF↔UCEL convergence
- Legacy `source_framework/transport/*` removal
- Figma remnant removal (incl. phantom `mcp.figma` capability seed)
- Model-overlap cleanup (nexora.component vs component_index etc.)

## Change Summary vs Rev 1

| Rev 1 | Rev 2 |
|---|---|
| U2 dynamic adapter resolution | **REMOVED** → deferred consolidation |
| U3 PlanningEngine consolidation | **REMOVED** → deferred consolidation |
| U5 3D = repo-search→ComponentPackage | **REWORKED**: full ingestion chain U3+U4; qualifying-artifact rule; RepositoryArtifact split for repo intel |
| U6 modify ComponentIntelligenceEngine directly | **GATED**: modification justified by verified metadata-bus gap; paired minimal discovery-side publish |
| — | Added normative capability vocabulary; architecture-integrity assertion set; explicit deferred list |

## Model / Config Change Summary

| Kind | Change |
|---|---|
| New Odoo models | none |
| Field changes | none |
| Module data | source_registry_data.xml: +2 rows, capabilities on 2 existing rows |
| Config files | none |
