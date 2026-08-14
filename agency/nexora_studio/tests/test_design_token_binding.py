# -*- coding: utf-8 -*-
"""
Design Token Binding Suite — Phase 12B Task 4 Audit.

Verifies:
1. Emission of comprehensive baseline UI tokens (colors, radii, shadows, spacing, typography, focus states).
2. Dynamic overriding via custom RenderProject tokens in :root and .dark scopes.
3. Direct CSS variable binding (var(--...)) across synthesized library primitives and molecules.
"""
import unittest
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.render_domain import RenderProject, RenderPage, RenderToken
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
from odoo.addons.nexora_studio.services.design.react_component_library import ReactComponentLibrary
from odoo.addons.nexora_studio.services.design.component_manifest import ComponentManifest


class TestDesignTokenBinding(unittest.TestCase):

    def setUp(self):
        self.engine = ReactRenderingProvider()
        self.library = ReactComponentLibrary(ComponentManifest.create_default_manifest())

    def test_01_baseline_tokens_css(self):
        """Verify baseline UI token generation in src/styles/tokens.css."""
        proj = RenderProject(
            id="proj-tokens-1",
            name="Token Baseline Project",
            project_type="web_app",
            pages=[RenderPage(id="p1", name="Home", path="/")],
            tokens=[]
        )
        output = self.engine.generate_react_project(proj)['project_structure']
        css = output["src/styles/tokens.css"]
        
        # Verify color variables
        self.assertIn("--color-primary:", css)
        self.assertIn("--color-surface:", css)
        self.assertIn("--color-border:", css)
        self.assertIn("--color-text:", css)
        self.assertIn("--color-text-muted:", css)
        
        # Verify spacing scale
        for scale in ['xs', 'sm', 'md', 'lg', 'xl', '2xl']:
            self.assertIn(f"--spacing-{scale}:", css)
            
        # Verify radius and shadow scales
        self.assertIn("--radius-md:", css)
        self.assertIn("--shadow-lg:", css)
        self.assertIn("*:focus-visible", css)

    def test_02_custom_token_overrides(self):
        """Verify custom RenderToken objects emit into CSS scopes."""
        custom_tokens = [
            RenderToken(name="color-brand-accent", value="#ff0055", token_type="color", category="color"),
            RenderToken(name="spacing-custom-gap", value="18px", token_type="spacing", category="spacing")
        ]
        proj = RenderProject(
            id="proj-tokens-2",
            name="Custom Token Project",
            project_type="web_app",
            pages=[RenderPage(id="p1", name="Home", path="/")],
            tokens=custom_tokens
        )
        output = self.engine.generate_react_project(proj)['project_structure']
        css = output["src/styles/tokens.css"]
        
        self.assertIn("--color-brand-accent: #ff0055;", css)
        self.assertIn("--spacing-custom-gap: 18px;", css)

    def test_03_component_library_token_binding(self):
        """Verify generated component library primitives bind directly to CSS variables."""
        files = self.library.synthesize_all()
        
        button_jsx = files["src/components/Button.jsx"]
        self.assertIn("var(--radius-md", button_jsx)
        self.assertIn("var(--color-primary", button_jsx)
        
        card_jsx = files["src/components/Card.jsx"]
        self.assertIn("var(--color-surface", card_jsx)
        self.assertIn("var(--color-text-muted", card_jsx)
        self.assertIn("var(--shadow-", card_jsx)
        self.assertIn("var(--spacing-lg", card_jsx)


if __name__ == '__main__':
    unittest.main()
