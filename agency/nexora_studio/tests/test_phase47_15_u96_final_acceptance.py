# -*- coding: utf-8 -*-
"""Phase 47.15 (U9.6) — Final unified validation & acceptance gate.

The SAME ValidationEngine (browser phase) computes ONE deterministic final
acceptance decision from the EXISTING evidence:
  * build acceptance   (ValidationReport.build_acceptance — U9.2)
  * preview runtime    (browser_validation.preview_* — U9.3)
  * browser validation (browser_validation.status/error — U9.4)
  * renderer runtime   (browser_validation.renderer_runtime — U9.5)

The decision is stored in ValidationReport.final_acceptance and in the
existing context metadata (no second report model, no new pipeline state).
The gate is pure: it consumes dicts only and never executes infrastructure
(no npm/build/preview/browser/connector/DB work). React is not_applicable
for renderer acceptance; a missing/unknown renderer identity FAILS (never
guessed). Warnings never block acceptance.

No FinalValidationService / AcceptanceService / QualityGateService /
second ValidationEngine / second ValidationReport / second pipeline exists.
"""
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODOO_ROOT = r'D:\ODOO'
SCENARIO_ROOT = os.path.join(ODOO_ROOT, '.u96_acceptance')
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


# ---------------------------------------------------------------------------
# Synthetic evidence builders (the gate consumes dicts only)
# ---------------------------------------------------------------------------
def _ba_passed():
    return {"ran": True, "failed": False, "build": {"success": True},
            "build_output_path": "/w/dist", "exit_code": 0}


def _rr_react():
    return {"provider": "react", "status": "not_applicable",
            "reason": "react_has_no_renderer_runtime_contract"}


def _rr_r3f_healthy():
    return {"provider": "react_three_fiber", "status": "healthy",
            "initialized": True, "canvas_present": True, "canvas_width": 800,
            "canvas_height": 600, "webgl_available": True, "errors": []}


def _rr_spline_healthy():
    return {"provider": "spline", "status": "healthy", "initialized": True,
            "scene_loaded": True, "errors": []}


def _evidence(renderer_runtime, status='healthy', failed=False, error=None,
              ran=True, preview_health='healthy', preview_url='http://127.0.0.1:3456',
              preview_process_id=9999):
    return {
        "ran": ran, "skipped": False, "failed": failed, "error": error,
        "status": status,
        "preview_url": preview_url, "preview_launcher": "vite",
        "preview_health": preview_health, "preview_process_id": preview_process_id,
        "preview_allocated_port": 3456,
        "routes": [{"route": "/", "success": True}],
        "console_errors": [], "console_warnings": [], "page_errors": [],
        "network_failures": [], "http_errors": [], "navigation_errors": [],
        "screenshots": [],
        "renderer_runtime": renderer_runtime,
    }


