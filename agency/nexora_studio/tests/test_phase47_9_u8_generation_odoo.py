# -*- coding: utf-8 -*-
"""Phase 47.9 (U8) — Odoo-level proofs against the live nexora_studio registry.

Covers the spec requirements that need a real Odoo environment:
  * §17.E  DesignOrchestrationEngine routes through the real
           nexora.design_orchestrator model and RenderingProviderRegistry.
  * §21.U  No connector/source/credential/config changes (DB invariants).
  * §22    Controlled React / R3F / Spline generation through the existing
           BuilderSessionService -> GenerationCoordinator -> GenerationRuntime
           -> WebsiteGenerationPipeline production path.

The AI provider boundary is the only patched dependency (route_request), so no
external AI service is contacted; every other stage runs real production code.
"""
import json
import os
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.generation.core.generation_runtime import GenerationRuntime
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import GenerationStateManager
from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import PipelineEventBus
from odoo.addons.nexora_studio.services.generation.engines.design_orchestration_engine import DesignOrchestrationEngine
from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    WebsiteGenerationArtifact, RequirementModel,
)

VALID_SPLINE_URL = "https://prod.spline.design/AbCdEf123/scene.splinecode"


def _fake_route_request(self, task_type, prompt, parameters=None, ctx=None):
    """Deterministic AI boundary stub.

    Only the external AI service is replaced. For code-patch tasks a valid
    React section declaration is returned (matching the component name the
    CodeGenerationEngine asked for). All other tasks return an empty dict so
    the engines use their existing deterministic fallbacks.
    """
    prompt_str = str(prompt or '')
    if task_type == 'ai_code_patch':
        match = re.search(r'named\s+([A-Za-z0-9_]+)', prompt_str)
        name = match.group(1) if match else 'GeneratedSection'
        code = (
            f"function {name}() {{\n"
            f"  return (\n"
            f"    <section className=\"generated-{name.lower()}\">\n"
            f"      <h2>{name}</h2>\n"
            f"      <p>Controlled generation content.</p>\n"
            f"    </section>\n"
            f"  )\n"
            f"}}"
        )
        return {'full_content': code}
    return {}


def _make_artifact(strategy, raw_input):
    blueprint = {
        'rendering': {'strategy': strategy, 'budget_polygon_count': 0},
        'layout': {'strategy': 'fluid', 'hierarchy': ['/']},
    }
    return WebsiteGenerationArtifact(
        requirements=RequirementModel(raw_input=raw_input, domain='Agency'),
        generation_metadata={'modular_blueprint': blueprint},
    )


