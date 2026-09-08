# ADR-0079: Structured Content Contract + Deterministic Secondary Rendering

Date: 2026-09-05
Phase: 47.27
Status: Accepted

## Context

Runtime evidence (47.26 E2E + content-artifact probe) proved:

1. **Secondary-page Content LLM calls add no semantic value.** The
   ContentArtifact body already contains the full copy (services page:
   4 title-line+paragraph blocks; contact page: label+text blocks). The
   ai_code_patch call merely converted known copy into predictable JSX
   (titled cards + nav). The contact-page LLM output even invented a
   street address absent from the artifact — a hallucination liability,
   not value.
2. **Structured item data is missing from the contract.** ProductGrid /
   menu rendering needs name/description/price per item; the current
   section schema (`type, semantic_heading, aria_label, body`) carries
   this only as prose. 47.26's plan/QA parsing from prose is
   regex-extraction — explicitly insufficient for the ProductGrid
   acceptance (data must originate from the canonical content path).

## Decision

1. **Smallest canonical ContentArtifact extension: optional `items` on a
   section.** `items: [{title?, body, price?, badge?, category?,
   question?, answer?}]` — bounded, validated in the existing
   `_normalize_content_schema`, populated from natural shapes
   (`editable.items`, `editable.list`, `items`, `faqs`, `plans`, `menu`,
   `products`). Backward compatible: sections without `items` are
   unchanged; every existing consumer ignores the field. ONE contract —
   no ProductArtifact/MenuArtifact/parallel schema.
2. **ContentEngine remains the single semantic-content owner.** The
   existing `generate_content` call (no new LLM call) asks for structured
   items on Pricing/FAQ/MenuHighlights sections; the response_format
   gains the optional `items` array. 47.20C extraction / normalization /
   validation / fallback untouched.
3. **Secondary Content sections become deterministic.** A
   `_pattern_content` builder renders titled cards from the
   ContentArtifact body (title-line + paragraph blocks) and/or structured
   items — themed tokens, route-validated CTA. No LLM call for structure.
   The home Hero remains LLM (the 47.26 hybrid decision — no new
   evidence against it).
4. **MenuHighlights/Pricing/FAQ builders prefer structured items** (from
   the canonical artifact) over prose parsing; prose parsing remains the
   bounded fallback for models that omit `items`. MenuHighlights composes
   the native ProductGrid when items carry prices (real item+price data),
   otherwise FeatureGrid.
5. **Composition manifest** additionally records per-mode percentages
   (deterministic/llm/hybrid/fallback) in the existing metadata.
6. **Rendering ownership unchanged:** CodeGenerationEngine remains the
   single deterministic rendering owner; no ContentRendererService, no
   second pipeline, no new connector, no DB change.

## Consequences

- LLM calls/site: 4 → 2 (generate_content + home Hero) — the two
  secondary Content code calls are eliminated with zero content loss
  (all copy already flows through the artifact; the deterministic
  builder renders it with guaranteed-correct tokens).
- ProductGrid/Menu items are canonical structured data (LLM → artifact →
  native component → browser), not regex products.
- hallucination surface shrinks (no LLM JSX on secondary pages).
- Weaker models that omit `items` still produce working sites via the
  prose-parsing fallbacks.
