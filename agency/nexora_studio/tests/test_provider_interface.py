# -*- coding: utf-8 -*-
"""
Unit Tests for Provider Interface & Multi-Renderer Foundation (Phase 12C).

Verifies:
1. ProviderCapabilityModel serialization, deserialization, and defaults.
2. ProviderVersioning serialization, deserialization, and compatibility tracking.
3. ProviderMetadata structure and data models.
4. RenderingContext instantiation and helper factory (from_project).
5. RenderingProvider ABC contract enforcement and 5-part validation contract signature.
"""

import unittest
import sys
import os
from typing import Dict, Any, List

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.providers.rendering_provider import (

    ProviderCapabilityModel,
    ProviderVersioning,
    ProviderMetadata,
    RenderingContext,
    RenderingProvider
)
from odoo.addons.nexora_studio.services.design.render_domain import (
    RenderProject, RenderPage, RenderComponent, RenderToken, RenderAsset, RenderContent
)
from odoo.addons.nexora_studio.services.design.component_manifest import ComponentManifest


class MockRenderingProvider(RenderingProvider):
    """Concrete mock provider for testing ABC interface compliance."""
    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="mock",
            display_name="Mock Provider",
            capabilities=ProviderCapabilityModel(animations=True, ssr=True),
            versioning=ProviderVersioning(provider_version="2.0.0", api_version="1.1.0", manifest_version="1.0.0"),
            supported_features=["mock_feature"],
            supported_components=["MockComp"],
            output_structure={"mock.file": "description"}
        )

    def generate_project(self, context: RenderingContext) -> Dict[str, Any]:
        return {"status": "success", "provider": "mock", "project_structure": {"mock.file": "content"}}

    def generate_layouts(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_components(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_pages(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_routes(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_assets(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_design_tokens(self, context: RenderingContext) -> Dict[str, str]: return {}

    def validate_manifest(self, context: RenderingContext) -> bool: return True
    def validate_project(self, context: RenderingContext, structure: Dict[str, str]) -> Dict[str, Any]:
        return {"valid": True, "errors": []}
    def validate_build(self, context: RenderingContext, workspace_path: str) -> Dict[str, Any]:
        return {"status": "success", "returncode": 0}
    def validate_runtime(self, context: RenderingContext, workspace_path: str) -> Dict[str, Any]:
        return {"status": "success", "error": None}
    def validate_artifacts(self, context: RenderingContext, workspace_path: str) -> Dict[str, Any]:
        return {"valid": True, "missing": []}


class TestProviderModels(unittest.TestCase):
    """Test data models for capability, versioning, and metadata."""

    def test_01_capability_model(self):
        cap = ProviderCapabilityModel()
        self.assertTrue(cap.layouts)
        self.assertTrue(cap.routing)
        self.assertTrue(cap.forms)
        self.assertFalse(cap.animations)
        self.assertTrue(cap.design_tokens)
        self.assertTrue(cap.accessibility)
        self.assertTrue(cap.static_export)
        self.assertFalse(cap.ssr)

        d = cap.to_dict()
        self.assertEqual(d["layouts"], True)
        self.assertEqual(d["animations"], False)

        cap2 = ProviderCapabilityModel.from_dict({"animations": True, "ssr": True, "layouts": False})
        self.assertFalse(cap2.layouts)
        self.assertTrue(cap2.animations)
        self.assertTrue(cap2.ssr)

    def test_02_versioning_model(self):
        ver = ProviderVersioning(provider_version="1.2.3", api_version="1.0.0", manifest_version="1.1.0")
        self.assertEqual(ver.provider_version, "1.2.3")
        d = ver.to_dict()
        ver2 = ProviderVersioning.from_dict(d)
        self.assertEqual(ver2, ver)

    def test_03_provider_metadata(self):
        meta = ProviderMetadata(
            provider_id="test_target",
            display_name="Test Rendering Target",
            capabilities=ProviderCapabilityModel(),
            versioning=ProviderVersioning(),
            supported_features=["feature_a", "feature_b"],
            supported_components=["CompA", "CompB"],
            output_structure={"src/": "source dir"}
        )
        self.assertEqual(meta.provider_id, "test_target")
        d = meta.to_dict()
        self.assertIn("capabilities", d)
        self.assertIn("versioning", d)
        meta2 = ProviderMetadata.from_dict(d)
        self.assertEqual(meta2.provider_id, "test_target")
        self.assertEqual(meta2.supported_components, ["CompA", "CompB"])


class TestRenderingContext(unittest.TestCase):
    """Test RenderingContext encapsulation and factory methods."""

    def test_04_from_project_factory(self):
        token = RenderToken(name="color-primary", value="#3b82f6", token_type="color")
        asset = RenderAsset(name="logo", source_uri="https://example.com/logo.png")
        content = RenderContent(id="c-1", text="Welcome")
        page = RenderPage(name="Home Page", path="/")

        proj = RenderProject(
            name="Test Context Project",
            version="1.0.0",
            pages=[page],
            tokens=[token],
            global_assets=[asset],
            global_content=[content],
            metadata={"test_meta": True}
        )

        ctx = RenderingContext.from_project(
            render_project=proj,
            output_config={"out_dir": "/tmp/test"},
            feature_flags={"enable_a11y": True}
        )

        self.assertEqual(ctx.render_project.name, "Test Context Project")
        self.assertEqual(len(ctx.tokens), 1)
        self.assertEqual(ctx.tokens[0].name, "color-primary")
        self.assertEqual(len(ctx.assets), 1)
        self.assertEqual(len(ctx.render_project.global_content), 1)
        self.assertEqual(ctx.render_project.metadata.get("test_meta"), True)
        self.assertEqual(ctx.output_config.get("out_dir"), "/tmp/test")
        self.assertEqual(ctx.feature_flags.get("enable_a11y"), True)
        self.assertIsInstance(ctx.manifest, ComponentManifest)
        self.assertEqual(ctx.manifest.project_name, "Test Context Project")



class TestRenderingProviderABC(unittest.TestCase):
    """Test abstract base class enforcement and interface execution."""

    def test_05_cannot_instantiate_abc(self):
        with self.assertRaises(TypeError):
            # Attempting to instantiate ABC directly should raise TypeError
            RenderingProvider()

    def test_06_mock_provider_execution(self):
        provider = MockRenderingProvider()
        meta = provider.get_metadata()
        self.assertEqual(meta.provider_id, "mock")
        self.assertTrue(meta.capabilities.animations)

        proj = RenderProject(name="Mock Proj")
        ctx = RenderingContext.from_project(proj)
        res = provider.generate_project(ctx)
        self.assertEqual(res["status"], "success")

        # Test 5-part validation contract execution
        self.assertTrue(provider.validate_manifest(ctx))
        self.assertTrue(provider.validate_project(ctx, {})["valid"])
        self.assertEqual(provider.validate_build(ctx, "/tmp")["returncode"], 0)
        self.assertEqual(provider.validate_runtime(ctx, "/tmp")["status"], "success")
        self.assertTrue(provider.validate_artifacts(ctx, "/tmp")["valid"])


if __name__ == "__main__":
    unittest.main()