class TestU8DesignOrchestrationOdoo(unittest.TestCase):
    """§17.E — engine routes through the real DesignOrchestrator model."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.workspace_path = tempfile.mkdtemp(prefix='nexora-u8-orch-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.workspace_path, ignore_errors=True)
        cls.cr.close()

    def _runtime(self):
        return GenerationRuntime(
            ai_provider_manager=self.env['nexora.ai_provider_manager'],
            workspace_path=self.workspace_path,
            event_bus=PipelineEventBus(),
            state_manager=GenerationStateManager(),
            session_id='u8-orch-session',
            generation_id='u8-orch-generation',
            env=self.env,
        )

    def _run_engine(self, strategy, raw_input):
        runtime = self._runtime()
        scoped = runtime.get_scoped_view(DesignOrchestrationEngine)
        engine = DesignOrchestrationEngine(runtime.orchestrator)
        artifact = _make_artifact(strategy, raw_input)
        return engine.execute(artifact, scoped)

    def test_real_design_orchestrator_model_exists(self):
        self.assertIn('nexora.design_orchestrator', self.env.registry.models,
                      'nexora.design_orchestrator must be registered in the Odoo registry')
        orch = self.env['nexora.design_orchestrator']
        self.assertTrue(hasattr(orch, 'execute_operation'))
        self.assertTrue(hasattr(orch, 'get_provider'))

    def test_react_selection_through_real_orchestrator(self):
        result = self._run_engine('none', 'Build a standard business website')
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.artifact.design['provider'], 'react')
        self.assertEqual(result.artifact.design['strategy'], 'none')
        self.assertIn('package.json', result.artifact.design['project_structure'])

    def test_r3f_selection_through_real_orchestrator(self):
        result = self._run_engine('webgl', 'Build an immersive 3d website')
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.artifact.design['provider'], 'react_three_fiber')
        structure = result.artifact.design['project_structure']
        self.assertIn('src/scene/Scene.jsx', structure)
        self.assertIn('three', result.artifact.design['dependencies'])
        self.assertIn('@react-three/fiber', result.artifact.design['dependencies'])

    def test_spline_selection_through_real_orchestrator(self):
        result = self._run_engine('spline', f'Website with Spline {VALID_SPLINE_URL}')
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.artifact.design['provider'], 'spline')
        structure = result.artifact.design['project_structure']
        self.assertIn('src/components/SplineScene.jsx', structure)
        self.assertIn('@splinetool/react-spline', result.artifact.design['dependencies'])

    def test_spline_without_scene_reference_fails_stage(self):
        result = self._run_engine('spline', 'Build a spline website')
        self.assertFalse(result.success)
        self.assertIn('spline', (result.error or '').lower())


class TestU8DBInvariants(unittest.TestCase):
    """§21.U — U8 must not change connector/source/credential/config state."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_connector_source_credential_config_invariants(self):
        connectors = self.env['nexora.connector'].search([])
        sources = self.env['nexora.source_registry'].search([])
        credentials = self.env['nexora.mcp_credential'].search([])
        configs = self.env['nexora.mcp_server_config'].search([])

        self.assertEqual(len(connectors), 6, 'connector_count must remain 6')
        # Phase 47.16 added the 7th source (tavily_knowledge).
        self.assertEqual(len(sources), 7, 'source_count must remain 7')
        self.assertIn('tavily_knowledge', sources.mapped('technical_name'))
        self.assertEqual(len(credentials), 5, 'credential_count must remain 5')
        self.assertEqual(len(configs), 6, 'config_count must remain 6')

        # All six connectors remain disabled — U8 enables nothing.
        for c in connectors:
            self.assertEqual(c.state, 'disabled',
                             f'Connector {c.connector_id} lifecycle changed: {c.state}')
            self.assertFalse(c.enabled, f'Connector {c.connector_id} became enabled')

    def test_no_renderer_mcp_connector_rows(self):
        """U8 must not create Spline/Three.js/R3F/Drei connector rows. The six
        canonical connectors are the only rows; renderer MCP stubs live only in
        config/mcp_registry.json as disabled/planned and are not bootstrapped."""
        connectors = self.env['nexora.connector'].search([])
        ids = {c.connector_id for c in connectors}
        self.assertEqual(ids, {
            'context7_mcp', 'firecrawl_mcp', 'github_mcp',
            'gosom_mcp', 'penpot_mcp', 'tavily_mcp',
        })
        for forbidden in ('spline_mcp', 'threejs_docs_mcp', 'r3f_docs_mcp', 'drei_docs_mcp'):
            self.assertNotIn(forbidden, ids, f'Forbidden connector row present: {forbidden}')


