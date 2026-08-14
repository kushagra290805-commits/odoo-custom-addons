# -*- coding: utf-8 -*-
"""
Canonical Pipeline Contract Test Suite (Phase 13A).

Verifies:
1. Strict Input/Output Type Safety across planning, rendering, and provider stages.
2. Immutability: Mutating downstream models (RenderProject or provider output) never corrupts upstream planning models (DesignBlueprint).
3. Provider Interface & Neutrality: Enforcing that all rendering providers adhere to RenderingProvider contract and that DesignOrchestrator is provider-neutral.
"""

import unittest
import sys
import os
import uuid
from typing import Dict, Any

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.design_blueprint import (
    DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint,
    DesignTokenSet, ColorPalette, ColorToken, TypographyScale, TypographyToken
)
from odoo.addons.nexora_studio.services.design.render_domain import (
    RenderProject, RenderPage, RenderComponent, RenderToken, RenderAsset, RenderContent
)
from odoo.addons.nexora_studio.services.design.providers.rendering_provider import (
    RenderingProvider, RenderingContext, ProviderMetadata
)
from odoo.addons.nexora_studio.services.design.providers.provider_registry import RenderingProviderRegistry
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
from odoo.addons.nexora_studio.services.design.design_orchestrator import DesignOrchestrator
from odoo.addons.nexora_studio.tests.test_runtime_validation import DummyOdooEnv


class TestPipelineContractValidation(unittest.TestCase):
    """Canonical validation of pipeline contract health, immutability, and provider boundaries."""

    @classmethod
    def setUpClass(cls):
        cls.env = DummyOdooEnv()
        cls.orchestrator = cls.env['nexora.design_orchestrator']

    def _create_sample_blueprint(self) -> DesignBlueprint:
        return DesignBlueprint(
            blueprint_id="bp-contract-val",
            project_name="Contract Validation Project",
            pages=[
                PageBlueprint(
                    id="p-100",
                    name="Landing",
                    slug="/",
                    archetype="landing",
                    sections=[
                        SectionBlueprint(
                            id="sec-100",
                            name="Hero Section",
                            section_type="hero",
                            components=[
                                ComponentBlueprint(id="comp-100", name="HeroTitle", category="text")
                            ]
                        )
                    ]
                )
            ],
            token_set=DesignTokenSet(
                id="ts-100",
                name="Contract Tokens",
                color_palette=ColorPalette(
                    id="cp-100",
                    name="Colors",
                    tokens=[ColorToken(id="ct-100", name="primary", hex_value="#3b82f6")]
                ),
                typography_scale=TypographyScale(
                    id="tscale-100",
                    name="Typo",
                    tokens=[TypographyToken(id="tt-100", name="heading-1", font_family="Inter", font_size_px=32)]
                )
            )
        )

    def test_01_input_output_type_contracts(self):
        """Verify strict input and output type contracts across stage boundaries."""
        bp = self._create_sample_blueprint()
        self.assertIsInstance(bp, DesignBlueprint)
        
        # Stage 1: Build RenderProject via from_generation_bundle
        render_proj = RenderProject.from_generation_bundle(bp)
        self.assertIsInstance(render_proj, RenderProject)
        self.assertEqual(render_proj.name, "Contract Validation Project")
        self.assertEqual(len(render_proj.pages), 1)
        self.assertIsInstance(render_proj.pages[0], RenderPage)
        
        # Stage 2: Execute Provider via Orchestrator
        res = self.orchestrator.execute_blueprint(bp, provider_name="react")
        self.assertIsInstance(res, dict)
        
        # Verify required output keys
        required_keys = {
            "status", "project_structure", "provider",
            "supported_operations_executed", "unsupported_granular_operations_deferred", "metadata"
        }
        for rk in required_keys:
            self.assertIn(rk, res, f"Required output key '{rk}' missing from provider response!")
            
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["provider"], "react")
        self.assertIsInstance(res["project_structure"], dict)
        self.assertIsInstance(res["supported_operations_executed"], list)

    def test_02_pipeline_immutability(self):
        """Verify that mutations to downstream models do not mutate or corrupt upstream planning models."""
        bp = self._create_sample_blueprint()
        orig_page_name = bp.pages[0].name
        orig_token_hex = bp.token_set.color_palette.tokens[0].hex_value
        
        # Convert to RenderProject
        render_proj = RenderProject.from_generation_bundle(bp)
        
        # Mutate downstream RenderProject
        render_proj.name = "Mutated Project Name"
        render_proj.pages[0].name = "Mutated Page Name"
        if render_proj.tokens:
            render_proj.tokens[0].value = "#ff0000"
            
        # Verify upstream DesignBlueprint remains completely unmutated
        self.assertEqual(bp.project_name, "Contract Validation Project")
        self.assertEqual(bp.pages[0].name, orig_page_name)
        self.assertEqual(bp.token_set.color_palette.tokens[0].hex_value, orig_token_hex)
        
        # Execute provider and mutate dictionary output
        res = self.orchestrator.execute_blueprint(bp, provider_name="react")
        res["project_structure"]["package.json"] = "{ mutated }"
        
        # Verify subsequent execution is clean
        res2 = self.orchestrator.execute_blueprint(bp, provider_name="react")
        self.assertNotEqual(res2["project_structure"]["package.json"], "{ mutated }")

    def test_03_provider_interface_and_neutrality(self):
        """Verify provider registry contract and neutrality of DesignOrchestrator."""
        provider = RenderingProviderRegistry.get_provider("react")
        self.assertIsInstance(provider, RenderingProvider)
        self.assertIsInstance(provider, ReactRenderingProvider)
        
        # Check required interface methods
        metadata = provider.get_metadata()
        self.assertIsInstance(metadata, ProviderMetadata)
        self.assertEqual(metadata.provider_id, "react")
        
        # Check DesignOrchestrator provider-neutrality (no react branching in execute_blueprint)
        import inspect
        orch_src = inspect.getsource(self.orchestrator.execute_blueprint)
        self.assertNotIn("ReactGenerationEngine", orch_src)
        self.assertIn("get_provider", orch_src)


if __name__ == "__main__":
    unittest.main()
