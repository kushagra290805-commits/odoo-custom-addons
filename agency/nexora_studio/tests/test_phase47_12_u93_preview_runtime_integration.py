# -*- coding: utf-8 -*-
"""Phase 47.12 (U9.3) — Preview Runtime Integration Closure contract locks.

Locks the U9.3 acceptance boundary using EXISTING owners only:
  * nexora.preview_service        -> start_workspace_preview / stop_workspace_preview
                                     (detect_launcher, allocate_port, launcher
                                     dispatch, check_health, stop_preview reused)
  * nexora.preview_launcher_vite  -> Vite dev server implementation (U9.2
                                     process-tree stop reused)
  * PreviewEngine                 -> consumes the preview result after build
                                     acceptance; existing base64 artifact
                                     behavior preserved
  * nexora.execution_sandbox_service -> managed-workspace boundary (U9.2 reuse)

No PreviewRuntime/PreviewManager/PreviewOrchestrator/second launcher registry/
second port manager/second health service is introduced. Playwright/browser/
console/network/WebGL/Spline-runtime/final-gate are NOT touched (U9.4-U9.6).

Real Vite preview tests always run for the lifecycle class (fast, reuse of the
existing Vite template + U9.2 install owner). Full production-path controlled
scenarios (React/R3F/Spline via run_generation) are opt-in via
NEXORA_U93_PREVIEW=1 and were executed + reported in the U9.3 audit.
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
import urllib.request
from types import SimpleNamespace
from unittest.mock import patch

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODOO_ROOT = r'D:\ODOO'
LIFECYCLE_ROOT = os.path.join(ODOO_ROOT, '.u93_preview')
TEMPLATE_DIR = os.path.join(ADDON, 'assets', 'frontend-templates', 'vite-react')
VALID_SPLINE_URL = "https://prod.spline.design/AbCdEf123/scene.splinecode"

import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.generation.engines.preview_engine import PreviewEngine


def _port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.5):
            return True
    except Exception:
        return False


def _http_ok(url):
    try:
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            return resp.status
    except Exception:
        return None


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)


class TestU93PreviewOwnership(unittest.TestCase):
    """A + S + T + F(ordering): PreviewService is the single preview owner."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_preview_service_is_the_preview_owner(self):
        service = self.env['nexora.preview_service']
        for op in ('detect_launcher', 'resolve_launcher', 'allocate_port',
                   'start_preview', 'stop_preview', 'check_health',
                   'start_workspace_preview', 'stop_workspace_preview'):
            self.assertTrue(callable(getattr(service, op, None)), f'{op} missing')

    def test_no_parallel_preview_architecture(self):
        models = self.env.registry.models
        forbidden = [n for n in models if n.startswith('nexora.') and any(
            k in n for k in ('preview_manager', 'preview_orchestrator',
                             'preview_controller', 'preview_runtime_service',
                             'preview_health', 'port_manager', 'port_allocator',
                             'launcher_registry', 'process_manager',
                             'build_service', 'project_manager',
                             'command_runner', 'npm_executor'))]
        self.assertEqual(forbidden, [], f'parallel preview architecture: {forbidden}')
        # exactly one preview service and one launcher base
        self.assertIn('nexora.preview_service', models)
        self.assertIn('nexora.preview_launcher', models)
        self.assertIn('nexora.preview_runtime', models)

    def test_generation_engines_do_not_own_launchers_or_subprocess(self):
        engines_dir = os.path.join(ADDON, 'services', 'generation', 'engines')
        offenders = []
        for name in os.listdir(engines_dir):
            if not name.endswith('.py'):
                continue
            with open(os.path.join(engines_dir, name), 'r', encoding='utf-8') as fh:
                text = fh.read()
            if ('subprocess' in text or 'Popen' in text
                    or 'preview_launcher_vite' in text
                    or 'preview_launcher_python_http' in text
                    or 'preview_launcher_static_file' in text):
                offenders.append(name)
        self.assertEqual(offenders, [],
                         'generation engines must not own launcher/subprocess directly')

    def test_preview_engine_scope_grants_env_only(self):
        with open(os.path.join(ADDON, 'services', 'generation', 'core',
                               'generation_runtime.py'), 'r', encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn("self._registry.register(PreviewEngine, {'env'})", src)

    def test_build_before_preview_pipeline_ordering(self):
        with open(os.path.join(ADDON, 'services', 'generation', 'pipeline',
                               'website_generation_pipeline.py'), 'r', encoding='utf-8') as fh:
            src = fh.read()
        # ValidationEngine (install+build acceptance, U9.2) runs before PreviewEngine.
        self.assertIn('GenerationState.REVIEW_COMPLETED: (ValidationEngine(orchestrator), GenerationState.VALIDATION_COMPLETED)', src)
        self.assertIn('GenerationState.VALIDATION_COMPLETED: (PreviewEngine(orchestrator), GenerationState.PREVIEW_READY)', src)
        # A failed engine (e.g. failed build acceptance) aborts the pipeline.
        self.assertIn('raise ValueError(f"Engine execution failed: {result.error}")', src)

    def test_build_acceptance_evidence_contract(self):
        # The validation stage records truthful build-acceptance evidence in the
        # existing ValidationReport contract; the preview stage gates on it.
        with open(os.path.join(ADDON, 'services', 'generation', 'core',
                               'generation_context.py'), 'r', encoding='utf-8') as fh:
            ctx_src = fh.read()
        self.assertIn('build_acceptance: Dict[str, Any] = field(default_factory=dict)', ctx_src)
        with open(os.path.join(ADDON, 'services', 'generation', 'engines',
                               'validation_engine.py'), 'r', encoding='utf-8') as fh:
            val_src = fh.read()
        self.assertIn('build_acceptance=build_evidence', val_src)
        with open(os.path.join(ADDON, 'services', 'generation', 'engines',
                               'preview_engine.py'), 'r', encoding='utf-8') as fh:
            prev_src = fh.read()
        self.assertIn('build_acceptance = getattr(validation, "build_acceptance", None) or {}', prev_src)


class TestU93BuildBeforePreviewGuard(unittest.TestCase):
    """E/F/G/H at the engine: metadata propagation + never preview before
    build acceptance. No real processes; preview service is a spy."""

    @classmethod
    def setUpClass(cls):
        cls.ws = tempfile.mkdtemp(prefix='nexora-u93-guard-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws, ignore_errors=True)

    def _artifact(self, build_acceptance, path=None):
        return SimpleNamespace(
            validation=SimpleNamespace(build_acceptance=build_acceptance),
            workspace=SimpleNamespace(project_path=path or self.ws),
        )

    def _runtime(self, service, session_id='123'):
        session = SimpleNamespace(exists=lambda: True)
        env = {
            'nexora.preview_service': service,
            'nexora.builder_session': SimpleNamespace(browse=lambda i: session),
        }
        return SimpleNamespace(env=env, metadata=SimpleNamespace(session_id=session_id))

    def _run(self, service, artifact, runtime):
        return PreviewEngine._run_preview_runtime(None, artifact, runtime)

    def test_build_acceptance_failed_never_starts_preview(self):
        calls = []
        service = SimpleNamespace(start_workspace_preview=lambda s, w: calls.append((s, w)) or {'status': 'healthy'})
        evidence = self._run(service, self._artifact({'ran': True, 'failed': True}), self._runtime(service))
        self.assertTrue(evidence['skipped'])
        self.assertEqual(evidence['skip_reason'], 'build_acceptance_failed')
        self.assertFalse(evidence['ran'])
        self.assertEqual(calls, [], 'preview must NOT start when build acceptance failed')

    def test_build_acceptance_not_ran_never_starts_preview(self):
        calls = []
        service = SimpleNamespace(start_workspace_preview=lambda s, w: calls.append((s, w)) or {'status': 'healthy'})
        evidence = self._run(service, self._artifact({}), self._runtime(service))
        self.assertTrue(evidence['skipped'])
        self.assertEqual(evidence['skip_reason'], 'build_acceptance_not_ran')
        self.assertEqual(calls, [])

    def test_build_acceptance_skipped_skips_preview(self):
        service = SimpleNamespace(start_workspace_preview=lambda s, w: {'status': 'healthy'})
        evidence = self._run(service, self._artifact({'ran': False, 'skipped': True}), self._runtime(service))
        self.assertTrue(evidence['skipped'])
        self.assertEqual(evidence['skip_reason'], 'build_acceptance_skipped')

    def test_unrelated_validation_issues_do_not_block_preview(self):
        # Build acceptance ran+passed; an unrelated dynamic-validation issue
        # must not prevent the preview (stage-level truth lives in
        # build_acceptance, not in overall issue cleanliness).
        result = {'status': 'healthy', 'launcher': 'vite', 'workspace': self.ws,
                  'host': '127.0.0.1', 'port': 3005, 'url': 'http://127.0.0.1:3005',
                  'pid': 1, 'health': 'healthy', 'diagnostics': None, 'error': None}
        service = SimpleNamespace(start_workspace_preview=lambda s, w: result)
        evidence = self._run(service, self._artifact({'ran': True, 'failed': False}), self._runtime(service))
        self.assertTrue(evidence['ran'])
        self.assertFalse(evidence['skipped'])
        self.assertFalse(evidence['failed'])

    def test_no_materialized_workspace_skips(self):
        service = SimpleNamespace(start_workspace_preview=lambda s, w: {'status': 'healthy'})
        evidence = self._run(service, self._artifact({'ran': True, 'failed': False},
                                                     path=os.path.join(self.ws, 'missing')),
                             self._runtime(service))
        self.assertTrue(evidence['skipped'])
        self.assertEqual(evidence['skip_reason'], 'no_materialized_workspace')

    def test_no_env_skips_mock_pipelines(self):
        service = SimpleNamespace(start_workspace_preview=lambda s, w: {'status': 'healthy'})
        runtime = SimpleNamespace(metadata=SimpleNamespace(session_id='123'))
        evidence = self._run(service, self._artifact({'ran': True, 'failed': False}), runtime)
        self.assertTrue(evidence['skipped'])
        self.assertEqual(evidence['skip_reason'], 'no_odoo_env')

    def test_non_numeric_session_skips(self):
        service = SimpleNamespace(start_workspace_preview=lambda s, w: {'status': 'healthy'})
        evidence = self._run(service, self._artifact({'ran': True, 'failed': False}),
                             self._runtime(service, session_id='mock-session'))
        self.assertTrue(evidence['skipped'])
        self.assertEqual(evidence['skip_reason'], 'no_session')

    def test_success_propagates_preview_metadata(self):
        result = {'status': 'healthy', 'launcher': 'vite', 'workspace': self.ws,
                  'host': '127.0.0.1', 'port': 3005, 'url': 'http://127.0.0.1:3005',
                  'pid': 4242, 'health': 'healthy', 'diagnostics': None, 'error': None}
        seen = {}
        service = SimpleNamespace(
            start_workspace_preview=lambda s, w: seen.update(session=s, ws=w) or result)
        evidence = self._run(service, self._artifact({'ran': True, 'failed': False}), self._runtime(service))
        self.assertTrue(evidence['ran'])
        self.assertFalse(evidence['failed'])
        self.assertEqual(evidence['preview_status'], 'healthy')
        self.assertEqual(evidence['preview_launcher'], 'vite')
        self.assertEqual(evidence['preview_url'], 'http://127.0.0.1:3005')
        self.assertEqual(evidence['preview_host'], '127.0.0.1')
        self.assertEqual(evidence['preview_port'], 3005)
        self.assertEqual(evidence['preview_pid'], 4242)
        self.assertEqual(evidence['preview_health'], 'healthy')
        self.assertEqual(seen['ws'], self.ws)

    def test_preview_failure_fails_the_stage(self):
        result = {'status': 'failed', 'launcher': 'vite', 'workspace': self.ws,
                  'host': '127.0.0.1', 'port': None, 'url': None, 'pid': None,
                  'health': None, 'diagnostics': 'boom', 'error': 'startup_timeout'}
        service = SimpleNamespace(start_workspace_preview=lambda s, w: result)
        evidence = self._run(service, self._artifact({'ran': True, 'failed': False}), self._runtime(service))
        self.assertTrue(evidence['ran'])
        self.assertTrue(evidence['failed'])
        self.assertIn('startup_timeout', evidence['error'])


class TestU93DetectionAndWorkspaceContract(unittest.TestCase):
    """B + R: existing detection selects Vite for all U8 scenarios; managed
    workspace boundary enforced."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.service = cls.env['nexora.preview_service']
        # Run the once-per-worker recovery sweep BEFORE any controlled
        # occupant processes exist (the sweep is pre-existing behavior).
        cls.service._ensure_initialized()

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def _detect(self, ws):
        launcher = self.service.detect_launcher(ws)
        manifest = launcher.launcher_manifest()
        return manifest.get('launcher_id') or manifest.get('launcher_type')

    def test_vite_detected_for_generated_workspaces(self):
        scenarios = {
            'react': os.path.join(ODOO_ROOT, '.u92_build', 'react'),
            'r3f': os.path.join(ODOO_ROOT, '.u92_build', 'r3f'),
            'spline': os.path.join(ODOO_ROOT, '.u92_build', 'spline'),
        }
        checked = 0
        for name, ws in scenarios.items():
            if not os.path.isfile(os.path.join(ws, 'package.json')):
                continue
            self.assertEqual(self._detect(ws), 'vite', f'{name} must detect as vite')
            checked += 1
        if checked == 0:
            # Fallback fixture: minimal vite workspace under the Odoo root.
            ws = os.path.join(ODOO_ROOT, '.u93_detect')
            _write(os.path.join(ws, 'package.json'),
                   json.dumps({'name': 'detect-probe', 'version': '1.0.0',
                               'scripts': {'dev': 'vite', 'build': 'vite build'},
                               'devDependencies': {'vite': '^5.2.0'}}))
            _write(os.path.join(ws, 'vite.config.js'), 'export default {}\n')
            try:
                self.assertEqual(self._detect(ws), 'vite')
            finally:
                shutil.rmtree(ws, ignore_errors=True)

    def test_out_of_root_workspace_rejected_without_process(self):
        self.cr.execute('SAVEPOINT u93_reject')
        try:
            cfg = self.env['nexora.builder_configuration'].create({'name': 'U93 reject'})
            session = self.env['nexora.builder_session'].create({
                'name': 'U93 reject', 'builder_configuration_id': cfg.id,
                'project_name': 'U93 reject',
            })
            res = self.service.start_workspace_preview(session, r'C:\Windows\Temp\evil')
            self.assertEqual(res['status'], 'failed')
            self.assertEqual(res['error'], 'workspace_not_allowed')
            self.assertIsNone(res['pid'])
            res = self.service.start_workspace_preview(session, os.path.join(ODOO_ROOT, '.u93_missing_ws'))
            self.assertEqual(res['error'], 'workspace_missing')
        finally:
            self.cr.execute('ROLLBACK TO SAVEPOINT u93_reject')
            self.cr.execute('RELEASE SAVEPOINT u93_reject')


class TestU93RealPreviewLifecycle(unittest.TestCase):
    """C/D/I/J/K/L/M/N + failure semantics with REAL Vite processes."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.service = cls.env['nexora.preview_service']
        # Run the once-per-worker recovery sweep before any controlled
        # occupant/unrelated processes are spawned by these tests.
        cls.service._ensure_initialized()
        cls._occupants = []
        cls._unrelated = []
        if os.path.isdir(LIFECYCLE_ROOT):
            shutil.rmtree(LIFECYCLE_ROOT, ignore_errors=True)
        # Main workspace: real Vite project from the existing template,
        # installed through the canonical U9.2 install owner.
        cls.main_ws = os.path.join(LIFECYCLE_ROOT, 'main')
        shutil.copytree(TEMPLATE_DIR, cls.main_ws)
        installer = cls.env['nexora.dependency_installer_service']
        inst = installer.install_project(cls.main_ws)
        if not inst.get('success'):
            raise unittest.SkipTest(f'npm install unavailable for lifecycle tests: {inst.get("stderr")}')

    @classmethod
    def tearDownClass(cls):
        try:
            cls.service.stop_workspace_preview(cls.session)
        except Exception:
            pass
        for s in cls._occupants:
            try:
                s.close()
            except Exception:
                pass
        for p in cls._unrelated:
            try:
                p.kill()
                p.wait(timeout=3)
            except Exception:
                pass
        shutil.rmtree(LIFECYCLE_ROOT, ignore_errors=True)
        cls.cr.close()

    def setUp(self):
        self.cfg = self.env['nexora.builder_configuration'].create({'name': 'U93 lifecycle'})
        self.session = self.env['nexora.builder_session'].create({
            'name': 'U93 lifecycle', 'builder_configuration_id': self.cfg.id,
            'project_name': 'U93 lifecycle',
        })
        self.cr.execute('SAVEPOINT u93_lifecycle')

    def tearDown(self):
        try:
            self.service.stop_workspace_preview(self.session)
        except Exception:
            pass
        self.cr.execute('ROLLBACK TO SAVEPOINT u93_lifecycle')
        self.cr.execute('RELEASE SAVEPOINT u93_lifecycle')

    def test_01_successful_start_health_stop(self):
        res = self.service.start_workspace_preview(self.session, self.main_ws)
        self.assertEqual(res['status'], 'healthy', f"startup failed: {res.get('error')} {res.get('diagnostics')}")
        self.assertEqual(res['launcher'], 'vite')
        self.assertEqual(res['workspace'], self.main_ws)
        self.assertEqual(res['host'], '127.0.0.1')
        self.assertTrue(res['port'] and res['port'] >= 3000)
        self.assertTrue(res['url'].startswith(f"http://127.0.0.1:{res['port']}"))
        self.assertTrue(res['pid'] and res['pid'] > 0)
        self.assertEqual(res['health'], 'healthy')
        # Truthful HTTP health (the only runtime acceptance in U9.3).
        self.assertEqual(_http_ok(res['url']), 200)
        # Canonical check_health through the existing owner.
        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', self.session.id),
            ('runtime_type', '=', 'preview')], limit=1)
        self.assertTrue(runtime)
        self.assertEqual(self.service.check_health(runtime), 'healthy')
        self.assertEqual(runtime.status, 'running')
        preview_rt = self.env['nexora.preview_runtime'].search(
            [('runtime_id', '=', runtime.id)], limit=1)
        self.assertEqual(preview_rt.launcher_type, 'vite')
        self.assertEqual(preview_rt.allocated_port, res['port'])
        self.assertEqual(preview_rt.preview_url, res['url'])
        # Stop: tree gone, port released.
        pid, port = res['pid'], res['port']
        stop = self.service.stop_workspace_preview(self.session)
        self.assertTrue(stop['stopped'])
        time.sleep(0.5)
        self.assertFalse(self.env['nexora.preview_launcher_vite']._is_process_alive(pid))
        self.assertFalse(_port_open(port), 'port must be released after stop')

    def test_02_idempotent_stop_and_no_runtime_stop(self):
        self.assertEqual(self.service.stop_workspace_preview(self.session)['stopped'], False)
        res = self.service.start_workspace_preview(self.session, self.main_ws)
        self.assertEqual(res['status'], 'healthy')
        self.assertTrue(self.service.stop_workspace_preview(self.session)['stopped'])
        self.assertTrue(self.service.stop_workspace_preview(self.session)['stopped'])

    def test_03_reuse_running_preview_is_idempotent(self):
        first = self.service.start_workspace_preview(self.session, self.main_ws)
        self.assertEqual(first['status'], 'healthy')
        second = self.service.start_workspace_preview(self.session, self.main_ws)
        self.assertEqual(second['status'], 'healthy')
        self.assertEqual(second['pid'], first['pid'], 'must reuse the running preview, not double-start')
        self.assertEqual(second['port'], first['port'])

    def test_04_startup_failure_process_exits_cleans_up(self):
        ws = os.path.join(LIFECYCLE_ROOT, 'fail_fast')
        _write(os.path.join(ws, 'fail.js'), 'process.exit(1);\n')
        _write(os.path.join(ws, 'package.json'), json.dumps({
            'name': 'fail-fast', 'version': '1.0.0',
            'scripts': {'dev': 'node fail.js', 'build': 'vite build'},
            'devDependencies': {'vite': '^5.2.0'}}))
        _write(os.path.join(ws, 'vite.config.js'), 'export default {}\n')
        res = self.service.start_workspace_preview(self.session, ws, startup_timeout=15.0)
        self.assertEqual(res['status'], 'failed')
        self.assertIn(res['error'], ('process_exited', 'startup_timeout'))
        self.assertIsNone(res['pid'])
        self.assertIsNone(res['url'])
        self.assertTrue(res['diagnostics'], 'diagnostics must be preserved on failure')
        # No leaked listener on any port we owned.
        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', self.session.id),
            ('runtime_type', '=', 'preview')], limit=1)
        self.assertEqual(runtime.status, 'error')

    def test_05_launcher_unavailable_fails(self):
        # Workspace IS detected as Vite (package.json + vite.config.js), but the
        # launcher's dependency probe finds no node/npm -> real validate() fails
        # -> truthful launcher_unavailable, never a success, never a process.
        ws = os.path.join(LIFECYCLE_ROOT, 'no_node')
        _write(os.path.join(ws, 'package.json'), json.dumps({
            'name': 'no-node', 'version': '1.0.0',
            'scripts': {'dev': 'vite', 'build': 'vite build'},
            'devDependencies': {'vite': '^5.2.0'}}))
        _write(os.path.join(ws, 'vite.config.js'), 'export default {}\n')
        from unittest.mock import patch as _patch
        with _patch('odoo.addons.nexora_studio.services.launchers.vite_launcher.shutil.which',
                    return_value=None):
            res = self.service.start_workspace_preview(self.session, ws)
        self.assertEqual(res['status'], 'failed')
        self.assertEqual(res['error'], 'launcher_unavailable')
        self.assertIsNone(res['pid'])
        self.assertTrue(res['diagnostics'], 'diagnostics must be preserved')

    def test_06_startup_timeout_cleans_up_tree(self):
        # Process stays alive but never serves HTTP -> startup timeout, then
        # the owned tree (npm parent + node child) must be cleaned up.
        ws = os.path.join(LIFECYCLE_ROOT, 'never_serves')
        _write(os.path.join(ws, 'hang.js'), 'setInterval(function () {}, 1000);\n')
        _write(os.path.join(ws, 'package.json'), json.dumps({
            'name': 'never-serves', 'version': '1.0.0',
            'scripts': {'dev': 'node hang.js', 'build': 'vite build'},
            'devDependencies': {'vite': '^5.2.0'}}))
        _write(os.path.join(ws, 'vite.config.js'), 'export default {}\n')
        res = self.service.start_workspace_preview(self.session, ws, startup_timeout=5.0)
        self.assertEqual(res['status'], 'failed')
        self.assertEqual(res['error'], 'startup_timeout')
        self.assertIsNone(res['pid'], 'failed startup must not report a live pid')
        self.assertTrue(res['diagnostics'], 'diagnostics must be preserved on timeout')

    def test_07_health_failure_after_start_cleans_up(self):
        res = self.service.start_workspace_preview(self.session, self.main_ws)
        self.assertEqual(res['status'], 'healthy')
        vite = self.env['nexora.preview_launcher_vite']
        # Simulate a crash of the owned tree outside the service.
        vite._kill_process_tree(res['pid'])
        time.sleep(0.5)
        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', self.session.id),
            ('runtime_type', '=', 'preview')], limit=1)
        self.assertEqual(self.service.check_health(runtime), 'critical')
        stop = self.service.stop_workspace_preview(self.session)
        self.assertTrue(stop['stopped'])
        self.assertFalse(_port_open(res['port']))

    def test_08_occupied_port_selects_alternate_and_spares_occupant(self):
        # The port the existing allocator would hand out is occupied by an
        # unrelated listener: preview must take the next valid port and must
        # never kill the occupant.
        candidate = self.service.allocate_port()
        occupant = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupant.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupant.bind(('127.0.0.1', candidate))
        occupant.listen(1)
        self._occupants.append(occupant)

        res = self.service.start_workspace_preview(self.session, self.main_ws)
        try:
            self.assertEqual(res['status'], 'healthy', f"startup failed: {res.get('error')}")
            self.assertNotEqual(res['port'], candidate,
                                'alternate port must be selected when preferred port is occupied')
            self.assertTrue(res['port'] >= 3000)
            self.assertEqual(_http_ok(res['url']), 200)
        finally:
            self.service.stop_workspace_preview(self.session)
        # The occupant still owns its port: it was never killed, and the
        # occupied port still accepts connections after the preview lifecycle.
        self.assertTrue(_port_open(candidate),
                        'occupied port must remain owned by the unrelated occupant')

    def test_09_unrelated_process_survives_preview_lifecycle(self):
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self._unrelated.append(unrelated)
        time.sleep(0.5)
        self.assertIsNone(unrelated.poll(), 'precondition: unrelated process alive')
        res = self.service.start_workspace_preview(self.session, self.main_ws)
        self.assertEqual(res['status'], 'healthy')
        self.service.stop_workspace_preview(self.session)
        time.sleep(0.5)
        self.assertIsNone(unrelated.poll(), 'unrelated process must NOT be terminated')
        self.assertFalse(_port_open(res['port']))


