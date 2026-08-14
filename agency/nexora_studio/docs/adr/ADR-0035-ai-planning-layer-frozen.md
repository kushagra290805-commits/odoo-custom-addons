# ADR-0035: AI Planning Layer Frozen

**Status:** Accepted  
**Date:** July 2026  
**Decision-Makers:** Nexora Studio Advanced Engineering Team  
**Scope:** Formal Freeze of Provider-Neutral Planning Contracts (Phases 11C–11F)  

---

## Context & Problem Statement

Through Phases 11C to 11F, Nexora Studio engineered a comprehensive, 5-stage AI design planning pipeline:
1. **Design Blueprint Engine (Phase 11C):** Structural composition, page hierarchies, section layouts, and design tokens.
2. **Design System Engine (Phase 11D):** Standardized typography, spacing scales, grid systems, component libraries, and component capabilities.
3. **Layout Intelligence Engine (Phase 11E):** Adaptive layout trees (`Container`, `Grid`, `Stack`, `Split`, `Masonry`), responsive viewport adaptations, and layout behaviors (`sticky`, `scroll_snap`, `lazy_loaded`, etc.).
4. **Asset Planning Engine (Phase 11F):** Visual media requirements, declarative AI prompt specifications, licensing governance, and 9-state asset lifecycle tracking.
5. **Content Intelligence Engine (Phase 11F):** Copywriting strategies, brand voice parameters, structured copy bundles (headlines, sub-headlines, body text, CTAs), and SEO metadata.

As we transition into Phase 12A and begin constructing concrete rendering providers—starting with the **React Generation Engine**, followed in future phases by HTML, Flutter, Native Mobile, and 3D rendering engines—there is an inherent architectural risk. Without strict boundaries, target-specific rendering requirements (e.g., React JSX syntax, CSS DOM classes, Three.js canvas bindings, or framework-specific routing concepts) could bleed backward into the provider-neutral planning domain models. Furthermore, developers building new renderers might be tempted to bypass intermediate planning engines for convenience, eroding design consistency and invalidating quantitative quality scores.

We require a formal architectural freeze on the AI planning layer to ensure that all rendering providers act purely as consumers of stable, provider-neutral planning contracts.

---

## Decision

We formally **FREEZE** the provider-neutral planning contracts established in Phases 11C–11F. The following five intelligence engines and their associated domain models are now designated as **Stable Architectural Contracts**:

1. **Design Blueprint Engine (`nexora.design_blueprint_engine`):**
   - Contracts: `DesignBlueprint`, `PageBlueprint`, `SectionBlueprint`, `ComponentBlueprint`, `DesignTokenBlueprint`.
2. **Design System Engine (`nexora.design_system_engine`):**
   - Contracts: `DesignSystem`, `ComponentLibrary`, `ComponentDefinition`, `ComponentCapability`, `SpacingScale`, `GridSystem`, `IconSystem`, `ThemeSystem`, `StateSystem`.
3. **Layout Intelligence Engine (`nexora.layout_engine`):**
   - Contracts: `LayoutTree`, `LayoutNode`, `Container`, `Grid`, `Stack`, `Split`, `Masonry`, `Overlay`, `LayoutBehavior`, `ConstraintRule`, `AlignmentRule`, `SectionFlow`, `ContentRegion`.
4. **Asset Planning Engine (`nexora.asset_planning_engine`):**
   - Contracts: `AssetDefinition`, `AssetCollection`, `AssetReference`, `AssetRequirement`, `AssetPriority`, `AssetDependency`, `AssetLicense`, `AssetMetadata`, `AssetLifecycle`, `PromptSpecification`.
5. **Content Intelligence Engine (`nexora.content_intelligence_engine`):**
   - Contracts: `ContentStrategy`, `BrandVoice`, `Headline`, `SubHeadline`, `BodyContent`, `CallToAction`, `SEOMetadata`, `ContentBundle`.

### Mandatory Governance Rules for Rendering Providers:

1. **Zero Modification of Planning Contracts:** Rendering engines (e.g., React Generation Engine, Penpot Provider, future HTML/Flutter renderers) must consume these five planning contracts *without modifying them*. Introducing rendering-specific fields (such as `jsx_code`, `css_class`, `react_hook`, or `dom_id`) into the planning domain models is strictly prohibited.
2. **No Pipeline Bypassing:** Rendering providers must not bypass any of the five planning engines. All blueprints must be processed through the complete 5-stage chain (`BuilderSession` $\rightarrow$ `BlueprintEngine` $\rightarrow$ `DesignSystemEngine` $\rightarrow$ `LayoutEngine` $\rightarrow$ `AssetPlanningEngine` $\rightarrow$ `ContentIntelligenceEngine`) before rendering execution.
3. **Extension at the Rendering Layer Only:** Any target-specific transformations, file structure generation, syntax formatting, styling token mappings, or prop bindings must be implemented entirely within the rendering provider layer (e.g., within `services/design/react_generation_engine.py` and its supporting mappers/binders).
4. **Formal Change Management:** Modifying, removing, or altering the schema of any frozen planning contract requires explicit architectural review and formal approval via a new Architecture Decision Record (ADR).

---

## Consequences

### Positive
- **Guaranteed Provider Neutrality:** Preserves 100% decoupling between AI design planning and frontend rendering technologies.
- **Multi-Target Reusability:** Ensures that any future rendering target (e.g., Flutter, Vue, iOS Native, Android Compose, Three.js) can consume the exact same 5-stage blueprint outputs without requiring modifications or regressions in the planning layer.
- **Consistent Quality Governance:** Quantitative quality scores (`design_system_compliance`, `layout_intelligence_compliance`, `asset_planning_compliance`, `content_intelligence_compliance`) remain objective, universal, and comparable across all rendering platforms.
- **Clean Separation of Concerns:** AI Planning engines focus exclusively on *what* to build, *why*, and *with what standards*, while rendering engines focus exclusively on *how* to construct target-specific code.

### Negative & Mitigation
- **Increased Mapping Complexity in Renderers:** Rendering providers cannot rely on planning models to hand them ready-made JSX or CSS strings.
  - *Mitigation:* Rendering providers will implement dedicated, modular mapping layers—such as Design Token Mappers, Asset Binding Layers, and Content Binding Layers—to cleanly translate provider-neutral domain structures into idiomatic target code.
