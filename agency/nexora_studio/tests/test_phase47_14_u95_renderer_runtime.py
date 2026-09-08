# -*- coding: utf-8 -*-
"""Phase 47.14 (U9.5) — Renderer runtime acceptance closure.

Extends the EXISTING U9.4 browser-validation contract with renderer-specific
runtime acceptance, using ONLY existing owners:
  * nexora.provider.playwright  -> the SAME action='validate' now optionally
    takes payload['renderer'] and performs a bounded browser-side runtime
    probe: it READS the provider-owned window.__NEXORA_RENDERER_RUNTIME__
    marker (set truthfully by the R3F onCreated / Spline onLoad lifecycles)
    plus independent DOM/canvas/WebGL facts. It never fabricates runtime
    state and never writes the marker.
  * ValidationEngine            -> the SAME browser phase; renderer identity
    comes from the existing artifact.design['provider'] contract (never
    inferred from file/package names); renderer failures map into the
    EXISTING issue/severity contract (type=error blocking, category=browser).
  * ReactThreeFiberProvider     -> owns the R3F runtime marker contract
    (Scene.jsx onCreated: initialized/canvas/webgl — only after R3F actually
    created its WebGLRenderer).
  * SplineRenderingProvider     -> owns the Spline runtime marker contract
    (SplineScene.jsx onLoad: initialized/scene_loaded — only after the scene
    actually loaded).

React -> renderer runtime not_applicable (no WebGL required).
SwiftShader/software WebGL counts as functional WebGL availability.
No new pipeline state: BROWSER_VALIDATED now means navigation + renderer
runtime acceptance. No new services/providers/registries/connectors exist.
"""
import functools
import http.server
import json
import os
import shutil
import socket
import socketserver
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODOO_ROOT = r'D:\ODOO'
SCENARIO_ROOT = os.path.join(ODOO_ROOT, '.u95_renderer')
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

MARKER = 'window.__NEXORA_RENDERER_RUNTIME__'


def _src(rel):
    with open(os.path.join(ADDON, rel.replace('/', os.sep)), 'r', encoding='utf-8') as fh:
        return fh.read()


def _chrome_pids():
    """PIDs of Playwright-owned Chromium only (U9.4 filter: the user's own
    Google Chrome spawns/reaps processes constantly and must not be counted)."""
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


