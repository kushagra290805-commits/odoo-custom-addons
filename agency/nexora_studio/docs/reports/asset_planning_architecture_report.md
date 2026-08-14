# Architectural Report: AI Asset Planning Engine (Phase 11F)

**Status:** Completed & Production-Ready  
**Date:** July 2026  
**Author:** Nexora Studio Advanced Engineering Team  
**System Scope:** Provider-Neutral & Rendering-Neutral AI Asset Planning & Lifecycle Layer  

---

## 1. Executive Summary

Phase 11F introduces an authoritative, provider-neutral **AI Asset Planning Engine** into the Nexora Studio Design Provider Framework. Sitting directly between the Layout Intelligence Engine (Phase 11E) and the Content Intelligence Engine (Phase 11F), this architectural layer replaces arbitrary placeholder images and unstructured media requests with a rigorous, declarative asset planning and lifecycle management system.

In strict adherence to project architectural constraints, the entire Asset Planning domain is **100% provider-neutral and rendering-neutral**. It contains no references to React, HTML, CSS, Three.js, Penpot, Figma, or any specific rendering technology. Furthermore, **no AI generation models are executed during planning**; all prompt specifications and media requirements are generated declaratively via deterministic rules, templates, and domain logic.

---

## 2. Architectural Pipeline & 5-Stage Boundary Enforcement

The updated Nexora Studio design generation pipeline progresses through five distinct intelligence stages before reaching the orchestration and provider layers:

```
[Client Requirements]
        │
        ▼
[Builder Session] (models/builder_session.py)
        │  • Generates DesignBlueprint via DesignBlueprintEngine (Phase 11C)
        │  • Enriches components via DesignSystemEngine (Phase 11D)
        │  • Resolves adaptive layouts via LayoutEngine (Phase 11E)
        │  • Plans visual assets via AssetPlanningEngine (Phase 11F)
        │  • Generates copy & SEO via ContentIntelligenceEngine (Phase 11F)
        ▼
[Asset Planning Engine] (nexora.asset_planning_engine)
        │  • Scans blueprint for ComponentBlueprint and SectionBlueprint media requirements
        │  • Formulates declarative PromptSpecification without calling external AI APIs
        │  • Manages AssetLifecycle states (planned -> requested -> generated -> approved)
        ▼
[Content Intelligence Engine] (nexora.content_intelligence_engine)
        │  • Enriches headlines, sub-headlines, body copy, and SEO metadata
        │  • Validates brand voice, trust elements, and conversion strategies
        ▼
[Design Orchestrator] (nexora.design_orchestrator)
        │  • Routes fully enriched 5-stage blueprint to designated provider
        ▼
[Penpot Design Provider] (nexora.penpot_provider)
        │  • Consumes asset and content plans into project metadata
        │  • Records granular canvas operations in unsupported_granular_operations_deferred
```

### Key Architectural Boundaries:
1. **Separation of Planning from Execution:** The Asset Planning Engine is solely responsible for specifying *what* media is needed, its dimensions, accessibility requirements, and prompt specifications. It never executes image generation APIs (e.g., Midjourney, DALL-E, Stable Diffusion) nor does it perform HTTP file uploads.
2. **Provider-Agnostic Consumption:** Rendering providers consume asset plans as structured JSON/dict payloads within blueprint metadata. Any provider-specific asset uploading (such as Penpot multipart uploads or bitmap insertions) that lacks documented API changeset schemas is explicitly deferred to maintain strict schema compliance.

---

## 3. Asset Planning Domain Model (`services/design/asset_domain.py`)

The Asset Planning domain is modeled using immutable dataclasses that serialize to clean Python dictionaries without circular recursion:

| Domain Model | Purpose & Key Attributes |
| :--- | :--- |
| `AssetDefinition` | Represents an individual media asset requirement (`id`, `name`, `asset_type`, `format`, `dimensions`, `priority`, `license`, `prompt_spec`, `lifecycle`). |
| `AssetCollection` | Logical grouping of related assets for a section, page, or campaign (`collection_id`, `name`, `assets`, `shared_style_keywords`). |
| `AssetReference` | Lightweight pointer binding an asset to a specific component or section (`reference_id`, `asset_id`, `target_element_id`, `role`, `fallback_asset_id`). |
| `AssetRequirement` | High-level specification defining media needs before prompt specification generation. |
| `AssetPriority` | Enumeration/string token indicating delivery importance (`critical`, `high`, `medium`, `low`). |
| `AssetDependency` | Explicit dependency tracking between composite assets (e.g., thumbnail depending on full video). |
| `AssetLicense` | Licensing governance and copyright metadata (`license_type`, `attribution_required`, `commercial_use`, `expiry_date`). |
| `AssetMetadata` | Technical media descriptors (`file_size_bytes_limit`, `mime_type`, `color_profile`, `alt_text`, `caption`). |
| `AssetLifecycle` | Provider-neutral lifecycle tracking (`planned`, `requested`, `generated`, `reviewed`, `approved`, `rejected`, `replaced`, `published`, `archived`). |
| `PromptSpecification` | Declarative AI prompt structure (`asset_type`, `subject_description`, `style_keywords`, `color_palette`, `aspect_ratio`, `lighting_mood`, `negative_prompt`, `reference_image_urls`). |

---

## 4. Declarative Prompt Specification Generation

To ensure reproducible, high-quality visual guidance without incurring AI API latency or costs during blueprint generation, the `AssetPlanningEngine` implements declarative prompt builders (`_create_prompt_spec`).

### Template Strategies by Asset Type:
- **`image`:** Produces professional photography specifications emphasizing composition, natural lighting, and project context (`"High-resolution professional photography depicting {asset_name} for {project_name}, clean composition, natural lighting."`).
- **`illustration`:** Generates modern digital illustration guidelines with sleek geometric shapes and corporate tech aesthetics.
- **`3d_asset`:** Formulates abstract 3D rendering specifications incorporating glassmorphism, soft studio lighting, metallic accents, and isometric views.
- **`icon`:** Constructs minimalist vector icon guidelines requiring clean pixel grids, bold outlines, and scalable symbols.

All generated prompts automatically integrate design system color palettes and style keywords from the project's root blueprint.

---

## 5. Asset & Content Validation Engine (`services/design/asset_content_validator.py`)

To guarantee media and copy excellence before rendering, Phase 11F introduces a 6-part validation ruleset accompanied by a deduction-based quality scoring model.

### The 6 Validation Rulesets:
1. **Completeness Validation:** Verifies that all assets have valid IDs, names, alt text, and non-empty prompt specifications. Confirms that all pages have SEO titles and descriptions.
2. **Licensing & Usage Governance:** Enforces that commercial projects utilize approved license types (`royalty_free`, `commercial`, `proprietary`, `creative_commons`) and checks for missing attributions or expired licenses.
3. **Accessibility Compliance (WCAG):** Audits image alt text length (enforcing >= 5 characters for meaningful screen reader support), checks caption availability, and verifies reading level standards for body text.
4. **Localization & Internationalization:** Validates that text content and asset metadata support target locales, flagging missing translations or hardcoded region-specific strings without localization mappings.
5. **Brand Voice & Storytelling Consistency:** Analyzes copy against the project's `ContentStrategy`, verifying tone adherence (`professional`, `authoritative`, `friendly`, `empathetic`), value proposition presence, and trust-building element inclusion.
6. **Prompt Quality Assurance:** Scans AI prompt specifications for vague terminology, missing subject descriptions, contradiction risks, or overly short prompt strings.

### Quality Scoring Model:
The validation engine computes an aggregated quality score starting at `100.0` and deducting points for infractions across six weighted categories:
- `completeness_score`
- `licensing_score`
- `accessibility_score`
- `localization_score`
- `consistency_score`
- `prompt_quality_score`
- `overall_score` (Weighted mean)

A blueprint is deemed compliant (`is_asset_compliant = True`, `is_content_compliant = True`) if zero fatal errors are detected and the overall quality score meets or exceeds the required threshold (default `>= 75.0`).

---

## 6. Penpot Provider Integration & Schema Compliance

When an enriched blueprint is passed to `PenpotDesignProvider.process_blueprint()`, the provider inspects and extracts both `asset_plan` and `content_plan` summaries into the live or offline project results.

### Deferral of Unsupported Granular Mutations:
In strict compliance with Nexora Studio's zero-invention policy (which forbids guessing undocumented Penpot API changeset schemas), granular canvas mutations related to assets are safely deferred:
- `"import_assets (requires multipart upload schema)"`
- `"upload_bitmap_to_canvas (requires multipart upload schema)"`

By recording these in `unsupported_granular_operations_deferred` and returning an explanatory note, the provider ensures robust, error-free execution while preserving complete diagnostic transparency for frontend inspection.
