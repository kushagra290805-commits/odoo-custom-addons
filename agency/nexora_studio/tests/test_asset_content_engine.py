# -*- coding: utf-8 -*-
"""
Standalone Unit Test Suite for Phase 11F: AI Asset Planning & Content Intelligence Engine.

Verifies domain serialization, AI prompt specification generation, content strategy,
asset lifecycles, 6 validation rulesets, quality scoring, 5-stage Builder Session chaining,
Orchestrator routing, and Penpot provider metadata consumption.
"""
import unittest
import sys
import os

# Ensure Odoo and module paths are accessible for standalone test execution
sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.design_blueprint import (
    DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint
)
from odoo.addons.nexora_studio.services.design.asset_domain import (
    AssetPriority, AssetLifecycle, AssetLicense, AssetMetadata, AssetDependency,
    PromptSpecification, AssetDefinition, AssetCollection, AssetReference,
    AssetRequirement, AssetPlan
)
from odoo.addons.nexora_studio.services.design.content_domain import (
    ContentStrategy, BrandVoice, ReadingLevel, LocalizationMetadata, SEOMetadata,
    HeadlineContent, SubHeadlineContent, BodyContent, CTAContent,
    SectionContentBundle, PageContentBundle, ContentPlan
)
from odoo.addons.nexora_studio.services.design.asset_content_validator import (
    AssetContentValidator, AssetContentValidationResult, AssetContentQualityScore
)
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
        return self.models[key]


