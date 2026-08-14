# Phase 11C — AI Design Blueprint Engine Architecture Report

**Document ID**: REP-DESIGN-0031  
**Status**: Approved & Published  
**Author**: Nexora Studio Architecture Team  
**Date**: July 2026  

---

## 1. Executive Summary

Phase 11C introduces the **AI Design Blueprint Engine**, a crucial architectural evolution in the Nexora Studio design intelligence pipeline. Previously, Builder Sessions produced ad-hoc raw structures that were tightly coupled or informally routed directly to design providers. 

The new architecture establishes a vendor-neutral, rendering-neutral **Design Blueprint** domain model that acts as the formal, authoritative boundary between generation sessions (`BuilderSession`) and downstream orchestration (`DesignOrchestrator`).

```
+---------------------+
| Client Requirements |
+---------------------+
           ↓
+---------------------+
|   Builder Session   |
+---------------------+
           ↓  (generate_design_blueprint)
+------------------------------------+
|      Design Blueprint Engine       |  <-- nexora.design_blueprint_engine
+------------------------------------+
           ↓  (DesignBlueprint + ValidationResult)
+------------------------------------+
|        Design Orchestrator         |  <-- nexora.design_orchestrator
+------------------------------------+
           ↓  (execute_blueprint / process_blueprint)
+------------------------------------+
|        PenpotDesignProvider        |  <-- Primary Default Design Provider
+------------------------------------+
```

---

## 2. Domain Model Hierarchy & Vendor Neutrality

The domain model (`services/design/design_blueprint.py`) is designed in strict adherence to the **Dependency Inversion Principle (DIP)** and **Interface Segregation Principle (ISP)**. Neither Penpot nor any frontend rendering technology (HTML, CSS, React, Vue, Tailwind, Three.js) appears anywhere within the domain definitions.

### Root Aggregate: `DesignBlueprint`
The root aggregate encapsulates all structural, semantic, aesthetic, and experiential dimensions of a website design:
- **`blueprint_id`**: Immutable unique identifier.
- **`project_name` & `version`**: Core project identity.
- **`pages`**: Ordered collection of `PageBlueprint` entities.
- **`token_set`**: Comprehensive `DesignTokenSet` covering color palettes, typography scales, spacing, and elevation.
- **`navigation`**: Hierarchical `NavigationTree` defining site routing and menus.
- **`breakpoints`**: List of `ResponsiveBreakpoint` definitions (`mobile`, `tablet`, `desktop`).
- **`experience`**: First-class `ExperienceBlueprint` defining interaction dynamics, visual style, and performance budgets.
- **`placeholders`**: Map of `AssetPlaceholder` entities for media and illustrations.
- **`animations`**: Map of `AnimationRule` entities for micro-animations and motion timing.

### First-Class Domain Object: `ExperienceBlueprint`
In response to advanced user experience requirements, `ExperienceBlueprint` models design intent without referencing rendering implementations:
- **`visual_style`**: Aesthetic intent (e.g., `modern`, `minimalist`, `glassmorphism`, `editorial`).
- **`interaction_style`**: Interactive responsiveness (e.g., `subtle`, `dynamic`, `playful`).
- **`animation_intensity`**: Motion prevalence (`none`, `subtle`, `expressive`).
- **`scrolling_behavior`**: Navigation flow (`smooth`, `snapping`, `standard`).
- **`section_transitions`**: Section boundary motion (`fade`, `slide`, `seamless`).
- **`parallax_level`**: Depth intensity (`none`, `low`, `medium`, `high`).
- **`cursor_behavior`**: Pointer interactivity (`default`, `custom-follower`, `magnetic`).
- **`rendering_preference`**: Dimensionality intent (`2D`, `3D`, `Hybrid`).
- **`performance_budget`**: Strict execution constraints (e.g., `max_asset_payload_kb`, `target_fps`, `max_animation_simultaneous`).
- **`accessibility_preferences`**: A11y mandates (e.g., `prefers_reduced_motion`, `wcag_target`, `screen_reader_optimized`).

---

## 3. Subsystem Integration & Responsibility Boundaries

### 3.1 Builder Session (`nexora.builder_session`)
- Replaces legacy raw structural outputs with `generate_design_blueprint(requirements)`.
- Delegates blueprint assembly and semantic validation to `DesignBlueprintEngine`.

### 3.2 Design Blueprint Engine (`nexora.design_blueprint_engine`)
- Acts as a stateless Odoo AbstractModel service.
- Transforms client requirements into a cohesive `DesignBlueprint`.
- Instantiates and invokes `BlueprintValidator`, embedding structured validation results alongside the generated blueprint.

### 3.3 Design Orchestrator (`nexora.design_orchestrator`)
- Exposes `execute_blueprint(blueprint, provider_name='penpot')`.
- Enforces pre-flight validation: if a blueprint fails validation, warnings are logged before routing to the target provider.
- Delegates execution to the target provider's `process_blueprint()` interface method.

### 3.4 Penpot Design Provider (`PenpotDesignProvider`)
- Implements `process_blueprint(blueprint, **kwargs)`.
- Enforces the strict schema boundary defined in Phase 11B:
  - **Supported Top-Level Operations Executed**: Live project creation (`create_project`) and structural validation (`validate_design`).
  - **Granular Intra-File Mutations Deferred**: Canvas creation operations (`create_page`, `create_component`, `create_design_tokens`, `apply_theme`, `import_assets`) are explicitly returned in a structured `unsupported_granular_operations_deferred` list rather than inventing undocumented changeset payloads.

---

## 4. Verification and Compliance

The architecture has been rigorously verified via an automated test suite (`tests/test_design_blueprint_engine.py`):
1. **Serialization Integrity**: 100% roundtrip fidelity for JSON and dictionary conversions across all 15 domain objects.
2. **Validation Engine Accuracy**: Verified catching of duplicate pages, broken navigation links, missing tokens, out-of-order breakpoints, and accessibility contrast failures.
3. **Experience Consistency Enforcement**: Verified detection of conflicts between reduced-motion accessibility preferences and expressive animation/parallax settings.
4. **Boundary Compliance**: Confirmed that `PenpotDesignProvider` successfully separates supported project-level operations from deferred canvas mutations without schema errors.