@unittest.skipUnless(os.environ.get('NEXORA_U93_PREVIEW') == '1',
                     'opt-in full production-path preview (set NEXORA_U93_PREVIEW=1)')
class TestU93ControlledScenarios(unittest.TestCase):
    """O/P/Q: React, R3F, Spline through the real production path:
    generate -> install -> build -> preview -> health, then clean stop."""

    SCENARIOS = [
        ('react', 'Build a modern SaaS landing page with pricing and testimonials.', None),
        ('r3f', 'Build an immersive 3d product showcase website with WebGL.', 'src/scene/Scene.jsx'),
        ('spline', 'Build a creative agency website featuring a Spline scene at ' + VALID_SPLINE_URL + ' .', 'src/components/SplineScene.jsx'),
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
        cls.env['nexora.preview_service']._ensure_initialized()
        if os.path.isdir(LIFECYCLE_ROOT):
            shutil.rmtree(LIFECYCLE_ROOT, ignore_errors=True)

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

    def test_controlled_scenarios_preview_via_production_path(self):
        service = self.env['nexora.builder_session_service']
        preview_service = self.env['nexora.preview_service']
        vite = self.env['nexora.preview_launcher_vite']
        for name, requirements, scaffold in self.SCENARIOS:
            ws = os.path.join(LIFECYCLE_ROOT, name)
            os.makedirs(ws, exist_ok=True)
            self.cr.execute('SAVEPOINT u93_scenario')
            session = None
            try:
                cfg = self.env['nexora.builder_configuration'].create({'name': f'U93 {name}'})
                session = self.env['nexora.builder_session'].create({
                    'name': f'U93 {name}', 'builder_configuration_id': cfg.id,
                    'project_name': f'U93 {name}', 'target_workspace_path': ws,
                })
                # Phase 47.13 (U9.4): the pipeline now runs browser validation
                # AFTER preview health. React/R3F previews are console-clean
                # and complete; the Spline fake scene URL produces real
                # console/page errors, so U9.4 truthfully fails that scenario
                # after the preview contract below is already established.
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

                # Renderer scaffold unchanged by preview wiring.
                if scaffold:
                    self.assertTrue(os.path.isfile(os.path.join(ws, scaffold.replace('/', os.sep))),
                                    f'{name}: renderer scaffold missing')

                # Preview runtime truth: DB records + live process + HTTP 200.
                # These hold for every scenario: preview starts BEFORE browser
                # validation and is never torn down by a later-stage failure.
                runtime = self.env['nexora.runtime'].search([
                    ('builder_session_id', '=', session.id),
                    ('runtime_type', '=', 'preview')], limit=1)
                self.assertTrue(runtime, f'{name}: preview runtime record missing')
                self.assertEqual(runtime.status, 'running', f'{name}: preview not running')
                self.assertEqual(runtime.health, 'healthy', f'{name}: preview not healthy')
                preview_rt = self.env['nexora.preview_runtime'].search(
                    [('runtime_id', '=', runtime.id)], limit=1)
                self.assertEqual(preview_rt.launcher_type, 'vite', f'{name}: vite not selected')
                self.assertTrue(preview_rt.allocated_port >= 3000)
                self.assertTrue(preview_rt.preview_url.startswith('http://127.0.0.1:'))
                self.assertEqual(_http_ok(preview_rt.preview_url), 200,
                                 f'{name}: preview URL does not respond 200')
                self.assertTrue(vite._is_process_alive(preview_rt.process_id))
                # Workspace invariant: generation == build == preview workspace.
                self.assertEqual(os.path.abspath(session.workspace_id.workspace_path),
                                 os.path.abspath(ws))
                self.assertTrue(os.path.isdir(os.path.join(ws, 'dist')),
                                f'{name}: build output missing (build must precede preview)')
            finally:
                try:
                    if session is not None:
                        preview_service.stop_workspace_preview(session)
                except Exception:
                    pass
                self.cr.execute('ROLLBACK TO SAVEPOINT u93_scenario')
                self.cr.execute('RELEASE SAVEPOINT u93_scenario')


if __name__ == '__main__':
    unittest.main()
