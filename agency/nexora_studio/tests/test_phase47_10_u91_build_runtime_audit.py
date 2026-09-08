# -*- coding: utf-8 -*-
"""Phase 47.10 (U9.1) — Build/Runtime Acceptance Audit contract locks.

Locks down the acceptance boundary discovered during the U9.1 audit WITHOUT
introducing any parallel build/preview/browser architecture:

  * the canonical dependency-install owner is nexora.dependency_installer_service;
  * no generation engine spawns npm/node/subprocess directly;
  * the generated workspace path is the real managed workspace root;
  * the package.json dependency union is deterministic (no duplicate versions);
  * preview ownership stays with nexora.preview_service (+ launcher plugins);
  * browser ownership stays with nexora.provider.playwright;
  * the deprecated LivePreviewEngine browser path is not used by the pipeline;
  * DB invariants (connectors/sources/credentials/configs/capability registry)
    are unchanged and renderer MCP capabilities remain disabled.

The heavyweight real npm build is opt-in (NEXORA_U91_BUILD=1) so the default
suite stays fast; the audit already captured real build evidence via probes.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.generation.engines.workspace_generator_engine import (
    WorkspaceGeneratorEngine,
)

VALID_SPLINE_URL = "https://prod.spline.design/AbCdEf123/scene.splinecode"


def _src(rel):
    with open(os.path.join(ADDON, rel.replace('/', os.sep)), 'r', encoding='utf-8') as fh:
        return fh.read()


class _FakeWorkspace:
    def __init__(self):
        self.written = {}

    def write_file(self, path, content):
        self.written[path] = content


class _FakeRuntime:
    def __init__(self):
        self.workspace = _FakeWorkspace()


class _FakeArtifact:
    class _Tree:
        def __init__(self, deps):
            self.dependencies = deps

    def __init__(self, deps):
        self.component_tree = self._Tree(deps)


class TestU91StaticContracts(unittest.TestCase):
    def test_dependency_installer_is_canonical_owner(self):
        src = _src('services/dependency_installer_service.py')
        self.assertIn("_name = 'nexora.dependency_installer_service'", src)
        self.assertIn('def install_node', src)
        self.assertIn("'npm', 'install'", src)

    def test_no_npm_or_subprocess_in_generation_engines(self):
        engines_dir = os.path.join(ADDON, 'services', 'generation', 'engines')
        offenders = []
        for name in os.listdir(engines_dir):
            if not name.endswith('.py'):
                continue
            with open(os.path.join(engines_dir, name), 'r', encoding='utf-8') as fh:
                text = fh.read()
            if re.search(r'\bsubprocess\b', text) or re.search(r"['\"]npm['\"]", text):
                offenders.append(name)
        self.assertEqual(offenders, [],
                         'generation engines must not spawn npm/subprocess directly')

    def test_vite_template_build_script_is_vite_build(self):
        pkg = json.loads(_src('assets/frontend-templates/vite-react/package.json'))
        self.assertEqual(pkg['scripts']['build'], 'vite build')

    def test_preview_engine_consumes_preview_service_owner_only(self):
        # Phase 47.12 (U9.3) supersedes the U9.1 gap lock: PreviewEngine now
        # consumes the canonical preview owner after build acceptance. It must
        # go through nexora.preview_service.start_workspace_preview only —
        # never direct launcher/subprocess ownership, never the IDE-layout
        # start_preview() path.
        src = _src('services/generation/engines/preview_engine.py')
        self.assertIn('nexora.preview_service', src)
        self.assertIn('start_workspace_preview', src)
        self.assertNotIn('start_preview(', src)
        self.assertNotIn('preview_launcher_vite', src)
        self.assertNotIn('subprocess', src)

    def test_validation_engine_uses_browser_provider_abstraction_only(self):
        # Phase 47.13 (U9.4) supersedes the U9.1 gap lock: ValidationEngine
        # now consumes the canonical browser owner through the provider
        # abstraction only — never direct Playwright/subprocess/browser
        # process ownership.
        src = _src('services/generation/engines/validation_engine.py')
        self.assertIn('nexora.provider.playwright', src)
        self.assertNotIn('sync_playwright', src)
        self.assertNotIn('import subprocess', src)
        self.assertNotIn('subprocess.', src)
        self.assertNotIn('chromium.launch', src.lower())

    def test_live_preview_engine_not_used_by_pipeline(self):
        for rel in (
            'services/generation/pipeline/website_generation_pipeline.py',
            'services/generation/engines/preview_engine.py',
            'services/generation/engines/validation_engine.py',
            'services/generation/core/generation_runtime.py',
        ):
            self.assertNotIn('live_preview_engine', _src(rel),
                             f'{rel} must not use the deprecated LivePreviewEngine')

    def test_dependency_union_is_deterministic_and_gap_tracked(self):
        template_pkg = {'dependencies': {'react': '^18.2.0'}, 'devDependencies': {'vite': '^5.2.0'}}
        provider_pkg = {'dependencies': {'react': '^18.3.1', 'three': '^0.169.0'}}
        rt = _FakeRuntime()
        artifact = _FakeArtifact(['lodash@^4.17.21', 'unknown-bare-dep'])
        gaps = WorkspaceGeneratorEngine._merge_dependencies(None, rt, template_pkg, provider_pkg, artifact)
        merged = json.loads(rt.workspace.written['package.json'])
        deps = merged['dependencies']
        self.assertEqual(deps['react'], '^18.3.1')
        self.assertEqual(deps['three'], '^0.169.0')
        self.assertEqual(deps['lodash'], '^4.17.21')
        self.assertIn('unknown-bare-dep', gaps)
        self.assertEqual(len(deps), len(set(deps)), 'no duplicate dependency keys')

    def test_workspace_path_is_managed_root(self):
        ws_src = _src('services/generation/engines/workspace_generator_engine.py')
        self.assertIn('str(runtime.workspace.root)', ws_src)
        coord_src = _src('services/generation/core/generation_coordinator.py')
        self.assertIn("getattr(workspace, 'workspace_path', None)", coord_src)


class TestU91OwnershipOdoo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_single_preview_service_and_existing_launchers(self):
        models = self.env.registry.models
        self.assertIn('nexora.preview_service', models)
        launchers = sorted(n for n in models if n.startswith('nexora.preview_launcher'))
        self.assertEqual(launchers, [
            'nexora.preview_launcher',
            'nexora.preview_launcher_python_http',
            'nexora.preview_launcher_static_file',
            'nexora.preview_launcher_vite',
        ])

    def test_single_playwright_provider(self):
        models = self.env.registry.models
        pw = sorted(n for n in models if 'playwright' in n)
        self.assertEqual(pw, ['nexora.provider.playwright'])

    def test_no_second_build_or_dependency_manager(self):
        models = self.env.registry.models
        self.assertIn('nexora.dependency_installer_service', models)
        self.assertIn('nexora.execution_sandbox_service', models)
        second = [n for n in models if n.startswith('nexora.') and (
            'build_service' in n or 'npm' in n or 'bundler' in n)]
        self.assertEqual(second, [])

    def test_db_invariants_and_renderer_mcp_disabled(self):
        env = self.env
        self.assertEqual(len(env['nexora.connector'].search([])), 6)
        # Phase 47.16 added the 7th source (tavily_knowledge: the
        # SEARCH -> KnowledgeDocument -> KnowledgeEnrichmentEngine chain).
        sources = env['nexora.source_registry'].search([])
        self.assertEqual(len(sources), 7)
        self.assertIn('tavily_knowledge', sources.mapped('technical_name'))
        self.assertEqual(len(env['nexora.mcp_credential'].search([])), 5)
        self.assertEqual(len(env['nexora.mcp_server_config'].search([])), 6)
        for c in env['nexora.connector'].search([]):
            self.assertEqual(c.state, 'disabled')
            self.assertFalse(c.enabled)

        penpot = env['nexora.capability_registry'].search(
            [('capability_id', '=', 'mcp.penpot.1.0.0')])
        self.assertEqual(len(penpot), 1)
        self.assertEqual(penpot.implementation_model, 'connector')
        self.assertFalse(penpot.supports_local)
        self.assertFalse(penpot.supports_remote)
        self.assertTrue(penpot.enabled)

        for code in ('mcp.spline', 'mcp.threejs_docs', 'mcp.r3f_docs', 'mcp.drei_docs'):
            cap = env['nexora.capability_registry'].search([('capability_code', '=', code)])
            for row in cap:
                self.assertFalse(row.enabled, f'{code} must remain disabled')


@unittest.skipUnless(os.environ.get('NEXORA_U91_BUILD') == '1',
                     'opt-in real npm build (set NEXORA_U91_BUILD=1)')
class TestU91RealBuild(unittest.TestCase):
    SCENARIOS = [
        ('react', 'Build a modern SaaS landing page with pricing and testimonials.', None),
        ('r3f', 'Build an immersive 3d product showcase website with WebGL.', None),
        ('spline', 'Build a creative agency website featuring a Spline scene at ' + VALID_SPLINE_URL + ' .', None),
    ]

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls._patcher = patch(
            'odoo.addons.nexora_studio.services.ai.provider_manager.AIProviderManager.route_request',
            cls._fake_route_request,
        )
        cls._patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls.cr.close()

    @staticmethod
    def _fake_route_request(self, task_type, prompt, parameters=None, ctx=None):
        if task_type == 'ai_code_patch':
            match = re.search(r'named\s+([A-Za-z0-9_]+)', str(prompt or ''))
            name = match.group(1) if match else 'GeneratedSection'
            return {'full_content': f"function {name}() {{ return <section><h2>{name}</h2></section> }}"}
        return {}

    def _npm(self):
        return shutil.which('npm') or shutil.which('npm.cmd')

    def test_generated_workspaces_build_or_capture_failure(self):
        npm = self._npm()
        if not npm:
            self.skipTest('ENVIRONMENT: npm not available')
        for name, requirements, _ in self.SCENARIOS:
            ws = tempfile.mkdtemp(prefix=f'nexora-u91-{name}-', dir=r'D:\ODOO')
            session = None
            self.cr.execute('SAVEPOINT u91_build')
            try:
                cfg = self.env['nexora.builder_configuration'].create({'name': f'U91 build {name}'})
                session = self.env['nexora.builder_session'].create({
                    'name': f'U91 build {name}',
                    'builder_configuration_id': cfg.id,
                    'project_name': f'U91 {name}',
                    'target_workspace_path': ws,
                })
                # Phase 47.13 (U9.4): browser validation now runs after
                # install/build/preview. React/R3F are console-clean; the
                # Spline fake scene URL truthfully fails that LATER stage.
                # Install/build evidence below is unaffected.
                raised = None
                try:
                    ok = self.env['nexora.builder_session_service'].run_generation(session, requirements=requirements)
                except Exception as e:
                    raised = e
                if name == 'spline':
                    self.assertIsNotNone(
                        raised, 'spline: fake scene must fail U9.4 browser validation')
                    self.assertIn('Browser validation failed', str(raised))
                else:
                    self.assertIsNone(raised, f'{name}: {raised}')
                    self.assertTrue(ok, f'{name}: run_generation failed')

                inst = subprocess.run([npm, 'install', '--no-audit', '--no-fund'], cwd=ws,
                                      capture_output=True, text=True, timeout=600)
                build = subprocess.run([npm, 'run', 'build'], cwd=ws,
                                       capture_output=True, text=True, timeout=300)
                self.assertEqual(inst.returncode, 0,
                                 f'{name}: npm install failed\n{inst.stderr[-2000:]}')
                self.assertEqual(build.returncode, 0,
                                 f'{name}: npm run build failed\n{build.stderr[-2000:]}')
                self.assertTrue(os.path.isdir(os.path.join(ws, 'dist')),
                                f'{name}: dist/ not produced')
            finally:
                # Phase 47.12 (U9.3): generation now starts a real development
                # preview; stop it via the canonical owner before rollback.
                try:
                    if session is not None:
                        self.env['nexora.preview_service'].stop_workspace_preview(session)
                except Exception:
                    pass
                self.cr.execute('ROLLBACK TO SAVEPOINT u91_build')
                self.cr.execute('RELEASE SAVEPOINT u91_build')
                shutil.rmtree(ws, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
