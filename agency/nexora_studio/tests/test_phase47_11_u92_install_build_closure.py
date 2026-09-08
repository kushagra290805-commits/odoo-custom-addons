# -*- coding: utf-8 -*-
"""Phase 47.11 (U9.2) — Project Install + Production Build Closure contract locks.

Locks the U9.2 acceptance boundary using EXISTING owners only:
  * nexora.dependency_installer_service  -> install_project / build_project
  * nexora.execution_sandbox_service     -> canonical command boundary + roots
  * ValidationEngine                     -> consumes install/build result
  * nexora.preview_launcher_vite         -> process-tree cleanup on stop

No parallel BuildService/ProjectManager/CommandRunner/dependency-manager is
introduced. PreviewService/Playwright/browser/WebGL/Spline-runtime/final-gate
are NOT touched (they remain U9.3-U9.6).

Real npm/build tests are opt-in via NEXORA_U92_BUILD=1 (executed + reported in
the U9.2 audit); static/contract/failure/cleanup tests always run and are fast.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODOO_ROOT = r'D:\ODOO'
FAIL_ROOT = os.path.join(ODOO_ROOT, '.u92_fail')
BUILD_ROOT = os.path.join(ODOO_ROOT, '.u92_build')
VALID_SPLINE_URL = "https://prod.spline.design/AbCdEf123/scene.splinecode"

import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.generation.engines.validation_engine import ValidationEngine


def _port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.5):
            return True
    except Exception:
        return False


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)


class TestU92SandboxBoundary(unittest.TestCase):
    """F + section 5: managed-workspace command boundary is truthful."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.sandbox = cls.env['nexora.execution_sandbox_service']

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_allowed_roots_include_odoo_managed_and_temp(self):
        roots = self.sandbox._allowed_execution_roots()
        self.assertIn(os.path.abspath(ODOO_ROOT), roots)
        managed = self.env['ir.config_parameter'].sudo().get_param('nexora.workspace_root')
        if managed:
            self.assertIn(os.path.abspath(managed), roots)
        self.assertIn(os.path.abspath(tempfile.gettempdir()), roots)

    def test_generated_workspace_under_managed_root_is_accepted(self):
        managed = self.env['ir.config_parameter'].sudo().get_param('nexora.workspace_root')
        self.assertTrue(managed, 'nexora.workspace_root must be configured')
        probe = os.path.join(managed, 'u92-generated-probe')
        self.assertTrue(self.sandbox.is_within_allowed_roots(probe))

    def test_generated_workspace_under_odoo_root_is_accepted(self):
        self.assertTrue(self.sandbox.is_within_allowed_roots(os.path.join(ODOO_ROOT, '.u92_build', 'react')))

    def test_system_path_is_rejected(self):
        self.assertFalse(self.sandbox.is_within_allowed_roots(r'C:\Windows\System32'))
        self.assertFalse(self.sandbox.is_within_allowed_roots(r'C:\Windows\Temp\evil'))

    def test_install_and_build_reject_out_of_root_workspace(self):
        installer = self.env['nexora.dependency_installer_service']
        res = installer.install_project(r'C:\Windows\Temp\evil')
        self.assertFalse(res['success'])
        self.assertEqual(res['error'], 'workspace_not_allowed')
        res = installer.build_project(r'C:\Windows\Temp\evil')
        self.assertFalse(res['success'])
        self.assertEqual(res['error'], 'workspace_not_allowed')


