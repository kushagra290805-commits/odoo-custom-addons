# ADR-0073: Business Location Intelligence Via A Gosom MCP Shim — First External Capability Connector

## Status: Proposed
## Date: 2026-08-26

## Context

Nexora Studio's connector program (Phase 46) targets ~15 high-value external capabilities. The first candidate is **business/location intelligence** via the open-source `gosom/google-maps-scraper` project (MIT, Go, actively maintained, v1.17.4): a Playwright-based Google Maps extractor with CLI, Web UI, and an unauthenticated REST job API (`/api/v1/jobs`), producing 36 structured fields per place (identity, contact, geo, hours, CTAs, social proof, optional reviews/emails).

Phase 46.1 audit (`docs/reports/phase46_1_gosom_maps_architecture_audit.md`) verified:
- No native MCP interface exists in gosom; its REST API is the automation surface.
- Nexora's canonical execution plane is the MCP connector platform + `UniversalCapabilityRouter` (`{connector}.{tool}` → `tools.call`, ADR-0069), with semantic capability tokens declared on `nexora.source_registry.capabilities` (ADR-0072 decision 4: SEARCH/FETCH/COMPONENT_SOURCE/REPOSITORY_INTELLIGENCE).
- The canonical domain model layer already contains **`BusinessData`** (`domain_models.py`: data_id/category/payload/provenance) — semantically exact for normalized business-place facts.
- The ProviderManager non-MCP adapter branch remains a deferred stub (ADR-0072 amendment); any design requiring it is blocked.

The candidate fills a factual dimension no current source provides: real-world business ground truth (identity, contact, location, hours, social proof) for local-business website generation, reconstruction, market context, and enrichment.

## Decision

1. **Integrate gosom as the first external capability connector using Option A — a minimal MCP shim.** A small stateless MCP stdio/server implementation wraps gosom's REST API and exposes exactly two tools: `business_search` (bounded multi-query search) and — later, when a consumer requires it — `business_fetch` (single-place detail). The shim is onboarded through the existing declarative connector pattern (`nexora.connector` + `nexora.mcp_server_config`, stdio command), inheriting transport, health, discovery, tester, and credential infrastructure with zero new Nexora-side frameworks.

2. **Semantic capability contract.** The source declares **`BUSINESS_SEARCH`** (and `BUSINESS_FETCH` when activated) on `source_registry.capabilities`. These extend the normative token vocabulary of ADR-0072 decision 4. Concrete gosom operations (REST endpoints, depth, fast-mode, proxies) remain implementation details behind the contract.

3. **Domain artifact = existing `BusinessData`.** Normalized places are emitted as `BusinessData(data_id=place_id-or-cid, category='business_place', payload={stable-core + present-variable fields}, provenance=Provenance(provider=source technical_name, …))`. RepositoryArtifact/ComponentPackage are explicitly NOT used. Business artifacts do NOT enter `ComponentRankingPipeline` (component-typed contract); they feed research/enrichment consumers as retrieval artifacts.

4. **Deployment & isolation.** gosom runs in its own container in REST mode, bound to the internal Docker network only (its REST API is unauthenticated upstream and must never be host/public-exposed). The MCP shim is the sole caller. Playwright/Chromium resource weight is isolated from Odoo processes.

5. **Bounded-operation governance (hard limits enforced by the shim):**
   - ≤ 5 input queries per request; results per query capped (depth ≤ 1 or fast-mode ≤ 21);
   - concurrency ≤ 2; per-job wall clock ≤ 10 min; shim polling timeout ≤ 60 s/cycle;
   - retries ≤ 1; `exit-on-inactivity` honored; results cached by normalized query+geo+lang;
   - enrichment switches (`-email`, `-extra-reviews`) OFF by default;
   - no auto-pagination beyond caps ⇒ "find every restaurant in Delhi" resolves to bounded, cancellable jobs.
   - Direction strictly read-only (no login/review-interaction flows).

6. **Security boundaries.** No new public network surface; secrets: none required for base operation (optional proxy credentials later via existing credential infrastructure). Scraped Google content is operational data subject to operator compliance responsibility (Google ToS); the MIT license covers the tool only — this risk is accepted at product level and mitigated by caching/bounding rather than uncontrolled harvesting.

7. **What is intentionally NOT introduced:** a second connector registry, discovery engine, ranking pipeline, router, generation path; a BusinessRegistry/MapsRegistry/MapsSearchEngine; forced `ComponentPackage` shaping of business data; any Figma-related integration (Figma = EXCLUDED from the connector program); implementation of the deferred ProviderManager non-MCP branch.

8. **Rejected alternatives:**
   - *Direct REST Python provider adapter inside Odoo* — requires the deferred ProviderManager branch, embeds HTTP/retry/pooling logic in-process, forfeits connector lifecycle/health isolation, and would pressure the team to implement that stub early (scope creep).
   - *Native LOCAL-target tool via `nexora.tool_registry`* — routes around source-registry semantics, overlaps the tool_registry vs capability_registry duplication flagged in the Phase 45 audit, and lacks connector lifecycle/health semantics.
   - *Adopting LeadsDB (companion SaaS) as the integration surface* — external managed dependency; unnecessary when gosom's own REST API suffices locally.
   - *Forcing place records into `ComponentPackage`* — semantic type abuse; component ranking/scoring does not apply to business facts.

9. **Migration/compatibility.** Additive only: one XML data triple (connector/config), one source_registry row declaring `BUSINESS_SEARCH` (+ shim command), one new adapter-agnostic consumer path reusing the Phase 45 reconciliation (semantic tokens already filter correctly post-F-01). Existing sources/connectors unaffected; rollback = remove data rows + shim binary.

10. **Testing/verification strategy.** Unit: shim tool mapping incl. bounded-params enforcement and error sanitization; normalization MCP→`BusinessData`; capability declaration discoverability. Integration: canonical `_run_test` against the live shim (job create → poll → initialize → tools.list); federated retrieval probe returning `BusinessData`. Negative: caps enforcement (oversized request rejected), unauthenticated-API exposure check (port not published). Regression: full Phase 45 focused suite.

11. **Operational notes.** Scraper fragility is inherent (Google changes); mitigation = active-upstream pinning (image/tag bumps treated as routine maintenance), bounded defaults above, and graceful degradation (enrichment is optional by design). Resource footprint (Playwright/Chromium) is containerized with explicit CPU/memory limits.

## Consequences

* **Positive**: first external capability lands with near-zero architectural cost; opens business/location intelligence for the highest-volume website vertical; establishes the reusable shim+semantic-token pattern for the remaining ~14 connectors; business facts become available to research/enrichment without touching component discovery/ranking.
* **Negative**: adds a Chromium-capable container to the dev stack; scraper-class maintenance dependency (upstream tracking Google changes); unauthenticated upstream REST forces strict internal-only binding discipline; scraped-data ToS compliance is an ongoing product-level responsibility; BUSINESS_FETCH intentionally deferred until needed.
