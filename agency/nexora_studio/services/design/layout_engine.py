# -*- coding: utf-8 -*-
"""
Phase 11E — AI Layout Intelligence & Responsive Composition Engine (Odoo Service)

This module implements the standalone Odoo abstract model 'nexora.layout_engine'.
In strict adherence to SOLID principles and Phase 11E architectural constraints:
- Chooses appropriate layouts from the catalog based on page archetypes and component capabilities.
- Optimizes content hierarchy and balances whitespace using Spacing Scale tokens.
- Generates adaptive responsive compositions across 4 standard viewports (Mobile, Tablet, Desktop, Wide Desktop)
  without referencing CSS media queries, HTML DOM, React styles, Three.js, or Penpot APIs.
- Prevents layout conflicts and computes quantitative LayoutQualityScore metrics.
"""

import copy
import logging
from typing import Dict, List, Optional, Any, Union
from odoo import models, api
from .layout_domain import (
    LayoutCatalog, LayoutDefinition, LayoutTree, LayoutNode,
    Container, Grid, Stack, Split, Masonry, Overlay,
    ConstraintRule, AlignmentRule, SectionFlow, LayoutBehavior
)
from .layout_validator import LayoutValidator, LayoutValidationResult, LayoutQualityScore

_logger = logging.getLogger(__name__)


