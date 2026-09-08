# ADR-0077: Native Component Library Activation via the Canonical Resource Path

Date: 2026-09-05
Phase: 47.25
Status: Accepted

## Context

The Phase 47.24 audit confirmed the native 27-component library
(`ReactComponentLibrary`, synthesized into every generated workspace at
`src/components/*.jsx`) is inert: no ComponentPackage exists for it in the
component-discovery path, ComponentIntelligenceEngine never sees it as a
candidate, the assembler import scaffolding does not know its paths, and the
deterministic pattern builders hand-roll markup instead of composing it. The
library itself is buildable (default exports, CSS-variable styling, composable
hierarchy) with one defect: hardcoded dark-theme translucent borders in Card.

## Decision

1. **One canonical path, native as a resource source.** A
   `NativeLibraryAdapter` (source-framework `BaseProviderAdapter`, same
   contract as the shadcn/react-bits registry adapters) exposes a curated set
   of production-ready marketing-site components (Card, FeatureGrid,
   Testimonial, PricingCard, ProductGrid, FAQ, Hero, Button) as
   `ComponentPackage`s carrying `metadata.source_code` (the exact
   synthesized code), `workspace_path` (the provider-scaffold location),
   semantic descriptions (section types / domains / category from the
   existing manifest vocabulary) and dependencies. It is registered by the
   existing `ProviderManager.load_from_registry()` as a code-level built-in
   (`native_library`) — no DB row, no new registry, no connector. Discovery,
   the source-code gate, intelligence matching and materialization treat
   native and external candidates identically.
2. **Selection stays semantic with explainable priority.** The
   ComponentIntelligenceEngine ranking is extended from
   `(has_source_code, overlap)` to `(has_source_code, overlap,
   -dependency_weight, is_local)`: after semantic relevance, fewer external
   dependencies win, then deterministic/local availability. Nothing is
   hardcoded to "always prefer native" — a semantically stronger or lighter
   external component still wins. Selection evidence (overlap,
   dependency weight, source, locality) is recorded on the matched node
   metadata. The shared tokenizer now splits camelCase/PascalCase names so
   `FeatureGrid` matches `feature`/`grid` semantics.
3. **Materialization reuses the scaffold files.** Native components are
   already materialized by the rendering provider at `src/components/`;
   CodeGenerationEngine registers assembler-owned import lines pointing at
   those existing files (writing the code only as a fallback if the file is
   absent). No duplicate copies under `external/`. Only SELECTED components
   are imported into pages.
4. **Pattern quality.** Patterns remain composition metadata. The catalog
   gains domain-appropriate sections using the existing builder vocabulary:
   restaurant gains `About` + `MenuHighlights`, SaaS gains `FeatureGrid`;
   the deterministic builders compose the matched component (native
   organism with props, card-family wrappers, or native Button CTAs) and
   keep the plain themed fallback when nothing matches.
5. **Card minor fix.** Card's hardcoded `rgba(255,255,255,…)` borders become
   `var(--color-border, …)` so native cards render correctly on light AND
   dark palettes (classification B → A).

## Consequences

- Native and external resources flow through ONE discovery/intelligence
  path; the source-code gate is unchanged and enforced for native too.
- The library's remaining app-oriented components (Modal, Sidebar, Table,
  AuthForm, …) remain shipped-but-unexposed (classified not suitable for
  marketing-site composition); nothing is deleted.
- LLM call count is unchanged (pattern sections were already deterministic);
  the win is reusable, known-good component composition replacing
  hand-rolled markup, plus local/deterministic retrieval with zero network
  cost and lower dependency complexity.
- No new generation orchestrator, component registry, asset system, pattern
  engine, connector, or DB schema change; frozen pipeline order unchanged;
  47.23/47.24 behavior preserved and regression-tested.
