# Component Intelligence Catalog Report (Phase 11D)

**Status:** Completed & Production-Ready  
**Date:** July 2026  
**Catalog Scope:** 14 Core Intelligent Component Definitions  
**Domain Service:** `services/design/component_intelligence.py`  

---

## 1. Executive Summary

The **Component Intelligence Catalog** (`ComponentIntelligence`) serves as the definitive repository of standard, reusable component definitions for Nexora Studio web applications. Rather than generating ad-hoc visual sections from scratch, the AI Builder Session and Design System Engine compose applications by selecting and parameterizing authoritative component definitions from this catalog.

Each definition in the catalog is 100% provider-neutral and rendering-neutral. It encapsulates:
1. **Semantic Metadata & Inputs:** Descriptive tags, required prop schemas, and optional configuration inputs.
2. **Accessibility & Responsive Rules:** Minimum WCAG contrast grades, ARIA roles, keyboard navigation requirements, and multi-breakpoint layout transformations.
3. **Component Variants (`ComponentVariant`):** Named stylistic and structural variations (e.g., `split-screen`, `drawer`, `comparison-table`).
4. **Component Capabilities (`ComponentCapability`):** Provider-neutral declarations of supported advanced behaviors (`video_background`, `3d_scene`, `particles`, `parallax`, `animation`, `localization`, `dark_mode`, `ai_content`, `forms`, `ecommerce`, `authentication`).
5. **Asset Requirements (`AssetRequirements`):** Required and optional media/content placeholders (`image`, `logo`, `generic_3d_asset`, `environment_asset`, `video`, `icon`, etc.).

---

## 2. Core Intelligent Component Definitions (14 Categories)

### 2.1 Hero (`lib_hero_standard`)
- **Name:** Standard Centered Hero
- **Description:** High-impact landing section with prominent headline, supporting copy, primary/secondary action triggers, and hero media asset.
- **Supported Variants:** 
  - `var_hero_split` (*split-screen*): Side-by-side layout with copy on left and illustration on right.
  - `var_hero_video` (*video-backdrop*): Full-width background media backdrop with overlaid copy.
- **Capabilities Supported:** `video_background`, `3d_scene`, `particles`, `parallax`, `animation`, `dark_mode`.
- **Asset Requirements:** 
  - *Required:* `illustration`, `logo`
  - *Optional:* `video`, `environment_asset`, `generic_3d_asset`
- **Accessibility Rules:** ARIA role `region`, heading level `1`, minimum WCAG grade `AA`, keyboard navigable.

---

### 2.2 Navbar (`lib_navbar_standard`)
- **Name:** Standard Navigation Bar
- **Description:** Top navigation header with brand mark, primary navigation links, and action button.
- **Supported Variants:**
  - `var_nav_drawer` (*drawer*): Mobile off-canvas side drawer navigation.
  - `var_nav_floating` (*floating*): Pill-shaped floating navigation bar with shadow.
- **Capabilities Supported:** `animation`, `dark_mode`, `localization`, `authentication`.
- **Asset Requirements:**
  - *Required:* `logo`
  - *Optional:* `icon`
- **Accessibility Rules:** ARIA role `navigation`, focus trap on mobile drawer, minimum WCAG grade `AA`.

---

### 2.3 Footer (`lib_footer_sitemap`)
- **Name:** Sitemap Footer
- **Description:** Comprehensive bottom footer with brand summary, multi-column navigation sitemap, social links, and legal notices.
- **Supported Variants:**
  - `var_footer_minimal` (*minimal*): Simple single-line copyright and social icons footer.
  - `var_footer_newsletter` (*with-newsletter*): Footer with prominent newsletter email subscription form.
- **Capabilities Supported:** `forms`, `localization`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* `logo`
  - *Optional:* `icon`
- **Accessibility Rules:** ARIA role `contentinfo`, minimum WCAG grade `AA`.

---

### 2.4 Pricing (`lib_pricing_grid`)
- **Name:** Tiered Pricing Comparison Grid
- **Description:** Multi-tier pricing showcase with feature checklists, billing cycle toggle, and recommended tier badge.
- **Supported Variants:**
  - `var_pricing_table` (*comparison-table*): Detailed feature-by-feature matrix comparison table.
  - `var_pricing_slider` (*slider*): Interactive user/seat volume slider with dynamic pricing calculations.
- **Capabilities Supported:** `ecommerce`, `animation`, `localization`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* None
  - *Optional:* `icon`, `illustration`
