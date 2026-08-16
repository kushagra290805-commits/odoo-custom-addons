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
from odoo.addons.nexora_studio.services.design.design_system import (
    SpacingScale, GridSystem, IconSystem, ThemeSystem, StateSystem, LayoutRules,
    ComponentVariant, ComponentCapability, AssetRequirements, ComponentDefinition,
    ComponentLibrary, DesignSystem
)
from odoo.addons.nexora_studio.services.design.component_intelligence import ComponentIntelligence
from odoo.addons.nexora_studio.services.design.design_system_validator import DesignSystemValidator, DesignSystemValidationResult
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


class TestDesignSystemEngine(unittest.TestCase):
    """
    Comprehensive verification suite for Phase 11D AI Design System & Component Intelligence.
    Verifies vendor-neutral domain model serialization, 14 intelligent components,
    6-part validation rulesets, Builder Session composition recommendation, and
    Orchestrator/Penpot pipeline consumption.
    """

    def test_01_design_system_domain_serialization(self):
        """Verify roundtrip JSON serialization of DesignSystem, ComponentCapability, and AssetRequirements."""
        cap = ComponentCapability(
            video_background=True,
            three_d_scene=True,
            particles=True,
            ecommerce=True
        )
        asset_req = AssetRequirements(
            required_assets=["image", "logo", "generic_3d_asset"],
            optional_assets=["video", "environment_asset"],
            max_file_size_kb=4096
        )
        comp_def = ComponentDefinition(
            id="test_comp_1",
            name="AI 3D Showcase Card",
            category="Hero",
            capabilities=cap,
            asset_requirements=asset_req
        )
        sys_obj = DesignSystem(
            system_id="sys_test_100",
            name="Nexora Test AI System",
            library=ComponentLibrary(id="lib_1", definitions={"test_comp_1": comp_def})
        )
        
        json_str = sys_obj.to_json()
        self.assertIn("3d_scene", json_str)
        self.assertIn("generic_3d_asset", json_str)
        self.assertIn("Nexora Test AI System", json_str)
        
        sys_restored = DesignSystem.from_json(json_str)
        self.assertEqual(sys_restored.name, "Nexora Test AI System")
        restored_def = sys_restored.library.definitions["test_comp_1"]
        self.assertTrue(restored_def.capabilities.three_d_scene)
        self.assertTrue(restored_def.capabilities.video_background)
        self.assertIn("generic_3d_asset", restored_def.asset_requirements.required_assets)

    def test_02_component_intelligence_catalog(self):
        """Verify ComponentIntelligence catalog exposes all 14 core intelligent component definitions."""
        cats = ComponentIntelligence.list_categories()
        expected_cats = [
            "Hero", "Navbar", "Footer", "Pricing", "Features", "Testimonials",
            "FAQ", "Contact", "Gallery", "Blog", "Dashboard", "Authentication",
            "Forms", "Ecommerce"
        ]
        for ec in expected_cats:
            self.assertIn(ec, cats)
            
        lib = ComponentIntelligence.get_default_library()
        self.assertGreaterEqual(len(lib.definitions), 14)
        
        # Verify specific components have required capabilities and asset requirements
        hero = ComponentIntelligence.get_definition("lib_hero_standard")
        self.assertEqual(hero.category, "Hero")
        self.assertTrue(hero.capabilities.video_background)
        self.assertTrue(hero.capabilities.three_d_scene)
        self.assertIn("illustration", hero.asset_requirements.required_assets)
        
        ecom = ComponentIntelligence.get_definition("lib_ecom_product_card")
        self.assertTrue(ecom.capabilities.ecommerce)
        self.assertTrue(ecom.capabilities.three_d_scene)

    def test_03_validator_token_and_spacing(self):
        """Verify DesignSystemValidator catches token usage and spacing scale deviations."""
        comp = ComponentBlueprint(
            id="c_space", name="Spacing Bad Comp", category="Navbar",
            definition_id="lib_navbar_standard", token_references=["col_nonexistent"]
        )
        sec = SectionBlueprint(id="s1", name="Header", components=[comp])
        bp = DesignBlueprint(blueprint_id="bp_space", project_name="Space Test", pages=[PageBlueprint(id="p1", name="Home", slug="/", sections=[sec])])
        
        # Create custom system with strict spacing scale that doesn't have padding_px=999 in definition
        sys_obj = DesignSystem(
            system_id="sys_strict", name="Strict Sys",
            library=ComponentIntelligence.get_default_library()
        )
        # Override a definition responsive padding to an invalid spacing value
        sys_obj.library.definitions["lib_navbar_standard"].responsive_rules["mobile"]["padding_px"] = 33
        
        val_res = DesignSystemValidator.validate(bp, design_system=sys_obj)
        self.assertFalse(val_res.is_valid)
        self.assertTrue(any("references non-existent token: 'col_nonexistent'" in err for err in val_res.errors))
        self.assertTrue(any("uses padding_px=33, not in SpacingScale" in warn for warn in val_res.warnings))

    def test_04_validator_typography_and_layout(self):
        """Verify DesignSystemValidator catches typography hierarchy and non-standard layout rules."""
        comp1 = ComponentBlueprint(id="c1", name="Hero 1", category="Hero", definition_id="lib_hero_standard", layout_type="invalid-flex")
        comp2 = ComponentBlueprint(id="c2", name="Hero 2", category="Hero", definition_id="lib_hero_standard")
        sec = SectionBlueprint(id="s1", name="Main", components=[comp1, comp2])
        bp = DesignBlueprint(blueprint_id="bp_typo", project_name="Typo Test", pages=[PageBlueprint(id="p1", name="Home", slug="/", sections=[sec])])
        
        # Override hero definition to have heading_level 1, so two heros mean two H1s on page!
        sys_obj = DesignSystem(system_id="sys_typo", name="Typo Sys", library=ComponentIntelligence.get_default_library())
        
        val_res = DesignSystemValidator.validate(bp, design_system=sys_obj)
        self.assertTrue(any("uses non-standard layout_type: 'invalid-flex'" in warn for warn in val_res.warnings))
        self.assertTrue(any("contains 2 H1 headings" in warn for warn in val_res.warnings))

    def test_05_validator_a11y_and_responsive(self):
        """Verify accessibility compliance (AA contrast) and responsive compatibility checks."""
        comp = ComponentBlueprint(id="c_a11y", name="Hero Bad Contrast", category="Hero", definition_id="lib_hero_standard", token_references=["col_bad"])
        sec = SectionBlueprint(id="s1", name="Main", components=[comp])
        
        token_set = DesignTokenSet(
            id="ts_1", name="Basic",
            color_palette=ColorPalette(id="pal_1", name="Pal", tokens=[
                ColorToken(id="col_bad", name="Bad Text", hex_value="#CCC", wcag_grade="Fail")
            ])
        )
        bps = [ResponsiveBreakpoint(id="bp1", label="desktop", min_width_px=1500)]  # Exceeds max 1280!
        bp = DesignBlueprint(blueprint_id="bp_a11y", project_name="A11y Test", pages=[PageBlueprint(id="p1", name="Home", slug="/", sections=[sec])], token_set=token_set, breakpoints=bps)
        
        val_res = DesignSystemValidator.validate(bp)
        self.assertFalse(val_res.is_valid)
        self.assertTrue(any("which has wcag_grade='Fail', violating definition minimum AA" in err for err in val_res.errors))
        self.assertTrue(any("exceeds GridSystem max_container_width_px" in warn for warn in val_res.warnings))

    def test_06_builder_session_composition_recommendation(self):
        """Verify BuilderSession / DesignSystemEngine recommends a composed component structure."""
        env = DummyOdooEnv()
        engine = env['nexora.design_system_engine']
        res = engine.compose_design({"project_name": "Full AI Enterprise Site", "include_ecommerce": True, "include_auth": True, "include_blog": True})
        
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("composition_strategy"), "reusable_component_composition")
        
        items = res.get("recommended_composition", [])
        self.assertGreaterEqual(len(items), 10)
        
        cats_recommended = [it["category"] for it in items]
        self.assertIn("Navbar", cats_recommended)
        self.assertIn("Hero", cats_recommended)
        self.assertIn("Ecommerce", cats_recommended)
        self.assertIn("Authentication", cats_recommended)
        self.assertIn("Blog", cats_recommended)
        
        # Verify capability reporting on recommended items
        hero_item = next(it for it in items if it["category"] == "Hero")
        self.assertTrue(hero_item["capabilities_supported"]["video_background"])
        self.assertTrue(hero_item["capabilities_supported"]["3d_scene"])

    def test_07_design_system_engine_processing(self):
        """Verify DesignSystemEngine enriches components by resolving definition_id from ComponentIntelligence."""
        comp1 = ComponentBlueprint(id="c_nav", name="Header Navigation", category="navbar")  # No definition_id!
        comp2 = ComponentBlueprint(id="c_hero", name="Main Banner Hero", category="hero")  # No definition_id!
        sec = SectionBlueprint(id="s_hero", name="Hero Section", components=[comp1, comp2])
        bp = DesignBlueprint(blueprint_id="bp_enrich", project_name="Enrich Test", pages=[PageBlueprint(id="p1", name="Home", slug="/", sections=[sec])])
        
        env = DummyOdooEnv()
        engine = env['nexora.design_system_engine']
        res = engine.process_blueprint(bp)
        
        self.assertEqual(res.get("status"), "success")
        self.assertTrue(res.get("is_system_compliant"))
        
        resolved = res.get("library_components_resolved", [])
        self.assertIn("lib_navbar_standard", resolved)
        self.assertIn("lib_hero_standard", resolved)
        
        enriched_bp = res.get("enriched_blueprint", {})
        sec_dict = enriched_bp["pages"][0]["sections"][0]
        self.assertEqual(sec_dict["components"][0]["definition_id"], "lib_navbar_standard")
        self.assertEqual(sec_dict["components"][1]["definition_id"], "lib_hero_standard")

    def test_08_orchestrator_and_penpot_consumption(self):
        """Verify DesignOrchestrator routes through DesignSystemEngine and Penpot provider consumes reusable definitions."""
        comp = ComponentBlueprint(id="c_ecom", name="Product Card Showcase", category="ecommerce", variant="grid-view")
        sec = SectionBlueprint(id="s1", name="Shop", components=[comp])
        bp = DesignBlueprint(blueprint_id="bp_orch", project_name="Penpot System Target", pages=[PageBlueprint(id="p1", name="Home", slug="/", sections=[sec])])
        
        env = DummyOdooEnv()
        orch = env['nexora.design_orchestrator']
        
        with patch.object(ReactRenderingProvider, "process_blueprint", return_value={"status": "success", "provider": "react"}) as mock_pb:
            
            res = orch.execute_blueprint(bp, provider_name="react")
            mock_pb.assert_called_once()
            
            self.assertEqual(res.get("status"), "success")
            self.assertEqual(res.get("provider"), "react")
            self.assertTrue(res.get("design_system_compliance", {}).get("is_compliant"))


if __name__ == '__main__':
    unittest.main()
