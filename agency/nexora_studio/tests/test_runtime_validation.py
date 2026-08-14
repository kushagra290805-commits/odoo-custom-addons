# -*- coding: utf-8 -*-
"""
Runtime Build Validation Suite — Phase 12A.1 Stage 2 & 3 Audit.

Verifies:
1. Workspace Manager functionality: managing temporary workspaces in `.tmp_val_workspace/`
   with shared base `node_modules` caching via directory junctions/symlinks.
2. Synthesizing React/Vite project files and executing `npm install` and `npm run build` via subprocess.
3. Asserting 100% build success across all 6 canonical archetypes (`landing`, `saas_dashboard`, `blog`,
   `ecommerce`, `contact`, `auth`).
4. Launching Vite preview server (`npm run preview` on local port) and verifying HTTP 200 response
   and bundled asset loading.
"""
import unittest
import sys
import os
import time
import shutil
import socket
import subprocess
import urllib.request
from typing import Dict, Any, List

# Ensure Odoo and module paths are accessible for standalone test execution
sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

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


class DummySysParam:
    def __init__(self, params=None):
        self.params = params or {}
    def sudo(self):
        return self
    def get_param(self, key):
        return self.params.get(key)


class DummyOdooEnv:
    def __init__(self, params=None):
        self.sysparam = DummySysParam(params or {})
        self.models = {}
        self.models['nexora.design_blueprint_engine'] = DesignBlueprintEngine(self, (), ())
        self.models['nexora.design_system_engine'] = DesignSystemEngine(self, (), ())
        self.models['nexora.layout_engine'] = DesignLayoutEngine(self, (), ())
        self.models['nexora.asset_planning_engine'] = AssetPlanningEngine(self, (), ())
        self.models['nexora.content_intelligence_engine'] = ContentIntelligenceEngine(self, (), ())
        self.models['nexora.design_orchestrator'] = DesignOrchestrator(self, (), ())

    def __getitem__(self, key):
        if key in self.models:
            return self.models[key]
        raise KeyError(key)


class WorkspaceManager:
    """Manages temporary validation workspaces and shared node_modules caching."""
    def __init__(self, base_workspace_dir: str):
        self.base_dir = os.path.abspath(base_workspace_dir)
        self.shared_cache_dir = os.path.join(self.base_dir, "shared_cache")
        self.npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    def ensure_shared_cache(self, base_package_json_content: str) -> float:
        """Ensures shared node_modules cache is initialized and returns time taken in ms."""
        t0 = time.perf_counter()
        os.makedirs(self.shared_cache_dir, exist_ok=True)
        pkg_path = os.path.join(self.shared_cache_dir, "package.json")
        if not os.path.exists(pkg_path) or not os.path.exists(os.path.join(self.shared_cache_dir, "node_modules")):
            with open(pkg_path, "w", encoding="utf-8") as f:
                f.write(base_package_json_content)
            res = subprocess.run(
                [self.npm_cmd, "install", "--no-audit", "--no-fund"],
                cwd=self.shared_cache_dir,
                capture_output=True,
                text=True
            )
            if res.returncode != 0:
                raise RuntimeError(f"Shared cache npm install failed:\n{res.stderr}\n{res.stdout}")
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0

    def prepare_project_workspace(self, project_name: str, project_structure: Dict[str, str]) -> str:
        """Synthesizes project structure into .tmp_val_workspace/{project_name} and links node_modules."""
        proj_dir = os.path.join(self.base_dir, project_name)
        os.makedirs(proj_dir, exist_ok=True)

        for rel_path, content in project_structure.items():
            abs_path = os.path.join(proj_dir, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)

        # Link node_modules from shared cache
        target_modules = os.path.join(proj_dir, "node_modules")
        source_modules = os.path.join(self.shared_cache_dir, "node_modules")
        if not os.path.exists(target_modules):
            if os.name == "nt":
                res = subprocess.run(["cmd", "/c", "mklink", "/J", target_modules, source_modules], cwd=proj_dir, capture_output=True, text=True)
                if res.returncode != 0:
                    raise RuntimeError(f"Failed to create directory junction on Windows: {res.stderr}")
            else:
                os.symlink(source_modules, target_modules, target_is_directory=True)
        return proj_dir