# ---------------------------------------------------------------------------
# Architecture / ownership locks (spec §3, §27, §29)
# ---------------------------------------------------------------------------
class TestU95OwnershipArchitecture(unittest.TestCase):

    FORBIDDEN_OWNERS = (
        'RendererRuntimeService', 'WebGLValidationService',
        'SplineValidationService', 'RendererBrowserService',
        'CanvasValidationService', 'BrowserRuntimeService',
        'ThreeRuntimeService', 'SplineRuntimeService',
    )

    def test_no_parallel_renderer_browser_architecture(self):
        offenders = []
        for root, dirs, files in os.walk(os.path.join(ADDON, 'services')):
            dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
            for f in files:
                if not f.endswith('.py'):
                    continue
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    text = fh.read()
                for name in self.FORBIDDEN_OWNERS:
                    if name in text:
                        offenders.append(f'{f}:{name}')
        for rel in ('models/playwright_provider.py',
                    'services/generation/engines/validation_engine.py'):
            with open(os.path.join(ADDON, rel.replace('/', os.sep)), 'r',
                      encoding='utf-8', errors='ignore') as fh:
                text = fh.read()
            for name in self.FORBIDDEN_OWNERS:
                if name in text:
                    offenders.append(f'{rel}:{name}')
        self.assertEqual(offenders, [],
                         'no parallel renderer/browser owner may be introduced')

    def test_single_browser_and_validation_owners_unchanged(self):
        # Exactly one Playwright provider, one ValidationEngine, one preview
        # service — all pre-existing owners reused, none duplicated.
        models = os.listdir(os.path.join(ADDON, 'models'))
        self.assertEqual([f for f in models if 'playwright' in f.lower()],
                         ['playwright_provider.py'])
        engines = os.listdir(os.path.join(ADDON, 'services', 'generation', 'engines'))
        self.assertEqual([f for f in engines if 'validation' in f.lower()],
                         ['validation_engine.py'])
        self.assertIn('preview_service.py',
                      os.listdir(os.path.join(ADDON, 'services')))
        # No second browser action: U9.5 extends action='validate'.
        prov = _src('models/playwright_provider.py')
        self.assertNotIn("action='renderer_validate'", prov)
        self.assertNotIn("'renderer_validate'", prov)

    def test_no_new_pipeline_state(self):
        # Spec §20: BROWSER_VALIDATED already means navigation + renderer
        # runtime acceptance — no RENDERER_VALIDATED state is added.
        ctx_src = _src('services/generation/core/generation_context.py')
        self.assertNotIn('RENDERER_VALIDATED', ctx_src)
        pipe_src = _src('services/generation/pipeline/website_generation_pipeline.py')
        self.assertIn("GenerationState.PREVIEW_READY: (ValidationEngine(orchestrator, phase='browser'), GenerationState.BROWSER_VALIDATED)", pipe_src)
        self.assertIn('GenerationState.BROWSER_VALIDATED: (OptimizationEngine(orchestrator), GenerationState.DEPLOYMENT_READY)', pipe_src)

    def test_renderer_identity_comes_from_design_contract_only(self):
        # Spec §6: identity from artifact.design provider contract — never
        # file names, package names or source inspection.
        engine = _src('services/generation/engines/validation_engine.py')
        self.assertIn('getattr(artifact, "design"', engine)
        self.assertIn('renderer_id not in ("react", "react_three_fiber", "spline")', engine)
        for heuristic in ("'package.json'", 'Scene.jsx', 'SplineScene.jsx',
                          'visual_complexity'):
            self.assertNotIn(heuristic, engine,
                             f'renderer identity must not be inferred: {heuristic}')

    def test_runtime_markers_are_truthful_provider_owned_lifecycle_signals(self):
        # R3F: the marker ASSIGNMENT lives only inside the Canvas onCreated
        # lifecycle callback (the docstring may mention the marker earlier;
        # only the assignment is the runtime signal).
        r3f = _src('services/design/providers/react_three_fiber_provider.py')
        self.assertIn('onCreated=', r3f)
        r3f_marker_assign = r3f.index(MARKER + ' =')
        self.assertLess(r3f.index('onCreated='), r3f_marker_assign,
                        'R3F marker must be assigned from the onCreated lifecycle only')
        self.assertIn('initialized: false', r3f,
                      'R3F marker must have a truthful failure path')
        self.assertEqual(r3f.count('initialized: true'), 1,
                         'R3F initialized:true appears exactly once (inside onCreated)')
        # Spline: the marker assignment lives only inside the onLoad
        # callback, and scene_loaded is DERIVED from the actual scene
        # response (r.ok) - never a hardcoded literal true.
        spline = _src('services/design/providers/spline_provider.py')
        self.assertIn('onLoad=', spline)
        spline_marker_assign = spline.index(MARKER + ' =')
        self.assertLess(spline.index('onLoad='), spline_marker_assign,
                        'Spline marker must be assigned from the onLoad lifecycle only')
        self.assertEqual(spline.count('initialized: true'), 2,
                         'Spline initialized:true appears exactly twice '
                         '(success + catch paths, both inside onLoad)')
        self.assertIn('scene_loaded: r.ok', spline,
                      'scene_loaded must be derived from the scene response')
        self.assertIn('scene_loaded: false', spline,
                      'Spline marker must have a truthful failure path')
        self.assertNotIn('scene_loaded: true', spline,
                         'scene_loaded must never be a hardcoded literal')
        # The Playwright provider and the engine only READ the marker - they
        # never assign it (no fabricated runtime success).
        prov = _src('models/playwright_provider.py')
        self.assertIn(f'{MARKER} || null', prov)
        self.assertNotIn(f'{MARKER} =', prov,
                         'browser provider must read, never write, the marker')
        self.assertNotIn('initialized: true', prov)
        self.assertNotIn('scene_loaded: true', prov)

    def test_engine_interprets_evidence_never_probes(self):
        # The engine maps provider evidence through the existing issue
        # contract; it never touches Playwright, page evaluation or WebGL.
        engine = _src('services/generation/engines/validation_engine.py')
        self.assertIn('_map_renderer_issues', engine)
        for forbidden in ('sync_playwright', 'import subprocess',
                          'page.evaluate', 'getContext(', 'querySelector'):
            self.assertNotIn(forbidden, engine)

    def test_renderer_evidence_lives_in_existing_browser_validation(self):
        # Spec §18: extend browser_validation, no second report model.
        engine = _src('services/generation/engines/validation_engine.py')
        self.assertIn('evidence["renderer_runtime"]', engine)
        ctx_src = _src('services/generation/core/generation_context.py')
        self.assertNotIn('renderer_runtime_validation:', ctx_src)
        self.assertNotIn('RendererRuntimeReport', ctx_src)

    def test_swiftshader_is_not_failure(self):
        # Spec §7/§9: functional WebGL availability is the criterion -
        # software rendering (SwiftShader) is accepted; only warnings.
        prov = _src('models/playwright_provider.py')
        self.assertIn('SwiftShader', prov,
                      'the provider contract must document SwiftShader acceptance')
        self.assertIn('functional WebGL availability', prov)
        self.assertEqual(prov.count('SwiftShader'), 1,
                         'SwiftShader may be mentioned once (acceptance doc), '
                         'never as a failure condition')

    def test_no_renderer_connector_rows(self):
        registry = Registry.new('nexora_studio')
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            connectors = env['nexora.connector'].search([])
            self.assertEqual(len(connectors), 6)
            ids = sorted(c.connector_id for c in connectors)
            self.assertEqual(ids, ['context7_mcp', 'firecrawl_mcp', 'github_mcp',
                                   'gosom_mcp', 'penpot_mcp', 'tavily_mcp'])
            caps = env['nexora.capability_registry'].search([
                ('capability_id', 'in', ('mcp.spline.1.0.0', 'mcp.threejs_docs.1.0.0',
                                         'mcp.r3f_docs.1.0.0', 'mcp.drei_docs.1.0.0'))])
            self.assertEqual(len(caps), 4)
            self.assertTrue(all(not c.enabled for c in caps),
                            'renderer MCP capabilities must stay disabled')


