# Asset Management Audit (Phase 5 Audit Report)

**Date:** July 2026  
**Type:** Strictly Read-Only Architecture Audit  
**Scope:** Asset Planning & Management Subsystem (`services/design/asset_*.py`, `render_domain.py`, `design_system.py`)  

---

## Executive Summary

This report assesses how **Nexora Studio** manages digital assets (fonts, icons, illustrations, media, templates, components, and static attachments). Our audit reveals a clear dichotomy: while Nexora possesses an advanced, provider-neutral **Asset Planning and Domain Layer** (`AssetPlanningEngine`, `AssetContentValidator`), it lacks a centralized backend binary storage and provider integration engine. Currently, asset URLs in generated projects resolve to external placeholder URIs or user-supplied URLs. Implementing an extensible **Asset Provider Framework** (Unsplash, Google Fonts, local caching) is a key priority for **Phase 15D**.

---

## 1. Asset Type Classification & Management Mapping

| Asset Category | Current Management Mechanism in Odoo / Nexora Studio | Storage & Caching Layer | Resolution & Generation Behavior |
| :--- | :--- | :--- | :--- |
| **Fonts (Typography)** | Managed declaratively via `RenderToken` (`token_type='typography'` or `'font'`) in `render_domain.py` and `DesignSystem`. | None in Odoo. Relies on browser resolution or external stylesheets (e.g., Google Fonts CDN links). | Converted into CSS custom properties (e.g., `--font-heading`) in `src/styles/tokens.css` by `ReactRenderingProvider`. |
| **Icons** | Managed via `IconSystem` in `design_system.py` (`library_name: 'lucide-standard'`, `allowed_sizes_px: [16, 20, 24, 32, 48]`). | None in Odoo. Relies on npm dependency (`lucide-react`) installed in target workspace. | Referenced by name in component manifests and imported dynamically in React TSX components. |
| **Illustrations & Media**| Represented as `AssetDefinition` in `asset_domain.py` and `RenderAsset` (`asset_type='image'`, `'illustration'`, `'3d_asset'`, `'video'`). | None in Odoo. No binary caching or local storage tables exist. | `AssetPlanningEngine` generates declarative `PromptSpecification` schemas; rendered as static dictionary entries in `src/config/assets.js`. |
| **Templates** | Managed via Odoo dependency `template_store` and analyzed via `TemplateAnalyzer` (`services/ai/template_analyzer.py`). | Stored as Odoo database records in `template_store` module. | Analyzed during planning to extract structural DOM sections and component categories. |
| **Components** | Managed via `ComponentDefinition`, `ComponentManifest`, and `ReactComponentLibrary` (`services/design/`). | Stored in memory / declarative Python code libraries; cached via `nexora.capability_registry`. | Synthesized into standalone `.jsx`/`.tsx` files in `src/components/` and exported via barrel index. |
| **Static Attachments**| Managed via generic Odoo `ir.attachment` when uploaded through standard Odoo chatter/views. | Standard Odoo filestore (`data_dir/filestore/`). | Not currently linked to automated website generation VFS workspaces. |

---

## 2. Existing Services & Domain Layer Analysis

### 2.1 Asset Domain Models (`services/design/asset_domain.py`)
Developed in Phase 11F, this module establishes a robust, rendering-neutral domain vocabulary:
- **`AssetDefinition`:** Encapsulates name, asset type, priority (`AssetPriority`), lifecycle state (`AssetLifecycle`), source type (`user_supplied`, `generated`, `reusable`), metadata (`AssetMetadata`), and licensing (`AssetLicense`).
- **`PromptSpecification`:** Declarative schema containing `subject_description`, `style_keywords`, `lighting_mood`, `color_palette_constraints`, `aspect_ratio`, and `negative_prompt`. Designed to instruct downstream image/3D generation workers without tying the planner to a specific AI image model.
- **`AssetPlan`:** Aggregates required, optional, user-supplied, and generated assets for a project.

### 2.2 Asset Planning Engine (`services/design/asset_planning_engine.py`)
- Scans client briefs and blueprint structures to construct an `AssetPlan`.
- Automatically synthesizes `PromptSpecification` objects for missing hero images, logos, and feature illustrations based on project type (`saas`, `ecommerce`, `landing`).

### 2.3 Asset Content Validator (`services/design/asset_content_validator.py`)
- Validates asset definitions against quality and accessibility constraints (e.g., enforcing `alt_text` for images, verifying valid aspect ratio strings, and checking file size thresholds).

---

## 3. Code Generation Asset Binding (`src/config/assets.js`)

During Stage 3 (Rendering), `ReactRenderingProvider.generate_assets(context)` processes all `RenderAsset` objects in the project and synthesizes an exported JavaScript dictionary in `src/config/assets.js`:

```javascript
export const ASSETS = {
  HERO_SECTION_PRIMARY_MEDIA: {
    id: 'a1b2c3d4-...',
    name: 'Hero Section Primary Media',
    type: '3d_asset',
    src: 'https://placehold.co/1920x1080/webp', // Placeholder or external URI
    alt: 'Acme Corp Hero Visual'
  },
  // ...
};
export default ASSETS;
```

---

## 4. Gap Assessment & Phase 15D Recommendations

| Capability Area | Current Status in Nexora Studio | Mandated Upgrade for Phase 15D (Asset Provider Framework) |
| :--- | :--- | :--- |
| **Provider Abstraction**| 🔴 **Missing** | Create `BaseAssetProvider` abstract model supporting `search()`, `fetch()`, `generate()`, and `get_license()`. |
| **Third-Party Providers**| 🔴 **Missing** | Implement concrete adapters for Unsplash (stock images), Google Fonts (typography), and local icon bundles. |
| **Binary Storage & Caching**| 🔴 **Missing** (VFS files only) | Build an `AssetCacheService` that downloads external media blobs, hashes them, stores them in Odoo filestore/S3, and mirrors them directly into `nexora.workspace_file` (`public/assets/`). |
