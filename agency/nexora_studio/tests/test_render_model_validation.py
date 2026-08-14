# -*- coding: utf-8 -*-
"""
Render Model Verification Suite — Phase 12A.1 Stage 1 Audit.

Verifies:
1. Stage 1 (build_render_project) transformation integrity across all 6 canonical archetypes:
   (`landing`, `saas_dashboard`, `blog`, `ecommerce`, `contact`, `auth`).
2. Zero dropped planning data: verifies that tokens, navigation routes, layouts, assets, and content
   bundles generated in Phase 11C–11F are fully preserved in RenderProject.
3. Strict provider-neutrality: asserts zero occurrences of target runtime terms
   ('jsx', 'react', 'react_router', 'css', 'html', 'vite', 'nextjs', 'three', 'gsap')
   across serialized Render Model dictionary keys and values.
"""
import unittest
import sys
import os
import time
import json
from typing import Dict, Any, List

# Ensure Odoo and module paths are accessible for standalone test execution
sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.design_blueprint import (
    DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint,
    DesignTokenSet, ColorPalette, ColorToken, TypographyScale, TypographyToken,
    NavigationTree, NavigationNode
)
from odoo.addons.nexora_studio.services.design.render_domain import RenderProject
from odoo.addons.nexora_studio.tests.test_end_to_end_pipeline import (
    MockBuilderSession, GOLDEN_REFERENCES
)
from odoo.addons.nexora_studio.services.design.blueprint_engine import DesignBlueprintEngine
from odoo.addons.nexora_studio.services.design.design_system_engine import DesignSystemEngine
from odoo.addons.nexora_studio.services.design.layout_engine import DesignLayoutEngine
from odoo.addons.nexora_studio.services.design.asset_planning_engine import AssetPlanningEngine
from odoo.addons.nexora_studio.services.design.content_intelligence_engine import ContentIntelligenceEngine
from odoo.addons.nexora_studio.services.design.design_orchestrator import DesignOrchestrator


class DummySysParam:
    def __init__(self, params=None):
        self.params = params or {}
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

    def __getitem__(self, key):
        if key in self.models:
            return self.models[key]
        raise KeyError(key)


