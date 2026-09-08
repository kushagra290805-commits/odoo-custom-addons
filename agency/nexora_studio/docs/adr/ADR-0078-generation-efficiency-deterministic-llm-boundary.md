# ADR-0078: Generation Efficiency — Deterministic/LLM Boundary by Evidence

Date: 2026-09-05
Phase: 47.26
Status: Accepted

## Context

Runtime call-graph evidence from the 47.25 E2E (2 models × 3 briefs, 7 LLM
calls/site) plus code-level consumer tracing showed:

1. `knowledge_enrichment` — the LLM-generated keys (business_summary, usp,
   seo_keywords, faq_suggestions, …) are consumed by NO downstream stage
   (verified: only `knowledge_documents` / `implementation_context` — the
   deterministic source-framework collections that pass THROUGH the
   knowledge artifact — are read by ContentEngine and
   CodeGenerationEngine). The LLM portion of the call is dead output.
2. Secondary-page `ai_code_patch` hero calls (services/contact pages)
   render heading + ContentEngine copy + the platform-chosen hero image +
   routes — 100% platform-owned data; the LLM adds no client-specific
   value there, and the observed outputs hallucinated 55 invalid
   `--nx-*` CSS variables per page (the model invented names from the
   theme payload's `prefix: "nx-"` hint — tokens.css defines zero
   `--nx-*` vars; the pages only looked themed because invalid vars fall
   back through the cascade).
3. The home-page hero genuinely benefits from LLM composition (novel,
   brief-specific layout) but suffers the same token-name hallucination.
4. Exposed-but-unused native organisms: PricingCard, ProductGrid, FAQ have
   no pattern section that exercises them.

## Decision

1. **Eliminate the knowledge_enrichment LLM call.** The engine becomes the
   deterministic source-framework collection (documents, repo artifacts,
   status) with a deterministic summary block from the requirements — the
   artifact contract (keys, consumers) is unchanged. No dead LLM output.
2. **Secondary-page heroes become deterministic and compose the NATIVE
   Hero organism** through the SiteLayout precedent (direct scaffold
   import with an assembler-owned fixed import line — the file is
   guaranteed by the provider scaffold). The home-page hero stays
   LLM-generated (novel showcase value). The native Hero is NOT exposed to
   semantic matching (exposing it would let it capture the home hero via
   `_generate_section` source adaptation and break its multi-file relative
   imports) — it is composed directly by the deterministic builder.
3. **LLM hero payload gains the exact usable CSS-variable vocabulary**
   (`--color-primary`, `--font-heading`, `--spacing-lg`, …) so the model
   stops inventing token names; the theme payload drops the misleading
   `prefix` hint.
4. **SaaS pattern gains Pricing + FAQ** sections; the restaurant
   MenuHighlights keeps its FeatureGrid composition. Pricing/FAQ section
   builders compose the native PricingCard/FAQ organisms from plan/Q&A
   blocks parsed out of the ContentEngine copy (hybrid: the LLM writes the
   copy in the existing content call; the builder structures it) with
   bounded fallbacks to themed lists.
5. **Composition manifest** — per-section generation evidence (type,
   pattern, component, source, mode: deterministic|llm|hybrid|fallback,
   asset) recorded in the existing CodeGenerationEngine result metadata.
   Measurement only — no new runtime subsystem.
6. Semantic aliases gain the FAQ group; `Pricing`/`FAQ` section types join
   the planning semantic map and the pattern catalog's shared builder
   vocabulary.

## Consequences

- LLM calls/site: 7 → 4 (content, home hero, services content, contact
  content) with zero consumed-output loss — the two eliminated call
  classes produced unused or platform-derivable output.
- Secondary pages render with guaranteed-correct theme tokens (the native
  Hero uses the real token vocabulary) instead of hallucinated ones.
- SaaS sites exercise PricingCard + FAQ natively; deterministic
  composition share rises.
- knowledge artifacts remain schema-compatible; the frozen pipeline,
  47.20C/47.23/47.24/47.25 contracts, one-selection-path, and all
  connectors are unchanged; no DB schema change.
- Secondary-page Content sections remain LLM (deferred — measured, not
  converted; the quality gate decides in a later phase if ever).
