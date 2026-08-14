# -*- coding: utf-8 -*-
"""
Unit Tests for RenderingProviderRegistry (Phase 12C).

Verifies:
1. Discovery and support querying (is_supported, list_providers).
2. Authoritative metadata and capability querying for active and deferred providers.
3. Provider resolution and dynamic instantiation (get_provider).
4. Enforcement of deferred implementation contract (NotImplementedError for stubs).
5. Dynamic registration of custom provider implementations and type checking.
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
    RenderingProvider, ProviderMetadata, ProviderCapabilityModel, ProviderVersioning, RenderingContext
)
from odoo.addons.nexora_studio.services.design.providers.provider_registry import RenderingProviderRegistry
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider


class DummyCustomProvider(RenderingProvider):
    """Custom provider used for testing dynamic registration."""
    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="custom_target",
            display_name="Custom Test Provider",
            capabilities=ProviderCapabilityModel(animations=True),
            versioning=ProviderVersioning(provider_version="3.0.0")
        )

    def generate_project(self, context: RenderingContext) -> Dict[str, Any]:
        return {"status": "success", "provider": "custom_target"}

    def generate_layouts(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_components(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_pages(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_routes(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_assets(self, context: RenderingContext) -> Dict[str, str]: return {}
    def generate_design_tokens(self, context: RenderingContext) -> Dict[str, str]: return {}

    def validate_manifest(self, context: RenderingContext) -> Dict[str, Any]: return {"valid": True}
    def validate_project(self, context: RenderingContext, structure: Dict[str, str]) -> Dict[str, Any]: return {"valid": True}
    def validate_build(self, context: RenderingContext, build_output: Any = None) -> Dict[str, Any]: return {"returncode": 0}
    def validate_runtime(self, context: RenderingContext, runtime_info: Any = None) -> Dict[str, Any]: return {"status": "success"}
    def validate_artifacts(self, context: RenderingContext, artifacts: Any = None) -> Dict[str, Any]: return {"valid": True}


class TestRenderingProviderRegistry(unittest.TestCase):
    """Test suite for RenderingProviderRegistry."""

    def test_01_discovery(self):
        self.assertTrue(RenderingProviderRegistry.is_supported("react"))
        self.assertTrue(RenderingProviderRegistry.is_supported("vue"))
        self.assertTrue(RenderingProviderRegistry.is_supported("angular"))
        self.assertTrue(RenderingProviderRegistry.is_supported("flutter"))
        self.assertTrue(RenderingProviderRegistry.is_supported("html"))
        self.assertTrue(RenderingProviderRegistry.is_supported("react_three_fiber"))
        self.assertFalse(RenderingProviderRegistry.is_supported("non_existent_target"))


        providers = RenderingProviderRegistry.list_providers()
        self.assertIn("react", providers)
        self.assertIn("vue", providers)

    def test_02_metadata_and_capabilities(self):
        react_meta = RenderingProviderRegistry.get_provider_metadata("react")
        self.assertEqual(react_meta.provider_id, "react")
        self.assertTrue(react_meta.capabilities.layouts)
        self.assertTrue(react_meta.capabilities.design_tokens)

        vue_meta = RenderingProviderRegistry.get_provider_metadata("vue")
        self.assertEqual(vue_meta.provider_id, "vue")
        self.assertIn("Vue 3", vue_meta.display_name)

        caps = RenderingProviderRegistry.get_capabilities("react")
        self.assertIsInstance(caps, ProviderCapabilityModel)
        self.assertTrue(caps.routing)

        with self.assertRaises(ValueError):
            RenderingProviderRegistry.get_provider_metadata("invalid_id")

    def test_03_provider_resolution(self):
        react_provider = RenderingProviderRegistry.get_provider("react")
        self.assertIsInstance(react_provider, ReactRenderingProvider)

        # Deferred providers must raise NotImplementedError in Phase 12C
        with self.assertRaises(NotImplementedError):
            RenderingProviderRegistry.get_provider("vue")
        with self.assertRaises(NotImplementedError):
            RenderingProviderRegistry.get_provider("angular")
        with self.assertRaises(NotImplementedError):
            RenderingProviderRegistry.get_provider("flutter")
        with self.assertRaises(NotImplementedError):
            RenderingProviderRegistry.get_provider("html")

    def test_04_dynamic_registration(self):
        custom_meta = ProviderMetadata(
            provider_id="custom_target",
            display_name="Custom Test Target",
            capabilities=ProviderCapabilityModel(animations=True)
        )
        RenderingProviderRegistry.register_provider(
            provider_id="custom_target",
            provider_cls=DummyCustomProvider,
            metadata=custom_meta
        )

        self.assertTrue(RenderingProviderRegistry.is_supported("custom_target"))
        meta = RenderingProviderRegistry.get_provider_metadata("custom_target")
        self.assertEqual(meta.display_name, "Custom Test Target")

        inst = RenderingProviderRegistry.get_provider("custom_target")
        self.assertIsInstance(inst, DummyCustomProvider)

    def test_05_invalid_registration_type(self):
        class NotAProvider:
            pass

        with self.assertRaises(TypeError):
            RenderingProviderRegistry.register_provider("bad_type", NotAProvider)


if __name__ == "__main__":
    unittest.main()