- **Accessibility Rules:** ARIA role `region`, announce price changes on billing toggle, minimum WCAG grade `AA`.

---

### 2.5 Features (`lib_features_grid`)
- **Name:** Feature Showcase Grid
- **Description:** Grid of product benefits or value propositions with supporting icons, headings, and descriptions.
- **Supported Variants:**
  - `var_features_alternating` (*alternating-rows*): Alternating left/right image and text blocks for deep dives.
  - `var_features_cards` (*bordered-cards*): Enclosed surface cards with subtle borders and hover lift.
- **Capabilities Supported:** `animation`, `particles`, `3d_scene`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* `icon`
  - *Optional:* `illustration`, `image`, `generic_3d_asset`
- **Accessibility Rules:** ARIA role `region`, minimum WCAG grade `AA`.

---

### 2.6 Testimonials (`lib_testimonials_grid`)
- **Name:** Customer Testimonial Grid
- **Description:** Social proof section highlighting user reviews, ratings, customer avatars, and company titles.
- **Supported Variants:**
  - `var_testi_carousel` (*carousel*): Interactive sliding carousel with navigation arrows and dots.
  - `var_testi_masonry` (*masonry*): Staggered vertical columns for variable-length quotes.
- **Capabilities Supported:** `animation`, `localization`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* `image` (Avatars)
  - *Optional:* `logo`, `icon`
- **Accessibility Rules:** ARIA role `region`, minimum WCAG grade `AA`.

---

### 2.7 FAQ (`lib_faq_accordion`)
- **Name:** Interactive FAQ Accordion
- **Description:** Expandable/collapsible question and answer list for support and overcoming conversion objections.
- **Supported Variants:**
  - `var_faq_2col` (*two-column-list*): Static two-column question and answer grid without toggles.
  - `var_faq_categorized` (*categorized-tabs*): FAQ split by category tabs (e.g., Billing, Technical, General).
- **Capabilities Supported:** `animation`, `localization`, `dark_mode`, `ai_content`.
- **Asset Requirements:**
  - *Required:* None
  - *Optional:* `icon`
- **Accessibility Rules:** ARIA role `region`, require `aria-expanded` attributes on toggles, minimum WCAG grade `AA`.

---

### 2.8 Contact (`lib_contact_form`)
- **Name:** Inquiry Contact Form
- **Description:** User inquiry submission container with validation fields, office location details, and submit action.
- **Supported Variants:**
  - `var_contact_minimal` (*minimal-center*): Single column centered email capture form.
  - `var_contact_map` (*with-map*): Split screen with interactive map embed on one side.
- **Capabilities Supported:** `forms`, `localization`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* None
  - *Optional:* `icon`, `image`
- **Accessibility Rules:** ARIA role `form`, require explicit label association, minimum WCAG grade `AA`.

---

### 2.9 Gallery (`lib_gallery_masonry`)
- **Name:** Responsive Media Gallery
- **Description:** Visual showcase for portfolio items, photography, or video assets with lightbox capability.
- **Supported Variants:**
  - `var_gallery_grid` (*uniform-grid*): Strict equal-ratio 1:1 square grid layout.
  - `var_gallery_slider` (*horizontal-slider*): Horizontal scrolling filmstrip gallery.
- **Capabilities Supported:** `video_background`, `animation`, `3d_scene`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* `image`
  - *Optional:* `video`, `generic_3d_asset`, `environment_asset`
- **Accessibility Rules:** ARIA role `region`, require non-empty alt text on all media items, minimum WCAG grade `AA`.

---

### 2.10 Blog (`lib_blog_cards`)
- **Name:** Article & News Showcase Cards
- **Description:** Editorial grid displaying recent blog posts, news announcements, publication dates, and author metadata.
- **Supported Variants:**
  - `var_blog_list` (*compact-list*): Horizontal list items with thumbnail on left and summary on right.
  - `var_blog_featured` (*hero-featured*): Large prominent featured article above a 3-column sub-grid.
- **Capabilities Supported:** `ai_content`, `localization`, `animation`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* `image`
  - *Optional:* `icon`
- **Accessibility Rules:** ARIA role `region`, minimum WCAG grade `AA`.

---

### 2.11 Dashboard (`lib_dashboard_kpi`)
- **Name:** Analytics KPI & Data Table Container
- **Description:** Enterprise data visualization container with KPI metric summary cards and tabular data grids.
- **Supported Variants:**
  - `var_dash_compact` (*compact-metrics*): Condensed metric bar without full tabular data.
  - `var_dash_charts` (*with-charts*): Includes visual chart placeholders below KPI summary cards.