# ---------------------------------------------------------------------------
# Acceptance matrix (spec §6, §7, §21) — pure function tests
# ---------------------------------------------------------------------------
class TestU96AcceptanceMatrix(unittest.TestCase):
    """Direct tests of ValidationEngine._compute_final_acceptance over
    synthetic evidence. Mocks/stubs only — no infrastructure is executed."""

    def _final(self, ba, ev, rid, raw='', blocking=None, warnings=None):
        return ValidationEngine._compute_final_acceptance(
            ba, ev, rid, raw, blocking or [], warnings or [])

    def _codes(self, final):
        return [b['code'] for b in final['blocking_issues'] if b.get('code')]

    def test_acceptance_matrix(self):
        ev = lambda rr: _evidence(rr)  # noqa: E731
        cases = [
            # (name, build, evidence, renderer_id, raw, blocking, warnings, expected, codes)
            ("1_react_all_pass", _ba_passed(), ev(_rr_react()), 'react', 'react',
             [], [], True, []),
            ("2_r3f_all_pass", _ba_passed(), ev(_rr_r3f_healthy()), 'react_three_fiber',
             'react_three_fiber', [], [], True, []),
            ("3_spline_all_pass", _ba_passed(), ev(_rr_spline_healthy()), 'spline',
             'spline', [], [], True, []),
            ("4_build_failed", {"ran": True, "failed": True, "error": "npm err"},
             ev(_rr_react()), 'react', 'react', [], [], False,
             ['build_acceptance_failed']),
            ("5_build_evidence_missing", {}, ev(_rr_react()), 'react', 'react',
             [], [], False, ['build_acceptance_not_ran']),
            ("6_preview_missing",
             _ba_passed(), _evidence(_rr_react(), preview_url=None,
                                     preview_process_id=None),
             'react', 'react', [], [], False, ['preview_acceptance_failed']),
            ("7_preview_unhealthy",
             _ba_passed(), _evidence(_rr_react(), preview_health='critical'),
             'react', 'react', [], [], False, ['preview_acceptance_failed']),
            ("8_browser_failed",
             _ba_passed(), _evidence(_rr_react(), status='failed', failed=True,
                                     error='console error'), 'react', 'react',
             [], [], False, ['browser_acceptance_failed']),
            ("9_browser_not_executed",
             _ba_passed(), _evidence(_rr_react(), ran=False), 'react', 'react',
             [], [], False, ['browser_validation_not_executed']),
            ("10_r3f_renderer_failed",
             _ba_passed(), ev({"provider": "react_three_fiber", "status": "failed",
                               "errors": ["webgl_unavailable"]}),
             'react_three_fiber', 'react_three_fiber', [], [], False,
             ['renderer_acceptance_failed']),
            ("11_r3f_renderer_missing",
             _ba_passed(), ev({}), 'react_three_fiber', 'react_three_fiber',
             [], [], False, ['renderer_acceptance_failed']),
            ("12_spline_renderer_failed",
             _ba_passed(), ev({"provider": "spline", "status": "failed",
                               "errors": ["spline_scene_not_loaded"]}),
             'spline', 'spline', [], [], False, ['renderer_acceptance_failed']),
            ("13_spline_renderer_missing",
             _ba_passed(), ev({}), 'spline', 'spline', [], [], False,
             ['renderer_acceptance_failed']),
            ("14_unknown_renderer",
             _ba_passed(), ev(_rr_react()), None, 'webgpu_next_gen', [], [],
             False, ['renderer_identity_unknown']),
            ("14b_missing_renderer_identity",
             _ba_passed(), ev(_rr_react()), None, '', [], [], False,
             ['renderer_identity_missing']),
            ("15_react_not_applicable_no_evidence",
             _ba_passed(), ev({}), 'react', 'react', [], [], True, []),
            ("16_warnings_only",
             _ba_passed(), ev(_rr_react()), 'react', 'react', [],
             [{'type': 'warning', 'category': 'browser', 'message': 'SwiftShader'}],
             True, []),
            ("17_blocking_issue_despite_positive_subsystems",
             _ba_passed(), ev(_rr_react()), 'react', 'react',
             [{'type': 'error', 'category': 'browser', 'message': 'console error'}],
             [], False, []),
            ("17b_non_acceptance_issue_observable_not_blocking",
             # Pre-U9.6 the pipeline never gated on design/seo/dynamic-
             # validation error issues; the final gate preserves that
             # behaviour and scopes blocking to the acceptance layers.
             _ba_passed(), ev(_rr_react()), 'react', 'react',
             [{'type': 'error', 'category': 'validation',
               'message': 'Dynamic validation step(s) failed'}],
             [], True, []),
        ]
        for name, ba, evidence, rid, raw, blocking, warnings, expected, codes in cases:
            final = self._final(ba, evidence, rid, raw, blocking, warnings)
            self.assertEqual(final['accepted'], expected, name)
            self.assertEqual(final['status'], 'accepted' if expected else 'failed', name)
            for code in codes:
                self.assertIn(code, self._codes(final), f'{name}: missing code {code}')

    def test_18_deterministic_repeated_evaluation(self):
        ba = _ba_passed()
        ev = _evidence(_rr_r3f_healthy())
        blocking = [{'type': 'error', 'category': 'browser', 'message': 'x'}]
        a = self._final(ba, ev, 'react_three_fiber', 'react_three_fiber', blocking)
        b = self._final(ba, ev, 'react_three_fiber', 'react_three_fiber', blocking)
        for key in ('accepted', 'status', 'blocking_issues', 'build', 'preview',
                    'browser', 'renderer'):
            self.assertEqual(a[key], b[key], key)

    def test_react_renderer_na_never_blocks_even_with_evidence(self):
        # React with a (hypothetical) non-applicable marker still accepts.
        rr = {"provider": "react", "status": "not_applicable"}
        final = self._final(_ba_passed(), _evidence(rr), 'react', 'react')
        self.assertTrue(final['accepted'])
        self.assertEqual(final['renderer']['status'], 'not_applicable')


