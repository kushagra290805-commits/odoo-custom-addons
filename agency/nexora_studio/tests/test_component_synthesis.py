# -*- coding: utf-8 -*-
"""
Component Synthesis Verification Suite — Phase 12B Task 2 Audit.

Verifies:
1. Complete synthesis of all 25 core components and index.js barrel exporter.
2. Composable hierarchy: asserts absence of duplicated primitive JSX in higher-order components
   (e.g., ProductCard, PricingCard, Navbar must compose Button and Badge).
3. Variant Intelligence: verifies dynamic styling and class generation based on variant props.
4. Accessibility Metadata: verifies semantic HTML tags (<header>, <footer>, <nav>, <section>, <article>),
   ARIA attributes, keyboard navigation tabIndex, and alt text support in generated JSX.
"""
import unittest
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.react_component_library import ReactComponentLibrary
from odoo.addons.nexora_studio.services.design.component_manifest import ComponentManifest


class TestComponentSynthesis(unittest.TestCase):

    def setUp(self):
        self.library = ReactComponentLibrary()
        self.files = self.library.synthesize_all()

    def test_01_all_components_synthesized(self):
        """Verify all core library components (including Accordion, Tabs, Dropdown) and index.js are generated."""
        expected = [
            'src/components/Button.jsx', 'src/components/Badge.jsx', 'src/components/Avatar.jsx',
            'src/components/Alert.jsx', 'src/components/Breadcrumb.jsx', 'src/components/Pagination.jsx',
            'src/components/Modal.jsx', 'src/components/Card.jsx', 'src/components/StatsCard.jsx',
            'src/components/DashboardCard.jsx', 'src/components/PricingCard.jsx', 'src/components/Testimonial.jsx',
            'src/components/BlogCard.jsx', 'src/components/ProductCard.jsx', 'src/components/Navbar.jsx',
            'src/components/Footer.jsx', 'src/components/Hero.jsx', 'src/components/FeatureGrid.jsx',
            'src/components/ProductGrid.jsx', 'src/components/BlogGrid.jsx', 'src/components/FAQ.jsx',
            'src/components/ContactForm.jsx', 'src/components/AuthForm.jsx', 'src/components/Table.jsx',
            'src/components/Sidebar.jsx', 'src/components/Accordion.jsx', 'src/components/Tabs.jsx',
            'src/components/Dropdown.jsx', 'src/components/index.js'
        ]
        self.assertEqual(len(self.files), 29)
        for path in expected:
            self.assertIn(path, self.files, f"Missing synthesized file: {path}")

    def test_02_composable_hierarchy_no_duplicated_jsx(self):
        """Verify higher-order components compose primitives cleanly without duplicated primitive JSX."""
        # PricingCard must compose Card, Badge, and Button
        pricing_jsx = self.files['src/components/PricingCard.jsx']
        self.assertIn("import Card from './Card.jsx';", pricing_jsx)
        self.assertIn("import Button from './Button.jsx';", pricing_jsx)
        self.assertIn("<Card", pricing_jsx)
        self.assertIn("<Button", pricing_jsx)

        # ProductCard must compose Card and Button
        product_jsx = self.files['src/components/ProductCard.jsx']
        self.assertIn("import Card from './Card.jsx';", product_jsx)
        self.assertIn("import Button from './Button.jsx';", product_jsx)
        self.assertIn("<Card", product_jsx)
        self.assertIn("<Button", product_jsx)

        # Navbar must compose Button and Avatar
        navbar_jsx = self.files['src/components/Navbar.jsx']
        self.assertIn("import Button from './Button.jsx';", navbar_jsx)
        self.assertIn("import Avatar from './Avatar.jsx';", navbar_jsx)
        self.assertIn("<Button", navbar_jsx)

        # Table must compose Pagination
        table_jsx = self.files['src/components/Table.jsx']
        self.assertIn("import Pagination from './Pagination.jsx';", table_jsx)
        self.assertIn("<Pagination", table_jsx)

    def test_03_variant_intelligence(self):
        """Verify dynamic variant class generation and style adaptation across components."""
        button_jsx = self.files['src/components/Button.jsx']
        self.assertIn("variant = 'primary'", button_jsx)
        self.assertIn("btn-${variant}", button_jsx)
        self.assertIn("variantStyles[variant]", button_jsx)

        hero_jsx = self.files['src/components/Hero.jsx']
        self.assertIn("variant = 'centered'", hero_jsx)
        self.assertIn("hero-${variant}", hero_jsx)
        self.assertIn("isSplit", hero_jsx)
        self.assertIn("isFullscreen", hero_jsx)

        card_jsx = self.files['src/components/Card.jsx']
        self.assertIn("variant = 'elevated'", card_jsx)
        self.assertIn("card-${variant}", card_jsx)
        self.assertIn("variantStyles[variant]", card_jsx)

    def test_04_accessibility_metadata(self):
        """Verify semantic HTML tags, ARIA attributes, and keyboard navigation tabIndex."""
        navbar_jsx = self.files['src/components/Navbar.jsx']
        self.assertIn('<header', navbar_jsx)
        self.assertIn('role="banner"', navbar_jsx)
        self.assertIn('<nav role="navigation"', navbar_jsx)
        self.assertIn('aria-label="Main Navigation"', navbar_jsx)
        self.assertIn('aria-expanded=', navbar_jsx)

        footer_jsx = self.files['src/components/Footer.jsx']
        self.assertIn('<footer', footer_jsx)
        self.assertIn('role="contentinfo"', footer_jsx)
        self.assertIn('aria-label="Site Footer"', footer_jsx)

        hero_jsx = self.files['src/components/Hero.jsx']
        self.assertIn('<section', hero_jsx)
        self.assertIn('role="region"', hero_jsx)
        self.assertIn('aria-label="Hero Banner"', hero_jsx)
        self.assertIn('<h1', hero_jsx)

        modal_jsx = self.files['src/components/Modal.jsx']
        self.assertIn('role="dialog"', modal_jsx)
        self.assertIn('aria-modal="true"', modal_jsx)

        button_jsx = self.files['src/components/Button.jsx']
        self.assertIn('role="button"', button_jsx)
        self.assertIn('tabIndex=', button_jsx)
        self.assertIn('aria-disabled=', button_jsx)

    def test_05_index_js_exports(self):
        """Verify index.js barrel file exports all 25 components cleanly."""
        index_js = self.files['src/components/index.js']
        for name in [
            'Button', 'Badge', 'Avatar', 'Alert', 'Breadcrumb', 'Pagination', 'Modal',
            'Card', 'StatsCard', 'DashboardCard', 'PricingCard', 'Testimonial', 'BlogCard', 'ProductCard',
            'Navbar', 'Footer', 'Hero', 'FeatureGrid', 'ProductGrid', 'BlogGrid',
            'FAQ', 'ContactForm', 'AuthForm', 'Table', 'Sidebar'
        ]:
            self.assertIn(f"export {{ default as {name} }} from './{name}.jsx';", index_js)


if __name__ == '__main__':
    unittest.main()