- **Capabilities Supported:** `animation`, `dark_mode`, `localization`.
- **Asset Requirements:**
  - *Required:* None
  - *Optional:* `icon`, `illustration`
- **Accessibility Rules:** ARIA role `region`, data tables require column header associations, minimum WCAG grade `AA`.

---

### 2.12 Authentication (`lib_auth_login`)
- **Name:** Secure Login & SSO Card
- **Description:** User authentication portal with credentials form, password recovery link, and social SSO identity buttons.
- **Supported Variants:**
  - `var_auth_split` (*split-brand*): Split screen with promotional branding on left and auth form on right.
  - `var_auth_modal` (*modal-popup*): Compact overlay dialog modal for inline authentication.
- **Capabilities Supported:** `authentication`, `forms`, `localization`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* `logo`
  - *Optional:* `icon`, `illustration`
- **Accessibility Rules:** ARIA role `form`, require secure input types and autocomplete attributes, minimum WCAG grade `AA`.

---

### 2.13 Forms (`lib_forms_multistep`)
- **Name:** Multi-Step Wizard Form Container
- **Description:** Guided step-by-step data collection workflow with progress indicator, back/next navigation, and field validation.
- **Supported Variants:**
  - `var_forms_single` (*single-step*): Consolidated single-page form container with grouped sections.
  - `var_forms_sidebar` (*with-sidebar*): Left sidebar showing step summary and FAQ helper tips.
- **Capabilities Supported:** `forms`, `animation`, `localization`, `dark_mode`, `ai_content`.
- **Asset Requirements:**
  - *Required:* None
  - *Optional:* `icon`, `illustration`
- **Accessibility Rules:** ARIA role `form`, announce step transitions to screen readers, minimum WCAG grade `AA`.

---

### 2.14 Ecommerce (`lib_ecom_product_card`)
- **Name:** Ecommerce Product Showcase & Cart
- **Description:** Product display card and showcase grid featuring product imagery, pricing, variant selectors, and add-to-cart trigger.
- **Supported Variants:**
  - `var_ecom_list` (*list-view*): Horizontal row layout with thumbnail, description, and buy button.
  - `var_ecom_featured` (*hero-product*): Large single-product showcase with 3D model viewer or video.
- **Capabilities Supported:** `ecommerce`, `3d_scene`, `animation`, `localization`, `dark_mode`.
- **Asset Requirements:**
  - *Required:* `image`
  - *Optional:* `video`, `generic_3d_asset`, `icon`
- **Accessibility Rules:** ARIA role `region`, announce cart additions to assistive tech, minimum WCAG grade `AA`.

---

## 3. Capability & Asset Matrix Summary

| Category | Definition ID | `3d_scene` | `video_background` | `ecommerce` | `auth` | Required Assets |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Hero** | `lib_hero_standard` | Yes | Yes | No | No | `illustration`, `logo` |
| **Navbar** | `lib_navbar_standard` | No | No | No | Yes | `logo` |
| **Footer** | `lib_footer_sitemap` | No | No | No | No | `logo` |
| **Pricing** | `lib_pricing_grid` | No | No | Yes | No | None |
| **Features** | `lib_features_grid` | Yes | No | No | No | `icon` |
| **Testimonials** | `lib_testimonials_grid` | No | No | No | No | `image` (Avatars) |
| **FAQ** | `lib_faq_accordion` | No | No | No | No | None |
| **Contact** | `lib_contact_form` | No | No | No | No | None |
| **Gallery** | `lib_gallery_masonry` | Yes | Yes | No | No | `image` |
| **Blog** | `lib_blog_cards` | No | No | No | No | `image` |
| **Dashboard** | `lib_dashboard_kpi` | No | No | No | No | None |
| **Authentication**| `lib_auth_login` | No | No | No | Yes | `logo` |
| **Forms** | `lib_forms_multistep` | No | No | No | No | None |
| **Ecommerce** | `lib_ecom_product_card`| Yes | No | Yes | No | `image` |

---

## 4. Conclusion

The Component Intelligence Catalog empowers Nexora Studio to assemble web applications with unmatched visual polish, consistency, and structural integrity. By defining clear capability contracts and asset requirements in a rendering-neutral format, the catalog bridges high-level AI design intent with robust production execution.
