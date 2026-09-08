# Phase 46.1 — GOSOM Google Maps Scraper — Architecture & Value Audit

**Mode:** READ-ONLY audit + documentation. No implementation, no installs, no DB/Docker/Nexora changes.
**Date:** 2026-08-26
**Subject:** https://github.com/gosom/google-maps-scraper (audited against live upstream `main` @ push 2026-08-22, release `v1.17.4`)
**Nexora side verified against:** Phase 45 implementation state (semantic capability reconciliation shipped; `BusinessData` domain model present at `services/source_framework/domain_models.py:87-92`; ProviderManager non-MCP branch remains a deferred stub).

---

## PART 1 — UPSTREAM AUDIT (verified facts)

### 1.1 Maintenance / release status
- **MIT licensed**, Go, **5,618★**, 881 forks, **not archived**, pushed **2026-08-22**, 328 commits.
- Latest release **v1.17.4** (2026-08-22, same week as audit) ships prebuilt binaries including `windows-amd64.exe`.
- Active maintenance cadence: multiple releases in the 1.17.x line; sponsored project (proxy/scraping vendors) ⇒ sustained maintenance incentive.

### 1.2 Deployment modes
| Mode | Status |
|---|---|
| CLI (batch query file → CSV/JSON) | ✅ primary |
| Docker image (`gosom/google-maps-scraper`, Playwright-based) | ✅ recommended |
| Web UI (`-web`, :8080) | ✅ |
| **REST API** (`/api/v1/jobs` POST/GET/DELETE + `/download`, OpenAPI 3.0.3) | ✅ when web server runs |
| Library/package | Go module (importable) |
| Distributed | PostgreSQL job provider + Kubernetes sample |
| SaaS edition | optional self-hosted multi-user platform |
| **Native MCP interface** | ❌ **does not exist** in this repo (the "MCP" mention belongs to the external LeadsDB companion) |

### 1.3 Input capabilities
- Query file (one search per line) or direct Google Maps URLs (`/maps/search/…`, `/maps/place/…`, short `maps.app.goo.gl` links).
- Custom per-line input IDs (`query#!#MyID`).
- Tuning: `-depth` (scroll pages), `-lang`, `-geo`+`-zoom`+`-radius`, `-grid-bbox`+`-grid-cell` (area coverage), `-fast-mode` (≤21 nearest results, beta).
- Optional enrichment switches: `-email` (crawls business websites), `-extra-reviews` (~300 reviews).

### 1.4 Output fields (36 documented)
See upstream "Extracted Data Points": title, category, address, complete_address, open_hours, popular_times, website, phone, plus_code, review_count, review_rating, reviews_per_rating, latitude, longitude, cid, place_id, data_id, status, descriptions, reviews_link, thumbnail, timezone, price_range, street_view_url, images, reservations, order_online, menu, owner, credit_cards_accepted, about, user_reviews, user_reviews_extended, emails, link, input_id.

### 1.5 Field stability classification (for Nexora dependence policy)
| Class | Fields | Policy |
|---|---|---|
| **Stable/core** (structural Google Maps entities, present across versions) | title, category, address/complete_address, latitude, longitude, phone, website, place_id/cid/data_id, link, status | Hard-depend OK (normalize into payload; absence tolerated gracefully) |
| **Valuable-but-variable** (populated per listing; format drifts) | rating, review_count, open_hours, price_range, images, thumbnail, about, descriptions, menu/order_online/reservations, timezone, street_view_url | Enrichment-only; never gate generation on them |
| **Fragile/expensive** (scraped sub-surfaces, anti-bot-sensitive, slow) | user_reviews, user_reviews_extended, emails (site crawling!), popular_times | Opt-in enrichment at most; MUST NOT be a hard dependency |

