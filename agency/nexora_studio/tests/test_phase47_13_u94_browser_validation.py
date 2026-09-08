# -*- coding: utf-8 -*-
"""Phase 47.13 (U9.4) — Browser validation + console/network evidence closure.

Locks the U9.4 acceptance boundary using EXISTING owners only:
  * nexora.provider.playwright  -> canonical browser provider, extended with
                                   action='validate' (navigation + console +
                                   page errors + network failures + HTTP
                                   status evidence + screenshots). Existing
                                   action='snapshot' preserved.
  * ValidationEngine            -> SAME validation owner, browser phase after
                                   PREVIEW_READY; interpretation through the
                                   existing issue/severity contract.
  * nexora.preview_service      -> preview URL/health contract only (U9.3);
                                   never owns a browser.

No BrowserValidationService/PlaywrightService/BrowserRuntime/BrowserManager/
BrowserOrchestrator/BrowserValidator/BrowserDiagnosticsService/second
Playwright provider/second validation engine is introduced.

No WebGL/canvas/Three.js/R3F/Spline-runtime assertions exist here or in the
production code — those belong to U9.5. The final unified gate is U9.6.

Real browser provider-contract tests always run against a test-owned local
HTTP server. Full production-path controlled scenarios (React/R3F/Spline via
run_generation) are opt-in via NEXORA_U94_BROWSER=1 and were executed +
reported in the U9.4 audit.
"""
import http.server
import functools
import json
import os
import re
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODOO_ROOT = r'D:\ODOO'
SCENARIO_ROOT = os.path.join(ODOO_ROOT, '.u94_browser')
VALID_SPLINE_URL = "https://prod.spline.design/AbCdEf123/scene.splinecode"

import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.generation.engines.validation_engine import ValidationEngine
from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    WebsiteGenerationArtifact, ValidationReport, Workspace, Content, ArchitectureModel,
)
from odoo.addons.nexora_studio.services.providers.execution_models import (
    ProviderExecutionRequest, ProviderExecutionResult,
)


def _src(rel):
    with open(os.path.join(ADDON, rel.replace('/', os.sep)), 'r', encoding='utf-8') as fh:
        return fh.read()


def _chrome_pids():
    """PIDs of Playwright-owned Chromium only.

    The user's own Google Chrome (C:\\Program Files\\Google\\Chrome) spawns
    and reaps renderer/GPU processes constantly; counting those makes the
    orphan checks flaky. Only processes whose executable lives under the
    Playwright browsers root (ms-playwright) belong to our provider.
    """
    try:
        import psutil
        names = {'chrome.exe', 'headless_shell.exe', 'chromium.exe'}
        pids = set()
        for p in psutil.process_iter(['name']):
            if (p.info.get('name') or '').lower() not in names:
                continue
            try:
                exe = (p.exe() or '').lower()
            except Exception:
                # Inaccessible exe (elevated/other-user process): not ours.
                continue
            if 'ms-playwright' in exe or 'playwright' in exe:
                pids.add(p.pid)
        return pids
    except Exception:
        return set()


def _wait_no_new_chrome(baseline, timeout=15.0):
    deadline = time.time() + timeout
    leftover = set()
    while time.time() < deadline:
        leftover = _chrome_pids() - baseline
        if not leftover:
            return True
        time.sleep(0.3)
    return not leftover


def _port_free(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.5):
            return False
    except Exception:
        return True


class _ControlledHandler(http.server.SimpleHTTPRequestHandler):
    """Test-owned server: static pages + a real HTTP 500 endpoint."""

    def do_GET(self):
        if self.path.startswith('/error500'):
            body = b'<html><head><title>server error</title></head><body>boom</body></html>'
            self.send_response(500)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def log_message(self, *args):
        pass


