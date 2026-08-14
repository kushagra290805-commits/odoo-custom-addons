# -*- coding: utf-8 -*-
"""
Layout Composition Suite — Phase 12B Task 4 Audit.

Verifies:
1. Hierarchical layout composition in _generate_layout_jsx and _generate_page_jsx.
2. Responsive grid and flexbox wrappers with CSS token bindings.
3. Clean routing and layout wrapping in App.jsx and routes.jsx.
"""
import unittest
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.render_domain import RenderProject, RenderPage, RenderComponent, RenderLayout, RenderRoute
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider


class TestLayoutComposition(unittest.TestCase):

    def setUp(self):
        self.engine = ReactRenderingProvider()

    def _create_sample_project(self) -> RenderProject:
        layout = RenderLayout(
            id="layout-main",
            layout_type="grid",
            constraints={"max_width_px": "1280"}
        )
        sec1 = RenderComponent(id="sec-1", name="Hero Banner", category="hero")
        sec2 = RenderComponent(id="sec-2", name="Feature Grid", category="features")
        
        page = RenderPage(
            id="page-1",
            name="Home Page",
            path="/",
            archetype="landing",
            page_layout=layout,
            sections=[sec1, sec2]
        )
        route = RenderRoute(
            route_id="route-1",
            path="/",
            page_id="page-1",
            title="Home"
        )
        return RenderProject(
            id="proj-layout-test",
            name="Layout Test Project",
            project_type="web_app",
            pages=[page],
            routes=[route],
            shared_layouts=[layout]
        )

    def test_01_layout_wrapper_jsx(self):
        """Verify layout synthesizer emits responsive grid/flex container styles."""
        proj = self._create_sample_project()
        output = self.engine.generate_react_project(proj)['project_structure']
        
        layout_jsx = output["src/layouts/GridLayout.jsx"]
        self.assertIn("import React from 'react';", layout_jsx)
        self.assertIn("export default function GridLayout({ children, className = '' })", layout_jsx)
        self.assertIn("maxWidth: '1280px'", layout_jsx)
        self.assertIn("margin: '0 auto'", layout_jsx)
        self.assertIn("display: 'grid'", layout_jsx)

    def test_02_page_composition_hierarchy(self):
        """Verify page synthesizer composes sections cleanly inside layout without duplicated JSX."""
        proj = self._create_sample_project()
        output = self.engine.generate_react_project(proj)['project_structure']
        
        page_jsx = output["src/pages/HomePage.jsx"]
        self.assertIn("import GridLayout from '../layouts/GridLayout.jsx';", page_jsx)
        self.assertIn("import HeroBanner from '../components/HeroBanner.jsx';", page_jsx)
        self.assertIn("import FeatureGrid from '../components/FeatureGrid.jsx';", page_jsx)
        self.assertIn("<GridLayout className=\"page-landing\">", page_jsx)
        self.assertIn("<HeroBanner />", page_jsx)
        self.assertIn("<FeatureGrid />", page_jsx)
        self.assertIn("</GridLayout>", page_jsx)

    def test_03_app_router_composition(self):
        """Verify routes.jsx and App.jsx bind routes to page components cleanly."""
        proj = self._create_sample_project()
        output = self.engine.generate_react_project(proj)['project_structure']
        
        routes_jsx = output["src/routes.jsx"]
        self.assertIn("import HomePage from './pages/HomePage.jsx';", routes_jsx)
        self.assertIn("import { Routes, Route } from 'react-router-dom';", routes_jsx)
        self.assertIn("<Route path=\"/\" element={<HomePage />} />", routes_jsx)

        app_jsx = output["src/App.jsx"]
        self.assertIn("import AppRoutes from './routes.jsx';", app_jsx)
        self.assertIn("<AppRoutes />", app_jsx)


if __name__ == '__main__':
    unittest.main()