### 1.6 Behavior
- **Execution model:** batch-oriented. CLI = synchronous over the whole query file; Web/REST = asynchronous jobs (job create → poll → download). Minimum configured runtime ≈ 3 minutes before results appear.
- **Incremental consumption:** writer pipeline streams rows as places are scraped (CSV/JSON grow during run); REST exposes completed-job downloads (per-job artifacts).
- **Pagination:** `-depth` scroll depth; `-fast-mode` caps at 21 results/query; grid mode for area coverage.
- **Concurrency:** `-c` jobs, `-pages-per-browser`, `-browser-pool-size`; throughput ≈120 places/min @ `-c 8 -depth 1`.
- **Anti-bot:** built-in proxy support (SOCKS5/HTTP(S), file); ratelimit package; fast-mode flagged block-prone; proxies effectively required at scale.

### 1.7 Runtime / resources
- Docker image bundles Playwright + Chromium ⇒ heavy: K8s sample requests 512Mi/500m per replica; browsers are CPU/RAM dominant. First run downloads browser libraries.
- Windows host supported via released binary (Chromium download on first run) or Docker.

### 1.8 License
**MIT** (code). No restriction on commercial/product use of the *tool*. Data-layer caveat: scraped Google Maps content is subject to Google ToS — compliance ownership sits with the operator/product, not the library (flagged in §6).

### 1.9 Known reliability signals
- Scraper-class software: inherently exposed to Google DOM/flow changes; mitigated by very active maintenance.
- Community reports historically cluster around blocking/rate-limits without proxies, fast-mode flakiness, and email-extraction slowness — all consistent with §1.6 controls rather than architectural defects.
- No authentication on the bundled REST API by default ⇒ must never be exposed publicly (integration constraint, §6).

## PART 2 — VALUE TO NEXORA

| Use case | How Maps intelligence contributes | VALUE_SCORE |
|---|---|---|
| **A. Local-business website generation** ("premium website for a restaurant in Ahmedabad") | Ground-truth identity (name/category/address/phone/geo), hours section, price-range positioning, photos, booking/ordering CTAs, rating/review-count social proof, local-SEO anchors (place_id, geo, locality terms), competitor set for tone/pricing calibration | **HIGH (9/10)** — fills the single biggest factual-gap dimension for the highest-volume website category |
| **B. Website reconstruction/improvement** ("better website for this business") | Resolves the REAL-world business identity before site/web analysis; cross-checks existing site claims (address/phone/hours) and detects missing assets (no menu link, low photo count) | **MEDIUM-HIGH (7/10)** |
| **C. Local market intelligence** ("premium salon in this locality") | Competitor density, rating baselines, price ranges, category mix within geo/radius ⇒ positioning + differentiation inputs | **MEDIUM-HIGH (7/10)** |
| **D. Business enrichment (non-mandatory)** | Any generation request mentioning a real place gains optional factual grounding; absent match ⇒ graceful no-op | **HIGH (8/10)** as opt-in enhancer |
| **E. Future agent workflows** | Read-only `BUSINESS_SEARCH/FETCH` tools for agents (prospect research, location briefs) | **MEDIUM (6/10) later** |

Aggregate: uniquely adds a **real-world factual dimension** no current Nexora source provides (all existing sources are UI/component/code/knowledge oriented).

## PART 3 — ARCHITECTURAL FIT (options compared)

Existing authorities (verified in Phase 45): `nexora.source_registry` + semantic capabilities → `ProviderManager` → adapters → `UniversalCapabilityRouter` (`{connector}.{tool}` → `tools.call`) → `ConnectorRuntime`/MCP stack; domain models in `domain_models.py`; ranking = `ComponentRankingPipeline` (component-typed).