class DesignLayoutEngine(models.AbstractModel):
    """
    Authoritative Layout Intelligence Engine for Nexora Studio.
    Transforms reusable component compositions into adaptive page layouts.
    """
    _name = 'nexora.layout_engine'
    _description = 'AI Layout Intelligence & Responsive Composition Engine'

    @api.model
    def _get_catalog(self) -> LayoutCatalog:
        return LayoutCatalog()

    @api.model
    def recommend_layout_tree(self, requirements: Dict[str, Any], blueprint: Optional[Any] = None) -> Dict[str, Any]:
        """
        Analyze client requirements and component compositions to recommend an optimal layout definition
        and generate adapted responsive layout trees across all 4 viewports.
        """
        catalog = self._get_catalog()
        
        # Determine archetype from requirements
        project_type = str(requirements.get("project_type") or requirements.get("category") or requirements.get("page_archetype") or "").lower()
        project_name = str(requirements.get("project_name") or "Unnamed Project Layout")

        # Mapping heuristics
        if "dash" in project_type or "saas" in project_type or "analytics" in project_type:
            def_id = "layout_saas_dashboard"
        elif "ecom" in project_type or "shop" in project_type or "store" in project_type or "catalog" in project_type:
            def_id = "layout_ecom_catalog"
        elif "blog" in project_type or "news" in project_type or "article" in project_type or "editorial" in project_type:
            def_id = "layout_blog_editorial"
        elif "auth" in project_type or "login" in project_type or "sso" in project_type or "register" in project_type:
            def_id = "layout_auth_portal"
        elif "contact" in project_type or "inquire" in project_type or "location" in project_type:
            def_id = "layout_contact_split"
        elif "price" in project_type or "tier" in project_type or "billing" in project_type:
            def_id = "layout_pricing_comparison"
        elif "faq" in project_type or "help" in project_type or "support" in project_type:
            def_id = "layout_faq_accordion"
        elif "form" in project_type or "wizard" in project_type or "step" in project_type or "onboard" in project_type:
            def_id = "layout_forms_wizard"
        else:
            def_id = "layout_landing_standard"

        def_obj = catalog.get_definition(def_id)
        if not def_obj:
            def_obj = catalog.get_definition("layout_landing_standard")

        _logger.info("Recommend Layout Tree: Mapped project type '%s' to layout definition '%s' (%s).", project_type, def_obj.definition_id, def_obj.name)

        base_tree = copy.deepcopy(def_obj.default_tree) if def_obj.default_tree else LayoutTree(project_name=project_name)
        base_tree.project_name = project_name

        # Generate responsive adaptations across 4 viewports
        responsive_trees = self.generate_responsive_compositions(base_tree, blueprint=blueprint)

        # Validate the generated composition
        val_res = LayoutValidator.validate(blueprint, layout_tree=base_tree)

        return {
            "status": "success",
            "recommended_definition_id": def_obj.definition_id,
            "definition_name": def_obj.name,
            "category": def_obj.category,
            "default_tree": base_tree.to_dict(),
            "responsive_trees": {vp: t.to_dict() for vp, t in responsive_trees.items()},
            "quality_score": val_res.quality_score.to_dict(),
            "validation_metrics": val_res.metrics
        }

    @api.model
    def generate_responsive_compositions(self, base_tree: LayoutTree, blueprint: Optional[Any] = None) -> Dict[str, LayoutTree]:
        """
        Generate adapted LayoutTree configurations for Mobile, Tablet, Desktop, and Wide Desktop viewports
        without referencing CSS media queries or frontend frameworks.
        """
        viewports = ["mobile", "tablet", "desktop", "wide_desktop"]
        adapted_trees: Dict[str, LayoutTree] = {}

        for vp in viewports:
            vp_tree = copy.deepcopy(base_tree)
            vp_tree.viewport = vp
            vp_tree.tree_id = f"{base_tree.tree_id}_{vp}"

            if vp_tree.root_node:
                self._adapt_node_for_viewport(vp_tree.root_node, vp)

            # Adjust SectionFlow spacing per viewport
            if vp_tree.section_flow:
                if vp == "mobile":
                    vp_tree.section_flow.section_spacing_px = min(32, vp_tree.section_flow.section_spacing_px)
                elif vp == "tablet":
                    vp_tree.section_flow.section_spacing_px = min(48, vp_tree.section_flow.section_spacing_px)
                elif vp == "wide_desktop":
                    vp_tree.section_flow.section_spacing_px = max(80, vp_tree.section_flow.section_spacing_px)

            adapted_trees[vp] = vp_tree

        return adapted_trees

    def _adapt_node_for_viewport(self, node: LayoutNode, viewport: str):
        """
        Recursively adapt primitive node parameters for a specific viewport.
        """
        # 1. Mobile adaptations (320px - 767px)
        if viewport == "mobile":
            if isinstance(node, Split):
                if node.stack_on_mobile:
                    # Convert split ratio behavior to vertical stacked flow
                    node.split_ratio = "100-0"
                    node.metadata["responsive_stack_applied"] = True
            elif isinstance(node, Grid):
                node.columns = min(2, node.columns)
                node.gutter_px = min(16, node.gutter_px)
            elif isinstance(node, Masonry):
                node.metadata["active_columns"] = node.columns_per_breakpoint.get("mobile", 1)
                node.gutter_px = min(16, node.gutter_px)
            elif isinstance(node, Stack):
                if node.gap_px > 24:
                    node.gap_px = 24
            elif isinstance(node, Container):
                if node.padding_px > 24:
                    node.padding_px = 24

            # Ensure constraint rules don't overflow mobile viewport bounds
            if node.constraints and node.constraints.min_width_px and node.constraints.min_width_px > 320:
                node.constraints.min_width_px = 320
                node.constraints.overflow_behavior = "wrap"

        # 2. Tablet adaptations (768px - 1023px)
        elif viewport == "tablet":
            if isinstance(node, Grid):
                node.columns = min(6, node.columns)
                node.gutter_px = min(20, node.gutter_px)
            elif isinstance(node, Masonry):
                node.metadata["active_columns"] = node.columns_per_breakpoint.get("tablet", 2)
            elif isinstance(node, Container):
                if node.padding_px > 32:
                    node.padding_px = 32

        # 3. Desktop adaptations (1024px - 1439px)
        elif viewport == "desktop":
            if isinstance(node, Masonry):
                node.metadata["active_columns"] = node.columns_per_breakpoint.get("desktop", 3)

        # 4. Wide Desktop adaptations (1440px+)
        elif viewport == "wide_desktop":
            if isinstance(node, Masonry):
                node.metadata["active_columns"] = node.columns_per_breakpoint.get("wide_desktop", 4)
            elif isinstance(node, Container) and node == node: # root or outer container
                if not node.constraints:
                    node.constraints = ConstraintRule()
                if not node.constraints.max_width_px:
                    node.constraints.max_width_px = 1280
                if not node.alignment:
                    node.alignment = AlignmentRule("center", "top")

        # Recurse children
        for child in node.children:
            self._adapt_node_for_viewport(child, viewport)

    @api.model
    def process_blueprint(self, blueprint: Any) -> Dict[str, Any]:
        """
        Enrich a candidate DesignBlueprint by resolving reusable layout definitions, generating
        responsive layout trees across all 4 viewports, and executing LayoutValidator quality scoring.
        """
        catalog = self._get_catalog()
        
        # Normalize blueprint to dict
        if hasattr(blueprint, 'to_dict'):
            bp_dict = blueprint.to_dict()
            proj_name = getattr(blueprint, 'project_name', 'Unnamed Project')
        elif isinstance(blueprint, dict):
            bp_dict = copy.deepcopy(blueprint)
            proj_name = bp_dict.get('project_name', 'Unnamed Project')
        else:
            raise ValueError("Invalid blueprint passed to DesignLayoutEngine.process_blueprint")

        _logger.info("Processing DesignBlueprint '%s' via AI Layout Intelligence Engine...", proj_name)

        pages = bp_dict.get('pages', [])
        resolved_layouts_count = 0
        proj_type = bp_dict.get('project_type') or bp_dict.get('metadata', {}).get('project_type') or bp_dict.get('metadata', {}).get('category') or ""

        for p in pages:
            p_name = p.get('name', '') if isinstance(p, dict) else getattr(p, 'name', '')
            p_type = p.get('page_type', '') if isinstance(p, dict) else getattr(p, 'page_type', '')
            
            # Resolve layout definition for page if missing
            p_def_id = p.get('layout_definition_id') if isinstance(p, dict) else getattr(p, 'layout_definition_id', None)
            if not p_def_id:
                rec = self.recommend_layout_tree({
                    "page_archetype": p_type or proj_type or p_name,
                    "project_type": proj_type or proj_name,
                    "project_name": proj_name
                })
                p_def_id = rec["recommended_definition_id"]
                if isinstance(p, dict):
                    p['layout_definition_id'] = p_def_id
                    p['layout_tree'] = rec["default_tree"]
                    p['responsive_layout_trees'] = rec["responsive_trees"]
                resolved_layouts_count += 1

            # Also inspect and enrich individual sections
            sections = p.get('sections', []) if isinstance(p, dict) else getattr(p, 'sections', [])
            for s in sections:
                s_def_id = s.get('layout_definition_id') if isinstance(s, dict) else getattr(s, 'layout_definition_id', None)
                s_title = s.get('title', '') if isinstance(s, dict) else getattr(s, 'title', '')
                if not s_def_id:
                    s_rec = self.recommend_layout_tree({
                        "page_archetype": s_title or "section",
                        "project_type": proj_type or proj_name,
                        "project_name": f"{proj_name} - {s_title}"
                    })
                    if isinstance(s, dict):
                        s['layout_definition_id'] = s_rec["recommended_definition_id"]
                        s['layout_tree'] = s_rec["default_tree"]
                    resolved_layouts_count += 1

        # Run validation and quality scoring over enriched blueprint
        val_res = LayoutValidator.validate(bp_dict)

        if not val_res.is_valid:
            _logger.warning("Layout Intelligence validation reported errors: %s", val_res.errors)

        return {
            "status": "success",
            "enriched_blueprint": bp_dict,
            "is_layout_compliant": val_res.is_valid,
            "validation_errors": val_res.errors,
            "validation_warnings": val_res.warnings,
            "validation_metrics": val_res.metrics,
            "quality_score": val_res.quality_score.to_dict(),
            "resolved_layouts_count": resolved_layouts_count
        }
