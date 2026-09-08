# ADR-0081: Content-Contract Hardening, Per-Section Imagery, Hero Polish, Manifest Surfacing

Date: 2026-09-06
Phase: 47.29
Status: Accepted

## Context

Phase 47.28 left four P1 client-quality gaps:

1. **Structured item emission was fragile with weaker free models.** The
   prompt asked for items "ONLY for" structured sections but gave no
   concrete field example; models that obeyed the *prose fallback*
   instructions ("Plan name - price" blocks) produced copy that the
   MenuHighlights builder could not parse at all (Pricing/FAQ had
   codegen-side prose parsers; MenuHighlights had none), and natural
   malformed shapes (nested `{"plan": {...}}` objects, object-keyed
   containers, `"Name - price"` strings, list-valued feature fields)
   lost fields or whole items.
2. **Section imagery repeated and suitable assets went unused.** Every
   section intent emitted the same entry id `stock_section`; the
   AssetEngine's `seen_assets` dedup then discarded all but the first
   section photo (fetched, ranked, relevant — then dropped), and every
   pattern builder read that single key, so ServicesGrid/About/Content
   rendered the same photo. Section queries were domain-agnostic fixed
   phrases ("company story team office"), so the candidate pool itself
   was weakly matched.
3. **The native Hero was unpolished**: always `variant="split"` (even
   with no image), no badge/eyebrow despite the native organism
   supporting one, and a subtitle bound (220) inconsistent with the
   canonical 200-char item/body bound.
4. **The composition manifest existed only in process-local context
   metadata.** EngineCompleted events carried duration only; nothing
   durable reached the operator.

## Decision

1. **Harden the existing generate_content contract (ContentEngine stays
   the single content owner).** The prompt now REQUIRES items for
   Pricing/FAQ/MenuHighlights with exact per-section field names and one
   inline example. The normalizer deterministically repairs: nested
   natural objects (pre-flattened, group-aware alias scan), object-keyed
   containers, priced string entries, and list-valued feature fields.
   The prompt's own instructed prose-block fallback format is normalized
   back into canonical items at the ContentArtifact boundary
   (`_items_from_body_blocks`, strict grammar: price-like right side for
   priced blocks, `?` for FAQ) — no schema loosening, no second LLM call,
   bounded (8 items / 200 chars), fallback reasons unchanged, plus a
   bounded `content_structured_items` evidence count in engine metadata.
2. **Per-section stock imagery through the existing AssetEngine.** Section
   entries carry per-section ids (`stock_section_<type>`), section
   evidence records the section type, and queries are subject-aware
   (`"<business category> <section phrase>"`). The renderer resolves a
   section's image through `_section_image` (per-section key first,
   legacy `stock_section` fallback). Deterministic uniqueness
   (`used_photo_ids`) is unchanged; Pexels remains the only stock
   provider; SVG/deterministic fallback remains the floor.
3. **Polish the existing native Hero builder (no second renderer).**
   Deterministic variant selection: `split` when hero imagery exists,
   `centered` otherwise. A deterministic badge/eyebrow derived from the
   brief's business category (or domain), cleaned and bounded to 40
   chars, empty when no signal exists. Subtitle bounded to 200 chars.
   The pre-47.29 `_build_secondary_hero` positional signature is
   preserved (artifact is optional). `secondaryCta` remains unpassed
   (ADR-0080: DOM-spread console error). MenuHighlights additionally
   gains the codegen-side priced-block parser as a final fallback
   (the Pricing/FAQ precedent).
4. **Surface the manifest through the EXISTING evidence paths only.**
   Live: EngineCompleted events now carry a bounded copy of the engine
   result metadata (`engine_result`) — depth/list/dict/string-capped —
   which travels the existing event bus → SSE operator stream.
   Durable: `BuilderSessionService.run_generation` emits a
   `generation.completed` runtime event (existing event type, existing
   `nexora.runtime_event` model, existing session-form timeline) with a
   concise composition summary (pattern, per-section modes/components,
   deterministic/llm/hybrid percentages, fallback and skipped sections,
   stock imagery and structured-item counts). No new model, no schema
   change, no new telemetry subsystem; generation of the manifest
   itself is unchanged.

## Consequences

- Weaker free models can omit or malform `items` without losing
  structured composition: prose fallbacks normalize deterministically at
  the content boundary; MenuHighlights composes ProductGrid from priced
  blocks. The single generate_content LLM call is unchanged (1/site).
- Each section type renders its own relevant, uniquely-assigned photo;
  no suitable collected asset is discarded by id collision; images
  remain deterministic (no LLM involvement).
- Heroes are visually stronger (eyebrow/badge, layout matched to
  imagery presence) with zero hardcoded business types — all signals
  come from the existing brief/content/theme.
- Operators see live composition evidence in the stream and durable
  per-session composition summaries in the event timeline.
- Invariants preserved: BuilderSessionService.run_generation entry,
  GenerationCoordinator orchestration, WebsiteGenerationPipeline
  pipeline, ContentEngine/AssetEngine/CodeGenerationEngine ownership,
  no new provider/connector/model, no Odoo schema change, no duplicate
  renderer or registry.