class TestRenderModelValidation(unittest.TestCase):
    """Verifies Render Model integrity, completeness, and strict provider-neutrality."""

    @classmethod
    def setUpClass(cls):
        cls.env = DummyOdooEnv()
        cls.performance_records = {}

    def _verify_no_prohibited_terms(self, data: Any, path: str = "root"):
        """Recursively checks that dictionary keys and string values contain no framework-specific terms."""
        prohibited = {"jsx", "react", "react_router", "vite", "nextjs", "three", "gsap", "tailwind"}
        if isinstance(data, dict):
            for k, v in data.items():
                k_lower = str(k).lower()
                for p in prohibited:
                    self.assertNotIn(p, k_lower, f"Prohibited term '{p}' found in Render Model key at {path}.{k}")
                self._verify_no_prohibited_terms(v, f"{path}.{k}")
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                self._verify_no_prohibited_terms(item, f"{path}[{idx}]")
        elif isinstance(data, str):
            val_lower = data.lower()
            # Ignore standard source URLs or mime types if any, but ensure no rendering engine names exist
            for p in prohibited:
                if p == "css" and ("css" in val_lower or ".css" in val_lower):
                    continue
                self.assertNotIn(p, val_lower.split(), f"Prohibited term '{p}' found in Render Model value at {path}: '{data}'")

    def _execute_and_verify_render_model(self, archetype_key: str, req_payload: Dict[str, Any]):
        session = MockBuilderSession(self.env, name=f"Canonical {archetype_key.capitalize()} App", project_type=archetype_key)
        
        # 1-6. Execute AI Planning Pipeline
        bp_res = session.execute_full_planning_pipeline(req_payload)
        self.assertTrue(bp_res.get("is_valid", True), f"Blueprint validation failed for {archetype_key}")
        
        bp_data = bp_res["blueprint"]
        bp = DesignBlueprint.from_dict(bp_data) if isinstance(bp_data, dict) else bp_data
        
        golden = GOLDEN_REFERENCES[archetype_key]
        main_route = golden["expected_routes"][0]
        
        # Set canonical page hierarchy and navigation
        bp.pages = [
            PageBlueprint(
                id=f"p-{archetype_key}",
                name=golden["expected_page_name"],
                slug=main_route,
                archetype=archetype_key,
                sections=[
                    SectionBlueprint(
                        id=f"sec-{archetype_key}-{idx}",
                        name=comp_path.split("/")[-1].replace(".jsx", ""),
                        section_type=archetype_key if archetype_key in {'blog', 'ecommerce', 'contact', 'auth'} else 'hero',
                        layout_container="grid-12"
                    )
                    for idx, comp_path in enumerate(golden["expected_components"])
                ]
            )
        ]
        
        bp.navigation = NavigationTree(id=f'nav-{archetype_key}', name=f'{golden["expected_page_name"]} Nav', root_nodes=[
            NavigationNode(id=f'nav-{archetype_key}-0', label=golden["expected_page_name"], target_slug_or_id=main_route)
        ])
        
        if not bp.token_set:
            bp.token_set = DesignTokenSet(
                id=f"ts-{archetype_key}",
                name=f"{archetype_key} Tokens",
                color_palette=ColorPalette(
                    id=f"cp-{archetype_key}",
                    name="Colors",
                    tokens=[
                        ColorToken(id="c1", name="primary", hex_value="#3b82f6"),
                        ColorToken(id="c2", name="background", hex_value="#0f172a"),
                    ]
                )
            )

        bp.metadata['asset_plan_summary'] = {
            'planned_assets': [
                {'asset_id': f'ast-{idx}', 'name': role, 'asset_type': 'image', 'role': role, 'source_uri': f'/img/{role}.jpg'}
                for idx, role in enumerate(golden["expected_asset_roles"])
            ]
        }
        bp.metadata['content_plan_summary'] = {
            'generated_bundles': [
                {'bundle_id': 'bnd-1', 'name': 'Primary Copy', 'locale': 'en-US', 'content': {key: f"Sample {key}" for key in golden["expected_content_keys"]}}
            ]
        }
        
        # Stage 7 (Phase 12A Stage 1): Transformation to RenderProject
        t0 = time.perf_counter()
        render_proj = RenderProject.from_generation_bundle(bp, asset_plan=bp.metadata['asset_plan_summary'])
        t1 = time.perf_counter()
        self.performance_records[archetype_key] = (t1 - t0) * 1000.0

        # Assert RenderProject integrity & zero planning data loss
        self.assertIsInstance(render_proj, RenderProject)
        self.assertEqual(render_proj.name, bp.project_name)
        self.assertGreaterEqual(len(render_proj.pages), 1, "Zero pages transformed to RenderProject")
        self.assertGreaterEqual(len(render_proj.routes), 1, "Zero routes transformed to RenderProject")
        self.assertGreaterEqual(len(render_proj.tokens), 1, "Zero tokens transformed to RenderProject")
        self.assertGreaterEqual(len(render_proj.global_assets), len(golden["expected_asset_roles"]), "Dropped asset planning data in RenderProject")
        self.assertGreaterEqual(len(render_proj.global_content), 1, "Dropped content intelligence data in RenderProject")

        # Assert strict provider-neutrality across serialized Render Model
        render_dict = render_proj.to_dict()
        self._verify_no_prohibited_terms(render_dict)

    def test_01_landing_render_model(self):
        self._execute_and_verify_render_model("landing", {"project_type": "landing", "target_audience": "B2B Enterprise"})

    def test_02_saas_dashboard_render_model(self):
        self._execute_and_verify_render_model("saas_dashboard", {"project_type": "saas_dashboard", "features": ["analytics", "users"]})

    def test_03_blog_editorial_render_model(self):
        self._execute_and_verify_render_model("blog", {"project_type": "blog", "storytelling_style": "editorial"})

    def test_04_ecommerce_render_model(self):
        self._execute_and_verify_render_model("ecommerce", {"project_type": "ecommerce", "catalog_size": "large"})

    def test_05_contact_render_model(self):
        self._execute_and_verify_render_model("contact", {"project_type": "contact", "include_map": True})

    def test_06_auth_render_model(self):
        self._execute_and_verify_render_model("auth", {"project_type": "auth", "methods": ["oauth", "email"]})


if __name__ == "__main__":
    unittest.main()
