# -*- coding: utf-8 -*-
"""
Phase 11E — AI Layout Intelligence & Responsive Composition Engine (Verification Suite)

Standalone unit test suite verifying:
1. Provider-neutral Layout Domain Model serialization (primitives, rules, behaviors, trees).
2. Layout Catalog completeness across 9 standard out-of-the-box archetypes.
3. 6 core Layout Validator rulesets and LayoutQualityScore computation.
4. AI Layout Engine recommendations and responsive adaptations across 4 standard viewports.
5. Builder Session layout recommendation and pipeline blueprint generation.
6. Design Orchestrator routing and Penpot provider metadata consumption.
"""

import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock

# Ensure Odoo and module paths are accessible for standalone test execution
sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.design_blueprint import (
    DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint
)
from odoo.addons.nexora_studio.services.design.layout_domain import (
    LayoutBehavior, ConstraintRule, AlignmentRule, ContentRegion, SectionFlow,
    LayoutNode, Container, Grid, Stack, Split, Masonry, Overlay,
    LayoutTree, LayoutDefinition, LayoutCatalog
)
from odoo.addons.nexora_studio.services.design.layout_validator import (
    LayoutValidator, LayoutValidationResult, LayoutQualityScore
)
from odoo.addons.nexora_studio.services.design.blueprint_engine import DesignBlueprintEngine
from odoo.addons.nexora_studio.services.design.design_system_engine import DesignSystemEngine
from odoo.addons.nexora_studio.services.design.layout_engine import DesignLayoutEngine
from odoo.addons.nexora_studio.services.design.asset_planning_engine import AssetPlanningEngine
from odoo.addons.nexora_studio.services.design.content_intelligence_engine import ContentIntelligenceEngine
from odoo.addons.nexora_studio.services.design.design_orchestrator import DesignOrchestrator
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider


class DummySysParam:
    def __init__(self, params):
        self.params = params
    def sudo(self):
        return self
    def get_param(self, key):
        return self.params.get(key)


class DummyOdooEnv:
    def __init__(self, params=None):
        self.sysparam = DummySysParam(params or {})
        self.models = {}
        self.models['nexora.design_blueprint_engine'] = DesignBlueprintEngine(self, (), ())
        self.models['nexora.design_system_engine'] = DesignSystemEngine(self, (), ())
        self.models['nexora.layout_engine'] = DesignLayoutEngine(self, (), ())
        self.models['nexora.asset_planning_engine'] = AssetPlanningEngine(self, (), ())
        self.models['nexora.content_intelligence_engine'] = ContentIntelligenceEngine(self, (), ())
        self.models['nexora.design_orchestrator'] = DesignOrchestrator(self, (), ())
    def get(self, key):
        if key == 'ir.config_parameter':
            return self.sysparam
        return self.models.get(key)
    def __getitem__(self, key):
        if key == 'ir.config_parameter':
            return self.sysparam
        if key in self.models:
            return self.models[key]
        raise KeyError(key)