| Criterion | **A. MCP-server wrap (selected)** | B. Direct REST provider adapter | C. Local process behind router (LOCAL target) |
|---|---|---|---|
| Reuse of existing architecture | **Max** — full MCP connector platform (transport, creds, health, discovery, tester, onboarding XML pattern) | Partial — requires the **deferred** ProviderManager non-MCP branch; bypasses connector lifecycle/health | Partial — LOCAL executor + `nexora.tool_registry` surface; loses source-registry semantics |
| New code | One small stateless MCP stdio shim (~100–150 LOC) wrapping gosom REST | Python REST client adapter + lifecycle handling inside Odoo | Tool plugin + process supervision |
| Operational complexity | Low-medium (one extra container/process; internal-only port) | Medium (HTTP client, retries, pooling inside Odoo) | Medium-high (process mgmt in-process) |
| Failure isolation | **Strong** (separate process/container; crash cannot take down Odoo) | Weak-medium (in-process HTTP faults) | Weak |
| Security | Strong: REST bound internal-only; shim is the sole caller; no new public surface | Medium: egress config inside Odoo | Medium |
| Testability | High (mock router; mock REST) | High | Medium |
| Scalability | gosom's own job queue/K8s scaling retained | Limited by Odoo worker pool | Limited |
| Future Maps-like sources | Natural: same shim pattern per family | Natural too, but blocked on deferred branch | Poor |
| Parallel-architecture risk | **None** (extends canonical MCP contract) | None if done via source_registry, but rides a deferred stub | Some (tool_registry vs capability_registry overlap) |

**SELECTED: Option A** — wrap gosom's REST API behind a minimal MCP stdio/server shim, onboard it exactly like `github_mcp` (connector + mcp_server_config + credential-slot-free config), declare semantic capabilities, consume through the existing router. Rationale: strict reuse of the hardened Phase 26–44 connector plane; zero parallel registry/discovery/ranking; smallest Nexora-side code; keeps the deferred ProviderManager work out of the critical path.

## PART 4 — DOMAIN ARTIFACT DECISION

**Selected artifact: existing `BusinessData`** (`services/source_framework/domain_models.py:87-92`):
```python
@dataclass
class BusinessData:
    data_id: str            # place_id (fallback cid/data_id)
    category: str           # 'business_place'
    payload: Dict[str, Any] # normalized field dict (stable core + optional enrichment)
    provenance: Optional[Provenance]
```
Justification:
- Semantically exact: gosom yields business-place facts, not components (⇒ not `ComponentPackage`) and not repo files (⇒ not `RepositoryArtifact`).
- Already canonical, already handled by `_normalize` discriminant/heuristic paths (`_type: business_data` / `data_id`+`category`), zero schema change.
- Normalization rule: stable-core fields always mapped; variable fields included when present; fragile fields (reviews/emails/popular_times) only when explicitly requested by the caller — never invented.
- No second registry/search/ranking: `BusinessData` instances are retrieval/enrichment artifacts delivered through the adapter; they do NOT enter `ComponentRankingPipeline` (component-typed by contract, mirroring the RepositoryArtifact precedent from Phase 45).

## PART 5 — CAPABILITY CONTRACT

Normative semantic additions (source_registry CSV vocabulary extension, same mechanism as SEARCH/FETCH):
- **`BUSINESS_SEARCH`** — discover businesses matching intent (name/category/locality/geo). Maps to shim tool `business_search`.
- **`BUSINESS_FETCH`** — retrieve one place's fuller record by place identifier/URL. Maps to `business_fetch`. *(Deferred until a consumer needs single-place detail; search suffices for first integration.)*

Concrete gosom operations (REST job creation, depth/fast-mode/proxies) remain hidden behind the shim.

```
BUSINESS_SEARCH (semantic)
   ↓ UniversalCapabilityRouter ({connector}.{tool} → tools.call)
   ↓ McpSourceAdapter / shim MCP server
   ↓ gosom REST API (async job → results)
   ↓ normalization → BusinessData (payload + Provenance)
   ↓ existing consumers (research/enrichment context; future agent tools)
```

## PART 6 — SECURITY / OPERATIONAL GOVERNANCE (bounded defaults)

