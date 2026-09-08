# ADR-0075: Deterministic Section Code Contract + Visual Foundation

Date: 2026-09-04
Phase: 47.23
Status: Accepted

## Context

The Phase 47.22 model-independence audit proved that the real-LLM generation
failures (4/4 E2E aborts with `Link is not defined` / `content_heading is not
defined`) are primarily a **contract** failure, not a model failure:

1. The `ai_code_patch` prompt forbids imports while the page assembler
   (`CodeGenerationEngine._build_page_module`) writes only `import React`.
   Any idiomatic `<Link>` emitted by a model is undefined by construction.
2. Payload context keys (`content`, `content_heading`, `available_routes`)
   whose values are code-shaped copy invite weaker models to copy the key
   names as undeclared identifiers.
3. In-loop section review is a no-op in production (UCEL namespace
   unresolvable), and `_validate_section_module` checks only the declared
   name and default-export — no identifier/import validation exists before
   browser validation.
4. Visual foundation is broken deterministically: `react_provider`
   self-referential CSS custom properties (`--font-body: var(--font-body,
   ...)`) collapse typography to the browser default, no webfont is ever
   loaded, and `ThemeEngine` hardcodes a universal Tailwind-blue palette
   regardless of the brief.

## Decision

1. **Assembler-owned import scaffolding.** `_build_page_module` injects
   imports from a fixed known-dependency table (react, react-router-dom
   `Link`) only when a generated section actually uses the construct and
   does not already carry a whitelisted import. The LLM never controls
   import paths.
2. **Static identifier/import validation** in
   `CodeGenerationEngine._validate_section_module` (extended, not
   duplicated): declared-name check, default-export check, whitelisted
   import specifiers, undefined JSX identifiers / bare expression
   identifiers / component tags against a declared + globals + known-set.
   Runs before browser validation.
3. **Deterministic code fallback** in the existing code-generation stage:
   LLM output → normalize → validate → valid: use; invalid: safe
   deterministic section (literals only, plain `<a>`, scaffold deps only),
   with a structured `code_fallbacks` reason in engine metadata — the same
   evidence pattern ContentEngine established in 47.20C. Source-adapted
   (retrieved) components keep the legacy checks until dependency
   resolution lands.
4. **Payload contract hardening.** `ai_code_patch` context inlines the copy
   and routes in the task text (labeled as literal copy, not code), removes
   the ambiguous `content` / `content_heading` / `available_routes` keys and
   renames `page`/`section` to `page_path`/`section_type`.
5. **Font materialization.** `react_provider` emits direct (non
   self-referential) token values, base typographic rules, and a
   deterministic Google Fonts `<link>` derived from the theme fonts; the
   site layout uses the theme CSS variables. No new connector.
6. **Brief-derived palette.** `ThemeEngine` (canonical owner) derives a
   constrained semantic token palette (background, foreground, primary,
   primary_foreground, secondary, accent, border, muted, card) from design
   language + domain, with WCAG-AA-safe foreground/background pairs
   enforced at derivation time. `DesignOrchestrationEngine` (existing
   pipeline-renderer bridge) injects the theme into the blueprint token set
   the rendering provider already consumes.
7. **Bounded transient-provider handling.** `ProviderExecutionPolicy`
   (canonical retry owner) retries transient 429 responses with bounded
   exponential backoff (honoring `Retry-After`, capped), preserving the
   `RateLimitException`→CostRouter fallback semantics after exhaustion.

## Consequences

- Model quality sets only the fallback *rate*, not the pipeline outcome:
  valid output is always accepted; invalid output degrades to a working
  deterministic section instead of aborting the run.
- The 47.20C JSON fence normalization is untouched (fenced/unfenced both
  supported).
- No new services, registries, orchestration, or parallel pipelines; every
  change lands in the existing canonical owner. Frozen pipeline order
  unchanged.
- Theme contract gains `font_heading`/`font_body` fields (artifact dataclass
  extension, no DB schema change).
