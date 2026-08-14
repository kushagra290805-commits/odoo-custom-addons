# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging
from typing import Dict, Any, Optional, List, Union
from .design_blueprint import DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint
from .design_system import DesignSystem, ComponentDefinition, ComponentLibrary
from .component_intelligence import ComponentIntelligence
from .design_system_validator import DesignSystemValidator, DesignSystemValidationResult

_logger = logging.getLogger(__name__)


class DesignSystemEngine(models.AbstractModel):
    """
    Phase 11D — AI Design System & Component Intelligence Engine.
    Sits between Design Blueprint Engine and rendering providers.
    Enforces reusable component composition, resolves library definitions,
    and validates spacing, typography, layout, token usage, a11y, and responsiveness.
    100% provider-neutral and rendering-neutral.
    """
    _name = 'nexora.design_system_engine'
    _description = 'AI Design System and Component Intelligence Engine'

    @api.model
    def compose_design(self, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Recommend a composition of intelligent, reusable component definitions from the
        Design System Component Library based on client requirements instead of isolated sections.
        """
        req = requirements or {}
        project_name = req.get("project_name", "AI Brand Website")
        include_ecommerce = req.get("include_ecommerce", req.get("ecommerce_enabled", False))
        include_auth = req.get("include_auth", req.get("auth_enabled", False))
        include_blog = req.get("include_blog", req.get("blog_enabled", False))
        hero_variant = req.get("hero_variant", "default")  # e.g. 'split-screen' or 'default'

        library = ComponentIntelligence.get_default_library()
        recommended_items = []

        # 1. Navbar
        nav_def = library.definitions["lib_navbar_standard"]
        recommended_items.append({
            "definition_id": nav_def.id,
            "name": nav_def.name,
            "category": nav_def.category,
            "variant": "drawer" if req.get("mobile_drawer", True) else "default",
            "capabilities_supported": nav_def.capabilities.to_dict(),
            "asset_requirements": nav_def.asset_requirements.to_dict()
        })

        # 2. Hero
        hero_def = library.definitions["lib_hero_standard"]
        selected_hero_var = "split-screen" if hero_variant == "split-screen" else "default"
        recommended_items.append({
            "definition_id": hero_def.id,
            "name": hero_def.name,
            "category": hero_def.category,
            "variant": selected_hero_var,
            "capabilities_supported": hero_def.capabilities.to_dict(),
            "asset_requirements": hero_def.asset_requirements.to_dict()
        })

        # 3. Features
        feat_def = library.definitions["lib_features_grid"]
        recommended_items.append({
            "definition_id": feat_def.id,
            "name": feat_def.name,
            "category": feat_def.category,
            "variant": "bordered-cards",
            "capabilities_supported": feat_def.capabilities.to_dict(),
            "asset_requirements": feat_def.asset_requirements.to_dict()
        })

        # 4. Optional Ecommerce
        if include_ecommerce:
            ecom_def = library.definitions["lib_ecom_product_card"]
            recommended_items.append({
                "definition_id": ecom_def.id,
                "name": ecom_def.name,
                "category": ecom_def.category,
                "variant": "grid-view",
                "capabilities_supported": ecom_def.capabilities.to_dict(),
                "asset_requirements": ecom_def.asset_requirements.to_dict()
            })

        # 5. Pricing
        pricing_def = library.definitions["lib_pricing_grid"]
        recommended_items.append({
            "definition_id": pricing_def.id,
            "name": pricing_def.name,
            "category": pricing_def.category,
            "variant": "comparison-table",
            "capabilities_supported": pricing_def.capabilities.to_dict(),
            "asset_requirements": pricing_def.asset_requirements.to_dict()
        })

        # 6. Testimonials
        testi_def = library.definitions["lib_testimonials_grid"]
        recommended_items.append({
            "definition_id": testi_def.id,
            "name": testi_def.name,
            "category": testi_def.category,
            "variant": "carousel",
            "capabilities_supported": testi_def.capabilities.to_dict(),
            "asset_requirements": testi_def.asset_requirements.to_dict()
        })

        # 7. Optional Blog
        if include_blog:
            blog_def = library.definitions["lib_blog_cards"]
            recommended_items.append({
                "definition_id": blog_def.id,
                "name": blog_def.name,
                "category": blog_def.category,
                "variant": "hero-featured",
                "capabilities_supported": blog_def.capabilities.to_dict(),
                "asset_requirements": blog_def.asset_requirements.to_dict()
            })

        # 8. Optional Authentication
        if include_auth:
            auth_def = library.definitions["lib_auth_login"]
            recommended_items.append({
                "definition_id": auth_def.id,
                "name": auth_def.name,
                "category": auth_def.category,
                "variant": "modal-popup",
                "capabilities_supported": auth_def.capabilities.to_dict(),
                "asset_requirements": auth_def.asset_requirements.to_dict()
            })

        # 9. FAQ
        faq_def = library.definitions["lib_faq_accordion"]
        recommended_items.append({
            "definition_id": faq_def.id,
            "name": faq_def.name,
            "category": faq_def.category,
            "variant": "default",
            "capabilities_supported": faq_def.capabilities.to_dict(),
            "asset_requirements": faq_def.asset_requirements.to_dict()
        })

        # 10. Footer
        footer_def = library.definitions["lib_footer_sitemap"]
        recommended_items.append({
            "definition_id": footer_def.id,
            "name": footer_def.name,
            "category": footer_def.category,
            "variant": "with-newsletter",
            "capabilities_supported": footer_def.capabilities.to_dict(),
            "asset_requirements": footer_def.asset_requirements.to_dict()
        })

        return {
            "status": "success",
            "project_name": project_name,
            "composition_strategy": "reusable_component_composition",
            "recommended_composition": recommended_items,
            "system_id": "lib_core_100",
            "total_reusable_components": len(recommended_items)
        }

    @api.model
    def process_blueprint(self, blueprint: Union[DesignBlueprint, Dict[str, Any]], apply_defaults: bool = True) -> Dict[str, Any]:
        """
        Consume a DesignBlueprint, enrich its components by matching and assigning reusable
        definition_id references from ComponentIntelligence, and validate against DesignSystemValidator.
        """
        if isinstance(blueprint, dict):
            bp = DesignBlueprint.from_dict(blueprint)
        else:
            bp = blueprint

        library = ComponentIntelligence.get_default_library()
        resolved_definitions = []

        # Category mapping for auto-resolution if definition_id is missing
        cat_map = {
            "hero": "lib_hero_standard",
            "navbar": "lib_navbar_standard",
            "header": "lib_navbar_standard",
            "footer": "lib_footer_sitemap",
            "pricing": "lib_pricing_grid",
            "features": "lib_features_grid",
            "testimonials": "lib_testimonials_grid",
            "faq": "lib_faq_accordion",
            "contact": "lib_contact_form",
            "gallery": "lib_gallery_masonry",
            "blog": "lib_blog_cards",
            "dashboard": "lib_dashboard_kpi",
            "authentication": "lib_auth_login",
            "auth": "lib_auth_login",
            "forms": "lib_forms_multistep",
            "form": "lib_forms_multistep",
            "ecommerce": "lib_ecom_product_card",
            "ecom": "lib_ecom_product_card",
            "card": "lib_features_grid"  # Default general card fallback
        }

        # Enrich components in pages
        for page in bp.pages:
            for sec in page.sections:
                def enrich_comp(comp: ComponentBlueprint):
                    if not comp.definition_id and apply_defaults:
                        cat_lower = comp.category.lower() if comp.category else "card"
                        name_lower = comp.name.lower()
                        
                        matched_id = None
                        if cat_lower in cat_map:
                            matched_id = cat_map[cat_lower]
                        else:
                            for k, v in cat_map.items():
                                if k in name_lower or k in cat_lower:
                                    matched_id = v
                                    break
                        if matched_id and matched_id in library.definitions:
                            comp.definition_id = matched_id
                            
                    if comp.definition_id and comp.definition_id in library.definitions:
                        if comp.definition_id not in resolved_definitions:
                            resolved_definitions.append(comp.definition_id)
                            
                    for child in comp.children:
                        enrich_comp(child)

                for comp in sec.components:
                    enrich_comp(comp)

        # Execute Design System validation
        val_res = DesignSystemValidator.validate(bp)
        status = "success" if val_res.is_valid else "warning"

        if not val_res.is_valid:
            _logger.warning("Design System validation reported errors for blueprint '%s': %s", bp.project_name, val_res.errors)

        return {
            "status": status,
            "is_system_compliant": val_res.is_valid,
            "validation_metrics": val_res.metrics,
            "validation_errors": val_res.errors,
            "validation_warnings": val_res.warnings,
            "enriched_blueprint": bp.to_dict(),
            "library_components_resolved": resolved_definitions,
            "note": "Processed through vendor-neutral DesignSystemEngine in accordance with Phase 11D architecture."
        }
