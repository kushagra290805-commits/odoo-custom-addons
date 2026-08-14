# ADR-0031: AI Design Blueprint Engine and Domain Model

**Date**: 2026-07-25  
**Status**: Accepted & Implemented  
**Deciders**: Nexora Studio Architecture Team  

---

## 1. Context & Problem Statement

In previous iterations of the Nexora Studio design intelligence pipeline, generation sessions (`BuilderSession`) produced ad-hoc, unstructured dictionaries or directly invoked vendor-specific methods on design providers. This created two significant architectural risks:
1. **Vendor Coupling**: Generation logic risked becoming entangled with specific design tool capabilities or schemas (such as Penpot or legacy Figma concepts).
2. **Lack of Pre-Flight Validation**: Invalid page routing, broken token references, inconsistent responsive breakpoints, and accessibility contrast failures were only discovered late during live rendering or API execution.

To establish a production-grade, enterprise design pipeline, we required an authoritative, intermediate domain model that acts as a vendor-neutral, rendering-neutral specification between generation sessions and design orchestration.

---

## 2. Decision

We introduce the **AI Design Blueprint Engine** (Phase 11C), establishing the `DesignBlueprint` domain model as the mandatory boundary between Builder Sessions and the Design Orchestrator:

```
Client Requirements → Builder Session → Design Blueprint Engine → Design Orchestrator → PenpotDesignProvider
```

### Key Architectural Rules Adopted:
1. **Absolute Vendor & Technology Neutrality**: The `DesignBlueprint` domain model and its 15 primitive classes (`PageBlueprint`, `SectionBlueprint`, `ComponentBlueprint`, `DesignTokenSet`, `ColorPalette`, `TypographyScale`, `ResponsiveBreakpoint`, `NavigationTree`, `AssetPlaceholder`, `AnimationRule`, etc.) contain **zero** references to Penpot, React, HTML, CSS, Three.js, Vue, Tailwind, or any rendering implementation.
2. **First-Class Experience Blueprinting**: To capture rich user experience intent without specifying technical rendering code, we introduce `ExperienceBlueprint` as a top-level aggregate inside `DesignBlueprint`. It governs `visual_style`, `interaction_style`, `animation_intensity`, `scrolling_behavior`, `parallax_level`, `rendering_preference` (`2D`/`3D`/`Hybrid`), `performance_budget`, and `accessibility_preferences`.
3. **Mandatory Pre-Flight Semantic Validation**: All blueprints must pass through `BlueprintValidator` before execution. The validator checks 7 exhaustive rulesets: Duplicate Pages, Navigation Integrity, Component Hierarchy bounds, Responsive Breakpoint ordering, WCAG 2.1 Contrast & Alt-Text, Token Consistency, and Experience Consistency (preventing motion conflicts when `prefers_reduced_motion` is enabled).
4. **Strict Schema Compliance in Provider Translation**: When `DesignOrchestrator` passes a validated blueprint to `PenpotDesignProvider.process_blueprint()`, the provider executes only documented, stable top-level operations (live project creation and structural validation). Granular intra-file mutations (`create_page`, `create_component`, etc.) are explicitly reported in a structured `unsupported_granular_operations_deferred` list rather than inventing undocumented changeset payloads (maintaining strict alignment with ADR-0030 / Phase 11B).

---

## 3. Consequences

### Positive
- **Decoupling**: Builder Sessions and AI prompt generators now target a stable, formal domain schema that never changes when underlying providers or UI rendering frameworks evolve.
- **Reliability & Accessibility**: The 7 validation rulesets ensure that broken links, missing tokens, and WCAG contrast failures are intercepted at the blueprint stage before any live API calls or code generation occurs.
- **Auditable Intent**: The presence of `ExperienceBlueprint` allows project managers and automated QA tools to inspect performance budgets and accessibility constraints programmatically.

### Negative / Trade-offs
- **Deferred Granular Canvas Generation**: Because stable Penpot RPC endpoints do not currently document public schemas for granular intra-file canvas mutations without inventing unsupported payloads, actual canvas drawing for individual pages and components remains deferred until offline/file-based sync or future schema updates are verified.

---

## 4. Verification

The architecture is covered by an automated test suite (`tests/test_design_blueprint_engine.py`) executed in standalone Odoo test environments, achieving 100% pass rate across domain model serialization, validation rulesets, Builder Session generation, and Orchestrator routing.
