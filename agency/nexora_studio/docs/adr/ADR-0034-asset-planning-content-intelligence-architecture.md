# ADR-0034: AI Asset Planning and Content Intelligence Architecture

**Status:** Accepted  
**Date:** July 2026  
**Decision-Makers:** Nexora Studio Advanced Engineering Team  
**Scope:** Phase 11F — AI Asset Planning & Content Intelligence Layer  

---

## Context & Problem Statement

In the previous phases of the Nexora Studio design evolution, we established an intelligent, multi-stage design pipeline:
1. **Phase 11C (Design Blueprint Engine):** Created provider-neutral structural blueprints defining pages, sections, and tokens.
2. **Phase 11D (Design System Engine):** Governed component composition, spacing scales, grid rules, and component capabilities.
3. **Phase 11E (Layout Intelligence Engine):** Resolved adaptive layout trees, containers, and responsive behaviors across breakpoints.

However, despite having robust structural, systemic, and spatial intelligence, the design pipeline lacked an authoritative mechanism to plan visual media assets and formulate compelling copywriting strategies. Previous iterations relied on generic placeholder images (e.g., static gray boxes or hardcoded placeholder URLs) and repetitive Lorem Ipsum text. This resulted in three major architectural gaps:

1. **Unstructured Media Requirements:** Component definitions lacked formal media specifications (dimensions, aspect ratios, licensing governance, WCAG accessibility alt text, and AI prompt specifications).
2. **Absence of Content Strategy:** Designs lacked declarative brand voice parameters, persuasive storytelling styles, conversion-focused calls-to-action (CTAs), and automated SEO metadata generation.
3. **Risk of AI Runtime Latency & Rendering Coupling:** Ad-hoc attempts to generate images or copy during blueprint creation risked invoking slow, expensive external AI APIs (Midjourney, DALL-E, GPT-4) or tightly coupling domain models to specific rendering canvases (Penpot, Figma, React).

We required an architectural layer that sits between Layout Intelligence and the Design Orchestrator to plan media assets and formulate copywriting strategies while remaining **100% provider-neutral, rendering-neutral, and free of runtime AI model execution**.

---

## Decision

We have decided to implement **Phase 11F — AI Asset Planning & Content Intelligence** as the 4th and 5th stages of the Nexora Studio Design Provider Framework with the following architectural mandates:

### 1. First-Class Provider-Neutral Domain Models (`asset_domain.py`, `content_domain.py`)
We introduce formal, immutable domain models encapsulating all asset and content structures without referencing rendering implementations:
- **Asset Domain:** `AssetDefinition`, `AssetCollection`, `AssetReference`, `AssetRequirement`, `AssetPriority`, `AssetDependency`, `AssetLicense`, `AssetMetadata`, `AssetLifecycle` (tracking states from `planned` to `approved`/`published`), and `PromptSpecification` (structuring AI prompts with subject, style, lighting, and color palettes).
- **Content Domain:** `ContentStrategy` (governing goals, audience, value propositions, trust elements, conversion/engagement strategies, and storytelling styles), `BrandVoice`, `Headline`, `SubHeadline`, `BodyContent`, `CallToAction`, `SEOMetadata`, and `ContentBundle`.

### 2. Declarative Prompt & Copy Generation (No AI Model Execution)
To guarantee high-performance, deterministic blueprint compilation, neither the `AssetPlanningEngine` nor the `ContentIntelligenceEngine` invokes external generative AI models at runtime. Instead, both engines utilize declarative rule builders and templates:
- **Prompt Specification Synthesis:** Automatically constructs structured AI prompt specifications for images, illustrations, 3D assets, and vector icons by combining asset requirements with the project's root design system color palette and style keywords.
- **Content Bundle Synthesis:** Formulates headlines, sub-headlines, body text, CTAs, and SEO metadata tailored to project archetypes (e-commerce retail, SaaS enterprise, blog editorial) and target audiences.

### 3. 5-Stage Pipeline Chaining in Builder Session
We update `BuilderSession.generate_design_blueprint()` (`models/builder_session.py`) to chain all five intelligence engines sequentially:
```
BlueprintEngine (11C) -> DesignSystemEngine (11D) -> LayoutEngine (11E) -> AssetPlanningEngine (11F) -> ContentIntelligenceEngine (11F)
```
Each engine enriches the root `DesignBlueprint` and appends its validation and quality scoring results to the blueprint metadata.

### 4. 6-Part Validation Rulesets & Deduction-Based Scoring (`asset_content_validator.py`)
We establish a unified validation engine enforcing six critical quality dimensions:
1. **Completeness Validation:** Verifies asset IDs, names, alt text, prompt specs, and SEO titles/descriptions.
2. **Licensing & Usage Governance:** Audits commercial license compliance (`royalty_free`, `commercial`, `creative_commons`) and attribution rules.
3. **Accessibility Compliance (WCAG):** Enforces meaningful alt text length (>= 5 characters) and reading level standards.
4. **Localization & Internationalization:** Verifies locale support and translation completeness across text and metadata.
5. **Brand Voice & Storytelling Consistency:** Ensures copy adheres to `ContentStrategy.storytelling_style` and avoids prohibited vocabulary.
6. **Prompt Quality Assurance:** Checks AI prompt specifications for clarity, detail, and subject description completeness.

The engine calculates an overall quality score starting at `100.0` and deducting points for infractions across these six categories.

### 5. Provider Consumption & Safe Mutation Deferral
We update `DesignOrchestrator` to route blueprints through the 5-stage pipeline and update `PenpotDesignProvider.process_blueprint()` to consume asset and content plans into live/offline project metadata. In strict accordance with our zero-invention policy for undocumented API changeset schemas, granular canvas operations are safely deferred:
- `"import_assets (requires multipart upload schema)"`
- `"upload_bitmap_to_canvas (requires multipart upload schema)"`
- `"bind_text_layer_content (requires undocumented update-file changeset schema)"`

---

## Consequences

### Positive
- **Complete, Production-Ready Design Blueprints:** Every blueprint exiting the Builder Session now contains complete structural, systemic, spatial, visual media, and copywriting instructions.
- **Zero Runtime AI Cost or Latency:** Declarative synthesis generates comprehensive prompt specifications and content bundles in milliseconds without API key dependencies or network overhead.
- **100% Rendering & Provider Decoupling:** The asset and content domain models can be consumed by Penpot, Figma, HTML/CSS, React, Three.js, or native mobile renderers without modification.
- **Strict Governance & Traceability:** The 6-part validation ruleset and deduction-based scoring provide objective quality metrics (`asset_planning_compliance`, `content_intelligence_compliance`) for automated CI/CD gating.

### Negative & Mitigation
- **Deferred Canvas Media Insertion:** Because live Penpot multipart asset uploads and text layer bindings lack documented changeset schemas, media assets are not yet injected directly into canvas shapes during synchronous blueprint execution.
  - *Mitigation:* The asset and content plans are stored cleanly in project metadata (`asset_plan`, `content_plan`), ready to be consumed by future frontend plugins or async workers once official Penpot upload schemas are published.
