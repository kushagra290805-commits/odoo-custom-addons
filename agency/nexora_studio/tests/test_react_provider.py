# -*- coding: utf-8 -*-
"""
Unit Tests for ReactRenderingProvider (Phase 12C).

Verifies:
1. Complete synthesis of React 18 (Vite + esbuild) projects from a RenderProject.
2. Modular granular generation methods (layouts, components, pages, routes, assets, tokens).
3. Elimination of duplicate exports in barrel index.js files.
4. Compliance with the 5-part validation contract (validate_manifest, validate_project, validate_build, validate_runtime, validate_artifacts).
5. Orchestration compatibility via RenderingProviderRegistry.get_provider('react').
"""

import unittest
import sys
import os
from typing import Dict, Any, List

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.providers.rendering_provider import RenderingContext
from odoo.addons.nexora_studio.services.design.providers.provider_registry import RenderingProviderRegistry
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
from odoo.addons.nexora_studio.services.design.render_domain import (
    RenderProject, RenderPage, RenderComponent, RenderToken, RenderAsset, RenderContent, RenderRoute, RenderLayout
)


class TestReactRenderingProvider(unittest.TestCase):
    """Test suite for ReactRenderingProvider synthesis and validation."""

    def setUp(self):
        self.provider = RenderingProviderRegistry.get_provider("react")
        self.token = RenderToken(name="color-primary", value="#3b82f6", token_type="color")
        self.asset = RenderAsset(name="hero-img", source_uri="https://example.com/hero.jpg", asset_type="image")
        self.content = RenderContent(id="cnt-1", text="Welcome to Nexora Studio")
        
        self.section_comp = RenderComponent(
            name="Hero", category="hero", props_schema={"title": "Nexora"}, variant="centered"
        )
        self.page_layout = RenderLayout(layout_type="standard")

        self.page = RenderPage(
            name="Landing Page", path="/", archetype="landing",
            sections=[self.section_comp], page_layout=self.page_layout
        )
        self.route = RenderRoute(path="/", page_id="LandingPage")

        
        self.project = RenderProject(
            name="Nexora React Test App",
            version="1.0.0",
            pages=[self.page],
            routes=[self.route],
            tokens=[self.token],
            global_assets=[self.asset],
            global_content=[self.content],
            metadata={"archetypes_present": ["landing"]}
        )
        self.context = RenderingContext.from_project(self.project)

    def test_01_metadata_and_capabilities(self):
        meta = self.provider.get_metadata()
        self.assertEqual(meta.provider_id, "react")
        self.assertTrue(meta.capabilities.layouts)
        self.assertTrue(meta.capabilities.design_tokens)
        self.assertIn("Button", meta.supported_components)
        self.assertIn("package.json", meta.output_structure)

    def test_02_full_project_synthesis(self):
        result = self.provider.generate_project(self.context)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["provider"], "react")
        self.assertEqual(result["project_name"], "Nexora React Test App")
        
        structure = result["project_structure"]
        required_files = [
            'package.json',
            'vite.config.js',
            'index.html',
            'src/main.jsx',
            'src/App.jsx',
            'src/routes.jsx',
            'src/styles/tokens.css',
            'src/config/assets.js',
            'src/config/content.js',
            'src/config/manifest.js',
            'src/components/index.js'
        ]
        for rf in required_files:
            self.assertIn(rf, structure, f"Missing required file in generated structure: {rf}")

        # Check absence of duplicate export in barrel index.js
        index_js = structure['src/components/index.js']
        self.assertEqual(index_js.count("export { default as Button }"), 1, "Duplicate Button export in index.js")
        self.assertIn("Hero", index_js)
        self.assertEqual(index_js.count("export { default as Hero }"), 1, "Duplicate Hero export in index.js")

    def test_03_granular_generation_methods(self):
        layouts = self.provider.generate_layouts(self.context)
        self.assertIn("src/layouts/StandardLayout.jsx", layouts)

        components = self.provider.generate_components(self.context)
        self.assertIn("src/components/Hero.jsx", components)
        self.assertIn("src/components/index.js", components)


        pages = self.provider.generate_pages(self.context)
        self.assertIn("src/pages/LandingPage.jsx", pages)

        routes = self.provider.generate_routes(self.context)
        self.assertIn("src/routes.jsx", routes)
        self.assertIn("src/App.jsx", routes)

        assets = self.provider.generate_assets(self.context)

        self.assertIn("src/config/assets.js", assets)

        tokens = self.provider.generate_design_tokens(self.context)
        self.assertIn("src/styles/tokens.css", tokens)
        self.assertIn("--color-primary: #3b82f6;", tokens['src/styles/tokens.css'])

    def test_04_validation_contract(self):
        res_manifest = self.provider.validate_manifest(self.context)
        self.assertTrue(res_manifest.get("valid", False))

        structure = self.provider.generate_project(self.context)["project_structure"]
        res_project = self.provider.validate_project(self.context, structure)
        self.assertTrue(res_project.get("valid", False), f"Project validation failed: {res_project.get('errors')}")

        res_build = self.provider.validate_build(self.context, {"status": "ok"})
        self.assertTrue(res_build.get("valid", False))
        self.assertEqual(res_build.get("toolchain"), "vite")

        res_runtime = self.provider.validate_runtime(self.context, {"http_status": 200})
        self.assertTrue(res_runtime.get("valid", False))
        self.assertEqual(res_runtime.get("http_status"), 200)

        res_artifacts = self.provider.validate_artifacts(self.context, {"screenshots": 6})
        self.assertTrue(res_artifacts.get("valid", False))
        self.assertEqual(res_artifacts.get("visual_audit"), "playwright")


if __name__ == "__main__":
    unittest.main()
