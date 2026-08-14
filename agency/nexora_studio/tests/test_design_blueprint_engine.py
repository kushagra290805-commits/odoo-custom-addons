# -*- coding: utf-8 -*-
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
    DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint,
    ColorPalette, ColorToken, TypographyScale, TypographyToken, DesignTokenSet,
    NavigationTree, NavigationNode, ResponsiveBreakpoint, AssetPlaceholder,
    AnimationRule, ExperienceBlueprint
)
from odoo.addons.nexora_studio.services.design.blueprint_validator import BlueprintValidator, ValidationResult
from odoo.addons.nexora_studio.services.design.blueprint_engine import DesignBlueprintEngine
from odoo.addons.nexora_studio.services.design.design_system_engine import DesignSystemEngine
from odoo.addons.nexora_studio.services.design.layout_engine import DesignLayoutEngine
from odoo.addons.nexora_studio.services.design.asset_planning_engine import AssetPlanningEngine
from odoo.addons.nexora_studio.services.design.content_intelligence_engine import ContentIntelligenceEngine
from odoo.addons.nexora_studio.services.design.design_orchestrator import DesignOrchestrator
from odoo.addons.nexora_studio.services.design.penpot_provider import PenpotDesignProvider


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


class TestDesignBlueprintEngine(unittest.TestCase):
    """
    Comprehensive verification suite for Phase 11C AI Design Blueprint Engine.
    Verifies vendor-neutral domain model serialization, 7-part validation rulesets,
    Experience Consistency checks, Builder Session blueprint generation, and
    Orchestrator/Penpot translation boundaries.
    """

    def test_01_domain_model_serialization(self):
        """Verify roundtrip JSON serialization of DesignBlueprint including ExperienceBlueprint."""
        exp = ExperienceBlueprint(
            visual_style="glassmorphism",
            interaction_style="playful",
            animation_intensity="subtle",
            scrolling_behavior="smooth",
            section_transitions="slide",
            parallax_level="low",
            cursor_behavior="custom-follower",
            rendering_preference="Hybrid",
            performance_budget={"max_asset_payload_kb": 3072, "target_fps": 60, "max_animation_simultaneous": 8},
            accessibility_preferences={"prefers_reduced_motion": False, "wcag_target": "AA", "screen_reader_optimized": True}
        )
        bp = DesignBlueprint(
            blueprint_id="bp_test_100",
            project_name="Studio Test AI Project",
            version="1.1.0",
            pages=[PageBlueprint(id="p1", name="Home", slug="/")],
            experience=exp
        )
        json_str = bp.to_json()
        self.assertIn("glassmorphism", json_str)
        self.assertIn("Hybrid", json_str)
        
        bp_restored = DesignBlueprint.from_json(json_str)
        self.assertEqual(bp_restored.project_name, "Studio Test AI Project")
        self.assertEqual(bp_restored.experience.visual_style, "glassmorphism")
        self.assertEqual(bp_restored.experience.rendering_preference, "Hybrid")

    def test_02_validator_duplicate_pages(self):
        """Verify BlueprintValidator catches duplicate page slugs and IDs."""
        bp = DesignBlueprint(
            blueprint_id="bp_dup",
            project_name="Duplicate Test",
            pages=[
                PageBlueprint(id="page_1", name="Home", slug="/home"),
                PageBlueprint(id="page_2", name="Home Alt", slug="/home")
            ]
        )
        res = BlueprintValidator.validate(bp)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Duplicate page slug detected" in err for err in res.errors))

    def test_03_validator_navigation_integrity(self):
        """Verify BlueprintValidator catches navigation nodes targeting non-existent routes."""
        nav = NavigationTree(id="nav_1", name="Main", root_nodes=[
            NavigationNode(id="n1", label="Valid", target_slug_or_id="/"),
            NavigationNode(id="n2", label="Broken", target_slug_or_id="/non-existent-page")
        ])
        bp = DesignBlueprint(
            blueprint_id="bp_nav",
            project_name="Nav Test",
            pages=[PageBlueprint(id="p1", name="Home", slug="/")],
            navigation=nav
        )
        res = BlueprintValidator.validate(bp)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("targets non-existent route or section: '/non-existent-page'" in err for err in res.errors))

    def test_04_validator_token_consistency(self):
        """Verify BlueprintValidator catches components referencing missing design tokens."""
        comp = ComponentBlueprint(id="c1", name="Broken Card", token_references=["col_nonexistent_token"])
        sec = SectionBlueprint(id="s1", name="Hero", components=[comp])
        page = PageBlueprint(id="p1", name="Home", slug="/", sections=[sec])
        
        token_set = DesignTokenSet(
            id="ts_1", name="Basic",
            color_palette=ColorPalette(id="pal_1", name="Pal", tokens=[ColorToken(id="col_prim", name="Prim", hex_value="#000")])
        )
        bp = DesignBlueprint(
            blueprint_id="bp_tok", project_name="Token Test", pages=[page], token_set=token_set
        )
        res = BlueprintValidator.validate(bp)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("references non-existent design token ID: 'col_nonexistent_token'" in err for err in res.errors))

    def test_05_validator_responsive_and_a11y(self):
        """Verify breakpoint ordering rules and WCAG contrast validation."""
        bps = [
            ResponsiveBreakpoint(id="bp1", label="desktop", min_width_px=1024),
            ResponsiveBreakpoint(id="bp2", label="mobile", min_width_px=320)  # Out of order!
        ]
        token_set = DesignTokenSet(
            id="ts_2", name="A11y",
            color_palette=ColorPalette(id="pal_2", name="Pal", tokens=[
                ColorToken(id="col_fail", name="Bad Contrast Text", hex_value="#CCC", role="text", contrast_ratio_on_background=2.1, wcag_grade="Fail")
            ])
        )
        bp = DesignBlueprint(
            blueprint_id="bp_a11y", project_name="A11y Test", breakpoints=bps, token_set=token_set
        )
        res = BlueprintValidator.validate(bp)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("not strictly greater than previous threshold" in err for err in res.errors))
        self.assertTrue(any("fails WCAG contrast requirements" in err for err in res.errors))

    def test_06_validator_experience_consistency(self):
        """Verify Experience Consistency validation (prefers_reduced_motion vs expressive/parallax)."""
        exp = ExperienceBlueprint(
            animation_intensity="expressive",
            parallax_level="high",
            accessibility_preferences={"prefers_reduced_motion": True, "wcag_target": "AA"}
        )
        bp = DesignBlueprint(blueprint_id="bp_exp", project_name="Exp Test", experience=exp)
        res = BlueprintValidator.validate(bp)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("'prefers_reduced_motion' is enabled in accessibility preferences, but animation_intensity is set to 'expressive'" in err for err in res.errors))
        self.assertTrue(any("'prefers_reduced_motion' is enabled, but parallax_level is set to 'high'" in err for err in res.errors))

    def test_07_engine_blueprint_output(self):
        """Verify DesignBlueprintEngine generates a valid, complete DesignBlueprint structure."""
        env = DummyOdooEnv()
        engine = env['nexora.design_blueprint_engine']
        res = engine.generate_blueprint({"project_name": "AI Generated Brand Website", "version": "2.0.0"})
        self.assertEqual(res.get("status"), "success")
        self.assertTrue(res.get("is_valid"))
        
        bp_dict = res.get("blueprint", {})
        self.assertEqual(bp_dict.get("project_name"), "AI Generated Brand Website")
        self.assertIn("experience", bp_dict)
        self.assertEqual(bp_dict["experience"]["rendering_preference"], "2D")

    def test_08_orchestrator_and_penpot_translation(self):
        """Verify DesignOrchestrator routes blueprint to PenpotDesignProvider and returns structured summary."""
        env = DummyOdooEnv()
        engine = env['nexora.design_blueprint_engine']
        bp_res = engine.generate_blueprint({"project_name": "Penpot Target Blueprint"})
        bp_dict = bp_res["blueprint"]
        
        orch = env['nexora.design_orchestrator']
        
        with patch.object(PenpotDesignProvider, "create_project", return_value={"id": "live-penpot-proj-999", "name": "Penpot Target Blueprint"}) as mock_cp, \
             patch.object(PenpotDesignProvider, "validate_design", return_value={"valid": True, "project_id": "live-penpot-proj-999"}) as mock_vd:
            
            res = orch.execute_blueprint(bp_dict, provider_name="penpot")
            mock_cp.assert_called_once()
            mock_vd.assert_called_once()
            
            self.assertEqual(res.get("status"), "success")
            self.assertEqual(res.get("provider"), "penpot")
            self.assertEqual(res.get("project_id"), "live-penpot-proj-999")
            self.assertIn("create_project", res.get("supported_operations_executed", []))
            self.assertIn("create_page", res.get("unsupported_granular_operations_deferred", [])[0])
            self.assertIn("schema compliance rules", res.get("note", ""))


if __name__ == '__main__':
    unittest.main()