# ---------------------------------------------------------------------------
# Real-browser provider contract (spec §15, §16, §22)
# ---------------------------------------------------------------------------
_R3F_MARKER_OK = (
    "<script>(function(){var cv=document.getElementById('c');"
    "try{var gl=cv.getContext('webgl2')||cv.getContext('webgl');"
    + MARKER +
    "={provider:'react_three_fiber',initialized:true,"
    "canvas:!!(cv&&cv.isConnected),webgl:!!gl};}"
    "catch(e){"
    + MARKER +
    "={provider:'react_three_fiber',initialized:false,error:String(e)};}"
    "})();</script>"
)


class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class TestU95ProviderContract(unittest.TestCase):
    """Real Chromium through the canonical provider; the test-owned server
    serves deterministic pages that exercise the marker/canvas/WebGL probe
    contract the generated R3F/Spline scaffolds implement."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.provider = cls.env['nexora.provider.playwright']

        cls.www = tempfile.mkdtemp(prefix='nexora-u95-www-')

        def _write(name, html):
            with open(os.path.join(cls.www, name), 'w', encoding='utf-8') as fh:
                fh.write(html)

        canvas = '<canvas id="c" width="800" height="600"></canvas>'
        _write('r3f_ok.html',
               '<html><head><title>U95 R3F OK</title></head><body>' + canvas
               + _R3F_MARKER_OK + '</body></html>')
        # A: canvas missing (app marker truthfully reports canvas:false).
        _write('r3f_no_canvas.html',
               '<html><head><title>U95 no canvas</title></head><body>'
               '<script>' + MARKER + '={provider:\'react_three_fiber\','
               'initialized:true,canvas:false,webgl:true};</script></body></html>')
        # B: WebGL unavailable (getContext stubbed to null, marker truthful).
        _write('r3f_no_webgl.html',
               '<html><head><title>U95 no webgl</title></head><body>' + canvas +
               '<script>HTMLCanvasElement.prototype.getContext=function(){return null;};</script>'
               '<script>' + MARKER + '={provider:\'react_three_fiber\','
               'initialized:true,canvas:true,webgl:false};</script></body></html>')
        # C: R3F initialization failure (marker reports failure).
        _write('r3f_init_fail.html',
               '<html><head><title>U95 init fail</title></head><body>' + canvas +
               '<script>' + MARKER + '={provider:\'react_three_fiber\','
               'initialized:false,error:\'boom\'};</script></body></html>')
        # Marker never appears (onCreated never fired).
        _write('r3f_marker_missing.html',
               '<html><head><title>U95 marker missing</title></head><body>'
               + canvas + "<script>console.log('plain log');</script></body></html>")
        # G: SwiftShader warning must stay observable but not fail.
        _write('r3f_swiftshader.html',
               '<html><head><title>U95 swiftshader</title></head><body>' + canvas
               + _R3F_MARKER_OK
               + "<script>console.warn('Your browser uses SwiftShader software rendering');</script>"
               '</body></html>')
        # Spline: marker-only contract.
        _write('spline_ok.html',
               '<html><head><title>U95 spline ok</title></head><body>' + canvas +
               '<script>' + MARKER + '={provider:\'spline\',initialized:true,'
               'scene_loaded:true};</script></body></html>')
        _write('spline_missing.html',
               '<html><head><title>U95 spline missing</title></head><body>' + canvas +
               "<script>console.log('no marker here');</script></body></html>")
        _write('spline_fail.html',
               '<html><head><title>U95 spline fail</title></head><body>' + canvas +
               '<script>' + MARKER + '={provider:\'spline\',initialized:false,'
               'scene_loaded:false};</script></body></html>')
        _write('react.html',
               '<html><head><title>U95 react</title></head><body><h1>plain</h1></body></html>')

        cls.server = socketserver.TCPServer(
            ('127.0.0.1', 0), functools.partial(_Handler, directory=cls.www))
        cls.server.allow_reuse_address = True
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f'http://127.0.0.1:{cls.port}'
        cls.evidence_root = tempfile.mkdtemp(prefix='nexora-u95-evidence-')

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

    def _validate(self, page, renderer, name, routes=None, timeout_ms=15000,
                  url=None):
        evidence_dir = os.path.join(self.evidence_root, name)
        # url is the SERVER ROOT; routes carry the page paths (the provider
        # concatenates base_url + route for each navigation).
        payload = {'action': 'validate', 'url': url or self.base_url,
                   'routes': routes or (['/' + page] if page else ['/']),
                   'timeout_ms': timeout_ms,
                   'evidence_dir': evidence_dir}
        if renderer is not None:
            payload['renderer'] = renderer
        request = ProviderExecutionRequest(
            namespace='nexora.provider.playwright', payload=payload, timeout=90.0)
        return self.provider.execute(request)

    def test_01_r3f_healthy_runtime(self):
        result = self._validate('r3f_ok.html', 'react_three_fiber', 'r3f_ok')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['provider'], 'react_three_fiber')
        self.assertEqual(rr['status'], 'healthy')
        self.assertIs(rr['initialized'], True)
        self.assertIs(rr['canvas_present'], True)
        self.assertGreater(rr['canvas_width'], 0)
        self.assertGreater(rr['canvas_height'], 0)
        self.assertIs(rr['webgl_available'], True)
        self.assertEqual(rr['errors'], [])
        self.assertEqual(rr['runtime_marker']['provider'], 'react_three_fiber')
        # Home-route evidence carries the probe (U9.4 route contract intact).
        route = result.data['routes'][0]
        self.assertIn('renderer_runtime', route)
        self.assertTrue(route['success'])

    def test_02_r3f_canvas_missing_fails(self):
        result = self._validate('r3f_no_canvas.html', 'react_three_fiber', 'r3f_nc')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'failed')
        self.assertIn('r3f_canvas_missing', rr['errors'])
        self.assertIn('r3f_canvas_zero_width', rr['errors'])

    def test_03_r3f_webgl_unavailable_fails(self):
        result = self._validate('r3f_no_webgl.html', 'react_three_fiber', 'r3f_nw')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'failed')
        self.assertIn('webgl_unavailable', rr['errors'])
        self.assertIn('r3f_marker_webgl_false', rr['errors'])

    def test_04_r3f_initialization_failure_fails(self):
        result = self._validate('r3f_init_fail.html', 'react_three_fiber', 'r3f_if')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'failed')
        self.assertIn('r3f_runtime_not_initialized', rr['errors'])

    def test_05_r3f_marker_missing_fails(self):
        result = self._validate('r3f_marker_missing.html', 'react_three_fiber', 'r3f_mm')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'failed')
        self.assertIn('runtime_marker_missing', rr['errors'])
        # Independent facts are still recorded truthfully.
        self.assertIs(rr['canvas_present'], True)
        self.assertIs(rr['webgl_available'], True)

    def test_06_spline_healthy_runtime(self):
        result = self._validate('spline_ok.html', 'spline', 'spline_ok')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['provider'], 'spline')
        self.assertEqual(rr['status'], 'healthy')
        self.assertIs(rr['initialized'], True)
        self.assertIs(rr['scene_loaded'], True)
        self.assertEqual(rr['errors'], [])

    def test_07_spline_marker_missing_fails(self):
        result = self._validate('spline_missing.html', 'spline', 'spline_mm')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'failed')
        self.assertIn('runtime_marker_missing', rr['errors'])

    def test_08_spline_initialization_failure_fails(self):
        result = self._validate('spline_fail.html', 'spline', 'spline_fail')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'failed')
        self.assertIn('spline_runtime_not_initialized', rr['errors'])
        self.assertIn('spline_scene_not_loaded', rr['errors'])

    def test_09_react_not_applicable(self):
        result = self._validate('react.html', 'react', 'react_na')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['provider'], 'react')
        self.assertEqual(rr['status'], 'not_applicable')
        # No canvas/WebGL requirement is imposed on plain React.
        self.assertIsNone(rr.get('canvas_present'))

    def test_10_swiftshader_warning_observable_not_blocking(self):
        result = self._validate('r3f_swiftshader.html', 'react_three_fiber',
                                'swiftshader')
        self.assertTrue(result.success, result.error)
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'healthy',
                         'SwiftShader/software rendering must not fail runtime')
        self.assertTrue(any('SwiftShader' in w.get('text', '')
                            for w in result.data['console_warnings']))
        self.assertEqual(result.data['console_errors'], [])

    def test_11_u94_contract_without_renderer_unchanged(self):
        result = self._validate('r3f_ok.html', None, 'u94_compat')
        self.assertTrue(result.success, result.error)
        self.assertNotIn('renderer_runtime', result.data,
                         'U9.4-only callers see the exact U9.4 output shape')
        self.assertNotIn('renderer_runtime', result.data['routes'][0])
        self.assertTrue(result.data['routes'][0]['success'])

    def test_12_navigation_failure_preserves_u94_semantics(self):
        baseline = _chrome_pids()
        result = self._validate(None, 'spline', 'nav_fail',
                                routes=['/'], timeout_ms=4000,
                                url='http://10.255.255.1:9999')
        self.assertTrue(result.success, result.error)
        route = result.data['routes'][0]
        self.assertFalse(route['success'])
        self.assertTrue(str(route['error']).startswith('navigation_failed'))
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'failed')
        self.assertIn('renderer_probe_skipped_navigation_failed', rr['errors'])
        self.assertTrue(_wait_no_new_chrome(baseline),
                        'no orphan Chromium after failed navigation')

    def test_13_renderer_probe_scoped_to_first_route(self):
        # The engine's route contract always puts home first; the renderer
        # probe runs on the FIRST route only and never on additional routes.
        result = self._validate(None, 'react_three_fiber', 'first_route',
                                routes=['/r3f_ok.html', '/react.html'])
        self.assertTrue(result.success, result.error)
        routes = result.data['routes']
        self.assertEqual(len(routes), 2)
        self.assertTrue(routes[0]['success'])
        self.assertTrue(routes[1]['success'])
        self.assertIn('renderer_runtime', routes[0],
                      'first (home) route must carry the renderer probe')
        self.assertNotIn('renderer_runtime', routes[1],
                         'additional routes must not be renderer-probed')
        rr = result.data['renderer_runtime']
        self.assertEqual(rr['status'], 'healthy')

    def test_14_browser_cleanup_no_orphan_chromium(self):
        baseline = _chrome_pids()
        result = self._validate('r3f_ok.html', 'react_three_fiber', 'cleanup_1')
        self.assertTrue(result.success, result.error)
        self.assertTrue(_wait_no_new_chrome(baseline),
                        'owned Chromium tree must be gone after validate')


# ---------------------------------------------------------------------------
# Engine-level integration (spec §6, §14, §19, §21) — spy provider
# ---------------------------------------------------------------------------
class TestU95EngineIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ws = tempfile.mkdtemp(prefix='nexora-u95-engine-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws, ignore_errors=True)

    def _artifact(self, design=None, build_acceptance=None):
        return WebsiteGenerationArtifact(
            design=design if design is not None else {},
            validation=ValidationReport(
                passed=True, accessibility_score=100, seo_score=100,
                performance_score=100, issues=[], build_acceptance=(
                    build_acceptance if build_acceptance is not None
                    else {"ran": True, "failed": False})),
            workspace=Workspace(project_path=self.ws),
            content=Content(pages={'/': {}}),
            architecture=ArchitectureModel(component_hierarchy={}),
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

    def _spy(self, renderer_runtime=None, console_warnings=None, console_errors=None):
        calls = []
        data = {
            'status': 'completed', 'success': True,
            'routes': [{'route': '/', 'requested_url': 'http://127.0.0.1:3456/',
                        'final_url': 'http://127.0.0.1:3456/', 'status': 200,
                        'title': 'Home', 'success': True, 'error': None,
                        'console_messages': [], 'console_errors': console_errors or [],
                        'console_warnings': console_warnings or [],
                        'page_errors': [], 'network_failures': [], 'http_errors': [],
                        'screenshot_captured': True,
                        'screenshot_path': os.path.join(self.ws, 'route_home.png')}],
            'console_errors': console_errors or [],
            'console_warnings': console_warnings or [],
            'console_messages': [], 'page_errors': [],
            'network_failures': [], 'http_errors': [], 'navigation_errors': [],
            'screenshots': [os.path.join(self.ws, 'route_home.png')],
        }
        if renderer_runtime is not None:
            data['renderer_runtime'] = renderer_runtime

        def execute(request):
            calls.append(request)
            return ProviderExecutionResult(success=True, data=data, error=None)

        return SimpleNamespace(execute=execute, calls=calls)

    def _healthy_rr(self, provider):
        return {'provider': provider, 'status': 'healthy', 'initialized': True,
                'canvas_present': True, 'canvas_width': 800, 'canvas_height': 600,
                'webgl_available': True, 'scene_loaded': None,
                'runtime_marker': {'provider': provider, 'initialized': True},
                'errors': [], 'diagnostics': {}}

    def test_renderer_identity_sent_to_provider(self):
        spy = self._spy(renderer_runtime=self._healthy_rr('react_three_fiber'))
        res = self._engine().execute(
            self._artifact(design={'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy)))
        self.assertTrue(res.success, res.error)
        self.assertEqual(spy.calls[0].payload['renderer'], 'react_three_fiber')

    def test_r3f_healthy_evidence_no_blocking_issue(self):
        spy = self._spy(renderer_runtime=self._healthy_rr('react_three_fiber'))
        res = self._engine().execute(
            self._artifact(design={'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy)))
        self.assertTrue(res.success)
        evidence = res.metadata['browser_validation']
        self.assertEqual(evidence['renderer_runtime']['status'], 'healthy')
        self.assertFalse(any(i['type'] == 'error' for i in
                             res.artifact.validation.issues))

    def test_r3f_webgl_failure_blocks(self):
        rr = {'provider': 'react_three_fiber', 'status': 'failed',
              'errors': ['webgl_unavailable', 'r3f_marker_webgl_false'],
              'runtime_marker': None, 'diagnostics': {}}
        spy = self._spy(renderer_runtime=rr)
        res = self._engine().execute(
            self._artifact(design={'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy)))
        self.assertFalse(res.success, 'WebGL failure must block browser validation')
        issues = res.artifact.validation.issues
        self.assertTrue(any(i['type'] == 'error' and i['category'] == 'browser'
                            and 'webgl_unavailable' in i['message'] for i in issues))
        evidence = res.metadata['browser_validation']
        self.assertEqual(evidence['renderer_runtime']['status'], 'failed')
        self.assertIn('Renderer runtime validation failed', evidence['error'])
        self.assertFalse(res.artifact.validation.passed)

    def test_spline_scene_not_loaded_blocks(self):
        rr = {'provider': 'spline', 'status': 'failed',
              'errors': ['spline_scene_not_loaded'],
              'runtime_marker': None, 'diagnostics': {}}
        spy = self._spy(renderer_runtime=rr)
        res = self._engine().execute(
            self._artifact(design={'provider': 'spline'}),
            self._runtime(self._env(spy)))
        self.assertFalse(res.success, 'Spline scene-load failure must block')
        self.assertTrue(any('spline_scene_not_loaded' in i['message']
                            for i in res.artifact.validation.issues))

    def test_react_not_applicable_no_blocking(self):
        spy = self._spy()  # no renderer_runtime in provider data
        res = self._engine().execute(
            self._artifact(design={'provider': 'react'}),
            self._runtime(self._env(spy)))
        self.assertTrue(res.success, res.error)
        self.assertEqual(spy.calls[0].payload['renderer'], 'react')
        evidence = res.metadata['browser_validation']
        self.assertEqual(evidence['renderer_runtime']['status'], 'not_applicable')
        self.assertEqual(evidence['renderer_runtime']['reason'],
                         'react_has_no_renderer_runtime_contract')
        self.assertFalse(any(i['type'] == 'error' for i in
                             res.artifact.validation.issues))

    def test_unknown_provider_identity_fails_final_acceptance(self):
        # Phase 47.15 (U9.6) §12: an unknown renderer identity is never
        # guessed and never silently accepted - the final acceptance gate
        # fails with renderer_identity_unknown. The U9.5 renderer EVIDENCE
        # remains not_applicable (no probe is sent).
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(design={'provider': 'webgpu_next_gen'}),
            self._runtime(self._env(spy)))
        self.assertFalse(res.success,
                         'unknown renderer identity must fail final acceptance')
        self.assertNotIn('renderer', spy.calls[0].payload,
                         'unknown identity must not be guessed or sent')
        evidence = res.metadata['browser_validation']
        self.assertEqual(evidence['renderer_runtime']['status'], 'not_applicable')
        self.assertEqual(evidence['renderer_runtime']['reason'],
                         'renderer_identity_unavailable')
        final = evidence['final_acceptance']
        self.assertFalse(final['accepted'])
        self.assertEqual(final['renderer']['reason'], 'renderer_identity_unknown')
        self.assertTrue(any(b.get('code') == 'renderer_identity_unknown'
                            for b in final['blocking_issues']))

    def test_missing_design_identity_fails_final_acceptance(self):
        # Phase 47.15 (U9.6) §12: missing renderer identity fails the final
        # acceptance gate (renderer_identity_missing); it is never converted
        # into not_applicable at the acceptance level.
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(design={}), self._runtime(self._env(spy)))
        self.assertFalse(res.success,
                         'missing renderer identity must fail final acceptance')
        self.assertNotIn('renderer', spy.calls[0].payload)
        evidence = res.metadata['browser_validation']
        self.assertEqual(
            evidence['renderer_runtime']['status'], 'not_applicable')
        final = evidence['final_acceptance']
        self.assertFalse(final['accepted'])
        self.assertEqual(final['renderer']['reason'], 'renderer_identity_missing')
        self.assertTrue(any(b.get('code') == 'renderer_identity_missing'
                            for b in final['blocking_issues']))

    def test_r3f_missing_renderer_evidence_blocks(self):
        spy = self._spy()  # provider returned no renderer_runtime evidence
        res = self._engine().execute(
            self._artifact(design={'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy)))
        self.assertFalse(res.success,
                         'missing renderer evidence for R3F must never pass')
        self.assertTrue(any('renderer_runtime_evidence_missing' in i['message']
                            for i in res.artifact.validation.issues))

    def test_spline_missing_renderer_evidence_blocks(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact(design={'provider': 'spline'}),
            self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        evidence = res.metadata['browser_validation']
        self.assertEqual(evidence['renderer_runtime']['status'], 'failed')

    def test_preview_unavailable_renderer_never_probed(self):
        spy = self._spy(renderer_runtime=self._healthy_rr('react_three_fiber'))
        res = self._engine().execute(
            self._artifact(design={'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy, preview=False)))
        self.assertFalse(res.success)
        self.assertEqual(res.metadata['browser_validation']['error'],
                         'preview_unavailable')
        self.assertEqual(spy.calls, [],
                         'browser/renderer provider must not launch without preview')

    def test_swiftshader_warning_does_not_block(self):
        warnings = [{'type': 'warning',
                     'text': 'Your browser uses SwiftShader software rendering'}]
        spy = self._spy(renderer_runtime=self._healthy_rr('react_three_fiber'),
                        console_warnings=warnings)
        res = self._engine().execute(
            self._artifact(design={'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy)))
        self.assertTrue(res.success,
                        'SwiftShader warning alone must never fail validation')
        self.assertTrue(any(i['type'] == 'warning' and 'SwiftShader' in i['message']
                            for i in res.artifact.validation.issues))

    def test_renderer_failure_propagates_to_report_and_metadata(self):
        rr = {'provider': 'react_three_fiber', 'status': 'failed',
              'errors': ['r3f_canvas_missing'],
              'runtime_marker': None, 'diagnostics': {'canvas_present': False}}
        spy = self._spy(renderer_runtime=rr)
        res = self._engine().execute(
            self._artifact(design={'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        report = res.artifact.validation
        self.assertFalse(report.passed)
        self.assertEqual(report.browser_validation['renderer_runtime'], rr)
        self.assertEqual(res.metadata['browser_validation']['renderer_runtime'], rr)


# ---------------------------------------------------------------------------
# Real production-path scenarios (spec §23) — opt-in
# ---------------------------------------------------------------------------
@unittest.skipUnless(os.environ.get('NEXORA_U95_RENDERER') == '1',
                     'opt-in full production-path renderer scenarios (set NEXORA_U95_RENDERER=1)')
class TestU95ControlledScenarios(unittest.TestCase):
    """React / R3F / Spline through the real production path:
    generate -> install -> build -> preview -> health -> browser validation
    -> renderer runtime probe. External AI stubbed at the existing boundary
    only; real Chromium always."""

    SCENARIOS = [
        ('react', 'Build a modern SaaS landing page with pricing and testimonials.'),
        ('r3f', 'Build an immersive 3d product showcase website with WebGL.'),
        ('spline', 'Build a creative agency website featuring a Spline scene at '
                   + VALID_SPLINE_URL + ' .'),
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
        import re
        if task_type == 'ai_code_patch':
            match = re.search(r'named\s+([A-Za-z0-9_]+)', str(prompt or ''))
            name = match.group(1) if match else 'GeneratedSection'
            return {'full_content':
                    f"function {name}() {{ return <section><h2>{name}</h2></section> }}"}
        return {}

    def _preview_contract(self, session):
        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'preview')], limit=1)
        preview_rt = self.env['nexora.preview_runtime'].search(
            [('runtime_id', '=', runtime.id)], limit=1) if runtime else None
        return runtime, preview_rt

    def _direct_renderer_evidence(self, preview_url, renderer):
        provider = self.env['nexora.provider.playwright']
        request = ProviderExecutionRequest(
            namespace='nexora.provider.playwright',
            payload={'action': 'validate', 'url': preview_url, 'routes': ['/'],
                     'timeout_ms': 30000, 'renderer': renderer},
            timeout=180.0,
        )
        return provider.execute(request)

    def test_controlled_scenarios_renderer_runtime_via_production_path(self):
        service = self.env['nexora.builder_session_service']
        preview_service = self.env['nexora.preview_service']
        for name, requirements in self.SCENARIOS:
            ws = os.path.join(SCENARIO_ROOT, name)
            os.makedirs(ws, exist_ok=True)
            self.cr.execute('SAVEPOINT u95_scenario')
            session = None
            try:
                cfg = self.env['nexora.builder_configuration'].create(
                    {'name': f'U95 {name}'})
                session = self.env['nexora.builder_session'].create({
                    'name': f'U95 {name}', 'builder_configuration_id': cfg.id,
                    'project_name': f'U95 {name}', 'target_workspace_path': ws,
                })
                raised = None
                try:
                    ok = service.run_generation(session, requirements=requirements)
                except Exception as e:
                    raised = e

                runtime, preview_rt = self._preview_contract(session)
                self.assertTrue(runtime and preview_rt,
                                f'{name}: preview runtime records missing')
                self.assertEqual(runtime.status, 'running')
                self.assertEqual(runtime.health, 'healthy')
                preview_url = preview_rt.preview_url

                if name == 'react':
                    self.assertIsNone(raised, f'react: {raised}')
                    self.assertTrue(ok, 'react: run_generation failed')
                    self.assertEqual(session.status, 'ai_reviewing')
                    result = self._direct_renderer_evidence(preview_url, 'react')
                    self.assertTrue(result.success, result.error)
                    rr = result.data['renderer_runtime']
                    self.assertEqual(rr['status'], 'not_applicable')
                    self.assertEqual(result.data['console_errors'], [])
                elif name == 'r3f':
                    # Pipeline success itself proves the in-pipeline renderer
                    # probe passed (engine sends renderer='react_three_fiber').
                    self.assertIsNone(raised, f'r3f: {raised}')
                    self.assertTrue(ok, 'r3f: run_generation failed')
                    self.assertEqual(session.status, 'ai_reviewing')
                    result = self._direct_renderer_evidence(
                        preview_url, 'react_three_fiber')
                    self.assertTrue(result.success, result.error)
                    rr = result.data['renderer_runtime']
                    self.assertEqual(rr['status'], 'healthy',
                                     f'r3f renderer probe failed: {rr}')
                    self.assertIs(rr['canvas_present'], True)
                    self.assertGreater(rr['canvas_width'], 0)
                    self.assertGreater(rr['canvas_height'], 0)
                    self.assertIs(rr['webgl_available'], True)
                    self.assertIs(rr['initialized'], True)
                    self.assertEqual(rr['runtime_marker']['provider'],
                                     'react_three_fiber')
                    self.assertEqual(result.data['console_errors'], [])
                else:  # spline with the known fake scene URL
                    self.assertIsNotNone(
                        raised, 'spline: fake scene must fail browser validation')
                    self.assertIn('Browser validation failed', str(raised))
                    self.assertEqual(session.status, 'failed')
                    # The preview contract survives the later-stage failure.
                    result = self._direct_renderer_evidence(preview_url, 'spline')
                    self.assertTrue(result.success, result.error)
                    rr = result.data['renderer_runtime']
                    self.assertEqual(rr['status'], 'failed',
                                     'fake scene must fail the Spline runtime probe')
                    # The marker is present but truthful: the Spline runtime
                    # initialized (onLoad fired) yet the scene resource was
                    # NOT retrievable, so scene_loaded is false.
                    marker = rr.get('runtime_marker') or {}
                    self.assertIs(marker.get('scene_loaded'), False,
                                   'a 403 scene must never report scene_loaded true')
                    self.assertEqual(marker.get('scene_status'), 403)
                    self.assertIn('spline_scene_not_loaded', rr['errors'])
                    self.assertTrue(result.data['console_errors'],
                                    'fake scene must still surface console errors')
            finally:
                try:
                    if session is not None:
                        preview_service.stop_workspace_preview(session)
                except Exception:
                    pass
                self.cr.execute('ROLLBACK TO SAVEPOINT u95_scenario')
                self.cr.execute('RELEASE SAVEPOINT u95_scenario')


if __name__ == '__main__':
    unittest.main()