# ---------------------------------------------------------------------------
# Engine integration (spy provider) — decision recorded + propagated
# ---------------------------------------------------------------------------
class TestU96EngineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = tempfile.mkdtemp(prefix='nexora-u96-engine-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws, ignore_errors=True)

    def _artifact(self, design):
        return WebsiteGenerationArtifact(
            design=design,
            validation=ValidationReport(
                passed=True, accessibility_score=100, seo_score=100,
                performance_score=100, issues=[],
                build_acceptance=_ba_passed()),
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

    def _spy(self, renderer_runtime=None, console_warnings=None):
        calls = []
        data = {
            'status': 'completed', 'success': True,
            'routes': [{'route': '/', 'requested_url': 'http://127.0.0.1:3456/',
                        'final_url': 'http://127.0.0.1:3456/', 'status': 200,
                        'title': 'Home', 'success': True, 'error': None,
                        'console_messages': [], 'console_errors': [],
                        'console_warnings': console_warnings or [],
                        'page_errors': [], 'network_failures': [], 'http_errors': [],
                        'screenshot_captured': True,
                        'screenshot_path': os.path.join(self.ws, 'route_home.png')}],
            'console_errors': [], 'console_warnings': console_warnings or [],
            'console_messages': [], 'page_errors': [], 'network_failures': [],
            'http_errors': [], 'navigation_errors': [],
            'screenshots': [os.path.join(self.ws, 'route_home.png')],
        }
        if renderer_runtime is not None:
            data['renderer_runtime'] = renderer_runtime

        def execute(request):
            calls.append(request)
            return ProviderExecutionResult(success=True, data=data, error=None)

        return SimpleNamespace(execute=execute, calls=calls)

    def test_react_all_pass_records_final_acceptance(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact({'provider': 'react'}), self._runtime(self._env(spy)))
        self.assertTrue(res.success, res.error)
        self.assertEqual(len(spy.calls), 1,
                         'final gate must not re-invoke the browser provider')
        report = res.artifact.validation
        final = report.final_acceptance
        self.assertTrue(final['accepted'])
        self.assertEqual(final['status'], 'accepted')
        self.assertEqual(final['build']['status'], 'passed')
        self.assertEqual(final['preview']['status'], 'passed')
        self.assertEqual(final['browser']['status'], 'passed')
        self.assertEqual(final['renderer']['status'], 'not_applicable')
        self.assertEqual(res.metadata['final_acceptance'], final)
        self.assertEqual(res.metadata['browser_validation']['final_acceptance'], final)
        self.assertTrue(report.passed)

    def test_r3f_all_pass_final_acceptance(self):
        spy = self._spy(renderer_runtime=_rr_r3f_healthy())
        res = self._engine().execute(
            self._artifact({'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy)))
        self.assertTrue(res.success, res.error)
        final = res.artifact.validation.final_acceptance
        self.assertTrue(final['accepted'])
        self.assertEqual(final['renderer']['status'], 'passed')

    def test_spline_all_pass_final_acceptance(self):
        spy = self._spy(renderer_runtime=_rr_spline_healthy())
        res = self._engine().execute(
            self._artifact({'provider': 'spline'}), self._runtime(self._env(spy)))
        self.assertTrue(res.success, res.error)
        final = res.artifact.validation.final_acceptance
        self.assertTrue(final['accepted'])
        self.assertEqual(final['renderer']['status'], 'passed')

    def test_preview_missing_fails_final_acceptance(self):
        spy = self._spy(renderer_runtime=_rr_react())
        res = self._engine().execute(
            self._artifact({'provider': 'react'}),
            self._runtime(self._env(spy, preview=False)))
        self.assertFalse(res.success)
        self.assertEqual(spy.calls, [])
        final = res.artifact.validation.final_acceptance
        self.assertFalse(final['accepted'])
        self.assertEqual(final['preview']['status'], 'failed')
        self.assertTrue(any(b.get('code') == 'preview_acceptance_failed'
                            for b in final['blocking_issues']))

    def test_r3f_renderer_failure_fails_final_acceptance(self):
        rr = {'provider': 'react_three_fiber', 'status': 'failed',
              'errors': ['webgl_unavailable'], 'runtime_marker': None,
              'diagnostics': {}}
        spy = self._spy(renderer_runtime=rr)
        res = self._engine().execute(
            self._artifact({'provider': 'react_three_fiber'}),
            self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        final = res.artifact.validation.final_acceptance
        self.assertFalse(final['accepted'])
        self.assertEqual(final['renderer']['reason'], 'renderer_acceptance_failed')
        self.assertTrue(any(b.get('code') == 'renderer_acceptance_failed'
                            for b in final['blocking_issues']))
        self.assertFalse(res.artifact.validation.passed)

    def test_spline_scene_not_loaded_fails_final_acceptance(self):
        rr = {'provider': 'spline', 'status': 'failed',
              'errors': ['spline_scene_not_loaded'], 'runtime_marker': None,
              'diagnostics': {}}
        spy = self._spy(renderer_runtime=rr)
        res = self._engine().execute(
            self._artifact({'provider': 'spline'}), self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        self.assertFalse(res.artifact.validation.final_acceptance['accepted'])

    def test_browser_failure_fails_final_acceptance(self):
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
        spy = self._spy()
        # force the spy to return the console-error data
        spy.execute = lambda request: ProviderExecutionResult(success=True, data=data)
        spy.calls = []
        res = self._engine().execute(
            self._artifact({'provider': 'react'}), self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        final = res.artifact.validation.final_acceptance
        self.assertFalse(final['accepted'])
        self.assertEqual(final['browser']['status'], 'failed')

    def test_unknown_renderer_fails_final_acceptance(self):
        spy = self._spy()
        res = self._engine().execute(
            self._artifact({'provider': 'webgpu_next_gen'}),
            self._runtime(self._env(spy)))
        self.assertFalse(res.success)
        final = res.artifact.validation.final_acceptance
        self.assertFalse(final['accepted'])
        self.assertEqual(final['renderer']['reason'], 'renderer_identity_unknown')

    def test_warnings_do_not_block_final_acceptance(self):
        warnings = [{'type': 'warning', 'text': 'SwiftShader software rendering'}]
        spy = self._spy(console_warnings=warnings)
        res = self._engine().execute(
            self._artifact({'provider': 'react'}), self._runtime(self._env(spy)))
        self.assertTrue(res.success)
        final = res.artifact.validation.final_acceptance
        self.assertTrue(final['accepted'])
        self.assertTrue(final['warnings'], 'warnings must remain observable')

    def test_deterministic_across_engine_runs(self):
        spy = self._spy(renderer_runtime=_rr_r3f_healthy())
        env = self._env(spy)
        r1 = self._engine().execute(
            self._artifact({'provider': 'react_three_fiber'}), self._runtime(env))
        r2 = self._engine().execute(
            self._artifact({'provider': 'react_three_fiber'}), self._runtime(env))
        f1, f2 = r1.artifact.validation.final_acceptance, r2.artifact.validation.final_acceptance
        for key in ('accepted', 'status', 'blocking_issues', 'build', 'preview',
                    'browser', 'renderer'):
            self.assertEqual(f1[key], f2[key], key)


# ---------------------------------------------------------------------------
# Architecture integrity (spec §3, §25, §27)
# ---------------------------------------------------------------------------
class TestU96Architecture(unittest.TestCase):
    FORBIDDEN_OWNERS = (
        'FinalValidationService', 'AcceptanceService', 'AcceptanceGateService',
        'QualityGateService', 'ValidationCoordinator', 'BuildValidationService',
        'BrowserAcceptanceService', 'RendererAcceptanceService',
        'DeploymentValidationService', 'DeploymentManager', 'DeploymentService',
    )

    def test_no_parallel_acceptance_architecture(self):
        offenders = []
        for root, dirs, files in os.walk(os.path.join(ADDON, 'services')):
            dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
            for f in files:
                if not f.endswith('.py'):
                    continue
                with open(os.path.join(root, f), 'r', encoding='utf-8',
                          errors='ignore') as fh:
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
                         'no parallel acceptance owner may be introduced')

    def test_single_validation_owner_and_no_new_states(self):
        engines = os.listdir(os.path.join(ADDON, 'services', 'generation', 'engines'))
        self.assertEqual([f for f in engines if 'validation' in f.lower()],
                         ['validation_engine.py'])
        ctx = _src('services/generation/core/generation_context.py')
        self.assertNotIn('FinalAcceptanceReport', ctx)
        self.assertNotIn('RENDERER_VALIDATED', ctx)
        self.assertNotIn('FINAL_VALIDATED', ctx)
        self.assertNotIn('ACCEPTANCE_COMPLETE', ctx)
        pipe = _src('services/generation/pipeline/website_generation_pipeline.py')
        self.assertIn('GenerationState.BROWSER_VALIDATED: (OptimizationEngine(orchestrator), GenerationState.DEPLOYMENT_READY)', pipe)

    def test_final_acceptance_lives_in_existing_contracts(self):
        ctx = _src('services/generation/core/generation_context.py')
        self.assertIn('final_acceptance: Dict[str, Any] = field(default_factory=dict)', ctx)
        eng = _src('services/generation/engines/validation_engine.py')
        self.assertIn('_compute_final_acceptance', eng)
        self.assertIn('"final_acceptance"', eng)

    def test_final_gate_is_pure_no_infrastructure_execution(self):
        eng = _src('services/generation/engines/validation_engine.py')
        start = eng.index('def _compute_final_acceptance')
        body = eng[start:]
        for forbidden in ('nexora.provider', 'dependency_installer', 'preview_service',
                          'execute_local', 'install_project', 'build_project',
                          'start_workspace_preview', 'subprocess', 'sync_playwright',
                          'cr.execute', 'env['):
            self.assertNotIn(forbidden, body,
                             f'final gate must never execute infrastructure: {forbidden}')

    def test_no_infra_mutations_from_final_gate(self):
        # The gate only READS evidence and never writes connector/source/
        # credential/MCP state: its body contains no model write calls.
        eng = _src('services/generation/engines/validation_engine.py')
        start = eng.index('def _compute_final_acceptance')
        body = eng[start:]
        for forbidden in ('.create(', '.write(', '.unlink(', '.search(', 'ir.config_parameter'):
            self.assertNotIn(forbidden, body, forbidden)

    def test_db_readonly_integrity(self):
        registry = Registry.new('nexora_studio')
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            connectors = env['nexora.connector'].search([])
            self.assertEqual(len(connectors), 6)
            ids = sorted(c.connector_id for c in connectors)
            self.assertEqual(ids, ['context7_mcp', 'firecrawl_mcp', 'github_mcp',
                                   'gosom_mcp', 'penpot_mcp', 'tavily_mcp'])
            # Phase 47.16 added the 7th source (tavily_knowledge).
            sources = env['nexora.source_registry'].search([])
            self.assertEqual(len(sources), 7)
            self.assertIn('tavily_knowledge', sources.mapped('technical_name'))
            self.assertEqual(len(env['nexora.mcp_credential'].search([])), 5)
            self.assertEqual(len(env['nexora.mcp_server_config'].search([])), 6)
            self.assertEqual(len(env['nexora.capability_registry'].search([])), 17)
            self.assertTrue(all(not c.enabled for c in connectors))
            penpot_cap = env['nexora.capability_registry'].search(
                [('capability_id', '=', 'mcp.penpot.1.0.0')], limit=1)
            self.assertTrue(penpot_cap)
            self.assertEqual(penpot_cap.implementation_model, 'connector')
            self.assertFalse(penpot_cap.supports_local)
            self.assertFalse(penpot_cap.supports_remote)
            self.assertTrue(penpot_cap.enabled)
            renderer_caps = env['nexora.capability_registry'].search([
                ('capability_id', 'in', ('mcp.spline.1.0.0', 'mcp.threejs_docs.1.0.0',
                                         'mcp.r3f_docs.1.0.0', 'mcp.drei_docs.1.0.0'))])
            self.assertEqual(len(renderer_caps), 4)
            self.assertTrue(all(not c.enabled for c in renderer_caps))


# ---------------------------------------------------------------------------
# Real production path (spec §22, §23) — opt-in
# ---------------------------------------------------------------------------
@unittest.skipUnless(os.environ.get('NEXORA_U96_ACCEPTANCE') == '1',
                     'opt-in full production-path final acceptance (set NEXORA_U96_ACCEPTANCE=1)')
class TestU96ControlledScenarios(unittest.TestCase):
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
        # Capture the REAL final acceptance decision computed inside the
        # pipeline (observation only - the gate logic is not altered).
        cls.captured = []
        cls._orig_final = ValidationEngine.__dict__['_compute_final_acceptance'].__func__

        def _spy_final(*args, **kwargs):
            final = cls._orig_final(*args, **kwargs)
            cls.captured.append(final)
            return final

        ValidationEngine._compute_final_acceptance = staticmethod(_spy_final)
        if os.path.isdir(SCENARIO_ROOT):
            shutil.rmtree(SCENARIO_ROOT, ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        ValidationEngine._compute_final_acceptance = staticmethod(cls._orig_final)
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

    def test_controlled_scenarios_final_acceptance_via_production_path(self):
        service = self.env['nexora.builder_session_service']
        preview_service = self.env['nexora.preview_service']
        for name, requirements in self.SCENARIOS:
            ws = os.path.join(SCENARIO_ROOT, name)
            os.makedirs(ws, exist_ok=True)
            self.cr.execute('SAVEPOINT u96_scenario')
            session = None
            self.captured.clear()
            try:
                cfg = self.env['nexora.builder_configuration'].create(
                    {'name': f'U96 {name}'})
                session = self.env['nexora.builder_session'].create({
                    'name': f'U96 {name}', 'builder_configuration_id': cfg.id,
                    'project_name': f'U96 {name}', 'target_workspace_path': ws,
                })
                raised = None
                try:
                    ok = service.run_generation(session, requirements=requirements)
                except Exception as e:
                    raised = e
                self.assertTrue(self.captured,
                                f'{name}: final acceptance must be computed')

                if name in ('react', 'r3f'):
                    self.assertIsNone(raised, f'{name}: {raised}')
                    self.assertTrue(ok, f'{name}: run_generation failed')
                    self.assertEqual(session.status, 'ai_reviewing')
                    self.assertTrue(self.captured[-1]['accepted'],
                                    f'{name}: final acceptance must be accepted')
                else:  # spline with the known fake scene URL
                    self.assertIsNotNone(
                        raised, 'spline: fake scene must fail final acceptance')
                    self.assertIn('Browser validation failed', str(raised))
                    self.assertEqual(session.status, 'failed')
                    self.assertTrue(any(not f['accepted'] for f in self.captured),
                                    'spline: final acceptance must truthfully fail')
            finally:
                try:
                    if session is not None:
                        preview_service.stop_workspace_preview(session)
                except Exception:
                    pass
                self.cr.execute('ROLLBACK TO SAVEPOINT u96_scenario')
                self.cr.execute('RELEASE SAVEPOINT u96_scenario')


if __name__ == '__main__':
    unittest.main()