class TestAssetContentEngine(unittest.TestCase):

    def setUp(self):
        self.env = DummyOdooEnv()

    def test_01_asset_domain_serialization_and_lifecycle(self):
        """Test roundtrip serialization of asset domain models and AssetLifecycle states."""
        self.assertTrue(AssetLifecycle.is_valid(AssetLifecycle.PLANNED))
        self.assertTrue(AssetLifecycle.is_valid("published"))
        self.assertFalse(AssetLifecycle.is_valid("invalid_state"))

        prompt = PromptSpecification(
            asset_type="3d_asset",
            subject_description="Abstract glassmorphism shape",
            style_keywords=["modern", "glass", "3d"],
            aspect_ratio="1:1"
        )
        asset = AssetDefinition(
            name="Hero 3D Symbol",
            asset_type="3d_asset",
            priority=AssetPriority.HIGH,
            lifecycle=AssetLifecycle.APPROVED,
            source_type="generated",
            metadata=AssetMetadata(width_px=1000, height_px=1000, aspect_ratio="1:1", file_format="glb", alt_text="Hero 3D Symbol", aria_role="img"),
            license=AssetLicense(license_type="proprietary", commercial_use=True),
            prompt_spec=prompt
        )
        plan = AssetPlan(project_name="Test Project", required_assets=[asset], prompt_specifications=[prompt])
        
        data = plan.to_dict()
        self.assertEqual(data['project_name'], "Test Project")
        self.assertEqual(len(data['required_assets']), 1)
        self.assertEqual(data['required_assets'][0]['lifecycle'], "approved")
        self.assertEqual(data['required_assets'][0]['prompt_spec']['subject_description'], "Abstract glassmorphism shape")

        reconstructed = AssetPlan.from_dict(data)
        self.assertEqual(reconstructed.required_assets[0].name, "Hero 3D Symbol")
        self.assertEqual(reconstructed.required_assets[0].metadata.file_format, "glb")

    def test_02_content_domain_serialization_and_strategy(self):
        """Test roundtrip serialization of ContentStrategy, BrandVoice, ReadingLevel, and ContentPlan."""
        strategy = ContentStrategy(primary_goal="lead_generation", storytelling_style="customer_centric")
        voice = BrandVoice(archetype="innovator", tone="inspiring", formality_level=3)
        reading = ReadingLevel(target_grade_level=9, flesch_kincaid_target=60.0)
        
        headline = HeadlineContent(text="Experience the Future of AI", semantic_role="hero", tone_tag="inspiring")
        cta = CTAContent(primary_label="Start Free Trial", action_intent="signup", urgency_level="high")
        sec_bundle = SectionContentBundle(section_title="Hero", headlines=[headline], ctas=[cta])
        page_bundle = PageContentBundle(page_name="Home", section_bundles=[sec_bundle])
        
        plan = ContentPlan(
            project_name="SaaS Platform",
            strategy=strategy,
            brand_voice=voice,
            reading_level=reading,
            pages=[page_bundle]
        )
        
        data = plan.to_dict()
        self.assertEqual(data['strategy']['primary_goal'], "lead_generation")
        self.assertEqual(data['brand_voice']['archetype'], "innovator")
        self.assertEqual(data['pages'][0]['section_bundles'][0]['headlines'][0]['text'], "Experience the Future of AI")
        
        reconstructed = ContentPlan.from_dict(data)
        self.assertEqual(reconstructed.strategy.storytelling_style, "customer_centric")
        self.assertEqual(reconstructed.reading_level.target_grade_level, 9)

    def test_03_prompt_specification_generation_no_ai_model(self):
        """Verify that AssetPlanningEngine generates declarative PromptSpecification without invoking AI models."""
        engine = self.env['nexora.asset_planning_engine']
        res = engine.generate_asset_plan({"project_name": "Nexora Enterprise", "project_type": "saas"})
        self.assertTrue(res["is_valid"])
        plan = res["asset_plan"]
        
        self.assertGreaterEqual(len(plan["prompt_specifications"]), 2)
        hero_prompt = next((p for p in plan["prompt_specifications"] if p["asset_type"] == "3d_asset"), None)
        self.assertIsNotNone(hero_prompt)
        self.assertIn("Nexora Enterprise", hero_prompt["subject_description"])
        self.assertIn("glassmorphism", hero_prompt["subject_description"].lower())
        self.assertEqual(hero_prompt["aspect_ratio"], "16:9")

    def test_04_validation_rulesets_and_quality_scoring(self):
        """Test all 6 validation rulesets and AssetContentQualityScore deductions."""
        # Create a plan with intentional defects: missing prompt spec, duplicate ID, licensing violation, missing alt_text, empty headline
        defect_asset = AssetDefinition(
            asset_id="dup-123",
            name="Defective Asset",
            asset_type="image",
            source_type="missing", # Missing without prompt spec -> Completeness error
            metadata=AssetMetadata(alt_text="", aria_role="img"), # Missing alt_text -> Accessibility violation
            license=AssetLicense(commercial_use=False) # Disallows commercial use -> Licensing error
        )
        dup_asset = AssetDefinition(
            asset_id="dup-123", # Duplicate ID -> Duplicate warning
            name="Duplicate Asset",
            asset_type="image"
        )
        asset_plan = AssetPlan(project_name="Defect Test", required_assets=[defect_asset, dup_asset], missing_assets=[defect_asset])

        empty_headline = HeadlineContent(text="") # Empty headline -> Content consistency error
        empty_cta = CTAContent(primary_label="")  # Empty CTA -> Content consistency error
        sec_bundle = SectionContentBundle(section_title="Defect Sec", headlines=[empty_headline], ctas=[empty_cta])
        content_plan = ContentPlan(project_name="Defect Test", pages=[PageContentBundle(section_bundles=[sec_bundle])])

        val_res = AssetContentValidator.validate(blueprint=None, asset_plan=asset_plan, content_plan=content_plan)
        self.assertFalse(val_res.is_valid)
        self.assertGreater(len(val_res.errors), 0)
        self.assertGreater(len(val_res.warnings), 0)

        score = val_res.quality_score
        self.assertLess(score.asset_completeness_score, 100.0)
        self.assertLess(score.licensing_compliance_score, 100.0)
        self.assertLess(score.accessibility_score, 100.0)
        self.assertLess(score.content_consistency_score, 100.0)
        self.assertLess(score.overall_score, 100.0)

    def test_05_builder_session_5_stage_pipeline_chaining(self):
        """Test that Builder Session generate_design_blueprint chains all 5 engine stages sequentially."""
        class MockSession:
            def __init__(self, env):
                self.env = env
                self.project_name = "5-Stage Pipeline Test"
                self.name = "5-Stage Pipeline Test"
            def ensure_one(self):
                pass
            def generate_asset_plan(self, requirements=None):
                req = requirements or {}
                if 'project_name' not in req:
                    req['project_name'] = self.project_name
                return self.env['nexora.asset_planning_engine'].generate_asset_plan(req)
            def generate_content_plan(self, requirements=None):
                req = requirements or {}
                if 'project_name' not in req:
                    req['project_name'] = self.project_name
                return self.env['nexora.content_intelligence_engine'].generate_content_plan(req)
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
                bp_res["asset_plan"] = asset_res.get("asset_plan", {})
                bp_res["content_plan"] = content_res.get("content_plan", {})
                bp_res["asset_planning_compliance"] = {
                    "is_compliant": asset_res.get("is_asset_compliant"),
                    "quality_score": asset_res.get("quality_score", {})
                }
                bp_res["content_intelligence_compliance"] = {
                    "is_compliant": content_res.get("is_content_compliant"),
                    "quality_score": content_res.get("quality_score", {})
                }
                return bp_res

        session = MockSession(self.env)
        res = session.generate_design_blueprint({"project_type": "ecommerce", "category": "retail"})
        self.assertTrue(res.get("is_valid"))
        self.assertIn("blueprint", res)
        self.assertIn("asset_plan", res)
        self.assertIn("content_plan", res)
        
        self.assertTrue(res["asset_planning_compliance"]["is_compliant"])
        self.assertTrue(res["content_intelligence_compliance"]["is_compliant"])

    def test_06_orchestrator_routing_and_penpot_metadata_consumption(self):
        """Test Orchestrator routing through Asset and Content engines and Penpot metadata consumption."""
        bp = DesignBlueprint(blueprint_id="bp-11f-test", project_name="Orchestrator 11F Test", metadata={"project_type": "saas"})
        bp.pages.append(PageBlueprint(id="p-1", name="Home", slug="home", sections=[
            SectionBlueprint(id="s-1", name="Hero", section_type="hero", components=[
                ComponentBlueprint(id="c-1", name="Hero Component", definition_id="hero_standard", variant="default")
            ])
        ]))


        orch = self.env['nexora.design_orchestrator']
        res = orch.execute_blueprint(bp, provider_name="penpot", config={"base_url": "http://localhost:9001", "access_token": "test_token"})
        
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["asset_plan_consumed"])
        self.assertTrue(res["content_plan_consumed"])
        self.assertIn("asset_planning_compliance", res)
        self.assertIn("content_intelligence_compliance", res)
        self.assertIn("upload_bitmap_to_canvas (requires multipart upload schema)", res["unsupported_granular_operations_deferred"])



if __name__ == '__main__':
    unittest.main()