class TestU94OwnershipArchitecture(unittest.TestCase):
    """AD–AJ + ordering: existing owners only, one browser provider, one
    validation owner, preview/browser ownership strictly separated."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_single_canonical_playwright_provider(self):
        models = self.env.registry.models
        pw = sorted(n for n in models if 'playwright' in n)
        self.assertEqual(pw, ['nexora.provider.playwright'])

    def test_no_parallel_browser_architecture(self):
        models = self.env.registry.models
        forbidden = [n for n in models if n.startswith('nexora.') and any(
            k in n for k in ('browser_validation_service', 'playwright_service',
                             'browser_runtime', 'browser_manager',
                             'browser_orchestrator', 'browser_validator',
                             'browser_diagnostics', 'browser_registry',
                             'second_validation', 'validation_engine'))]
        self.assertEqual(forbidden, [], f'parallel browser architecture: {forbidden}')

    def test_no_browser_connector_rows(self):
        ids = {c.connector_id for c in self.env['nexora.connector'].search([])}
        self.assertEqual(ids, {
            'context7_mcp', 'firecrawl_mcp', 'github_mcp',
            'gosom_mcp', 'penpot_mcp', 'tavily_mcp',
        })

    def test_validation_engine_uses_provider_abstraction_only(self):
        src = _src('services/generation/engines/validation_engine.py')
        self.assertIn('nexora.provider.playwright', src)
        self.assertNotIn('sync_playwright', src)
        self.assertNotIn('import subprocess', src)
        self.assertNotIn('subprocess.', src)
        self.assertNotIn('chromium.launch', src.lower())

    def test_preview_service_has_no_browser_ownership(self):
        src = _src('services/preview_service.py')
        self.assertNotIn('playwright', src.lower())
        self.assertNotIn('chromium', src.lower())

    def test_pipeline_ordering_build_preview_browser(self):
        src = _src('services/generation/pipeline/website_generation_pipeline.py')
        self.assertIn(
            'GenerationState.REVIEW_COMPLETED: (ValidationEngine(orchestrator), GenerationState.VALIDATION_COMPLETED)', src)
        self.assertIn(
            'GenerationState.VALIDATION_COMPLETED: (PreviewEngine(orchestrator), GenerationState.PREVIEW_READY)', src)
        self.assertIn(
            "GenerationState.PREVIEW_READY: (ValidationEngine(orchestrator, phase='browser'), GenerationState.BROWSER_VALIDATED)", src)
        self.assertIn(
            'GenerationState.BROWSER_VALIDATED: (OptimizationEngine(orchestrator), GenerationState.DEPLOYMENT_READY)', src)
        # A failed engine aborts the pipeline (no false success).
        self.assertIn('raise ValueError(f"Engine execution failed: {result.error}")', src)

    def test_state_and_report_contracts(self):
        ctx_src = _src('services/generation/core/generation_context.py')
        self.assertIn('BROWSER_VALIDATED = "BROWSER_VALIDATED"', ctx_src)
        self.assertIn('browser_validation: Dict[str, Any] = field(default_factory=dict)', ctx_src)

    def test_no_renderer_runtime_assertions_in_validation(self):
        # Phase 47.13 (U9.4) lock, superseded by Phase 47.14 (U9.5):
        # renderer-runtime evidence is now legitimately interpreted by the
        # SAME ValidationEngine through the provider abstraction. The locks
        # that remain:
        #   * the ENGINE never probes the browser itself (no Playwright, no
        #     page evaluation, no WebGL/DOM inspection) — it only interprets
        #     provider evidence;
        #   * the browser-side WebGL/marker probe lives ONLY in the canonical
        #     nexora.provider.playwright script;
        #   * no U9.6 final unified gate / deployment work leaks into U9.5.
        src = _src('services/generation/engines/validation_engine.py').lower()
        self.assertIn('renderer_runtime', src,
                      'U9.5 renderer evidence must live in the existing engine contract')
        self.assertIn('getattr(artifact, "design"', src,
                      'renderer identity must come from the existing artifact.design contract')
        for forbidden in ('sync_playwright', 'import subprocess', 'page.evaluate',
                          'getcontext(', 'queryselector'):
            self.assertNotIn(forbidden, src,
                             f'engine must interpret provider evidence only: {forbidden}')
        prov_src = _src('models/playwright_provider.py').lower()
        self.assertIn('__nexora_renderer_runtime__', prov_src,
                      'U9.5 probe must read the provider-owned runtime marker')
        self.assertIn('webgl', prov_src,
                      'U9.5 browser-side WebGL probe lives in the canonical provider')
        for forbidden in ('final_validation_gate', 'unified_acceptance_gate',
                          'deployment_gate'):
            self.assertNotIn(forbidden, src)
            self.assertNotIn(forbidden, prov_src)


class TestU94ProviderContract(unittest.TestCase):
    """B–K + controlled failures with REAL Chromium through the canonical
    provider against a test-owned local HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.provider = cls.env['nexora.provider.playwright']

        cls.www = tempfile.mkdtemp(prefix='nexora-u94-www-')
        with open(os.path.join(cls.www, 'ok.html'), 'w', encoding='utf-8') as fh:
            fh.write('<html><head><title>U94 OK</title></head><body><h1>ok</h1>'
                     "<script>console.log('plain log');console.info('info msg');"
                     "console.debug('debug msg');</script></body></html>")
        with open(os.path.join(cls.www, 'console_error.html'), 'w', encoding='utf-8') as fh:
            fh.write('<html><head><title>U94 console</title></head><body>'
                     "<script>console.error('controlled console error');"
                     "console.warn('controlled warning');</script></body></html>")
        with open(os.path.join(cls.www, 'network_fail.html'), 'w', encoding='utf-8') as fh:
            fh.write('<html><head><title>U94 network</title></head><body>'
                     '<script src="http://127.0.0.1:9/x.js"></script>'
                     '<img src="/missing.png"></body></html>')

        cls.server = socketserver.TCPServer(
            ('127.0.0.1', 0), functools.partial(_ControlledHandler, directory=cls.www))
        cls.server.allow_reuse_address = True
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f'http://127.0.0.1:{cls.port}'
        cls.evidence_root = tempfile.mkdtemp(prefix='nexora-u94-evidence-')
        cls._chrome_baseline = _chrome_pids()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.www, ignore_errors=True)
        shutil.rmtree(cls.evidence_root, ignore_errors=True)
        cls.cr.close()

    def _validate(self, routes, name, timeout_ms=15000):
        evidence_dir = os.path.join(self.evidence_root, name)
        request = ProviderExecutionRequest(
            namespace='nexora.provider.playwright',
            payload={'action': 'validate', 'url': self.base_url,
                     'routes': routes, 'timeout_ms': timeout_ms,
                     'evidence_dir': evidence_dir},
            timeout=90.0,
        )
        return self.provider.execute(request), evidence_dir

    def test_01_navigation_success_final_url_title_screenshot(self):
        result, evidence_dir = self._validate(['/ok.html'], 'nav_ok')
        self.assertTrue(result.success, result.error)
        data = result.data
        self.assertEqual(data['status'], 'completed')
        self.assertEqual(len(data['routes']), 1)
        route = data['routes'][0]
        self.assertTrue(route['success'])
        self.assertEqual(route['status'], 200)
        self.assertEqual(route['requested_url'], self.base_url + '/ok.html')
        self.assertTrue(route['final_url'].endswith('/ok.html'))
        self.assertEqual(route['title'], 'U94 OK')
        self.assertTrue(route['screenshot_captured'])
        self.assertTrue(os.path.isfile(route['screenshot_path']),
                        'screenshot evidence must be retained')
        self.assertEqual(data['screenshots'], [route['screenshot_path']])
        self.assertTrue(data['success'])
        self.assertEqual(data['console_errors'], [])
        self.assertEqual(data['network_failures'], [])
        self.assertEqual(data['http_errors'], [])

    def test_02_console_types_kept_distinct(self):
        result, _ = self._validate(['/ok.html'], 'console_types')
        self.assertTrue(result.success, result.error)
        data = result.data
        types = {msg['type'] for msg in data['console_messages']}
        texts = {msg['text'] for msg in data['console_messages']}
        self.assertIn('log', types)
        self.assertIn('info', types)
        self.assertIn('debug', types)
        self.assertIn('plain log', texts)
        self.assertIn('info msg', texts)
        self.assertIn('debug msg', texts)
        self.assertEqual(data['console_errors'], [])
        self.assertEqual(data['console_warnings'], [])

    def test_03_console_errors_and_warnings_captured(self):
        result, _ = self._validate(['/console_error.html'], 'console_err')
        self.assertTrue(result.success, result.error)
        data = result.data
        self.assertTrue(any('controlled console error' in e['text']
                            for e in data['console_errors']),
                        'console error must be captured')
        self.assertTrue(all(e['type'] == 'error' for e in data['console_errors']))
        self.assertTrue(any('controlled warning' in w['text']
                            for w in data['console_warnings']),
                        'console warning must be captured')
        self.assertTrue(all(w['type'] == 'warning' for w in data['console_warnings']))
        # Everything remains observable in the full message stream.
        texts = {msg['text'] for msg in data['console_messages']}
        self.assertIn('controlled console error', texts)
        self.assertIn('controlled warning', texts)

    def test_04_network_request_failure_and_http_404_captured(self):
        result, _ = self._validate(['/network_fail.html'], 'net_fail')
        self.assertTrue(result.success, result.error)
        data = result.data
        self.assertTrue(data['network_failures'],
                        'transport request failure must be captured')
        self.assertTrue(any('x.js' in f['url'] for f in data['network_failures']))
        failed = [f for f in data['network_failures'] if 'x.js' in f['url']][0]
        self.assertTrue(failed['failure'], 'failure text must be preserved')
        self.assertTrue(any(h['status'] == 404 and 'missing.png' in h['url']
                            for h in data['http_errors']),
                        'HTTP 404 response must be captured')

    def test_05_http_500_route_fails_and_captured(self):
        result, _ = self._validate(['/error500'], 'http_500')
        # Provider reports truthful evidence; the 500 route is not a success.
        self.assertTrue(result.success, result.error)
        data = result.data
        route = data['routes'][0]
        self.assertFalse(route['success'], 'HTTP 500 page must not be a route success')
        self.assertEqual(route['status'], 500)
        self.assertEqual(route['error'], 'http_status_500')
        self.assertTrue(any(h['status'] == 500 for h in data['http_errors']))
        self.assertFalse(data['success'])
        self.assertTrue(data['navigation_errors'])

    def test_06_multi_route_validation(self):
        result, _ = self._validate(['/ok.html', '/console_error.html'], 'multi')
        self.assertTrue(result.success, result.error)
        data = result.data
        self.assertEqual([r['route'] for r in data['routes']],
                         ['/ok.html', '/console_error.html'])
        self.assertTrue(data['routes'][0]['success'])
        self.assertTrue(data['routes'][1]['success'])  # navigation ok; errors are evidence
        self.assertTrue(data['console_errors'])
        self.assertTrue(data['success'],
                        'route success is navigation truth; interpretation is the engine job')

    def test_07_navigation_timeout_fails_route_and_cleans_up(self):
        # /hang is never served by the controlled server -> connection hangs
        # only briefly; use an unroutable port to force a real goto timeout.
        request = ProviderExecutionRequest(
            namespace='nexora.provider.playwright',
            payload={'action': 'validate', 'url': 'http://10.255.255.1:9999',
                     'routes': ['/'], 'timeout_ms': 4000,
                     'evidence_dir': os.path.join(self.evidence_root, 'timeout')},
            timeout=90.0,
        )
        baseline = _chrome_pids()
        result = self.provider.execute(request)
        self.assertTrue(result.success, result.error)
        data = result.data
        route = data['routes'][0]
        self.assertFalse(route['success'])
        self.assertTrue(str(route['error']).startswith('navigation_failed'),
                        f'expected navigation_failed, got {route["error"]}')
        self.assertFalse(data['success'])
        self.assertTrue(_wait_no_new_chrome(baseline),
                        'no orphan Chromium after navigation timeout')

    def test_08_browser_launch_failure_is_truthful(self):
        # Point Playwright at an empty browser directory -> chromium.launch
        # really fails inside the sandbox script. Diagnostics must survive.
        empty = tempfile.mkdtemp(prefix='nexora-u94-nobrowsers-')
        old = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = empty
        try:
            request = ProviderExecutionRequest(
                namespace='nexora.provider.playwright',
                payload={'action': 'validate', 'url': self.base_url,
                         'routes': ['/ok.html'], 'timeout_ms': 5000},
                timeout=90.0,
            )
            result = self.provider.execute(request)
        finally:
            if old is None:
                os.environ.pop('PLAYWRIGHT_BROWSERS_PATH', None)
            else:
                os.environ['PLAYWRIGHT_BROWSERS_PATH'] = old
            shutil.rmtree(empty, ignore_errors=True)
        self.assertFalse(result.success, 'launch failure must never become success')
        self.assertTrue(result.error)
        self.assertIsInstance(result.data, dict, 'diagnostics must survive failure')
        self.assertIn('browser_launch_failed', str(result.data.get('error')) + str(result.error))

    def test_09_browser_cleanup_no_orphan_chromium(self):
        baseline = _chrome_pids()
        result, _ = self._validate(['/ok.html'], 'cleanup_1')
        self.assertTrue(result.success, result.error)
        self.assertTrue(_wait_no_new_chrome(baseline),
                        'owned Chromium tree must be gone after validate')
        # A second run immediately after must also work (no leaked state).
        result2, _ = self._validate(['/ok.html'], 'cleanup_2')
        self.assertTrue(result2.success, result2.error)
        self.assertTrue(_wait_no_new_chrome(baseline))

    def test_10_snapshot_action_preserved(self):
        request = ProviderExecutionRequest(
            namespace='nexora.provider.playwright',
            payload={'action': 'snapshot', 'url': self.base_url + '/ok.html'},
            timeout=60.0,
        )
        result = self.provider.execute(request)
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data.get('status'), 'snapshot_taken')
        self.assertEqual(result.data.get('title'), 'U94 OK')
        self.assertTrue(result.data.get('screenshot_captured'))

    def test_11_missing_arguments_fail(self):
        result = self.provider.execute(ProviderExecutionRequest(
            namespace='nexora.provider.playwright', payload={'action': 'validate'}))
        self.assertFalse(result.success)
        self.assertIn("'action' and 'url'", str(result.error))