class TestRuntimeValidation(unittest.TestCase):
    """Verifies runtime build success and live server HTTP 200 response across all archetypes."""

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
        cls.install_time_ms = cls.ws_manager.ensure_shared_cache(base_pkg)
        cls.performance_records = {}

    def _get_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            return s.getsockname()[1]

    def _execute_runtime_audit_for_archetype(self, archetype_key: str, req_payload: Dict[str, Any]):
        session = MockBuilderSession(self.env, name=f"Runtime {archetype_key.capitalize()}", project_type=archetype_key)
        
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
        self.assertEqual(react_res["status"], "success")
        struct = react_res["project_structure"]

        # 1. Synthesize project workspace
        t0_prep = time.perf_counter()
        proj_dir = self.ws_manager.prepare_project_workspace(f"val_{archetype_key}", struct)
        t1_prep = time.perf_counter()

        # 2. Execute npm run build
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        t0_build = time.perf_counter()
        build_proc = subprocess.run(
            [npm_cmd, "run", "build"],
            cwd=proj_dir,
            capture_output=True,
            text=True
        )
        t1_build = time.perf_counter()

        self.assertEqual(build_proc.returncode, 0, f"npm run build failed for {archetype_key}:\nSTDOUT:\n{build_proc.stdout}\nSTDERR:\n{build_proc.stderr}")
        
        # Assert build artifacts exist
        dist_dir = os.path.join(proj_dir, "dist")
        self.assertTrue(os.path.exists(os.path.join(dist_dir, "index.html")), f"dist/index.html missing for {archetype_key}")
        self.assertTrue(os.path.exists(os.path.join(dist_dir, "assets")), f"dist/assets missing for {archetype_key}")
        
        assets_files = os.listdir(os.path.join(dist_dir, "assets"))
        self.assertTrue(any(f.endswith(".js") for f in assets_files), f"No bundled .js found in dist/assets for {archetype_key}")
        self.assertTrue(any(f.endswith(".css") for f in assets_files), f"No bundled .css found in dist/assets for {archetype_key}")

        # 3. Verify live Vite preview server HTTP 200 response
        port = self._get_free_port()
        preview_proc = subprocess.Popen(
            [npm_cmd, "run", "preview", "--", "--port", str(port), "--host", "localhost"],
            cwd=proj_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        t0_srv = time.perf_counter()
        http_ok = False
        html_body = ""
        url = f"http://localhost:{port}/"

        try:
            # Poll server startup up to 6 seconds
            for _ in range(30):
                time.sleep(0.2)
                if preview_proc.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(url, timeout=1.5) as response:
                        if response.status == 200:
                            http_ok = True
                            html_body = response.read().decode('utf-8', errors='ignore')
                            break
                except Exception:
                    continue
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

        t1_srv = time.perf_counter()

        self.assertTrue(http_ok, f"Vite preview server failed to respond with HTTP 200 on port {port} for {archetype_key}")
        self.assertIn('<div id="root"></div>', html_body, f"Root mount point missing in HTTP response for {archetype_key}")
        self.assertIn('/assets/', html_body, f"Bundled asset references missing in HTTP response for {archetype_key}")

        # Record metrics
        self.performance_records[archetype_key] = {
            "prep_workspace_ms": (t1_prep - t0_prep) * 1000.0,
            "npm_build_ms": (t1_build - t0_build) * 1000.0,
            "preview_verify_ms": (t1_srv - t0_srv) * 1000.0
        }

    def test_01_landing_runtime(self):
        self._execute_runtime_audit_for_archetype("landing", {"project_type": "landing"})

    def test_02_saas_dashboard_runtime(self):
        self._execute_runtime_audit_for_archetype("saas_dashboard", {"project_type": "saas_dashboard"})

    def test_03_blog_runtime(self):
        self._execute_runtime_audit_for_archetype("blog", {"project_type": "blog"})

    def test_04_ecommerce_runtime(self):
        self._execute_runtime_audit_for_archetype("ecommerce", {"project_type": "ecommerce"})

    def test_05_contact_runtime(self):
        self._execute_runtime_audit_for_archetype("contact", {"project_type": "contact"})

    def test_06_auth_runtime(self):
        self._execute_runtime_audit_for_archetype("auth", {"project_type": "auth"})


if __name__ == "__main__":
    unittest.main()