class TestU92InstallBuildFailures(unittest.TestCase):
    """C/D/E + package.json/build-script failures using crafted workspaces."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.installer = cls.env['nexora.dependency_installer_service']
        if os.path.isdir(FAIL_ROOT):
            shutil.rmtree(FAIL_ROOT, ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(FAIL_ROOT, ignore_errors=True)
        cls.cr.close()

    def test_package_json_missing_fails_clearly(self):
        ws = os.path.join(FAIL_ROOT, 'no_pkg')
        os.makedirs(ws, exist_ok=True)
        res = self.installer.install_project(ws)
        self.assertFalse(res['success'])
        self.assertEqual(res['error'], 'package_json_missing')
        res = self.installer.build_project(ws)
        self.assertFalse(res['success'])
        self.assertEqual(res['error'], 'package_json_missing')

    def test_build_script_missing_fails_clearly(self):
        ws = os.path.join(FAIL_ROOT, 'no_build_script')
        _write(os.path.join(ws, 'package.json'),
               json.dumps({'name': 'no-build', 'version': '1.0.0'}))
        res = self.installer.build_project(ws)
        self.assertFalse(res['success'])
        self.assertEqual(res['error'], 'build_script_missing')

    def test_build_exit_zero_but_missing_dist_fails(self):
        # E: npm exits 0 (script runs) but produces no dist/build output.
        ws = os.path.join(FAIL_ROOT, 'echo_no_dist')
        _write(os.path.join(ws, 'package.json'),
               json.dumps({'name': 'echo-no-dist', 'version': '1.0.0',
                           'scripts': {'build': 'echo built-but-no-output'}}))
        res = self.installer.build_project(ws)
        self.assertFalse(res['success'], 'exit 0 without dist must NOT be success')
        self.assertEqual(res['exit_code'], 0)
        self.assertFalse(res['dist_present'])
        self.assertEqual(res['error'], 'build_output_missing')

    def test_workspace_missing_fails_clearly(self):
        res = self.installer.install_project(os.path.join(FAIL_ROOT, 'does_not_exist'))
        self.assertFalse(res['success'])
        self.assertEqual(res['error'], 'workspace_missing')


class TestU92ValidationEngineSemantics(unittest.TestCase):
    """C/D at the owning stage: install/build failure fails the validation stage."""

    @classmethod
    def setUpClass(cls):
        cls.ws = tempfile.mkdtemp(prefix='nexora-u92-ve-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws, ignore_errors=True)

    def _artifact(self, path):
        return SimpleNamespace(workspace=SimpleNamespace(project_path=path))

    def _runtime(self, installer):
        env = {'nexora.dependency_installer_service': installer}
        return SimpleNamespace(env=env)

    def _run(self, installer, path=None):
        issues = []
        evidence = ValidationEngine._run_build_acceptance(
            None, self._artifact(path or self.ws), self._runtime(installer), issues)
        return evidence, issues

    def test_install_failure_fails_stage(self):
        installer = SimpleNamespace(
            install_project=lambda ws: {'success': False, 'exit_code': 1, 'stderr': 'E404', 'error': 'install_failed'},
            build_project=lambda ws: {'success': True, 'exit_code': 0, 'dist_path': 'x', 'dist_present': True},
        )
        evidence, issues = self._run(installer)
        self.assertTrue(evidence['failed'])
        self.assertFalse(evidence['install']['success'])
        self.assertTrue(any(i['category'] == 'build' for i in issues))

    def test_build_failure_fails_stage(self):
        installer = SimpleNamespace(
            install_project=lambda ws: {'success': True, 'exit_code': 0},
            build_project=lambda ws: {'success': False, 'exit_code': 2, 'stderr': 'vite error',
                                      'error': 'build_failed', 'dist_present': False, 'dist_path': None},
        )
        evidence, issues = self._run(installer)
        self.assertTrue(evidence['failed'])
        self.assertTrue(evidence['install']['success'])
        self.assertFalse(evidence['build']['success'])
        self.assertTrue(any(i['category'] == 'build' for i in issues))

    def test_success_does_not_fail_stage(self):
        installer = SimpleNamespace(
            install_project=lambda ws: {'success': True, 'exit_code': 0},
            build_project=lambda ws: {'success': True, 'exit_code': 0,
                                      'dist_path': os.path.join(self.ws, 'dist'), 'dist_present': True},
        )
        evidence, issues = self._run(installer)
        self.assertFalse(evidence['failed'])
        self.assertEqual([i for i in issues if i['category'] == 'build'], [])

    def test_no_materialized_workspace_is_skipped_not_failed(self):
        installer = SimpleNamespace(
            install_project=lambda ws: {'success': True, 'exit_code': 0},
            build_project=lambda ws: {'success': True, 'exit_code': 0, 'dist_present': True},
        )
        evidence, issues = self._run(installer, path=os.path.join(self.ws, 'no_such_dir'))
        self.assertTrue(evidence['skipped'])
        self.assertFalse(evidence['failed'])
        self.assertEqual(issues, [])


class TestU92ViteProcessCleanup(unittest.TestCase):
    """J/K/L: ViteLauncher kills the full tree, is idempotent, spares unrelated."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.vite = cls.env['nexora.preview_launcher_vite']
        cls._procs = []

    @classmethod
    def tearDownClass(cls):
        for p in cls._procs:
            try:
                p.kill()
            except Exception:
                pass
        cls.cr.close()

    def _spawn(self, code):
        p = subprocess.Popen([sys.executable, '-c', code])
        self._procs.append(p)
        return p

    def test_kill_tree_removes_children(self):
        parent = self._spawn(
            "import subprocess,sys,time;"
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']);"
            "time.sleep(60)")
        time.sleep(1.0)
        import psutil
        try:
            child_pids = [c.pid for c in psutil.Process(parent.pid).children(recursive=True)]
        except Exception:
            child_pids = []
        self.assertGreater(len(child_pids), 0, 'test precondition: parent must have a child')
        self.vite._kill_process_tree(parent.pid)
        time.sleep(0.5)
        self.assertFalse(self.vite._is_process_alive(parent.pid), 'parent survived tree kill')
        for cpid in child_pids:
            self.assertFalse(self.vite._is_process_alive(cpid), f'child {cpid} leaked')

    def test_kill_tree_spares_unrelated_process(self):
        unrelated = self._spawn("import time; time.sleep(30)")
        target = self._spawn("import time; time.sleep(30)")
        time.sleep(0.5)
        self.assertIsNone(unrelated.poll(), 'precondition: unrelated alive')
        self.vite._kill_process_tree(target.pid)
        time.sleep(0.5)
        self.assertIsNone(unrelated.poll(), 'unrelated process must NOT be killed')
        self.assertIsNotNone(target.poll(), 'target should be terminated')

    def test_stop_is_idempotent_and_safe(self):
        rt = SimpleNamespace(process_id=0, allocated_port=0, port=0)
        self.assertTrue(self.vite.stop(rt))
        self.assertTrue(self.vite.stop(rt))
        dead = SimpleNamespace(process_id=999999, allocated_port=0, port=0)
        self.assertTrue(self.vite.stop(dead))


