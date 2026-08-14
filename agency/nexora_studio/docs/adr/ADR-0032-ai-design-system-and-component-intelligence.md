# ADR-0032: AI Design System and Component Intelligence Layer

**Status:** Accepted  
**Date:** July 2026  
**Decision-Makers:** Nexora Studio Advanced Engineering Team  
**Scope:** Phase 11D — AI Design System & Component Intelligence  

---

## Context & Problem Statement

Following the completion of Phase 11C (AI Design Blueprint Engine), Nexora Studio successfully transitioned from legacy raw structural outputs to a formal, provider-neutral `DesignBlueprint` domain model. However, while the blueprint defines *what* pages, sections, and tokens exist, it previously lacked an authoritative mechanism to govern *how components are structured, reused, and standardized* across designs.

Without an intermediate Design System layer:
1. **Ad-Hoc Section Generation:** AI Builder Sessions tended to generate isolated, bespoke section geometries without standard typography scales, spacing increments, or reusable component variants.
2. **Lack of Component Intelligence:** Components lacked formal contracts describing their supported capabilities (such as 3D scenes, video backgrounds, e-commerce, or authentication) and their required media assets.
3. **Validation Gaps:** Spacing scale drift, typography hierarchy violations, and contrast failures could only be caught during or after frontend rendering.
4. **Risk of Vendor / Rendering Coupling:** Attempts to standardize components often inadvertently bind domain models to specific frontend technologies (React, HTML/CSS, Three.js) or design canvas tools (Penpot, Figma).

We required an architectural layer that sits directly between the Design Blueprint Engine and rendering providers to enforce reusable component composition and validation while remaining 100% provider-neutral and rendering-neutral.

---

## Decision

We have decided to implement **Phase 11D — AI Design System & Component Intelligence** with the following structural and architectural mandates:

### 1. First-Class Provider-Neutral Domain Model (`services/design/design_system.py`)
We introduce a comprehensive, immutable domain model encapsulating all design system standards without referencing rendering code:
- **Core Systems:** `SpacingScale`, `GridSystem`, `IconSystem`, `ThemeSystem`, `StateSystem`, and `LayoutRules`.
- **Component Structuring:** `ComponentVariant`, `ComponentCapability` (describing supported features like `video_background`, `3d_scene`, `particles`, `ecommerce`, `authentication`), and `AssetRequirements` (describing required/optional media like `image`, `logo`, `generic_3d_asset`, `environment_asset`).
- **Library Aggregation:** `ComponentDefinition`, `ComponentLibrary`, and the root `DesignSystem` aggregate.

### 2. Component Intelligence Catalog (`services/design/component_intelligence.py`)
We establish an authoritative, standard library (`ComponentIntelligence`) providing out-of-the-box intelligent definitions for 14 core web application categories:
- `Hero`, `Navbar`, `Footer`, `Pricing`, `Features`, `Testimonials`, `FAQ`, `Contact`, `Gallery`, `Blog`, `Dashboard`, `Authentication`, `Forms`, and `Ecommerce`.

### 3. Automated Validation Engine (`services/design/design_system_validator.py`)
We implement `DesignSystemValidator` to evaluate blueprints against six core quality rulesets prior to provider execution:
1. *Token Usage Ruleset* (catches missing or invalid color/typography token references).
2. *Spacing Consistency Ruleset* (enforces adherence to Spacing Scale pixel increments).
3. *Typography Hierarchy Ruleset* (enforces semantic HTML heading levels and single-H1 SEO rules).
4. *Layout Consistency Ruleset* (enforces valid flexbox/grid layout primitives and alignment modes).
5. *Accessibility Compliance Ruleset* (enforces WCAG AA contrast grades and mandatory asset placeholders).
6. *Responsive Compatibility Ruleset* (enforces grid container bounds across breakpoints).

### 4. Service & Pipeline Orchestration (`nexora.design_system_engine`)
We implement `DesignSystemEngine` as an Odoo standalone abstract model (`services/design/design_system_engine.py`) exposing:
- `compose_design()`: Recommends a structured composition of reusable component definitions based on client requirements instead of isolated sections.
- `process_blueprint()`: Enriches candidate blueprints by auto-resolving component definitions from the Component Intelligence library and executing Design System validation.

### 5. Strict Schema & Rendering Neutrality Enforcement
In strict compliance with previous architectural ADRs (ADR-0030 and ADR-0031):
- **No Rendering Syntax:** The domain model and catalog contain zero references to React, HTML, CSS, Three.js, or Penpot APIs.
- **No Invented Mutation Payloads:** In accordance with Phase 11B rules, `PenpotDesignProvider` consumes reusable component definitions and records composition metadata in project summaries while deferring granular canvas generation (`create_page`, `create_component`, etc.) until public RPC schemas are documented.

---

## Consequences

### Positive
- **Visual Excellence & Brand Consistency:** Reusable component compositions eliminate visual drift, ensuring every generated web application exhibits premium typography, harmonious spacing, and cohesive layouts.
- **Intelligent Composition:** AI Builder Sessions can now reason about advanced component capabilities (`3d_scene`, `ecommerce`, `ai_content`) and asset requirements (`generic_3d_asset`, `logo`) at the domain level.
- **Early Defect Prevention:** Automated 6-part validation catches token errors, contrast failures, and responsive overflow in `< 0.01s` before any external provider network calls are made.
- **Total Architectural Independence:** The entire Design System layer can interoperate with any future rendering provider (Penpot, React, HTML/CSS, Flutter) without refactoring domain logic.

### Trade-offs & Limitations
- **Category Resolution Mapping:** Components generated by legacy sessions without an explicit `definition_id` rely on heuristic category/name mapping in `process_blueprint()` to resolve library definitions.
- **Deferred Canvas Rendering:** While component definitions and composition metadata are fully recorded in live Penpot project summaries, granular intra-file canvas rendering remains deferred in accordance with Phase 11B strict schema compliance rules.

---

## Verification & Compliance

The implementation is verified by the standalone test suite (`tests/test_design_system_engine.py`) and cross-verified against Phase 11C regression tests (`tests/test_design_blueprint_engine.py`), achieving a 100% pass rate across all unit and integration tests.