| Control | Default |
|---|---|
| Direction | Read-only; no login/review-posting flows used |
| Network | gosom REST bound to internal docker network / localhost ONLY; never host-exposed (API is unauthenticated upstream) |
| Queries per request | ≤ 5 input lines |
| Results per query | depth ≤ 1 (≈16) or fast-mode ≤ 21; hard cap enforced by shim |
| Concurrency | `-c ≤ 2`, one browser page/job |
| Timeout | per-job wall clock ≤ 10 min; shim request timeout ≤ 60 s per poll cycle (async polling) |
| Retry | job-level retry ≤ 1; no infinite scrape loops (`exit-on-inactivity` honored) |
| Caching | results cached keyed by (normalized query, geo, lang) with TTL; repeat intent hits cache |
| Enrichment switches | `-email`/`-extra-reviews` OFF by default (cost/fragility) |
| Process isolation | gosom in its own container (Playwright/Chromium isolated from Odoo) |
| Failure containment | adapter maps job failure → sanitized error; partial results still usable |
| Credentials | none required for base operation (proxies optional, injected via env later) |
| Logging | INFO; never log result payloads at DEBUG; no secrets involved |
| Unbounded-scrape prevention | hard caps above + query-count guard + no auto-pagination beyond depth cap ⇒ "every restaurant in Delhi" is clamped to bounded, cached, cancellable jobs |

## PART 7 — WEBSITE-GENERATION VALUE CHAIN

```
User intent ("restaurant in Ahmedabad")
   ↓ [NEXORA] planner/research identifies business-context need
   ↓ BUSINESS_SEARCH via router → gosom → BusinessData[]      ← gosom owns: place facts
   ↓ [NEXORA] existing research/web intelligence (site fetch, knowledge)  ← owns: web/domain analysis
   ↓ [NEXORA] content/identity synthesis into requirements/blueprint     ← owns: narrative & structure
   ↓ existing component discovery / ranking                              ← owns: UI candidates (untouched)
   ↓ existing generation pipeline → website                             ← owns: generation
```
gosom must NOT: generate sites, rank UI, plan websites, orchestrate generation, or act as a second search engine. It is a **factual source** feeding existing engines.

## PART 8 — SCALING TO THE ~15-CONNECTOR PROGRAM

The selected pattern generalizes: **external capability = (declarative connector triple) + (semantic capability tokens) + (thin protocol shim to the canonical MCP/router plane) + (existing domain model or smallest extension)**. Families that map cleanly: business/location (gosom), GitHub repo intelligence (Phase 45 pattern), web research/crawling, documentation/context servers, 3D asset/component intelligence (R3F/Drei/GLB/Spline ecosystems), shader/material sources. Each brings its own domain payload via `BusinessData`/`KnowledgeDocument`/`DesignAsset`/`ComponentPackage` — the four existing canonical artifact types — with no new registries/engines. **Figma = EXCLUDED** (per standing directive; no proposal, no remnant revival).

## PART 9 — DECISION MATRIX

| Criterion | Score (1-10) | Reason |
|---|---:|---|
| Website-generation value | 9 | Unique real-world factual dimension; local-business segment is core volume |
| Data richness | 9 | 36 fields incl. hours/geo/CTAs/social proof |
| Reliability | 6 | Scraper-class fragility; mitigated by very active maintenance (v1.17.4 same-week) |
| Operational complexity | 5 | Playwright container weight; async job model |
| Integration complexity | 7 | Thin MCP shim reuses everything (high = easy/favorable here) |
| Reusability | 8 | BUSINESS_* tokens + BusinessData serve agents, enrichment, market intel |
| Scalability | 7 | Built-in job queue/K8s/proxy scaling |
| Architectural fit | 9 | Option A = pure extension; zero parallel structures |
| Security risk | 6 | Internal-only binding + caps required (unauthenticated REST upstream); scraping-ToS caveat |
| Maintenance burden | 6 | Shim is small; gosom upgrades = image bumps |

**GOSOM_RECOMMENDATION = INTEGRATE** — as connector #1 because it (a) opens an entirely new, high-volume factual dimension aligned with Nexora's core local-business product scenario, (b) does so with zero parallel architecture and minimal Nexora-side code, (c) establishes the reusable external-capability pattern (shim + semantic tokens + existing domain artifact) that the remaining ~14 connectors will follow, and (d) is MIT-licensed, actively maintained, and operationally self-contained.

## Files (documentation only — no implementation)
- This audit: `docs/reports/phase46_1_gosom_maps_architecture_audit.md`
- Draft ADR (Proposed): `docs/adr/ADR-0073-business-location-intelligence-via-gosom-mcp-shim.md`