@unittest.skipUnless(os.environ.get('NEXORA_U92_BUILD') == '1',
                     'opt-in real npm build (set NEXORA_U92_BUILD=1)')
class TestU92RealInstallBuild(unittest.TestCase):
    """A/B/G/H/I + real install-failure + managed-root build + vite dev stop."""

    SCENARIOS = [
        ('react', 'Build a modern SaaS landing page with pricing and testimonials.'),
        ('r3f', 'Build an immersive 3d product showcase website with WebGL.'),
        ('spline', 'Build a creative agency website featuring a Spline scene at ' + VALID_SPLINE_URL + ' .'),
    ]

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls._patcher = patch(
            'odoo.addons.nexora_studio.services.ai.provider_manager.AIProviderManager.route_request',
            cls._fake_route_request)
        cls._patcher.start()
        if os.path.isdir(BUILD_ROOT):
            shutil.rmtree(BUILD_ROOT, ignore_errors=True)

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

    def test_01_controlled_scenarios_install_and_build_via_production_path(self):
        service = self.env['nexora.builder_session_service']
        for name, requirements in self.SCENARIOS:
            ws = os.path.join(BUILD_ROOT, name)
            os.makedirs(ws, exist_ok=True)
            self.cr.execute('SAVEPOINT u92_build')
            try:
                cfg = self.env['nexora.builder_configuration'].create({'name': f'U92 {name}'})
                session = self.env['nexora.builder_session'].create({
                    'name': f'U92 {name}', 'builder_configuration_id': cfg.id,
                    'project_name': f'U92 {name}', 'target_workspace_path': ws,
                })
                # Phase 47.13 (U9.4): browser validation now runs after
                # install/build/preview. React/R3F are console-clean and
                # complete; the Spline fake scene URL truthfully fails that
                # LATER stage — install/build evidence below is unaffected.
                raised = None
                try:
                    ok = service.run_generation(session, requirements=requirements)
                except Exception as e:
                    raised = e
                if name == 'spline':
                    self.assertIsNotNone(
                        raised, 'spline: fake scene must fail U9.4 browser validation')
                    self.assertIn('Browser validation failed', str(raised))
                else:
                    self.assertIsNone(raised, f'{name}: {raised}')
                    self.assertTrue(ok, f'{name}: run_generation failed')
                    self.assertEqual(session.status, 'ai_reviewing')
                self.assertTrue(os.path.isfile(os.path.join(ws, 'package-lock.json')),
                                f'{name}: install did not create package-lock.json')
                self.assertTrue(os.path.isdir(os.path.join(ws, 'node_modules')),
                                f'{name}: node_modules missing')
                dist = os.path.join(ws, 'dist')
                self.assertTrue(os.path.isdir(dist), f'{name}: dist missing after build')
                self.assertTrue(os.path.isfile(os.path.join(dist, 'index.html')),
                                f'{name}: dist/index.html missing')
            finally:
                # Phase 47.12 (U9.3): generation now starts a real development
                # preview; stop it via the canonical owner before rollback.
                try:
                    self.env['nexora.preview_service'].stop_workspace_preview(session)
                except Exception:
                    pass
                self.cr.execute('ROLLBACK TO SAVEPOINT u92_build')
                self.cr.execute('RELEASE SAVEPOINT u92_build')

    def test_02_real_install_nonzero_fails(self):
        installer = self.env['nexora.dependency_installer_service']
        ws = os.path.join(BUILD_ROOT, 'bad_dep')
        _write(os.path.join(ws, 'package.json'), json.dumps({
            'name': 'bad-dep', 'version': '1.0.0',
            'dependencies': {'nexora_nonexistent_package_xyz_999': '^1.0.0'}}))
        res = installer.install_project(ws)
        self.assertFalse(res['success'], 'install of impossible dependency must fail')
        self.assertNotEqual(res['exit_code'], 0)

    def test_03_managed_root_workspace_builds(self):
        managed = self.env['ir.config_parameter'].sudo().get_param('nexora.workspace_root')
        self.assertTrue(managed)
        ws = os.path.join(managed, 'u92-managed-probe')
        if os.path.isdir(ws):
            shutil.rmtree(ws, ignore_errors=True)
        os.makedirs(ws, exist_ok=True)
        try:
            _write(os.path.join(ws, 'package.json'), json.dumps({
                'name': 'managed-probe', 'version': '1.0.0',
                'scripts': {'build': 'node -e "const fs=require(\'fs\');fs.mkdirSync(\'dist\',{recursive:true});fs.writeFileSync(\'dist/index.html\',\'ok\')"'}}))
            installer = self.env['nexora.dependency_installer_service']
            inst = installer.install_project(ws)
            self.assertTrue(inst['success'], f'install in managed root failed: {inst.get("stderr")}')
            bld = installer.build_project(ws)
            self.assertTrue(bld['success'], f'build in managed root failed: {bld.get("stderr")}')
            self.assertTrue(bld['dist_present'])
        finally:
            shutil.rmtree(ws, ignore_errors=True)

    def test_04_vite_dev_stop_releases_port_and_kills_tree(self):
        ws = os.path.join(ODOO_ROOT, '.u91_probe', 'react')
        if not os.path.isdir(os.path.join(ws, 'node_modules')):
            self.skipTest('no prebuilt react workspace available')
        vite = self.env['nexora.preview_launcher_vite']
        port = _free_port()
        pid, cmd, url = vite.start(ws, port, None, logs_directory=ws, temp_directory=ws)
        time.sleep(3.0)
        import psutil
        try:
            child_pids = [c.pid for c in psutil.Process(pid).children(recursive=True)]
        except Exception:
            child_pids = []
        rt = SimpleNamespace(process_id=pid, allocated_port=port, port=port)
        vite.stop(rt)
        time.sleep(1.0)
        self.assertFalse(vite._is_process_alive(pid), 'vite parent survived stop')
        for cpid in child_pids:
            self.assertFalse(vite._is_process_alive(cpid), f'vite child {cpid} leaked')
        self.assertFalse(_port_open(port), 'port not released after stop')