class TestU8ControlledGeneration(unittest.TestCase):
    """§22 — controlled React / R3F / Spline generation through the real
    BuilderSessionService -> GenerationCoordinator -> GenerationRuntime ->
    WebsiteGenerationPipeline production workflow."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls._patcher = patch(
            'odoo.addons.nexora_studio.services.ai.provider_manager.AIProviderManager.route_request',
            _fake_route_request,
        )
        cls._patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls.cr.close()

    def setUp(self):
        self.workspace_path = tempfile.mkdtemp(prefix='nexora-u8-gen-')
        self.config = self.env['nexora.builder_configuration'].create({
            'name': 'Phase 47.9 U8 Test Configuration',
        })
        self.session = self.env['nexora.builder_session'].create({
            'name': 'Phase 47.9 U8 Test Session',
            'builder_configuration_id': self.config.id,
            'project_name': 'U8 controlled generation',
            'target_workspace_path': self.workspace_path,
        })
        self.cr.execute('SAVEPOINT u8_generation')

    def tearDown(self):
        # Phase 47.12 (U9.3): generation now starts a real development
        # preview. Stop it through the canonical preview owner before the
        # savepoint rollback so no Vite process tree or port leaks.
        try:
            self.env['nexora.preview_service'].stop_workspace_preview(self.session)
        except Exception:
            pass
        self.cr.execute('ROLLBACK TO SAVEPOINT u8_generation')
        self.cr.execute('RELEASE SAVEPOINT u8_generation')
        shutil.rmtree(self.workspace_path, ignore_errors=True)

    def _run(self, requirements):
        service = self.env['nexora.builder_session_service']
        ok = service.run_generation(self.session, requirements=requirements)
        self.assertTrue(ok, 'run_generation must complete successfully')
        self.assertEqual(self.session.status, 'ai_reviewing')
        ws_path = self.session.workspace_id.workspace_path
        return ws_path

    def _read(self, ws_path, rel):
        full = os.path.join(ws_path, rel.replace('/', os.sep))
        if not os.path.exists(full):
            return None
        with open(full, 'r', encoding='utf-8', errors='ignore') as fh:
            return fh.read()

    def _meta(self, ws_path):
        raw = self._read(ws_path, '.nexora/workspace_meta.json')
        return json.loads(raw) if raw else {}

    def test_scenario_1_standard_react(self):
        ws = self._run('Build a modern SaaS landing page with pricing and testimonials.')
        pkg = self._read(ws, 'package.json')
        self.assertIsNotNone(pkg, 'package.json must be materialized')
        self.assertNotIn('three', pkg)
        self.assertNotIn('@splinetool', pkg)
        self.assertIsNone(self._read(ws, 'src/scene/Scene.jsx'))
        self.assertIsNone(self._read(ws, 'src/components/SplineScene.jsx'))
        meta = self._meta(ws)
        self.assertEqual((meta.get('design') or {}).get('provider'), 'react')
        # CodeGenerationEngine wrote the application entry and a home page.
        self.assertIsNotNone(self._read(ws, 'src/App.jsx'))
        self.assertIsNotNone(self._read(ws, 'src/pages/index.tsx'))

    def test_scenario_2_webgl_r3f(self):
        ws = self._run('Build an immersive 3d product showcase website with WebGL.')
        pkg = self._read(ws, 'package.json')
        self.assertIsNotNone(pkg)
        self.assertIn('three', pkg)
        self.assertIn('@react-three/fiber', pkg)
        scene = self._read(ws, 'src/scene/Scene.jsx')
        self.assertIsNotNone(scene, 'R3F scene entry must be materialized')
        self.assertIn('<Canvas', scene)
        meta = self._meta(ws)
        self.assertEqual((meta.get('design') or {}).get('provider'), 'react_three_fiber')
        home = self._read(ws, 'src/pages/index.tsx')
        self.assertIsNotNone(home)
        self.assertIn('Scene', home, 'home page must bind the provider scene component')

    def test_scenario_3_explicit_spline(self):
        # Phase 47.13 (U9.4): the fake scene URL produces real browser
        # console/page errors, so browser validation (which now runs after
        # preview) truthfully fails the Spline generation. The U8 ownership
        # assertions below still hold: scaffold, dependencies and wiring are
        # all materialized BEFORE the browser phase fails.
        raised = None
        try:
            self._run(
                'Build a creative agency website featuring a Spline scene at '
                f'{VALID_SPLINE_URL} .'
            )
        except Exception as e:
            raised = e
        self.assertIsNotNone(
            raised, 'fake Spline scene must fail U9.4 browser validation')
        self.assertIn('Browser validation failed', str(raised))
        ws = self.session.workspace_id.workspace_path
        pkg = self._read(ws, 'package.json')
        self.assertIsNotNone(pkg)
        self.assertIn('@splinetool/react-spline', pkg)
        integration = self._read(ws, 'src/components/SplineScene.jsx')
        self.assertIsNotNone(integration, 'Spline integration must be materialized')
        self.assertIn(VALID_SPLINE_URL, integration)
        meta = self._meta(ws)
        self.assertEqual((meta.get('design') or {}).get('provider'), 'spline')
        home = self._read(ws, 'src/pages/index.tsx')
        self.assertIsNotNone(home)
        self.assertIn('SplineScene', home, 'home page must bind the Spline scene component')


if __name__ == '__main__':
    unittest.main()
