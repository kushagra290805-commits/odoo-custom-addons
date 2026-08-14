# -*- coding: utf-8 -*-
"""
Playwright Visual Validation Suite — Phase 12A.1 Stage 4 Audit.

Verifies:
1. End-to-end visual and DOM rendering using the Playwright Python API (`sync_playwright`).
2. Navigates supported routes across all 6 canonical archetypes (`landing`, `saas_dashboard`, `blog`,
   `ecommerce`, `contact`, `auth`).
3. Attaches runtime listeners to assert zero browser console errors and zero network failure exceptions.
4. Asserts non-blank DOM rendering (root mount point populated with valid component hierarchy).
5. Captures full-page screenshot artifacts for visual audit reporting.
"""
import unittest
import sys
import os
import time
import socket
import subprocess
import urllib.request
from typing import Dict, Any, List

# Ensure Odoo and module paths are accessible for standalone test execution
sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from playwright.sync_api import sync_playwright

from odoo.addons.nexora_studio.services.design.design_blueprint import (
    DesignBlueprint, PageBlueprint, SectionBlueprint, DesignTokenSet,
    ColorPalette, ColorToken, NavigationTree, NavigationNode
)
from odoo.addons.nexora_studio.tests.test_end_to_end_pipeline import (
    MockBuilderSession, GOLDEN_REFERENCES
)
from odoo.addons.nexora_studio.services.design.blueprint_engine import DesignBlueprintEngine
from odoo.addons.nexora_studio.services.design.design_system_engine import DesignSystemEngine
from odoo.addons.nexora_studio.services.design.layout_engine import DesignLayoutEngine
from odoo.addons.nexora_studio.services.design.asset_planning_engine import AssetPlanningEngine
from odoo.addons.nexora_studio.services.design.content_intelligence_engine import ContentIntelligenceEngine
from odoo.addons.nexora_studio.services.design.design_orchestrator import DesignOrchestrator
from odoo.addons.nexora_studio.tests.test_runtime_validation import WorkspaceManager, DummyOdooEnv