class TestU92NoParallelArchitecture(unittest.TestCase):
    """M + N + O: no second build/dep/command architecture; U8 path intact."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_single_install_build_and_sandbox_owners(self):
        models = self.env.registry.models
        self.assertIn('nexora.dependency_installer_service', models)
        self.assertIn('nexora.execution_sandbox_service', models)
        forbidden = [n for n in models if n.startswith('nexora.') and any(
            k in n for k in ('build_service', 'project_manager', 'command_runner',
                             'npm_executor', 'bundler', 'dependency_manager'))]
        self.assertEqual(forbidden, [], f'parallel build/command architecture introduced: {forbidden}')

    def test_installer_keeps_backward_compat_and_adds_project_ops(self):
        installer = self.env['nexora.dependency_installer_service']
        for op in ('install_node', 'install_git', 'install_python', 'install_project', 'build_project'):
            self.assertTrue(callable(getattr(installer, op, None)), f'{op} missing')

    def test_generation_engines_do_not_spawn_npm_or_subprocess(self):
        engines_dir = os.path.join(ADDON, 'services', 'generation', 'engines')
        offenders = []
        for name in os.listdir(engines_dir):
            if not name.endswith('.py'):
                continue
            with open(os.path.join(engines_dir, name), 'r', encoding='utf-8') as fh:
                text = fh.read()
            if re.search(r'\bsubprocess\b', text) or re.search(r"['\"]npm['\"]", text):
                offenders.append(name)
        self.assertEqual(offenders, [], 'generation engines must not spawn npm/subprocess directly')

    def test_validation_engine_scope_unchanged(self):
        with open(os.path.join(ADDON, 'services', 'generation', 'core', 'generation_runtime.py'),
                  'r', encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn("self._registry.register(ValidationEngine, {'env', 'orchestrator'})", src)

    def test_u8_renderer_providers_still_registered(self):
        from odoo.addons.nexora_studio.services.design.providers.provider_registry import (
            RenderingProviderRegistry,
        )
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('webgl'), 'react_three_fiber')
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('spline'), 'spline')
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('none'), 'react')


if __name__ == '__main__':
    unittest.main()