class TestU94BrowserPhaseGuards(unittest.TestCase):
    """E/L/M/V/W + failure policy + metadata propagation at the engine level.
    The provider is a spy: these tests lock ordering and interpretation, never
    replacing the real browser layer for the provider-contract class above."""

    @classmethod
    def setUpClass(cls):
        cls.ws = tempfile.mkdtemp(prefix='nexora-u94-guard-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws, ignore_errors=True)

    def _artifact(self, build_acceptance=None, pages=None, hierarchy=None, ws=None, design=None):
        return WebsiteGenerationArtifact(
            # Phase 47.15 (U9.6): real-path browser-phase success requires a
            # known renderer identity (the final acceptance gate fails on a
            # missing/unknown renderer identity). Tests exercising a real
            # success path pass a known provider; tests not passing design
            # only exercise skip/guard paths.
            design=design if design is not None else {},
            validation=ValidationReport(
                passed=True, accessibility_score=100, seo_score=100,
                performance_score=100,
                issues=[{"type": "warning", "message": "prior", "category": "seo"}],
                build_acceptance=build_acceptance if build_acceptance is not None
                else {"ran": True, "failed": False},
            ),
            workspace=Workspace(project_path=ws or self.ws),
            content=Content(pages=pages if pages is not None else {'/': {}, '/pricing': {}}),
            architecture=ArchitectureModel(component_hierarchy=hierarchy or {
                'p1': {'type': 'page', 'path': '/contact'},
                'c1': {'type': 'section', 'path': '/ignored'},
            }),
        )

    def _env(self, provider_spy, health='healthy', preview=True, session=True):
        preview_rt = SimpleNamespace(
            preview_url='http://127.0.0.1:3456', process_id=9999,
            launcher_type='vite', allocated_port=3456) if preview else None
        runtime_rec = SimpleNamespace(id=7) if preview else None
        session_rec = SimpleNamespace(exists=lambda: True, id=123) if session else None
        return {
            'nexora.runtime': SimpleNamespace(
                search=lambda domain, limit=None: runtime_rec),
            'nexora.preview_runtime': SimpleNamespace(
                search=lambda domain, limit=None: preview_rt),
            'nexora.preview_service': SimpleNamespace(
                check_health=lambda r: health),
            'nexora.builder_session': SimpleNamespace(
                browse=lambda i: session_rec),
            'nexora.provider.playwright': provider_spy,
        }

    def _runtime(self, env, session_id='123'):
        return SimpleNamespace(env=env, metadata=SimpleNamespace(session_id=session_id))

    def _engine(self):
        return ValidationEngine(orchestrator=None, phase='browser')

    def _spy(self, result=None):
        calls = []

        def execute(request):
            calls.append(request)
            return result if result is not None else ProviderExecutionResult(
                success=True, data={
                    'status': 'completed', 'success': True,
                    'routes': [{'route': '/', 'requested_url': 'http://127.0.0.1:3456/',
                                'final_url': 'http://127.0.0.1:3456/', 'status': 200,
                                'title': 'Home', 'success': True, 'error': None,
                                'console_messages': [], 'console_errors': [],
                                'console_warnings': [], 'page_errors': [],
                                'network_failures': [], 'http_errors': [],
                                'screenshot_captured': True,
                                'screenshot_path': os.path.join(self.ws, 'route_home.png')}],
                    'console_errors': [], 'console_warnings': [], 'console_messages': [],
                    'page_errors': [], 'network_failures': [], 'http_errors': [],
                    'navigation_errors': [],
                    'screenshots': [os.path.join(self.ws, 'route_home.png')],
                }, error=None)

        spy = SimpleNamespace(execute=execute, calls=calls)
        return spy

    def test_build_acceptance_failed_skips_browser_phase(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(build_acceptance={'ran': True, 'failed': True}),
            self._runtime(self._env(spy)))
        self.assertTrue(res.success)
        evidence = res.metadata['browser_validation']
        self.assertTrue(evidence['skipped'])
        self.assertEqual(evidence['skip_reason'], 'build_acceptance_failed')
        self.assertEqual(spy.calls, [], 'browser must not launch after build failure')

    def test_build_acceptance_not_ran_skips(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(build_acceptance={}), self._runtime(self._env(spy)))
        self.assertTrue(res.metadata['browser_validation']['skipped'])
        self.assertEqual(spy.calls, [])

    def test_no_env_skips_mock_pipelines(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(), SimpleNamespace(metadata=SimpleNamespace(session_id='123')))
        self.assertEqual(res.metadata['browser_validation']['skip_reason'], 'no_odoo_env')
        self.assertEqual(spy.calls, [])

    def test_no_session_skips(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(), self._runtime(self._env(spy), session_id='mock-session'))
        self.assertEqual(res.metadata['browser_validation']['skip_reason'], 'no_session')
        self.assertEqual(spy.calls, [])

    def test_no_materialized_workspace_skips(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(ws=os.path.join(self.ws, 'missing')),
            self._runtime(self._env(spy)))
        self.assertEqual(res.metadata['browser_validation']['skip_reason'],
                         'no_materialized_workspace')
        self.assertEqual(spy.calls, [])

    def test_preview_unavailable_fails_browser_not_launched(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(), self._runtime(self._env(spy, preview=False)))
        self.assertFalse(res.success)
        evidence = res.metadata['browser_validation']
        self.assertTrue(evidence['failed'])
        self.assertEqual(evidence['error'], 'preview_unavailable')
        self.assertTrue(evidence['ran'])
        self.assertEqual(spy.calls, [], 'browser provider must not start without preview')
        self.assertTrue(any(i['type'] == 'error' and i['category'] == 'browser'
                            for i in res.artifact.validation.issues))
        self.assertFalse(res.artifact.validation.passed)

    def test_preview_unhealthy_fails_browser_not_launched(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(), self._runtime(self._env(spy, health='critical')))
        self.assertFalse(res.success)
        evidence = res.metadata['browser_validation']
        self.assertIn('preview_unhealthy', evidence['error'])
        self.assertEqual(spy.calls, [], 'browser must not launch when preview health fails')

    def test_healthy_preview_consumes_db_preview_url_and_routes(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(design={'provider': 'react'}),
            self._runtime(self._env(spy)))
        self.assertTrue(res.success, res.error)
        self.assertEqual(len(spy.calls), 1)
        payload = spy.calls[0].payload
        self.assertEqual(payload['action'], 'validate')
        self.assertEqual(payload['url'], 'http://127.0.0.1:3456',
                         'preview URL must come from the U9.3 preview contract')
        self.assertEqual(payload['routes'], ['/', '/pricing', '/contact'])
        evidence = res.metadata['browser_validation']
        self.assertTrue(evidence['ran'])
        self.assertEqual(evidence['status'], 'healthy')
        self.assertEqual(evidence['preview_url'], 'http://127.0.0.1:3456')
        self.assertEqual(evidence['preview_launcher'], 'vite')

    def test_provider_failure_fails_stage_with_diagnostics(self):
        spy = self._spy(result=ProviderExecutionResult(
            success=False, data={'error': 'browser_launch_failed: no executable'},
            error='Sandbox execution failed.', error_ms=None) if False else
            ProviderExecutionResult(
                success=False,
                data={'error': 'browser_launch_failed: no executable'},
                error='Sandbox execution failed.'))
        res = self._engine().execute(self._artifact(), self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        evidence = res.metadata['browser_validation']
        self.assertTrue(evidence['failed'])
        self.assertIn('browser_launch_failed', evidence['error'])

    def test_console_error_is_blocking_error_issue(self):
        data = {
            'status': 'completed', 'success': True,
            'routes': [{'route': '/', 'success': True, 'status': 200, 'error': None,
                        'console_errors': [{'type': 'error', 'text': 'boom'}],
                        'console_warnings': [], 'console_messages': [],
                        'page_errors': [], 'network_failures': [], 'http_errors': []}],
            'console_errors': [{'type': 'error', 'text': 'boom'}],
            'console_warnings': [], 'console_messages': [], 'page_errors': [],
            'network_failures': [], 'http_errors': [], 'navigation_errors': [],
            'screenshots': [],
        }
        spy = self._spy(result=ProviderExecutionResult(success=True, data=data))
        res = self._engine().execute(self._artifact(), self._runtime(self._env(spy)))
        self.assertFalse(res.success, 'console error must block validation')
        issues = res.artifact.validation.issues
        self.assertTrue(any(i['type'] == 'error' and i['category'] == 'browser'
                            and 'boom' in i['message'] for i in issues))
        self.assertFalse(res.artifact.validation.passed)
        self.assertTrue(res.metadata['browser_validation']['failed'])

    def test_console_warning_is_observable_not_blocking(self):
        data = {
            'status': 'completed', 'success': True,
            'routes': [{'route': '/', 'success': True, 'status': 200, 'error': None,
                        'console_errors': [],
                        'console_warnings': [{'type': 'warning', 'text': 'careful'}],
                        'console_messages': [], 'page_errors': [],
                        'network_failures': [], 'http_errors': []}],
            'console_errors': [], 'console_warnings': [{'type': 'warning', 'text': 'careful'}],
            'console_messages': [], 'page_errors': [], 'network_failures': [],
            'http_errors': [], 'navigation_errors': [], 'screenshots': [],
        }
        spy = self._spy(result=ProviderExecutionResult(success=True, data=data))
        res = self._engine().execute(
            self._artifact(design={'provider': 'react'}),
            self._runtime(self._env(spy)))
        self.assertTrue(res.success, 'warnings alone must never fail validation')
        issues = res.artifact.validation.issues
        self.assertTrue(any(i['type'] == 'warning' and 'careful' in i['message']
                            for i in issues))
        self.assertFalse(any(i['type'] == 'error' and i['category'] == 'browser'
                             for i in issues))

    def test_network_failure_is_blocking(self):
        data = {
            'status': 'completed', 'success': True,
            'routes': [{'route': '/', 'success': True, 'status': 200, 'error': None,
                        'console_errors': [], 'console_warnings': [], 'console_messages': [],
                        'page_errors': [],
                        'network_failures': [{'url': 'http://x/y.js',
                                              'failure': 'net::ERR_CONNECTION_REFUSED',
                                              'resource_type': 'script'}],
                        'http_errors': []}],
            'console_errors': [], 'console_warnings': [], 'console_messages': [],
            'page_errors': [],
            'network_failures': [{'url': 'http://x/y.js',
                                  'failure': 'net::ERR_CONNECTION_REFUSED',
                                  'resource_type': 'script'}],
            'http_errors': [], 'navigation_errors': [], 'screenshots': [],
        }
        spy = self._spy(result=ProviderExecutionResult(success=True, data=data))
        res = self._engine().execute(self._artifact(), self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        self.assertTrue(any(i['type'] == 'error' and 'y.js' in i['message']
                            for i in res.artifact.validation.issues))

    def test_http_500_blocking_and_subresource_404_warning(self):
        data = {
            'status': 'completed', 'success': True,
            'routes': [{'route': '/', 'success': True, 'status': 200, 'error': None,
                        'console_errors': [], 'console_warnings': [], 'console_messages': [],
                        'page_errors': [], 'network_failures': [],
                        'http_errors': [
                            {'url': 'http://h/api', 'status': 500, 'resource_type': 'xhr'},
                            {'url': 'http://h/missing.png', 'status': 404,
                             'resource_type': 'image'}]}],
            'console_errors': [], 'console_warnings': [], 'console_messages': [],
            'page_errors': [], 'network_failures': [],
            'http_errors': [
                {'url': 'http://h/api', 'status': 500, 'resource_type': 'xhr'},
                {'url': 'http://h/missing.png', 'status': 404, 'resource_type': 'image'}],
            'navigation_errors': [], 'screenshots': [],
        }
        spy = self._spy(result=ProviderExecutionResult(success=True, data=data))
        res = self._engine().execute(self._artifact(), self._runtime(self._env(spy)))
        self.assertFalse(res.success, 'HTTP 500 must never become success')
        issues = res.artifact.validation.issues
        self.assertTrue(any(i['type'] == 'error' and 'HTTP 500' in i['message']
                            for i in issues))
        self.assertTrue(any(i['type'] == 'warning' and 'HTTP 404' in i['message']
                            for i in issues))

    def test_navigation_failure_is_blocking(self):
        data = {
            'status': 'completed', 'success': False,
            'routes': [{'route': '/', 'success': False, 'status': None,
                        'error': 'navigation_failed: Timeout 30000ms exceeded',
                        'console_errors': [], 'console_warnings': [], 'console_messages': [],
                        'page_errors': [], 'network_failures': [], 'http_errors': []}],
            'console_errors': [], 'console_warnings': [], 'console_messages': [],
            'page_errors': [], 'network_failures': [], 'http_errors': [],
            'navigation_errors': [{'route': '/', 'error': 'navigation_failed', 'status': None}],
            'screenshots': [],
        }
        spy = self._spy(result=ProviderExecutionResult(success=True, data=data))
        res = self._engine().execute(self._artifact(), self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        self.assertTrue(any('navigation failed' in i['message'].lower()
                            for i in res.artifact.validation.issues))

    def test_evidence_and_prior_report_preserved(self):
        spy = self._spy()
        artifact = self._artifact(design={'provider': 'react'})
        res = self._engine().execute(artifact, self._runtime(self._env(spy)))
        report = res.artifact.validation
        evidence = report.browser_validation
        for key in ('ran', 'status', 'preview_url', 'routes', 'console_errors',
                    'console_warnings', 'network_failures', 'navigation_errors',
                    'screenshots', 'timestamp'):
            self.assertIn(key, evidence)
        # Prior pass-1 state preserved.
        self.assertEqual(report.build_acceptance, {'ran': True, 'failed': False})
        self.assertIn({'type': 'warning', 'message': 'prior', 'category': 'seo'},
                      report.issues)
        self.assertEqual(report.accessibility_score, 100)
        self.assertEqual(res.metadata['browser_validation'], evidence)


@unittest.skipUnless(os.environ.get('NEXORA_U94_BROWSER') == '1',
                     'opt-in full production-path browser scenarios (set NEXORA_U94_BROWSER=1)')
class TestU94ControlledScenarios(unittest.TestCase):
    """AA/AB/AC + X/Y/Z through the real production path:
    generate -> install -> build -> preview -> health -> browser validation.
    External AI stubbed at the existing boundary only; real browser always."""

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
        if os.path.isdir(SCENARIO_ROOT):
            shutil.rmtree(SCENARIO_ROOT, ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        if os.path.isdir(SCENARIO_ROOT):
            shutil.rmtree(SCENARIO_ROOT, ignore_errors=True)
        cls.cr.close()

    @staticmethod
    def _fake_route_request(self, task_type, prompt, parameters=None, ctx=None):
        if task_type == 'ai_code_patch':
            match = re.search(r'named\s+([A-Za-z0-9_]+)', str(prompt or ''))
            name = match.group(1) if match else 'GeneratedSection'
            return {'full_content': f"function {name}() {{ return <section><h2>{name}</h2></section> }}"}
        return {}

    def _preview_contract(self, session):
        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'preview')], limit=1)
        preview_rt = self.env['nexora.preview_runtime'].search(
            [('runtime_id', '=', runtime.id)], limit=1) if runtime else None
        return runtime, preview_rt

    def _direct_browser_evidence(self, preview_url, routes):
        """Capture browser evidence through the canonical provider against the
        real preview URL (the same contract the pipeline consumed)."""
        provider = self.env['nexora.provider.playwright']
        request = ProviderExecutionRequest(
            namespace='nexora.provider.playwright',
            payload={'action': 'validate', 'url': preview_url, 'routes': routes,
                     'timeout_ms': 30000},
            timeout=180.0,
        )
        return provider.execute(request)

    def test_controlled_scenarios_browser_validation_via_production_path(self):
        service = self.env['nexora.builder_session_service']
        preview_service = self.env['nexora.preview_service']
        for name, requirements, scaffold in self.SCENARIOS:
            ws = os.path.join(SCENARIO_ROOT, name)
            os.makedirs(ws, exist_ok=True)
            self.cr.execute('SAVEPOINT u94_scenario')
            session = None
            try:
                cfg = self.env['nexora.builder_configuration'].create({'name': f'U94 {name}'})
                session = self.env['nexora.builder_session'].create({
                    'name': f'U94 {name}', 'builder_configuration_id': cfg.id,
                    'project_name': f'U94 {name}', 'target_workspace_path': ws,
                })
                if name in ('react', 'r3f'):
                    self._scenario_success(name, requirements, scaffold, ws, service)
                else:
                    self._scenario_spline(requirements, scaffold, ws, service)
            finally:
                try:
                    if session is not None:
                        preview_service.stop_workspace_preview(session)
                except Exception:
                    pass
                self.cr.execute('ROLLBACK TO SAVEPOINT u94_scenario')
                self.cr.execute('RELEASE SAVEPOINT u94_scenario')

    def _scenario_success(self, name, requirements, scaffold, ws, service):
        session = self.env['nexora.builder_session'].search(
            [('name', '=', f'U94 {name}')], limit=1)
        ok = service.run_generation(session, requirements=requirements)
        self.assertTrue(ok, f'{name}: run_generation failed')
        self.assertEqual(session.status, 'ai_reviewing')

        if scaffold:
            self.assertTrue(os.path.isfile(os.path.join(ws, scaffold.replace('/', os.sep))),
                            f'{name}: renderer scaffold missing')

        # Pipeline browser phase really ran: screenshot evidence exists in
        # the managed workspace (home route at minimum + generated routes).
        evidence_dir = os.path.join(ws, '.nexora', 'browser_evidence')
        shots = [f for f in os.listdir(evidence_dir) if f.startswith('route_')] \
            if os.path.isdir(evidence_dir) else []
        self.assertIn('route_home.png', shots,
                      f'{name}: pipeline browser validation did not run')
        if name == 'react':
            self.assertGreaterEqual(len(shots), 2,
                                    'react: generated additional routes must be validated')

        # Preview truth after generation.
        runtime, preview_rt = self._preview_contract(session)
        self.assertTrue(runtime and preview_rt)
        self.assertEqual(runtime.status, 'running')
        self.assertEqual(runtime.health, 'healthy')
        preview_url = preview_rt.preview_url

        # Direct canonical-provider evidence capture against the real preview.
        result = self._direct_browser_evidence(preview_url, ['/'])
        self.assertTrue(result.success, f'{name}: {result.error}')
        data = result.data
        route = data['routes'][0]
        self.assertTrue(route['success'])
        self.assertEqual(route['status'], 200)
        self.assertTrue(route['final_url'].startswith(preview_url))
        self.assertTrue(route['title'])
        self.assertEqual(data['console_errors'], [],
                         f'{name}: console errors must be empty, got {data["console_errors"]}')
        self.assertEqual(data['network_failures'], [])
        self.assertEqual(data['http_errors'], [])
        # U9.5 boundary: evidence carries U9.4 navigation/console/network
        # fields only — no WebGL/canvas/renderer-runtime keys.
        for forbidden in ('webgl', 'canvas', 'spline_runtime', 'scene_rendered'):
            self.assertFalse(any(forbidden in str(k).lower() for k in data.keys()),
                             f'{name}: renderer-runtime field leaked: {forbidden}')

    def _scenario_spline(self, requirements, scaffold, ws, service):
        session = self.env['nexora.builder_session'].search(
            [('name', '=', 'U94 spline')], limit=1)
        raised = None
        try:
            service.run_generation(session, requirements=requirements)
        except Exception as e:
            raised = e
        self.assertIsNotNone(raised, 'spline: broken scene reference must fail browser validation')
        self.assertIn('Browser validation failed', str(raised))
        self.assertEqual(session.status, 'failed')
        self.assertTrue(os.path.isfile(os.path.join(ws, scaffold.replace('/', os.sep))),
                        'spline scaffold must remain materialized')

        # The preview is still the truthful source; capture browser evidence
        # through the canonical provider (console/network truth of the broken
        # fake scene reference — no Spline-runtime assertions).
        runtime, preview_rt = self._preview_contract(session)
        self.assertTrue(runtime and preview_rt and preview_rt.preview_url)
        result = self._direct_browser_evidence(preview_rt.preview_url, ['/'])
        self.assertTrue(result.success, result.error)
        data = result.data
        route = data['routes'][0]
        self.assertTrue(route['success'], 'navigation itself succeeds (page loads)')
        self.assertTrue(data['console_errors'],
                        'spline scene failure must surface as console errors')
        self.assertTrue(data['page_errors'] or data['http_errors'],
                        'spline scene failure must surface as page/network evidence')
        http_urls = ' '.join(h.get('url', '') for h in data['http_errors'])
        self.assertIn('prod.spline.design', http_urls + ' '.join(
            e.get('text', '') for e in data['console_errors']))
        self.assertNotIn('spline_runtime', json.dumps(data),
                         'no Spline-runtime assertions in U9.4')


if __name__ == '__main__':
    unittest.main()
