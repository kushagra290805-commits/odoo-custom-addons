# ADR-0076: Resource Pipeline Reconciliation, Component Composition, Page Patterns & Stock Imagery

Date: 2026-09-04
Phase: 47.24
Status: Accepted

## Context

The accepted 47.22 audit found two competing component worlds: the
source-framework path (ComponentDiscoveryEngine → SearchEngine → MCP-bound
source rows → source-code gate → ComponentIntelligenceEngine) that
generation actually runs, and the provider-platform adapters
(ShadcnComponentProvider, ReactBitsComponentProvider) that genuinely
retrieve source but are consumed by no generation stage. All MCP component
sources were dead at runtime (connectors disabled), so no candidate ever
carried `metadata.source_code` and the (correct) source-code gate rejected
everything. Endpoints had also drifted: the shadcn registry moved from
`/registry/...` to `/r/...` (verified live: `/r/index.json` 200,
`/r/styles/default/{item}.json` 200); React Bits moved from a source tree
to a published registry (`public/r/<Name>-<Variant>.json`, verified live)
with self-contained JS+CSS variants needing zero extra dependencies.
Additionally: pages were universally Hero+Content; the 30-component
library and lucide-react were unused; the only imagery was one
deterministic SVG repeated on every page.

## Decision

1. **One canonical retrieval path.** The source-framework stays the
   runtime owner. New source-framework adapters `ShadcnRegistryAdapter`
   and `ReactBitsRegistryAdapter` (BaseProviderAdapter contract) are
   registered by the existing `ProviderManager.load_from_registry()` for
   the existing `shadcn` / `react_bits` source rows and **delegate to the
   existing provider-platform adapters** — one retrieval implementation,
   bridged contracts. No MCP lifecycle change, no new registry rows, no
   third path. Provider-platform adapter URLs are repaired to the verified
   live endpoints; component source, files, dependencies and provenance
   flow into `ComponentPackage` with `metadata.source_code`, satisfying
   the (unchanged) source-code gate without weakening it.
2. **Deterministic page-pattern catalog** (`services/design/page_patterns.py`)
   — composition metadata (id, suitability, per-page sections, reason),
   selected deterministically by PlanningEngine from domain/brief and
   stored in `generation_metadata['page_pattern']`; ArchitectureEngine
   derives page sections from it. Standard sections (ServicesGrid,
   Testimonial, ContactCTA, Gallery) are built deterministically by
   CodeGenerationEngine — no LLM call, ContentEngine copy consumed, theme
   tokens, lucide icons, external components and stock images composed.
   Hero/Content remain LLM-generated with the 47.23 validation/fallback.
3. **External components materialize as their own modules**
   (`src/components/external/<Name>.jsx` + auxiliary files) written by
   CodeGenerationEngine (same file-ownership precedent as SiteLayout.jsx);
   pages import them through assembler-registered known-import lines — the
   LLM never controls import paths. The 47.23 static validator receives
   the per-run known identifiers. react_provider conditionally enables
   Tailwind v4 + `@` alias + `cn()` utility + `@theme` token mapping ONLY
   when selected external component code requires them, with dependency
   versions emitted into package.json (no version gaps).
4. **Lucide activation**: a curated whitelisted icon set is a known
   identifier universe; the assembler injects the fixed
   `import { ... } from 'lucide-react'` line for icons the code actually
   uses. Deterministic sections use icons directly. No placeholder
   `data-lucide` svg elements remain in generated pages.
5. **Stock photography: Pexels (the one new external resource provider).**
   Chosen over Unsplash on: instant free API key, 200 req/hour, free
   commercial license with no attribution requirement, simple JSON API
   (verified live; note: Cloudflare blocks default urllib UA — the
   provider uses requests). `PexelsStockPhotoProvider`
   (`services/providers/asset/`) is called by the existing AssetEngine —
   the canonical owner of provider selection, request, normalization,
   role assignment, caching (module-level query cache) and failure
   handling. The key is stored via the existing `ir.config_parameter`
   mechanism (`nexora.pexels.api_key`), never in source. Asset intent is
   structural (role/subject/orientation/query) — the LLM never controls
   external URLs. Retrieval is optional: any failure falls back to the
   deterministic SVG behavior. CodeGenerationEngine downloads chosen
   photos to `public/images/` (WorkspaceAdapter gains `write_binary`) and
   renders them by role (hero / section / gallery) with real alt text.
6. **Pattern selection remains explainable** (pattern id + reason list in
   planning metadata) and deterministic — no new LLM call.

## Consequences

- Real, provenance-carrying external components and real stock images
  reach the generated site through the existing frozen pipeline.
- Component retrieval is cached at the adapter level; repeated generation
  does not re-download the same component source or photo query results.
- LLM call count drops (deterministic pattern sections) — content and
  hero/content code remain LLM-driven.
- No new generation orchestrator, component registry, asset engine,
  pattern generator, or connector lifecycle change; no DB schema change
  (one `ir.config_parameter` row for the Pexels key; no model changes).
- 47.23 invariants (static validation, deterministic code fallback,
  payload hardening, fonts, palette) and the 47.20C content contract are
  preserved and regression-tested.
