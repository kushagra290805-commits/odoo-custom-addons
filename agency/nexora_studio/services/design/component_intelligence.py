# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from .design_system import (
    ComponentDefinition, ComponentVariant, ComponentCapability, AssetRequirements, ComponentLibrary
)

class ComponentIntelligence:
    """
    Component Intelligence catalog repository.
    Provides standard, reusable, intelligent component definitions for 14 core categories.
    100% provider-neutral and rendering-neutral.
    """

    @classmethod
    def get_default_library(cls) -> ComponentLibrary:
        """Returns an authoritative ComponentLibrary containing all 14 core intelligent component definitions."""
        definitions = {
            # 1. HERO
            "lib_hero_standard": ComponentDefinition(
                id="lib_hero_standard",
                name="Standard Centered Hero",
                category="Hero",
                description="High-impact landing section with prominent headline, supporting copy, primary/secondary action triggers, and hero media asset.",
                tags=["landing", "hero", "header", "conversion"],
                required_inputs={"title": "string", "subtitle": "string", "cta_primary_label": "string"},
                optional_inputs={"cta_secondary_label": "string", "badge_text": "string", "background_effect": "string"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Hero banner",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "heading_level": 1
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "alignment": "center", "text_align": "center", "padding_px": 24},
                    "tablet": {"layout": "flex-column", "alignment": "center", "text_align": "center", "padding_px": 48},
                    "desktop": {"layout": "flex-column", "alignment": "center", "text_align": "center", "padding_px": 96}
                },
                design_constraints={
                    "min_height_px": 480,
                    "max_width_px": 1280,
                    "allowed_width_modes": ["fill"],
                    "allowed_alignments": ["center", "start"]
                },
                variants=[
                    ComponentVariant(id="var_hero_split", name="split-screen", description="Side-by-side layout with copy on left and illustration on right", layout_override="flex-row"),
                    ComponentVariant(id="var_hero_video", name="video-backdrop", description="Full-width background media backdrop with overlaid copy", layout_override="stack")
                ],
                capabilities=ComponentCapability(
                    video_background=True,
                    three_d_scene=True,
                    particles=True,
                    parallax=True,
                    animation=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["illustration", "logo"],
                    optional_assets=["video", "environment_asset", "generic_3d_asset"],
                    max_file_size_kb=4096,
                    allowed_aspect_ratios=["16:9", "auto"]
                )
            ),

            # 2. NAVBAR
            "lib_navbar_standard": ComponentDefinition(
                id="lib_navbar_standard",
                name="Standard Navigation Bar",
                category="Navbar",
                description="Top navigation header with brand mark, primary navigation links, and action button.",
                tags=["header", "navigation", "menu", "sticky"],
                required_inputs={"brand_name": "string", "nav_links": "list[dict]", "cta_label": "string"},
                optional_inputs={"logo_asset_id": "string", "user_profile_enabled": "boolean"},
                accessibility_requirements={
                    "aria_role": "navigation",
                    "aria_label": "Main navigation",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "focus_trap_on_drawer": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-row", "alignment": "space-between", "menu_mode": "drawer", "padding_px": 16},
                    "tablet": {"layout": "flex-row", "alignment": "space-between", "menu_mode": "inline", "padding_px": 24},
                    "desktop": {"layout": "flex-row", "alignment": "space-between", "menu_mode": "inline", "padding_px": 32}
                },
                design_constraints={
                    "height_px": 80,
                    "width_mode": "fill",
                    "sticky_supported": True
                },
                variants=[
                    ComponentVariant(id="var_nav_drawer", name="drawer", description="Mobile off-canvas side drawer"),
                    ComponentVariant(id="var_nav_floating", name="floating", description="Pill-shaped floating navigation bar with shadow")
                ],
                capabilities=ComponentCapability(
                    animation=True,
                    dark_mode=True,
                    localization=True,
                    authentication=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["logo"],
                    optional_assets=["icon"],
                    max_file_size_kb=512,
                    allowed_aspect_ratios=["auto", "1:1"]
                )
            ),

            # 3. FOOTER
            "lib_footer_sitemap": ComponentDefinition(
                id="lib_footer_sitemap",
                name="Sitemap Footer",
                category="Footer",
                description="Comprehensive bottom footer with brand summary, multi-column navigation sitemap, social links, and legal notices.",
                tags=["footer", "sitemap", "legal", "navigation"],
                required_inputs={"brand_summary": "string", "sitemap_columns": "list[dict]", "copyright_notice": "string"},
                optional_inputs={"newsletter_signup_enabled": "boolean", "social_links": "list[dict]"},
                accessibility_requirements={
                    "aria_role": "contentinfo",
                    "aria_label": "Site footer",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "alignment": "start", "columns": 1, "padding_px": 32},
                    "tablet": {"layout": "grid", "alignment": "start", "columns": 2, "padding_px": 48},
                    "desktop": {"layout": "grid", "alignment": "space-between", "columns": 4, "padding_px": 64}
                },
                design_constraints={
                    "min_height_px": 320,
                    "width_mode": "fill"
                },
                variants=[
                    ComponentVariant(id="var_footer_minimal", name="minimal", description="Simple single-line copyright and social icons footer"),
                    ComponentVariant(id="var_footer_newsletter", name="with-newsletter", description="Footer with prominent newsletter email subscription form")
                ],
                capabilities=ComponentCapability(
                    forms=True,
                    localization=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["logo"],
                    optional_assets=["icon"],
                    max_file_size_kb=512,
                    allowed_aspect_ratios=["auto"]
                )
            ),

            # 4. PRICING
            "lib_pricing_grid": ComponentDefinition(
                id="lib_pricing_grid",
                name="Tiered Pricing Comparison Grid",
                category="Pricing",
                description="Multi-tier pricing showcase with feature checklists, billing cycle toggle, and recommended tier badge.",
                tags=["pricing", "plans", "subscription", "conversion", "ecommerce"],
                required_inputs={"tiers": "list[dict]", "billing_toggle_enabled": "boolean"},
                optional_inputs={"money_back_guarantee_text": "string", "faq_link": "string"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Pricing tiers",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "announce_price_change_on_toggle": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "alignment": "center", "columns": 1, "gap_px": 24},
                    "tablet": {"layout": "grid", "alignment": "center", "columns": 2, "gap_px": 24},
                    "desktop": {"layout": "grid", "alignment": "center", "columns": 3, "gap_px": 32}
                },
                design_constraints={
                    "min_height_px": 540,
                    "card_elevation": "md",
                    "highlighted_card_elevation": "xl"
                },
                variants=[
                    ComponentVariant(id="var_pricing_table", name="comparison-table", description="Detailed feature-by-feature matrix comparison table"),
                    ComponentVariant(id="var_pricing_slider", name="slider", description="Interactive user/seat volume slider with dynamic pricing calculations")
                ],
                capabilities=ComponentCapability(
                    ecommerce=True,
                    animation=True,
                    localization=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=[],
                    optional_assets=["icon", "illustration"],
                    max_file_size_kb=1024,
                    allowed_aspect_ratios=["auto", "1:1"]
                )
            ),

            # 5. FEATURES
            "lib_features_grid": ComponentDefinition(
                id="lib_features_grid",
                name="Feature Showcase Grid",
                category="Features",
                description="Grid of product benefits or value propositions with supporting icons, headings, and descriptions.",
                tags=["features", "benefits", "grid", "showcase"],
                required_inputs={"section_title": "string", "features": "list[dict]"},
                optional_inputs={"section_subtitle": "string", "columns_count": "integer"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Product features",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "columns": 1, "gap_px": 24, "padding_px": 32},
                    "tablet": {"layout": "grid", "columns": 2, "gap_px": 32, "padding_px": 48},
                    "desktop": {"layout": "grid", "columns": 3, "gap_px": 48, "padding_px": 64}
                },
                design_constraints={
                    "min_height_px": 400,
                    "width_mode": "fill"
                },
                variants=[
                    ComponentVariant(id="var_features_alternating", name="alternating-rows", description="Alternating left/right image and text blocks for deep dives"),
                    ComponentVariant(id="var_features_cards", name="bordered-cards", description="Enclosed surface cards with subtle borders and hover lift")
                ],
                capabilities=ComponentCapability(
                    animation=True,
                    particles=True,
                    three_d_scene=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["icon"],
                    optional_assets=["illustration", "image", "generic_3d_asset"],
                    max_file_size_kb=3072,
                    allowed_aspect_ratios=["1:1", "4:3", "auto"]
                )
            ),

            # 6. TESTIMONIALS
            "lib_testimonials_grid": ComponentDefinition(
                id="lib_testimonials_grid",
                name="Customer Testimonial Grid",
                category="Testimonials",
                description="Social proof section highlighting user reviews, ratings, customer avatars, and company titles.",
                tags=["testimonials", "reviews", "social-proof", "trust"],
                required_inputs={"section_title": "string", "testimonials": "list[dict]"},
                optional_inputs={"overall_rating_score": "float", "trust_badge_ids": "list[string]"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Customer testimonials",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "columns": 1, "gap_px": 16},
                    "tablet": {"layout": "grid", "columns": 2, "gap_px": 24},
                    "desktop": {"layout": "grid", "columns": 3, "gap_px": 32}
                },
                design_constraints={
                    "min_height_px": 360,
                    "avatar_size_px": 48
                },
                variants=[
                    ComponentVariant(id="var_testi_carousel", name="carousel", description="Interactive sliding carousel with navigation arrows and dots"),
                    ComponentVariant(id="var_testi_masonry", name="masonry", description="Staggered vertical columns for variable-length quotes")
                ],
                capabilities=ComponentCapability(
                    animation=True,
                    localization=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["image"],  # Avatars
                    optional_assets=["logo", "icon"],
                    max_file_size_kb=1024,
                    allowed_aspect_ratios=["1:1", "auto"]
                )
            ),

            # 7. FAQ
            "lib_faq_accordion": ComponentDefinition(
                id="lib_faq_accordion",
                name="Interactive FAQ Accordion",
                category="FAQ",
                description="Expandable/collapsible question and answer list for support and overcoming conversion objections.",
                tags=["faq", "support", "questions", "accordion"],
                required_inputs={"section_title": "string", "questions": "list[dict]"},
                optional_inputs={"support_contact_link": "string", "category_filters": "list[string]"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Frequently asked questions",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "require_aria_expanded": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "width_mode": "fill", "padding_px": 24},
                    "tablet": {"layout": "flex-column", "width_mode": "fill", "padding_px": 48},
                    "desktop": {"layout": "flex-column", "max_width_px": 800, "alignment": "center", "padding_px": 64}
                },
                design_constraints={
                    "min_height_px": 300,
                    "animation_duration_ms": 250
                },
                variants=[
                    ComponentVariant(id="var_faq_2col", name="two-column-list", description="Static two-column question and answer grid without toggles"),
                    ComponentVariant(id="var_faq_categorized", name="categorized-tabs", description="FAQ split by category tabs (e.g. Billing, Technical, General)")
                ],
                capabilities=ComponentCapability(
                    animation=True,
                    localization=True,
                    dark_mode=True,
                    ai_content=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=[],
                    optional_assets=["icon"],
                    max_file_size_kb=256,
                    allowed_aspect_ratios=["1:1", "auto"]
                )
            ),

            # 8. CONTACT
            "lib_contact_form": ComponentDefinition(
                id="lib_contact_form",
                name="Inquiry Contact Form",
                category="Contact",
                description="User inquiry submission container with validation fields, office location details, and submit action.",
                tags=["contact", "form", "inquiry", "support", "lead-generation"],
                required_inputs={"form_title": "string", "fields": "list[dict]", "submit_label": "string"},
                optional_inputs={"office_address": "string", "contact_phone": "string", "contact_email": "string"},
                accessibility_requirements={
                    "aria_role": "form",
                    "aria_label": "Contact us form",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "require_label_association": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "columns": 1, "padding_px": 24},
                    "tablet": {"layout": "flex-column", "columns": 1, "padding_px": 48},
                    "desktop": {"layout": "grid", "columns": 2, "gap_px": 64, "padding_px": 64}  # Form on left, info on right
                },
                design_constraints={
                    "min_height_px": 480,
                    "input_height_px": 48,
                    "border_radius_px": 8
                },
                variants=[
                    ComponentVariant(id="var_contact_minimal", name="minimal-center", description="Single column centered email capture form"),
                    ComponentVariant(id="var_contact_map", name="with-map", description="Split screen with interactive map embed on one side")
                ],
                capabilities=ComponentCapability(
                    forms=True,
                    localization=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=[],
                    optional_assets=["icon", "image"],
                    max_file_size_kb=1024,
                    allowed_aspect_ratios=["16:9", "auto"]
                )
            ),

            # 9. GALLERY
            "lib_gallery_masonry": ComponentDefinition(
                id="lib_gallery_masonry",
                name="Responsive Media Gallery",
                category="Gallery",
                description="Visual showcase for portfolio items, photography, or video assets with lightbox capability.",
                tags=["gallery", "portfolio", "media", "masonry", "showcase"],
                required_inputs={"media_items": "list[dict]"},
                optional_inputs={"filter_categories_enabled": "boolean", "lightbox_enabled": "boolean"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Media gallery",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "require_alt_text_on_all_items": True
                },
                responsive_rules={
                    "mobile": {"layout": "grid", "columns": 1, "gap_px": 12},
                    "tablet": {"layout": "grid", "columns": 2, "gap_px": 16},
                    "desktop": {"layout": "grid", "columns": 4, "gap_px": 24}
                },
                design_constraints={
                    "min_height_px": 500,
                    "hover_scale_factor": 1.05
                },
                variants=[
                    ComponentVariant(id="var_gallery_grid", name="uniform-grid", description="Strict equal-ratio 1:1 square grid layout"),
                    ComponentVariant(id="var_gallery_slider", name="horizontal-slider", description="Horizontal scrolling filmstrip gallery")
                ],
                capabilities=ComponentCapability(
                    video_background=True,
                    animation=True,
                    three_d_scene=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["image"],
                    optional_assets=["video", "generic_3d_asset", "environment_asset"],
                    max_file_size_kb=8192,
                    allowed_aspect_ratios=["16:9", "4:3", "1:1", "auto"]
                )
            ),

            # 10. BLOG
            "lib_blog_cards": ComponentDefinition(
                id="lib_blog_cards",
                name="Article & News Showcase Cards",
                category="Blog",
                description="Editorial grid displaying recent blog posts, news announcements, publication dates, and author metadata.",
                tags=["blog", "news", "articles", "editorial", "content"],
                required_inputs={"section_title": "string", "articles": "list[dict]"},
                optional_inputs={"view_all_link": "string", "featured_article_id": "string"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Recent articles",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "columns": 1, "gap_px": 24},
                    "tablet": {"layout": "grid", "columns": 2, "gap_px": 32},
                    "desktop": {"layout": "grid", "columns": 3, "gap_px": 32}
                },
                design_constraints={
                    "min_height_px": 450,
                    "card_border_radius_px": 12
                },
                variants=[
                    ComponentVariant(id="var_blog_list", name="compact-list", description="Horizontal list items with thumbnail on left and summary on right"),
                    ComponentVariant(id="var_blog_featured", name="hero-featured", description="Large prominent featured article above a 3-column sub-grid")
                ],
                capabilities=ComponentCapability(
                    ai_content=True,
                    localization=True,
                    animation=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["image"],
                    optional_assets=["icon"],
                    max_file_size_kb=3072,
                    allowed_aspect_ratios=["16:9", "4:3"]
                )
            ),

            # 11. DASHBOARD
            "lib_dashboard_kpi": ComponentDefinition(
                id="lib_dashboard_kpi",
                name="Analytics KPI & Data Table Container",
                category="Dashboard",
                description="Enterprise data visualization container with KPI metric summary cards and tabular data grids.",
                tags=["dashboard", "analytics", "metrics", "table", "enterprise"],
                required_inputs={"kpi_metrics": "list[dict]", "table_headers": "list[string]", "table_rows": "list[list]"},
                optional_inputs={"date_range_picker_enabled": "boolean", "export_button_enabled": "boolean"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Dashboard analytics",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "table_requires_headers": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "kpi_columns": 1, "table_overflow": "scroll-x"},
                    "tablet": {"layout": "grid", "kpi_columns": 2, "table_overflow": "scroll-x"},
                    "desktop": {"layout": "grid", "kpi_columns": 4, "table_overflow": "auto"}
                },
                design_constraints={
                    "min_height_px": 600,
                    "dense_spacing_supported": True
                },
                variants=[
                    ComponentVariant(id="var_dash_compact", name="compact-metrics", description="Condensed metric bar without full tabular data"),
                    ComponentVariant(id="var_dash_charts", name="with-charts", description="Includes visual chart placeholders below KPI summary cards")
                ],
                capabilities=ComponentCapability(
                    animation=True,
                    dark_mode=True,
                    localization=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=[],
                    optional_assets=["icon", "illustration"],
                    max_file_size_kb=1024,
                    allowed_aspect_ratios=["auto"]
                )
            ),

            # 12. AUTHENTICATION
            "lib_auth_login": ComponentDefinition(
                id="lib_auth_login",
                name="Secure Login & SSO Card",
                category="Authentication",
                description="User authentication portal with credentials form, password recovery link, and social SSO identity buttons.",
                tags=["auth", "login", "signup", "sso", "security"],
                required_inputs={"title": "string", "submit_label": "string", "sso_providers": "list[string]"},
                optional_inputs={"forgot_password_link": "string", "signup_redirect_link": "string"},
                accessibility_requirements={
                    "aria_role": "form",
                    "aria_label": "User authentication",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "require_secure_input_types": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "alignment": "center", "width_mode": "fill", "padding_px": 16},
                    "tablet": {"layout": "flex-column", "alignment": "center", "max_width_px": 440, "padding_px": 32},
                    "desktop": {"layout": "flex-column", "alignment": "center", "max_width_px": 480, "padding_px": 48}
                },
                design_constraints={
                    "card_elevation": "lg",
                    "border_radius_px": 16,
                    "centered_viewport": True
                },
                variants=[
                    ComponentVariant(id="var_auth_split", name="split-brand", description="Split screen with promotional branding on left and auth form on right"),
                    ComponentVariant(id="var_auth_modal", name="modal-popup", description="Compact overlay dialog modal for inline authentication")
                ],
                capabilities=ComponentCapability(
                    authentication=True,
                    forms=True,
                    localization=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["logo"],
                    optional_assets=["icon", "illustration"],
                    max_file_size_kb=1024,
                    allowed_aspect_ratios=["1:1", "auto"]
                )
            ),

            # 13. FORMS
            "lib_forms_multistep": ComponentDefinition(
                id="lib_forms_multistep",
                name="Multi-Step Wizard Form Container",
                category="Forms",
                description="Guided step-by-step data collection workflow with progress indicator, back/next navigation, and field validation.",
                tags=["forms", "wizard", "multi-step", "onboarding", "conversion"],
                required_inputs={"steps": "list[dict]", "completion_title": "string"},
                optional_inputs={"save_progress_enabled": "boolean", "step_indicator_type": "string"},
                accessibility_requirements={
                    "aria_role": "form",
                    "aria_label": "Multi-step form wizard",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "announce_step_change": True
                },
                responsive_rules={
                    "mobile": {"layout": "flex-column", "step_indicator_mode": "compact-bar", "padding_px": 16},
                    "tablet": {"layout": "flex-column", "step_indicator_mode": "numbered-circles", "padding_px": 32},
                    "desktop": {"layout": "flex-column", "step_indicator_mode": "full-stepper", "max_width_px": 720, "padding_px": 48}
                },
                design_constraints={
                    "min_height_px": 500,
                    "transition_duration_ms": 300
                },
                variants=[
                    ComponentVariant(id="var_forms_single", name="single-step", description="Consolidated single-page form container with grouped sections"),
                    ComponentVariant(id="var_forms_sidebar", name="with-sidebar", description="Left sidebar showing step summary and FAQ helper tips")
                ],
                capabilities=ComponentCapability(
                    forms=True,
                    animation=True,
                    localization=True,
                    dark_mode=True,
                    ai_content=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=[],
                    optional_assets=["icon", "illustration"],
                    max_file_size_kb=1024,
                    allowed_aspect_ratios=["auto"]
                )
            ),

            # 14. ECOMMERCE
            "lib_ecom_product_card": ComponentDefinition(
                id="lib_ecom_product_card",
                name="Ecommerce Product Showcase & Cart",
                category="Ecommerce",
                description="Product display card and showcase grid featuring product imagery, pricing, variant selectors, and add-to-cart trigger.",
                tags=["ecommerce", "shop", "product", "cart", "catalog"],
                required_inputs={"products": "list[dict]", "currency_symbol": "string"},
                optional_inputs={"quick_view_enabled": "boolean", "wishlist_enabled": "boolean"},
                accessibility_requirements={
                    "aria_role": "region",
                    "aria_label": "Product catalog",
                    "minimum_wcag_grade": "AA",
                    "keyboard_navigable": True,
                    "announce_cart_addition": True
                },
                responsive_rules={
                    "mobile": {"layout": "grid", "columns": 1, "gap_px": 16},
                    "tablet": {"layout": "grid", "columns": 2, "gap_px": 24},
                    "desktop": {"layout": "grid", "columns": 4, "gap_px": 32}
                },
                design_constraints={
                    "image_aspect_ratio": "1:1",
                    "hover_elevation": "lg"
                },
                variants=[
                    ComponentVariant(id="var_ecom_list", name="list-view", description="Horizontal row layout with thumbnail, description, and buy button"),
                    ComponentVariant(id="var_ecom_featured", name="hero-product", description="Large single-product showcase with 3D model viewer or video")
                ],
                capabilities=ComponentCapability(
                    ecommerce=True,
                    three_d_scene=True,
                    animation=True,
                    localization=True,
                    dark_mode=True
                ),
                asset_requirements=AssetRequirements(
                    required_assets=["image"],
                    optional_assets=["video", "generic_3d_asset", "icon"],
                    max_file_size_kb=6144,
                    allowed_aspect_ratios=["1:1", "4:3", "auto"]
                )
            )
        }
        return ComponentLibrary(id="lib_core_100", name="Core Component Library", definitions=definitions)

    @classmethod
    def get_definition(cls, definition_id: str) -> ComponentDefinition:
        """Retrieve a specific intelligent component definition by ID."""
        lib = cls.get_default_library()
        if definition_id not in lib.definitions:
            raise KeyError(f"Component definition '{definition_id}' not found in ComponentIntelligence library.")
        return lib.definitions[definition_id]

    @classmethod
    def list_categories(cls) -> List[str]:
        """List all supported component categories."""
        return [
            "Hero", "Navbar", "Footer", "Pricing", "Features", "Testimonials",
            "FAQ", "Contact", "Gallery", "Blog", "Dashboard", "Authentication",
            "Forms", "Ecommerce"
        ]
