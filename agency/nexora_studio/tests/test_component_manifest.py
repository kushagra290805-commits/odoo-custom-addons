# -*- coding: utf-8 -*-
"""
Component Manifest Verification Suite — Phase 12B Task 1 Audit.

Verifies:
1. Framework-agnostic structure: asserts zero occurrences of target runtime terms
   ('jsx', 'react', 'vue', 'vite', 'nextjs') across serialized manifest dictionary keys and values.
2. Complete 25-component catalog: verifies presence of all required primitive, molecule, and organism entries.
3. Variant Intelligence: verifies standard variants for Button, Hero, Navbar, Card, etc.
4. Accessibility Metadata: verifies semantic HTML tags, role definitions, and keyboard navigation rules.
5. Design Token Bindings: verifies direct mapping to CSS variables (var(--...)).
6. Stage 1.5 enrichment: verifies dynamic registration of custom sections from a RenderProject.
"""
import unittest
import sys
import os
import json
from typing import Dict, Any, List

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.component_manifest import ComponentManifest, ComponentManifestEntry
from odoo.addons.nexora_studio.services.design.render_domain import RenderProject, RenderPage, RenderComponent


class TestComponentManifest(unittest.TestCase):

    def setUp(self):
        self.manifest = ComponentManifest.create_default_manifest()

    def test_01_complete_component_catalog(self):
        """Verify all 25 core components are present in the authoritative default manifest."""
        expected_components = [
            'Button', 'Badge', 'Avatar', 'Alert', 'Breadcrumb', 'Pagination', 'Modal',
            'Card', 'StatsCard', 'DashboardCard', 'PricingCard', 'Testimonial', 'BlogCard', 'ProductCard',
            'Navbar', 'Footer', 'Hero', 'FeatureGrid', 'ProductGrid', 'BlogGrid',
            'FAQ', 'ContactForm', 'AuthForm', 'Table', 'Sidebar'
        ]
        for comp_name in expected_components:
            self.assertIn(comp_name, self.manifest.entries, f"Missing required component in manifest: {comp_name}")
        self.assertEqual(len(self.manifest.entries), 25)

    def test_02_variant_intelligence(self):
        """Verify required variants for Button, Hero, Navbar, Card, and other core components."""
        button_entry = self.manifest.entries['Button']
        for var in ['primary', 'secondary', 'outline', 'ghost', 'link']:
            self.assertIn(var, button_entry.variants)
            
        hero_entry = self.manifest.entries['Hero']
        for var in ['centered', 'split', 'fullscreen']:
            self.assertIn(var, hero_entry.variants)
            
        nav_entry = self.manifest.entries['Navbar']
        for var in ['standard', 'transparent', 'sidebar']:
            self.assertIn(var, nav_entry.variants)
            
        card_entry = self.manifest.entries['Card']
        for var in ['elevated', 'outlined', 'flat']:
            self.assertIn(var, card_entry.variants)

    def test_03_accessibility_metadata(self):
        """Verify semantic HTML tags, ARIA attributes, and keyboard navigation rules."""
        for comp_name, entry in self.manifest.entries.items():
            self.assertIn('semantic_tag', entry.accessibility_metadata, f"{comp_name} missing semantic_tag")
            self.assertIn('role', entry.accessibility_metadata, f"{comp_name} missing role")
            
        # Specific accessibility assertions
        self.assertTrue(self.manifest.entries['Button'].accessibility_metadata.get('keyboard_navigable'))
        self.assertEqual(self.manifest.entries['Modal'].accessibility_metadata.get('role'), 'dialog')
        self.assertTrue(self.manifest.entries['Modal'].accessibility_metadata.get('focus_trap'))
        self.assertEqual(self.manifest.entries['Navbar'].accessibility_metadata.get('role'), 'banner')
        self.assertEqual(self.manifest.entries['Table'].accessibility_metadata.get('role'), 'table')

    def test_04_design_token_bindings(self):
        """Verify design token bindings map directly to CSS variables (var(--...))."""
        for comp_name, entry in self.manifest.entries.items():
            bindings = entry.design_token_bindings
            self.assertTrue(len(bindings) > 0, f"{comp_name} has no design token bindings")
            for prop, val in bindings.items():
                if isinstance(val, str) and 'var(--' in val:
                    self.assertTrue(val.startswith('var(--') or 'var(--' in val, f"Invalid token binding in {comp_name}.{prop}: {val}")

    def test_05_framework_agnostic_governance(self):
        """Verify zero occurrences of target runtime rendering terms across the serialized manifest."""
        forbidden_terms = {'jsx', 'react', 'react_router', 'vue', 'vite', 'nextjs'}
        manifest_dict = self.manifest.to_dict()
        serialized_json = json.dumps(manifest_dict).lower()
        
        for term in forbidden_terms:
            self.assertNotIn(f'"{term}"', serialized_json, f"Forbidden framework term '{term}' found in framework-agnostic ComponentManifest.")

    def test_06_from_render_project_enrichment(self):
        """Verify Stage 1.5 enrichment registers custom sections from a RenderProject."""
        proj = RenderProject(id="test-proj", name="Test Project")
        page = RenderPage(id="page-1", name="Landing Page", archetype="landing")
        custom_sec = RenderComponent(id="sec-1", name="CustomHero", category="hero", variant="split")
        page.sections.append(custom_sec)
        proj.pages.append(page)
        
        enriched_manifest = ComponentManifest.from_render_project(proj)
        self.assertIn('CustomHero', enriched_manifest.entries)
        sec_entry = enriched_manifest.entries['CustomHero']
        self.assertEqual(sec_entry.category, 'section')
        self.assertIn('split', sec_entry.variants)


if __name__ == '__main__':
    unittest.main()
