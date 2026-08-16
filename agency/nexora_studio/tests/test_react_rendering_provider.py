# -*- coding: utf-8 -*-
"""
Standalone Unit Test Suite for Phase 12A: React Generation Engine Foundation.

Verifies:
1. Provider-neutral Render Model (RenderProject, RenderPage, RenderComponent, etc.) instantiation, roundtrip serialization, and zero target-specific references.
2. Stage 1 (build_render_project): Converting frozen AI Planning Models into RenderProject.
3. Stage 2 (generate_react_project): Synthesizing clean, modular React project files (package.json, routes, styles, layouts, components, pages).
4. Support for all 6 required application archetypes (Landing, SaaS Dashboard, Blog, E-commerce, Contact, Authentication).
5. Orchestrator routing via execute_blueprint(..., provider_name='react') and deferred granular canvas mutations.
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
    DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint,
    DesignTokenSet, ColorPalette, ColorToken, TypographyScale, TypographyToken
)
from odoo.addons.nexora_studio.services.design.render_domain import (
    RenderToken, RenderAsset, RenderContent, RenderRoute,
    RenderComponent, RenderLayout, RenderPage, RenderProject
)
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
from odoo.addons.nexora_studio.services.design.blueprint_engine import DesignBlueprintEngine
from odoo.addons.nexora_studio.services.design.design_system_engine import DesignSystemEngine
from odoo.addons.nexora_studio.services.design.layout_engine import DesignLayoutEngine
from odoo.addons.nexora_studio.services.design.asset_planning_engine import AssetPlanningEngine
from odoo.addons.nexora_studio.services.design.content_intelligence_engine import ContentIntelligenceEngine
from odoo.addons.nexora_studio.services.design.design_orchestrator import DesignOrchestrator


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


class TestReactRenderingProviderFoundation(unittest.TestCase):

    def setUp(self):
        self.env = DummyOdooEnv()
        self.engine = ReactRenderingProvider()

    def test_01_render_domain_provider_neutrality(self):
        """Test instantiation and serialization of Render Model without target-specific references."""
        token = RenderToken(name="primary-color", token_type="color", value="#3b82f6")
        asset = RenderAsset(name="hero-img", asset_type="image", source_uri="/img/hero.jpg", role="hero_background")
        content = RenderContent(content_type="headline", text="Welcome to Nexora")
        comp = RenderComponent(name="HeroSection", category="hero", bound_assets=[asset], bound_content=[content])
        layout = RenderLayout(layout_type="grid", constraints={"columns": 12})
        page = RenderPage(name="Home", archetype="landing", path="/", page_layout=layout, sections=[comp])
        route = RenderRoute(path="/", page_id=page.id, title="Home")
        project = RenderProject(name="Test Render Project", tokens=[token], pages=[page], routes=[route], global_assets=[asset], global_content=[content])

        # Test roundtrip serialization
        proj_dict = project.to_dict()
        restored = RenderProject.from_dict(proj_dict)
        self.assertEqual(restored.name, "Test Render Project")
        self.assertEqual(len(restored.pages), 1)
        self.assertEqual(restored.pages[0].sections[0].name, "HeroSection")

        # Verify zero target-specific keywords in serialized dictionary keys
        serialized_str = str(proj_dict).lower()
        prohibited_terms = ["jsx", "react", "react_router", "css", "html", "vite", "nextjs"]
        for term in prohibited_terms:
            self.assertNotIn(f"'{term}'", serialized_str, f"Prohibited target-specific term '{term}' found in RenderModel keys!")

    def test_02_stage_1_build_render_project(self):
        """Test Stage 1: Converting frozen Planning Models into provider-neutral RenderProject."""
        bp = DesignBlueprint(
            blueprint_id="bp_test_100",
            project_name="SaaS App Blueprint",
            pages=[
                PageBlueprint(
                    id="p-1",
                    name="Dashboard",
                    slug="/dashboard",
                    archetype="saas_dashboard",
                    sections=[
                        SectionBlueprint(id="s-1", name="Analytics Grid", section_type="dashboard", layout_container="grid-12"),
                        SectionBlueprint(id="s-2", name="User Table", section_type="forms", layout_container="grid-12")
                    ]
                )
            ],
            token_set=DesignTokenSet(
                id="ts-1",
                name="SaaS Tokens",
                color_palette=ColorPalette(
                    id="cp-1",
                    name="Colors",
                    tokens=[
                        ColorToken(id="c-1", name="primary", hex_value="#3b82f6"),
                        ColorToken(id="c-2", name="background", hex_value="#0f172a")
                    ]
                ),
                typography_scale=TypographyScale(
                    id="tscale-1",
                    name="Typo",
                    tokens=[
                        TypographyToken(id="tt-1", name="heading-1", font_family="Inter", font_size_px=32)
                    ]
                ),
                spacing_scale_px=[8, 16, 24, 32]
            )
        )
        
        # Add mock asset and content plans in metadata as produced by Phase 11F
        bp.metadata['asset_plan_summary'] = {
            'planned_assets': [
                {'asset_id': 'ast-1', 'name': 'logo', 'asset_type': 'logo', 'role': 'navbar_logo'}
            ]
        }
        bp.metadata['content_plan_summary'] = {
            'generated_bundles': [
                {'bundle_id': 'bnd-1', 'name': 'Hero Copy', 'locale': 'en-US'}
            ]
        }

        render_proj = RenderProject.from_generation_bundle(bp)
        self.assertIsInstance(render_proj, RenderProject)
        self.assertEqual(render_proj.name, "SaaS App Blueprint")
        self.assertGreaterEqual(len(render_proj.tokens), 3) # colors, typography, spacing
        self.assertEqual(len(render_proj.global_assets), 1)
        self.assertEqual(len(render_proj.global_content), 1)
        self.assertEqual(len(render_proj.pages), 1)
        self.assertEqual(render_proj.pages[0].archetype, "saas_dashboard")
        self.assertEqual(len(render_proj.pages[0].sections), 2)
        self.assertEqual(len(render_proj.routes), 1)

    def test_03_stage_2_generate_react_project(self):
        """Test Stage 2: Synthesizing clean, modular React project files from RenderProject."""
        comp1 = RenderComponent(name="HeroSection", category="hero")
        comp2 = RenderComponent(name="PricingSection", category="pricing")
        page = RenderPage(name="Home", archetype="landing", path="/", sections=[comp1, comp2], page_layout=RenderLayout(layout_type="container"))
        route = RenderRoute(path="/", page_id=page.id, title="Home")
        proj = RenderProject(name="Landing App", pages=[page], routes=[route])

        res = self.engine.generate_react_project(proj)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["provider"], "react")
        
        struct = res["project_structure"]
        self.assertIn("package.json", struct)
        self.assertIn("vite.config.js", struct)
        self.assertIn("src/main.jsx", struct)
        self.assertIn("src/App.jsx", struct)
        self.assertIn("src/routes.jsx", struct)
        self.assertIn("src/styles/tokens.css", struct)
        self.assertIn("src/config/assets.js", struct)
        self.assertIn("src/config/content.js", struct)
        self.assertIn("src/layouts/ContainerLayout.jsx", struct)
        self.assertIn("src/components/HeroSection.jsx", struct)
        self.assertIn("src/components/PricingSection.jsx", struct)
        self.assertIn("src/pages/HomePage.jsx", struct)

        # Verify valid JSX/TSX syntax patterns in generated files
        self.assertIn("import React from 'react';", struct["src/components/HeroSection.jsx"])
        self.assertIn("export default function HeroSection", struct["src/components/HeroSection.jsx"])
        
        # Verify no prohibited runtime engines
        all_code = " ".join(struct.values())
        self.assertNotIn("three", all_code.lower())
        self.assertNotIn("react-three-fiber", all_code.lower())
        self.assertNotIn("gsap", all_code.lower())

    def test_04_support_all_6_archetypes(self):
        """Test generation support for all 6 required application archetypes across both Stage 1 and Stage 2."""
        archetypes = ["landing", "saas_dashboard", "blog", "ecommerce", "contact", "auth"]
        pages = []
        for idx, arch in enumerate(archetypes):
            pages.append(PageBlueprint(
                id=f"p-{idx}",
                name=f"{arch.capitalize()}",
                slug=f"/{arch}",
                archetype=arch,
                sections=[
                    SectionBlueprint(id=f"s-{idx}", name=f"{arch.capitalize()} Section", section_type=arch if arch in {'blog', 'ecommerce', 'contact', 'auth'} else 'hero')
                ]
            ))

        bp = DesignBlueprint(blueprint_id="bp-multi-arch", project_name="Multi Archetype App", pages=pages)
        render_proj = RenderProject.from_generation_bundle(bp)
        res = self.engine.generate_react_project(render_proj)
        
        self.assertEqual(res["status"], "success")
        supported = res["metadata"]["archetypes_supported"]
        for arch in archetypes:
            self.assertIn(arch, supported)
            self.assertIn(f"src/pages/{arch.capitalize()}Page.jsx", res["project_structure"])

    def test_05_orchestrator_routing_and_deferred_operations(self):
        """Test DesignOrchestrator routing via execute_blueprint(..., provider_name='react')."""
        orch = self.env['nexora.design_orchestrator']
        bp = DesignBlueprint(
            blueprint_id="bp-orch-react",
            project_name="Orchestrator React Test",
            pages=[PageBlueprint(id="p-orch-1", name="Home", slug="/", archetype="landing")]
        )

        res = orch.execute_blueprint(bp, provider_name='react')
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["provider"], "react")
        
        # Verify 5-stage planning compliance metrics are attached
        self.assertIn("design_system_compliance", res)
        self.assertIn("layout_intelligence_compliance", res)
        self.assertIn("asset_planning_compliance", res)
        self.assertIn("content_intelligence_compliance", res)
        
        # Verify React project structure was generated
        self.assertIn("project_structure", res)
        self.assertIn("package.json", res["project_structure"])

        # Verify deferred granular canvas mutations
        deferred = res["unsupported_granular_operations_deferred"]
        self.assertIn("create_page (requires interactive canvas mutation)", deferred)
        self.assertIn("export_svg (requires rendering engine canvas execution)", deferred)


if __name__ == "__main__":
    unittest.main()
