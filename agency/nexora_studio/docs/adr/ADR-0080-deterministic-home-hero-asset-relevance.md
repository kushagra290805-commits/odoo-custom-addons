# ADR-0080: Deterministic Home Hero + Context-Aware Asset Relevance

Date: 2026-09-06
Phase: 47.28
Status: Accepted

## Context

After 47.27 the home Hero ai_code_patch was the last remaining LLM code
call (2 LLM calls/site: generate_content + home Hero). Phase 47.28 gated
its removal on evidence, not on the call-count target:

1. **The home Hero payload contained only platform-owned data.** The task
   carried the ContentEngine heading/body copy, the platform-chosen hero
   image path/alt, and the route contract. The model's contribution was
   JSX structure around known data — the same shape the 47.26/47.27 audits
   proved valueless (and hallucination-prone) on secondary pages.
2. **Asset selection was effectively first-match.** The AssetEngine
   collected the first Pexels results per role with no relevance scoring;
   section context (type, heading, domain) never influenced the pick.

## Decision

1. **Deterministic home Hero becomes canonical** (evidence-gated A/B,
   3 briefs × 2 models × {control, candidate} = 12 fresh E2E runs):
   - Control (LLM hero): 2 calls/site, 40–60% deterministic.
   - Candidate (deterministic hero): 1 call/site, 50–70% deterministic.
   - Both: 12/12 COMPLETED, 0 console/page errors, mobile 375×812 OK,
     final acceptance accepted, ProductGrid/PricingCard/FAQ visibility
     unchanged.
   - The candidate was equal or better on every measured criterion, so
     the decision gate removes the home Hero ai_code_patch. Target:
     **2 → 1 LLM call/site (generate_content only)**.
2. **The deterministic home Hero composes the native Hero organism**
   (guaranteed scaffold file, assembler-owned fixed import — the
   SiteLayout/secondary-hero precedent) with: ContentArtifact
   heading/subtitle, AssetEngine imagery (stock hero preferred, branded
   SVG floor), a business-aware CTA label (services-derived), and the
   route contract. A themed centered fallback covers non-react renderers.
   The `secondaryCta` prop is NOT passed: the native Hero spreads unknown
   props onto the DOM `<section>`, which React flags as a console error
   (a blocking browser-validation issue in the first candidate run).
3. **AssetEngine gains deterministic relevance ranking** (no new service;
   the existing owner extends): candidates are scored against the intent
   context via alt-text keyword overlap (domain + section-type +
   role keyword sets), aspect-ratio suitability, resolution preference,
   and a photo_id tie-breaker. Intents are section-aware (role +
   section_type context). `per_page` rises 4 → 8 so ranking has
   candidates to choose from; relevance scores are recorded in the stock
   evidence.
4. **No ContentArtifact schema change.** The 47.27 structured-items
   contract is preserved unchanged (ProductGrid/PricingCard/FAQ compose
   from `items`); no speculative fields were added.
5. **Rendering ownership unchanged:** CodeGenerationEngine remains the
   single rendering owner; AssetEngine remains the single asset owner;
   no new services, no second pipeline, no new connector, no DB change.
   The `_generate_section` LLM path survives for genuinely custom
   sections (none in the standard patterns).

## Consequences

- LLM calls/site: 2 → 1 (generate_content only). The code-generation
  stage is now fully deterministic for every standard pattern section.
- Deterministic composition: 50–70% per site (+10–11 points vs 47.27);
  home Hero mode records as `deterministic` / `native/Hero`.
- Hero hallucination surface eliminated (no LLM JSX anywhere in standard
  codegen); the 47.23 static-validation/fallback contract still guards
  the surviving custom-section LLM path.
- Pexels selection is context-aware and reproducible; irrelevant first
  matches no longer win.
- Token usage/site roughly halves (the hero ai_code_patch ~5k prompt +
  ~6k response tokens is gone).
- Latency/site drops ~15–25s (one fewer model round-trip).