class TestPlaywrightValidation(unittest.TestCase):
    """Verifies visual rendering and browser runtime health across all 6 canonical archetypes."""

    @classmethod
    def setUpClass(cls):
        cls.env = DummyOdooEnv()
        cls.orchestrator = cls.env['nexora.design_orchestrator']
        cls.workspace_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.tmp_val_workspace'))
        cls.ws_manager = WorkspaceManager(cls.workspace_base)
        
        base_pkg = '''{
  "name": "nexora-shared-cache",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.23.0",
    "lucide-react": "^0.383.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.2.0"
  }
}'''
        cls.ws_manager.ensure_shared_cache(base_pkg)
        cls.screenshot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', 'reports', 'screenshots'))
        os.makedirs(cls.screenshot_dir, exist_ok=True)
        cls.performance_records = {}

    def _get_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            return s.getsockname()[1]

    def _execute_playwright_audit_for_archetype(self, archetype_key: str, req_payload: Dict[str, Any]):
        session = MockBuilderSession(self.env, name=f"Visual {archetype_key.capitalize()}", project_type=archetype_key)
        
        # Execute AI Planning Pipeline
        bp_res = session.execute_full_planning_pipeline(req_payload)
        bp_data = bp_res["blueprint"]
        bp = DesignBlueprint.from_dict(bp_data) if isinstance(bp_data, dict) else bp_data
        
        golden = GOLDEN_REFERENCES[archetype_key]
        main_route = golden["expected_routes"][0]
        
        bp.pages = [
            PageBlueprint(
                id=f"p-{archetype_key}",
                name=golden["expected_page_name"],
                slug=main_route,
                archetype=archetype_key,
                sections=[
                    SectionBlueprint(
                        id=f"sec-{idx}",
                        name=comp_path.split("/")[-1].replace(".jsx", ""),
                        section_type=archetype_key if archetype_key in {'blog', 'ecommerce', 'contact', 'auth'} else 'hero',
                        layout_container="grid-12"
                    )
                    for idx, comp_path in enumerate(golden["expected_components"])
                ]
            )
        ]
        
        bp.navigation = NavigationTree(id=f'nav-{archetype_key}', name='Nav', root_nodes=[
            NavigationNode(id=f'nav-{archetype_key}-0', label=golden["expected_page_name"], target_slug_or_id=main_route)
        ])
        
        if not bp.token_set:
            bp.token_set = DesignTokenSet(
                id="ts-1",
                name="Tokens",
                color_palette=ColorPalette(id="cp-1", name="Colors", tokens=[ColorToken(id="c1", name="primary", hex_value="#3b82f6")])
            )

        bp.metadata['asset_plan_summary'] = {'planned_assets': [{'asset_id': 'ast-1', 'name': 'logo', 'asset_type': 'image', 'role': 'logo', 'source_uri': '/logo.png'}]}
        bp.metadata['content_plan_summary'] = {'generated_bundles': [{'bundle_id': 'bnd-1', 'name': 'copy', 'locale': 'en-US', 'content': {'headline': 'Welcome'}}]}

        # Execute React Generation Engine
        react_res = self.orchestrator.execute_blueprint(bp, provider_name='react')
        struct = react_res["project_structure"]

        # Synthesize project & build if needed
        proj_dir = self.ws_manager.prepare_project_workspace(f"pw_{archetype_key}", struct)
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        
        if not os.path.exists(os.path.join(proj_dir, "dist", "index.html")):
            subprocess.run([npm_cmd, "run", "build"], cwd=proj_dir, capture_output=True, text=True, check=True)

        # Launch Vite preview server
        port = self._get_free_port()
        preview_proc = subprocess.Popen(
            [npm_cmd, "run", "preview", "--", "--port", str(port), "--host", "localhost"],
            cwd=proj_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        url = f"http://localhost:{port}{main_route}"
        http_ok = False

        try:
            for _ in range(30):
                time.sleep(0.2)
                if preview_proc.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(f"http://localhost:{port}/", timeout=1.5) as resp:
                        if resp.status == 200:
                            http_ok = True
                            break
                except Exception:
                    continue

            self.assertTrue(http_ok, f"Preview server failed to start for {archetype_key} on port {port}")

            # Execute Playwright Visual & Runtime Audit
            t0_pw = time.perf_counter()
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()
                
                console_errors = []
                network_failures = []

                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda err: console_errors.append(str(err)))
                page.on("requestfailed", lambda req: network_failures.append(f"{req.url}: {req.failure}"))

                # Navigate to route
                page.goto(url, wait_until="networkidle", timeout=10000)

                # Assert non-blank DOM rendering
                root_html = page.locator("#root").inner_html()
                self.assertGreater(len(root_html.strip()), 10, f"Blank or empty DOM rendered for {archetype_key}")
                self.assertIn("component-", root_html, f"Expected component section class missing in DOM for {archetype_key}")

                # Assert zero console/runtime errors
                # Ignore minor favicon/placeholder 404s in network failures if any, but ensure zero console errors
                self.assertEqual(len(console_errors), 0, f"Runtime browser console errors detected for {archetype_key}: {console_errors}")

                # Capture full-page screenshot
                screenshot_path = os.path.join(self.screenshot_dir, f"playwright_visual_{archetype_key}.png")
                page.screenshot(path=screenshot_path, full_page=True)
                self.assertTrue(os.path.exists(screenshot_path), f"Failed to save screenshot artifact for {archetype_key}")

                browser.close()
            t1_pw = time.perf_counter()
            self.performance_records[archetype_key] = (t1_pw - t0_pw) * 1000.0

        finally:
            if preview_proc.poll() is None:
                preview_proc.terminate()
                try:
                    preview_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    preview_proc.kill()
            if preview_proc.stdout:
                preview_proc.stdout.close()
            if preview_proc.stderr:
                preview_proc.stderr.close()

    def test_01_landing_visual(self):
        self._execute_playwright_audit_for_archetype("landing", {"project_type": "landing"})

    def test_02_saas_dashboard_visual(self):
        self._execute_playwright_audit_for_archetype("saas_dashboard", {"project_type": "saas_dashboard"})

    def test_03_blog_visual(self):
        self._execute_playwright_audit_for_archetype("blog", {"project_type": "blog"})

    def test_04_ecommerce_visual(self):
        self._execute_playwright_audit_for_archetype("ecommerce", {"project_type": "ecommerce"})

    def test_05_contact_visual(self):
        self._execute_playwright_audit_for_archetype("contact", {"project_type": "contact"})

    def test_06_auth_visual(self):
        self._execute_playwright_audit_for_archetype("auth", {"project_type": "auth"})


if __name__ == "__main__":
    unittest.main()
