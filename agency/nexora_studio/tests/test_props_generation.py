# -*- coding: utf-8 -*-
"""
Props Intelligence and Variant Handling Suite — Phase 12B Task 4 Audit.

Verifies:
1. Prop bindings and default fallbacks in section synthesizers.
2. Variant adaptation across atomic, molecular, and organism components.
3. Clean prop forwarding ({...props}) and data object mappings.
"""
import unittest
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.render_domain import RenderProject, RenderPage, RenderComponent
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider


class TestPropsGeneration(unittest.TestCase):

    def setUp(self):
        self.engine = ReactRenderingProvider()

    def _create_sample_project(self, components) -> RenderProject:
        page = RenderPage(
            id="page-1",
            name="Landing Page",
            path="/",
            archetype="landing",
            sections=components,
            metadata={"title": "Test SEO Title"}
        )
        return RenderProject(
            id="proj-props-test",
            name="Props Test Project",
            project_type="web_app",
            pages=[page],
            tokens=[]
        )

    def test_01_hero_props_and_variant(self):
        hero_comp = RenderComponent(
            id="comp-hero-1",
            name="Hero Section",
            category="hero",
            variant="split",
            props_schema={"title": "Custom Title", "badge": "New Release"}
        )
        proj = self._create_sample_project([hero_comp])
        output = self.engine.generate_react_project(proj)['project_structure']
        
        hero_jsx_path = "src/components/HeroSection.jsx"
        self.assertIn(hero_jsx_path, output)
        code = output[hero_jsx_path]
        
        self.assertIn("import { Hero } from './index.js';", code)
        self.assertIn("title={secData.title || props.title || \"Hero Section\"}", code)
        self.assertIn("variant={props.variant || \"split\"}", code)
        self.assertIn("{...props}", code)

    def test_02_navbar_props_and_navigation_fallback(self):
        nav_comp = RenderComponent(
            id="comp-nav-1",
            name="Navbar Header",
            category="navbar",
            variant="transparent",
            props_schema={"logo": "Nexora"}
        )
        proj = self._create_sample_project([nav_comp])
        output = self.engine.generate_react_project(proj)['project_structure']
        
        nav_jsx_path = "src/components/NavbarHeader.jsx"
        self.assertIn(nav_jsx_path, output)
        code = output[nav_jsx_path]
        
        self.assertIn("import { Navbar } from './index.js';", code)
        self.assertIn("logo={navData.logo || props.logo || \"BrandLogo\"}", code)
        self.assertIn("navigation={navItems}", code)
        self.assertIn("variant={props.variant || \"transparent\"}", code)

    def test_03_table_props_and_pagination(self):
        table_comp = RenderComponent(
            id="comp-table-1",
            name="User Grid",
            category="table",
            variant="striped",
            props_schema={"pageSize": 15}
        )
        proj = self._create_sample_project([table_comp])
        output = self.engine.generate_react_project(proj)['project_structure']
        
        table_jsx_path = "src/components/UserGrid.jsx"
        self.assertIn(table_jsx_path, output)
        code = output[table_jsx_path]
        
        self.assertIn("import { Table } from './index.js';", code)
        self.assertIn("columns={columns}", code)
        self.assertIn("data={data}", code)
        self.assertIn("pagination={{ pageSize: 10 }}", code)
        self.assertIn("{...props}", code)

    def test_04_variant_fallback_behavior(self):
        comp = RenderComponent(
            id="comp-hero-default",
            name="Hero Default",
            category="hero",
            variant="",
            props_schema={}
        )
        proj = self._create_sample_project([comp])
        output = self.engine.generate_react_project(proj)['project_structure']
        code = output["src/components/HeroDefault.jsx"]
        self.assertIn("variant={props.variant || \"centered\"}", code)


if __name__ == '__main__':
    unittest.main()