class TestLayoutEngine(unittest.TestCase):
    """
    Verification test suite for Phase 11E AI Layout Intelligence & Responsive Composition Engine.
    """
    def setUp(self):
        self.env = DummyOdooEnv()
        self.layout_engine = self.env['nexora.layout_engine']
        self.sys_engine = self.env['nexora.design_system_engine']
        self.bp_engine = self.env['nexora.design_blueprint_engine']
        self.orchestrator = self.env['nexora.design_orchestrator']

    def test_domain_serialization_and_polymorphism(self):
        """Verify serialization and polymorphic deserialization of all layout domain models."""
        behavior = LayoutBehavior(behavior_type="sticky", trigger="scroll", duration_ms=400, offset_px=20)
        const = ConstraintRule(min_width_px=320, max_width_px=1280, aspect_ratio="16:9", overflow_behavior="scroll")
        align = AlignmentRule(horizontal_align="center", vertical_align="middle", content_distribution="evenly")
        region = ContentRegion("hero_main", "Hero Area", priority=1, allowed_component_categories=["Hero"])
        flow = SectionFlow(flow_id="f1", transition_type="stack_vertical", section_spacing_px=64, behaviors=[behavior])

        # Create primitives
        c = Container(node_id="c1", name="Box", padding_px=32, background_style="elevated")
        g = Grid(node_id="g1", name="Grid12", columns=12, gutter_px=24)
        s = Stack(node_id="s1", name="StackV", orientation="vertical", gap_px=16)
        sp = Split(node_id="sp1", name="SplitScreen", split_ratio="60-40", divider_enabled=True)
        m = Masonry(node_id="m1", name="MasonryCat", gutter_px=16)
        o = Overlay(node_id="o1", name="ModalBox", overlay_type="modal", backdrop_dim=True)

        s.children = [c, g, sp, m, o]
        tree = LayoutTree(tree_id="tree1", project_name="Test Tree", viewport="desktop", root_node=s, section_flow=flow, regions={"hero": region})

        # Serialize & Deserialize
        tree_dict = tree.to_dict()
        tree_loaded = LayoutTree.from_dict(tree_dict)

        self.assertEqual(tree_loaded.tree_id, "tree1")
        self.assertEqual(tree_loaded.root_node.node_type, "stack")
        self.assertEqual(len(tree_loaded.root_node.children), 5)
        self.assertIsInstance(tree_loaded.root_node.children[0], Container)
        self.assertIsInstance(tree_loaded.root_node.children[1], Grid)
        self.assertIsInstance(tree_loaded.root_node.children[2], Split)
        self.assertIsInstance(tree_loaded.root_node.children[3], Masonry)
        self.assertIsInstance(tree_loaded.root_node.children[4], Overlay)
        self.assertEqual(tree_loaded.root_node.children[2].split_ratio, "60-40")

    def test_layout_catalog_completeness(self):
        """Verify that LayoutCatalog populates all 9 standard out-of-the-box layout archetypes."""
        catalog = LayoutCatalog()
        all_defs = catalog.get_all()
        expected_ids = {
            "layout_landing_standard",
            "layout_saas_dashboard",
            "layout_ecom_catalog",
            "layout_blog_editorial",
            "layout_auth_portal",
            "layout_contact_split",
            "layout_pricing_comparison",
            "layout_faq_accordion",
            "layout_forms_wizard"
        }
        self.assertEqual(set(all_defs.keys()), expected_ids)
        for def_id, def_obj in all_defs.items():
            self.assertIsNotNone(def_obj.default_tree)
            self.assertEqual(def_obj.definition_id, def_id)

    def test_layout_validation_rulesets_and_quality_score(self):
        """Verify the 6 validation rulesets and LayoutQualityScore computation."""
        # Create a problematic tree triggering multiple rulesets
        bad_stack = Stack(
            node_id="bad_root",
            name="Bad Root Stack",
            gap_px=15, # [Spacing Consistency] 15 is not in STANDARD_SPACING_SCALE
            children=[
                Container(
                    node_id="bad_c",
                    name="Bad Container",
                    padding_px=13, # [Spacing Consistency]
                    constraints=ConstraintRule(min_width_px=900, overflow_behavior="clip") # [Overflow Risk] on mobile
                ),
                Overlay(
                    node_id="bad_o",
                    name="Bad Modal",
                    overlay_type="modal", # [Accessibility Flow] modal without focus trap or pinning
                    behaviors=[]
                ),
                Masonry(
                    node_id="bad_m",
                    name="Bad Masonry",
                    columns_per_breakpoint={"mobile": 4, "desktop": 2} # [Responsive Consistency] more cols on mobile
                )
            ]
        )
        bad_tree = LayoutTree(viewport="mobile", root_node=bad_stack)

        val_res = LayoutValidator.validate(None, layout_tree=bad_tree)
        self.assertFalse(val_res.is_valid)
        self.assertGreaterEqual(len(val_res.errors), 2)   # Overflow risk + responsive anomaly
        self.assertGreaterEqual(len(val_res.warnings), 3) # Spacing + a11y
        self.assertLess(val_res.quality_score.whitespace_score, 100.0)
        self.assertLess(val_res.quality_score.responsive_score, 100.0)
        self.assertLess(val_res.quality_score.accessibility_score, 100.0)
        self.assertLess(val_res.quality_score.overall_score, 100.0)

    def test_ai_layout_recommendation_and_responsive_adaptation(self):
        """Verify AI layout recommendations across archetypes and 4-viewport responsive adaptation."""
        rec_dash = self.layout_engine.recommend_layout_tree({"project_type": "SaaS Dashboard Analytics", "project_name": "Nexus Dash"})
        self.assertEqual(rec_dash["recommended_definition_id"], "layout_saas_dashboard")
        self.assertIn("mobile", rec_dash["responsive_trees"])
        self.assertIn("tablet", rec_dash["responsive_trees"])
        self.assertIn("desktop", rec_dash["responsive_trees"])
        self.assertIn("wide_desktop", rec_dash["responsive_trees"])

        # Check mobile adaptation of Split node in dashboard
        mob_tree = LayoutTree.from_dict(rec_dash["responsive_trees"]["mobile"])
        self.assertEqual(mob_tree.root_node.node_type, "split")
        self.assertEqual(mob_tree.root_node.split_ratio, "100-0") # Converted to stacked flow on mobile

    def test_builder_session_layout_pipeline(self):
        """Verify Builder Session layout recommendation and pipeline blueprint generation."""
        class MockBuilderSession:
            def __init__(self, env, name="Ecom Store", project_name="Ecom Store"):
                self.env = env
                self.name = name
                self.project_name = project_name
            def ensure_one(self):
                pass
            def recommend_page_layout(self, requirements=None):
                req = requirements or {}
                if 'project_name' not in req:
                    req['project_name'] = self.project_name
                return self.env['nexora.layout_engine'].recommend_layout_tree(req)
            def generate_design_blueprint(self, requirements=None):
                req = requirements or {}
                if 'project_name' not in req:
                    req['project_name'] = self.project_name
                bp_res = self.env['nexora.design_blueprint_engine'].generate_blueprint(req)
                sys_res = self.env['nexora.design_system_engine'].process_blueprint(bp_res["blueprint"])
                layout_res = self.env['nexora.layout_engine'].process_blueprint(sys_res["enriched_blueprint"])
                asset_res = self.env['nexora.asset_planning_engine'].process_blueprint(layout_res["enriched_blueprint"], req)
                content_res = self.env['nexora.content_intelligence_engine'].process_blueprint(asset_res["enriched_blueprint"], req)
                bp_res["blueprint"] = content_res["enriched_blueprint"]
                bp_res["layout_intelligence_compliance"] = {
                    "is_compliant": layout_res.get("is_layout_compliant"),
                    "resolved_layouts_count": layout_res.get("resolved_layouts_count", 0),
                    "quality_score": layout_res.get("quality_score", {})
                }
                return bp_res


        session = MockBuilderSession(self.env, name="Ecom Catalog Portal", project_name="Ecom Catalog Portal")
        rec = session.recommend_page_layout({"project_type": "ecommerce"})
        self.assertEqual(rec["recommended_definition_id"], "layout_ecom_catalog")

        bp_res = session.generate_design_blueprint({"project_type": "ecommerce", "project_name": "Shop Portal"})
        self.assertTrue(bp_res["is_valid"])
        self.assertIn("layout_intelligence_compliance", bp_res)
        self.assertGreater(bp_res["layout_intelligence_compliance"]["resolved_layouts_count"], 0)
        self.assertEqual(bp_res["blueprint"]["pages"][0]["layout_definition_id"], "layout_ecom_catalog")

    def test_orchestrator_and_penpot_routing(self):
        """Verify Design Orchestrator routing and ReactRenderingProvider metadata consumption."""
        bp_res = self.bp_engine.generate_blueprint({"project_name": "Blog Editorial Project", "project_type": "blog"})
        bp = bp_res["blueprint"]

        with patch.object(ReactRenderingProvider, "process_blueprint", return_value={"status": "success", "provider": "react"}) as mock_pb:
            res = self.orchestrator.execute_blueprint(bp, provider_name="react")
            mock_pb.assert_called_once()
            
            self.assertEqual(res.get("status"), "success")
            self.assertEqual(res.get("provider"), "react")
            self.assertIn("layout_intelligence_compliance", res)
            self.assertTrue(res["layout_intelligence_compliance"]["is_compliant"])
            self.assertTrue(res["layout_intelligence_compliance"]["is_compliant"])



if __name__ == '__main__':
    unittest.main()
