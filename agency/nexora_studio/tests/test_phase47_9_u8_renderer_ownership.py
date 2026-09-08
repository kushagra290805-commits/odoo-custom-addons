# -*- coding: utf-8 -*-
"""Phase 47.9 (U8) — Existing renderer ownership closure: focused DB-free tests.

Covers spec §17 (A–S focused behaviors) and §18 (negative architecture
assertions) without any database. Odoo-level proofs (real DesignOrchestrator,
DB invariants, controlled generation) live in
test_phase47_9_u8_generation_odoo.py.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.providers.provider_registry import RenderingProviderRegistry
from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
from odoo.addons.nexora_studio.services.design.providers.react_three_fiber_provider import ReactThreeFiberProvider
from odoo.addons.nexora_studio.services.design.providers.spline_provider import SplineRenderingProvider, validate_spline_scene_url
from odoo.addons.nexora_studio.services.design.requirement_analyzer import RequirementAnalyzer
from odoo.addons.nexora_studio.services.design.planners.rendering_planner import RenderingPlanner
from odoo.addons.nexora_studio.services.design.blueprint_models import RawRequirement

from odoo.addons.nexora_studio.services.generation.engines.design_orchestration_engine import DesignOrchestrationEngine
from odoo.addons.nexora_studio.services.generation.engines.workspace_generator_engine import WorkspaceGeneratorEngine
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import CodeGenerationEngine
from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    WebsiteGenerationArtifact, RequirementModel, ArchitectureModel, ComponentTree, TemplateResolution, Assets,
)
from odoo.addons.nexora_studio.services.generation.core.workspace_adapter import WorkspaceAdapter

MODULE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VALID_SPLINE_URL = "https://prod.spline.design/AbCdEf123/scene.splinecode"


# --------------------------------------------------------------------------
# Fakes mirroring existing production contracts (no parallel architecture)
# --------------------------------------------------------------------------

class FakeDesignOrchestratorModel:
    """Mirrors nexora.design_orchestrator.execute_operation dispatch:
    resolve the provider through RenderingProviderRegistry, call the operation."""

    def __init__(self):
        self.calls = []

    def get_provider(self, provider_name=None, config=None):
        return RenderingProviderRegistry.get_provider((provider_name or 'react').lower(), config=config)

    def execute_operation(self, operation, provider_name=None, **kwargs):
        self.calls.append({'operation': operation, 'provider_name': provider_name, 'kwargs': kwargs})
        provider = self.get_provider(provider_name=provider_name)
        if not hasattr(provider, operation):
            raise ValueError(f"Operation '{operation}' not supported.")
        return getattr(provider, operation)(**kwargs)


class FakeEnv:
    def __init__(self):
        self.design_orchestrator = FakeDesignOrchestratorModel()

    def __getitem__(self, model):
        if model == 'nexora.design_orchestrator':
            return self.design_orchestrator
        raise KeyError(model)


class FakeMetadata:
    def __init__(self, session_id='u8-session'):
        self.session_id = session_id
        self.scope_name = 'U8 Test Scope'


class FakeAI:
    def generate(self, operation, payload):
        prompt = str(payload.get('task') or payload.get('prompt') or '')
        match = re.search(r'named\s+(\w+)', prompt)
        if match:
            name = match.group(1)
            return {'full_content': f"function {name}() {{\n  return <section>{name}</section>\n}}"}
        return {}


class FakeTools:
    def execute(self, namespace, payload, scoped_runtime, budget=100):
        return []


class FakeRuntime:
    def __init__(self, workspace=None):
        self.env = FakeEnv()
        self.metadata = FakeMetadata()
        self.workspace = workspace
        self.ai = FakeAI()
        self.tools = FakeTools()


def make_artifact(strategy='none', raw_input='Build a website', component_nodes=None,
                  component_deps=None, hierarchy=None, assets=None):
    blueprint = {
        'rendering': {'strategy': strategy, 'budget_polygon_count': 0},
        'layout': {'strategy': 'fluid', 'hierarchy': ['/']},
    }
    arch = ArchitectureModel(component_hierarchy=hierarchy or {
        'page_home': {'type': 'page', 'path': '/', 'sections': ['Hero']},
    })
    return WebsiteGenerationArtifact(
        requirements=RequirementModel(raw_input=raw_input, domain='Agency'),
        architecture=arch,
        component_tree=ComponentTree(nodes=component_nodes or [], dependencies=component_deps or []),
        assets=assets or Assets(),
        generation_metadata={'modular_blueprint': blueprint},
    )


def r3f_node(component_id='OrbitScene', code=None, semantic='3d orbit scene'):
    return {
        'component_id': component_id,
        'name': component_id,
        'code': code if code is not None else (
            "import React from 'react'\n"
            "import { Canvas } from '@react-three/fiber'\n"
            "export default function OrbitScene() {\n"
            "  return <mesh><sphereGeometry args={[1, 32, 32]} /><meshStandardMaterial color=\"red\" /></mesh>\n"
            "}"
        ),
        'metadata': {'from_source': True, 'semantic': semantic, 'source_identifier': 'threed_component_library'},
    }


# --------------------------------------------------------------------------
# A/B/C + R: deterministic renderer selection contract
# --------------------------------------------------------------------------

class TestRendererSelectionContract(unittest.TestCase):

    def test_a_ordinary_react_strategy_selects_react_provider(self):
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('none'), 'react')
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('css_3d'), 'react')
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('canvas'), 'react')
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id(None), 'react')
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('unknown_strategy'), 'react')

        engine = DesignOrchestrationEngine(None)
        result = engine.execute(make_artifact(strategy='none'), FakeRuntime())
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.artifact.design['provider'], 'react')
        self.assertEqual(result.artifact.design['strategy'], 'none')

    def test_b_webgl_strategy_selects_r3f_provider(self):
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('webgl'), 'react_three_fiber')
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('immersive'), 'react_three_fiber')

        req = RequirementAnalyzer().analyze('Build an immersive 3d product showcase website')
        self.assertEqual(req.preferences.get('rendering'), 'webgl')
        blueprint = RenderingPlanner().plan(req)
        self.assertEqual(blueprint.strategy, 'webgl')

        engine = DesignOrchestrationEngine(None)
        result = engine.execute(make_artifact(strategy='webgl', raw_input='3d website'), FakeRuntime())
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.artifact.design['provider'], 'react_three_fiber')

    def test_c_explicit_spline_requirement_selects_spline_provider(self):
        self.assertEqual(RenderingProviderRegistry.resolve_provider_id('spline'), 'spline')

        req = RequirementAnalyzer().analyze(f'Build a website with a Spline scene {VALID_SPLINE_URL}')
        self.assertEqual(req.preferences.get('rendering'), 'spline')
        blueprint = RenderingPlanner().plan(req)
        self.assertEqual(blueprint.strategy, 'spline')

        engine = DesignOrchestrationEngine(None)
        artifact = make_artifact(strategy='spline', raw_input=f'Website with Spline {VALID_SPLINE_URL}')
        result = engine.execute(artifact, FakeRuntime())
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.artifact.design['provider'], 'spline')
        self.assertEqual(result.artifact.design['provider_metadata'].get('spline_scene_url'), VALID_SPLINE_URL)

    def test_c2_spline_not_inferred_from_visual_complexity(self):
        req = RequirementAnalyzer().analyze('Build a visually complex premium dark website with animations')
        self.assertNotEqual(req.preferences.get('rendering'), 'spline')

    def test_c3_spline_takes_precedence_over_generic_3d(self):
        req = RequirementAnalyzer().analyze(f'A 3d website using spline {VALID_SPLINE_URL}')
        self.assertEqual(req.preferences.get('rendering'), 'spline')

    def test_r_ordinary_react_generation_unchanged(self):
        provider = RenderingProviderRegistry.get_provider('react')
        result = provider.process_blueprint({'rendering': {'strategy': 'none'}})
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['provider'], 'react')
        structure = result['project_structure']
        for required in ['package.json', 'vite.config.js', 'index.html', 'src/main.jsx',
                         'src/App.jsx', 'src/routes.jsx', 'src/styles/tokens.css']:
            self.assertIn(required, structure)
        self.assertNotIn('src/scene/Scene.jsx', structure)
        self.assertNotIn('src/components/SplineScene.jsx', structure)
        self.assertNotIn('three', result['dependencies'])
        self.assertNotIn('@splinetool/react-spline', result['dependencies'])


# --------------------------------------------------------------------------
# E/F: DesignOrchestrationEngine bridge + registry singularity
# --------------------------------------------------------------------------

class TestDesignOrchestrationBridge(unittest.TestCase):

    def test_e_engine_calls_existing_design_orchestrator(self):
        runtime = FakeRuntime()
        engine = DesignOrchestrationEngine(None)
        result = engine.execute(make_artifact(strategy='webgl', raw_input='3d site'), runtime)
        self.assertTrue(result.success, result.error)
        calls = runtime.env.design_orchestrator.calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['operation'], 'process_blueprint')
        self.assertEqual(calls[0]['provider_name'], 'react_three_fiber')

    def test_engine_requires_explicit_env(self):
        runtime = FakeRuntime()
        runtime.env = None
        engine = DesignOrchestrationEngine(None)
        result = engine.execute(make_artifact(), runtime)
        self.assertFalse(result.success)
        self.assertIn('environment', result.error)

    def test_l_invalid_provider_output_fails_stage(self):
        engine = DesignOrchestrationEngine(None)
        # Spline strategy without a scene reference -> honest failure, no fabrication.
        artifact = make_artifact(strategy='spline', raw_input='Build a spline website')
        result = engine.execute(artifact, FakeRuntime())
        self.assertFalse(result.success)
        self.assertIn('spline', result.error.lower())

    def test_l2_provider_identity_mismatch_fails_stage(self):
        engine = DesignOrchestrationEngine(None)
        bad = {'status': 'success', 'provider': 'react', 'project_structure': {'a.js': 'export {}'},
               'validation': {'valid': True}}
        self.assertIn('identity mismatch', engine._validate_provider_result(bad, 'spline'))
        self.assertIsNone(engine._validate_provider_result(
            {'status': 'success', 'provider': 'react', 'project_structure': {'a.js': 'export {}'},
             'validation': {'valid': True}}, 'react'))

    def test_design_payload_preserves_ownership_contract(self):
        engine = DesignOrchestrationEngine(None)
        result = engine.execute(make_artifact(strategy='webgl', raw_input='3d site'), FakeRuntime())
        design = result.artifact.design
        ownership = design['file_ownership']
        self.assertEqual(ownership['provider'], 'react_three_fiber')
        self.assertIn('src/scene/Scene.jsx', ownership['provider_owned_files'])
        self.assertNotIn('src/App.jsx', ownership['provider_owned_files'])
        self.assertFalse(any(p.startswith('src/pages/') for p in ownership['provider_owned_files']))
        self.assertIn('src/pages/*', ownership['code_generation_owned'])


# --------------------------------------------------------------------------
# G/H/I: R3F provider closure
# --------------------------------------------------------------------------

class TestR3FProviderClosure(unittest.TestCase):

    def _generate(self, selected_components=None, renderer_assets=None):
        provider = RenderingProviderRegistry.get_provider('react_three_fiber')
        self.assertIsInstance(provider, ReactThreeFiberProvider)
        return provider.process_blueprint(
            {'rendering': {'strategy': 'webgl'}},
            rendering_strategy='webgl',
            selected_components=selected_components or [],
            renderer_assets=renderer_assets or [],
        )

    def test_g_r3f_emits_required_dependencies_and_render_entry(self):
        result = self._generate()
        self.assertEqual(result['status'], 'success', result.get('errors'))
        self.assertEqual(result['provider'], 'react_three_fiber')
        deps = result['dependencies']
        self.assertIn('three', deps)
        self.assertIn('@react-three/fiber', deps)
        structure = result['project_structure']
        self.assertIn('src/scene/Scene.jsx', structure)
        scene = structure['src/scene/Scene.jsx']
        self.assertIn('<Canvas', scene)
        self.assertIn('camera=', scene)
        self.assertIn('ambientLight', scene)
        self.assertIn('directionalLight', scene)
        self.assertIn('"three"', structure['package.json'])
        self.assertIn('"@react-three/fiber"', structure['package.json'])
        self.assertTrue(result['validation']['valid'], result['validation'].get('errors'))

    def test_g2_drei_not_injected_blindly(self):
        result = self._generate()
        self.assertNotIn('@react-three/drei', result['dependencies'])

    def test_h_r3f_consumes_selected_component_tree_information(self):
        result = self._generate(selected_components=[r3f_node()])
        self.assertEqual(result['status'], 'success', result.get('errors'))
        structure = result['project_structure']
        three_files = [p for p in structure if p.startswith('src/components/three/')]
        self.assertEqual(len(three_files), 1)
        self.assertIn('sphereGeometry', structure[three_files[0]])
        self.assertIn(three_files[0].rsplit('/', 1)[-1].split('.jsx')[0], structure['src/scene/Scene.jsx'])
        consumed = result['metadata']['r3f_components_consumed']
        self.assertEqual(len(consumed), 1)
        self.assertEqual(consumed[0]['component_id'], 'OrbitScene')
        self.assertEqual(consumed[0]['provenance'], 'component_tree')
        self.assertEqual(result['metadata']['scene_provenance'], 'component_tree')

    def test_h2_non_r3f_source_components_are_not_consumed_by_renderer(self):
        dom_node = {
            'component_id': 'FancyCard', 'name': 'FancyCard',
            'code': 'export default function FancyCard() { return <div /> }',
            'metadata': {'from_source': True, 'semantic': 'pricing card', 'source_identifier': 'react_bits'},
        }
        result = self._generate(selected_components=[dom_node])
        self.assertEqual(result['status'], 'success', result.get('errors'))
        self.assertEqual(result['metadata']['r3f_components_consumed'], [])
        self.assertFalse(any(p.startswith('src/components/three/') for p in result['project_structure']))

    def test_h3_drei_added_only_when_selected_component_requires_it(self):
        node = r3f_node(component_id='EnvScene', code=(
            "import React from 'react'\n"
            "import { Environment } from '@react-three/drei'\n"
            "export default function EnvScene() { return <Environment preset=\"city\" /> }"
        ))
        result = self._generate(selected_components=[node])
        self.assertIn('@react-three/drei', result['dependencies'])

    def test_i_r3f_fallback_scene_does_not_invent_provenance(self):
        result = self._generate(selected_components=[])
        self.assertEqual(result['status'], 'success', result.get('errors'))
        self.assertEqual(result['metadata']['scene_provenance'], 'generated-fallback')
        self.assertEqual(result['metadata']['r3f_components_consumed'], [])
        scene = result['project_structure']['src/scene/Scene.jsx']
        self.assertIn('<mesh', scene)
        self.assertNotIn('threed_component_library', scene)

    def test_i2_usegltf_only_with_real_asset_reference(self):
        result = self._generate()
        self.assertNotIn('useGLTF', result['project_structure']['src/scene/Scene.jsx'])
        self.assertNotIn('@react-three/drei', result['dependencies'])

        result_with_asset = self._generate(
            renderer_assets=[{'asset_id': 'a1', 'name': 'model', 'type': 'model',
                              'url': 'https://example.com/assets/model.glb'}])
        scene = result_with_asset['project_structure']['src/scene/Scene.jsx']
        self.assertIn('useGLTF', scene)
        self.assertIn('https://example.com/assets/model.glb', scene)
        self.assertIn('@react-three/drei', result_with_asset['dependencies'])
        self.assertEqual(result_with_asset['metadata']['gltf_assets_referenced'],
                         ['https://example.com/assets/model.glb'])

    def test_r3f_rejects_disallowed_renderer(self):
        provider = RenderingProviderRegistry.get_provider('react_three_fiber')
        result = provider.process_blueprint({'rendering': {'strategy': 'webgl'}}, rendering_strategy='webgl')
        structure = dict(result['project_structure'])
        structure['src/components/three/Bad.jsx'] = "import { Engine } from 'babylonjs';\nexport default function Bad() { return null }"
        val = provider.validate_project(None, structure)
        self.assertFalse(val['valid'])
        self.assertTrue(any('Unapproved 3D dependency' in e for e in val['errors']))


# --------------------------------------------------------------------------
# J/K: Spline provider closure
# --------------------------------------------------------------------------

class TestSplineProviderClosure(unittest.TestCase):

    def test_j_spline_emits_valid_integration(self):
        provider = RenderingProviderRegistry.get_provider('spline')
        self.assertIsInstance(provider, SplineRenderingProvider)
        result = provider.process_blueprint(
            {'rendering': {'strategy': 'spline'}},
            rendering_strategy='spline',
            spline_scene_url=VALID_SPLINE_URL,
        )
        self.assertEqual(result['status'], 'success', result.get('errors'))
        self.assertEqual(result['provider'], 'spline')
        structure = result['project_structure']
        self.assertIn('src/components/SplineScene.jsx', structure)
        integration = structure['src/components/SplineScene.jsx']
        self.assertIn("@splinetool/react-spline", integration)
        self.assertIn(f'scene="{VALID_SPLINE_URL}"', integration)
        self.assertIn('"@splinetool/react-spline"', structure['package.json'])
        self.assertIn('@splinetool/react-spline', result['dependencies'])
        self.assertEqual(result['metadata']['spline_scene_source_type'], 'remote_url')
        self.assertTrue(result['validation']['valid'], result['validation'].get('errors'))

    def test_k_unsafe_spline_url_fails(self):
        provider = RenderingProviderRegistry.get_provider('spline')
        for bad_url in [
            'javascript:alert(1)',
            'data:text/html;base64,AAAA',
            'http://prod.spline.design/AbCdEf123/scene.splinecode',
            'https://evil.example.com/scene.splinecode',
            'https://prod.spline.design/AbCdEf123/scene.exe',
            '',
        ]:
            result = provider.process_blueprint(
                {'rendering': {'strategy': 'spline'}},
                rendering_strategy='spline',
                spline_scene_url=bad_url,
            )
            self.assertEqual(result['status'], 'error', f'URL should be rejected: {bad_url}')
            self.assertFalse(result.get('project_structure'))

    def test_k2_url_validator_contract(self):
        self.assertTrue(validate_spline_scene_url(VALID_SPLINE_URL)['valid'])
        self.assertTrue(validate_spline_scene_url('scenes/hero.splinecode')['valid'])
        self.assertFalse(validate_spline_scene_url('https://prod.spline.design/x/scene.glb')['valid'])

    def test_spline_scene_not_fabricated_when_missing(self):
        provider = RenderingProviderRegistry.get_provider('spline')
        result = provider.process_blueprint({'rendering': {'strategy': 'spline'}}, rendering_strategy='spline')
        self.assertEqual(result['status'], 'error')
        joined = ' '.join(result['errors']).lower()
        self.assertNotIn('prod.spline.design', ' '.join(result.get('project_structure', {})))
        self.assertIn('scene reference rejected', joined)


# --------------------------------------------------------------------------
# M/N/P: workspace materialization + dependency aggregation + ownership
# --------------------------------------------------------------------------

class TestWorkspaceMaterialization(unittest.TestCase):

    def setUp(self):
        self.workspace_path = tempfile.mkdtemp(prefix='nexora-u8-')
        template_path = os.path.join(MODULE_ROOT, 'assets', 'frontend-templates', 'vite-react')
        self.template = TemplateResolution(template_id=0, template_name='Default Vite-React',
                                           template_path=template_path, template_source='local')

    def tearDown(self):
        shutil.rmtree(self.workspace_path, ignore_errors=True)

    def _provider_result(self, strategy):
        runtime = FakeRuntime()
        engine = DesignOrchestrationEngine(None)
        raw = '3d website' if strategy == 'webgl' else f'spline {VALID_SPLINE_URL}'
        result = engine.execute(make_artifact(strategy=strategy, raw_input=raw), runtime)
        self.assertTrue(result.success, result.error)
        return result.artifact

    def _run_workspace(self, artifact):
        runtime = FakeRuntime(workspace=WorkspaceAdapter(self.workspace_path))
        engine = WorkspaceGeneratorEngine(None)
        return engine.execute(artifact, runtime), runtime

    def test_n_provider_files_reach_managed_workspace(self):
        artifact = self._provider_result('webgl')
        artifact = artifact.evolve(template=self.template)
        result, runtime = self._run_workspace(artifact)
        self.assertTrue(result.success, result.error)
        self.assertTrue(runtime.workspace.exists('src/scene/Scene.jsx'))
        self.assertTrue(runtime.workspace.exists('vite.config.js'))
        self.assertTrue(runtime.workspace.exists('src/styles/tokens.css'))
        self.assertTrue(runtime.workspace.exists('.nexora/workspace_meta.json'))
        self.assertGreater(result.metadata['provider_files_materialized'], 0)
        self.assertTrue(result.metadata['workspace_path'].startswith(self.workspace_path) or
                        os.path.samefile(result.metadata['workspace_path'], self.workspace_path))

    def test_p_codegen_owned_files_have_single_owner(self):
        artifact = self._provider_result('webgl')
        # Provider structure always contains App.jsx/pages; workspace engine must skip them.
        self.assertIn('src/App.jsx', artifact.design['project_structure'])
        artifact = artifact.evolve(template=self.template)
        result, runtime = self._run_workspace(artifact)
        self.assertTrue(result.success, result.error)
        # Template App.jsx remains untouched (placeholder), provider App.jsx not written.
        app_content = runtime.workspace.read_file('src/App.jsx')
        self.assertIn('{{project_name}}', app_content)
        self.assertNotIn('AppRoutes', app_content)
        self.assertFalse(runtime.workspace.exists('src/pages/LandingPage.jsx'))

    def test_m_dependency_aggregation_union(self):
        artifact = self._provider_result('webgl')
        artifact = artifact.evolve(
            template=self.template,
            component_tree=ComponentTree(nodes=[], dependencies=['react', 'three', 'mystery-pkg']),
        )
        result, runtime = self._run_workspace(artifact)
        self.assertTrue(result.success, result.error)
        pkg = json.loads(runtime.workspace.read_file('package.json'))
        deps = pkg['dependencies']
        self.assertIn('react', deps)
        self.assertIn('three', deps)
        self.assertIn('@react-three/fiber', deps)
        self.assertIn('vite', pkg.get('devDependencies', {}))
        self.assertNotIn('mystery-pkg', deps)
        self.assertIn('mystery-pkg', result.metadata.get('dependency_contract_gaps', []))

    def test_workspace_fails_without_template(self):
        artifact = make_artifact()
        runtime = FakeRuntime(workspace=WorkspaceAdapter(self.workspace_path))
        result = WorkspaceGeneratorEngine(None).execute(artifact, runtime)
        self.assertFalse(result.success)


# --------------------------------------------------------------------------
# O/Q: CodeGenerationEngine enrichment + validation extension coverage
# --------------------------------------------------------------------------

class TestCodeGenerationOwnership(unittest.TestCase):

    def setUp(self):
        self.workspace_path = tempfile.mkdtemp(prefix='nexora-u8-codegen-')
        self.runtime = FakeRuntime(workspace=WorkspaceAdapter(self.workspace_path))

    def tearDown(self):
        shutil.rmtree(self.workspace_path, ignore_errors=True)

    def _seed_scaffold(self, provider='react_three_fiber'):
        scene = "// provider-owned scene scaffold\nexport default function Scene() { return null }\n"
        self.runtime.workspace.write_file('src/scene/Scene.jsx', scene)
        self.runtime.workspace.write_file('src/components/SplineScene.jsx', '// spline scaffold\nexport default function SplineScene() { return null }\n')
        design = {'provider': provider, 'strategy': 'webgl' if provider == 'react_three_fiber' else 'spline',
                  'project_structure': {}, 'file_ownership': {'provider': provider}}
        return make_artifact(strategy=design['strategy']).evolve(design=design)

    def test_o_r3f_enriches_pages_without_recreating_scaffold(self):
        artifact = self._seed_scaffold('react_three_fiber')
        before = self.runtime.workspace.read_file('src/scene/Scene.jsx')
        result = CodeGenerationEngine(None).execute(artifact, self.runtime)
        self.assertTrue(result.success, result.error)
        page = self.runtime.workspace.read_file('src/pages/index.tsx')
        self.assertIn("import Scene from '../scene/Scene.jsx'", page)
        self.assertIn('<Scene />', page)
        self.assertEqual(self.runtime.workspace.read_file('src/scene/Scene.jsx'), before)
        self.assertEqual(result.metadata['renderer_provider'], 'react_three_fiber')

    def test_o2_spline_enriches_pages_without_recreating_scaffold(self):
        artifact = self._seed_scaffold('spline')
        before = self.runtime.workspace.read_file('src/components/SplineScene.jsx')
        result = CodeGenerationEngine(None).execute(artifact, self.runtime)
        self.assertTrue(result.success, result.error)
        page = self.runtime.workspace.read_file('src/pages/index.tsx')
        self.assertIn("import SplineScene from '../components/SplineScene.jsx'", page)
        self.assertIn('<SplineScene />', page)
        self.assertEqual(self.runtime.workspace.read_file('src/components/SplineScene.jsx'), before)

    def test_o3_ordinary_react_pages_unchanged(self):
        artifact = make_artifact()
        result = CodeGenerationEngine(None).execute(artifact, self.runtime)
        self.assertTrue(result.success, result.error)
        page = self.runtime.workspace.read_file('src/pages/index.tsx')
        self.assertNotIn('Scene', page)
        self.assertNotIn('SplineScene', page)
        self.assertEqual(result.metadata['renderer_provider'], 'react')

    def test_q_validation_covers_actual_generated_extensions(self):
        provider = RenderingProviderRegistry.get_provider('react_three_fiber')
        result = provider.process_blueprint({'rendering': {'strategy': 'webgl'}}, rendering_strategy='webgl')
        structure = dict(result['project_structure'])
        # A .tsx page (as written by CodeGenerationEngine) with a banned engine
        # must still be inspected by provider validation.
        structure['src/pages/Home.tsx'] = "import babylon from 'babylonjs';\nexport default function Home() { return null }"
        val = provider.validate_project(None, structure)
        self.assertFalse(val['valid'])
        self.assertTrue(any('Home.tsx' in e for e in val['errors']))

        spline = RenderingProviderRegistry.get_provider('spline')
        sres = spline.process_blueprint({'rendering': {'strategy': 'spline'}},
                                        rendering_strategy='spline', spline_scene_url=VALID_SPLINE_URL)
        sstructure = dict(sres['project_structure'])
        sstructure['src/pages/Home.tsx'] = "export default function Home() { return <div scene=\"javascript:alert(1)\" /> }"
        sval = spline.validate_project(None, sstructure)
        self.assertFalse(sval['valid'])


# --------------------------------------------------------------------------
# D/F/S/T + §18: negative architecture assertions (production code scan)
# --------------------------------------------------------------------------

FORBIDDEN_IDENTIFIERS = [
    'R3FGenerationEngine',
    'ReactThreeFiberGenerationEngine',
    'SplineGenerationEngine',
    'ThreeDRegistry',
    'RendererRegistry2',
    'RendererSelectionService',
    'RendererSelectionEngine',
    'SecondGenerationPipeline',
    'PolyHaven',
    'polyhaven',
    'sketchfab',
    'Sketchfab',
    'gltf_transform',
    'SplineMcp',
    'spline_mcp',
    'ThreeJsMcp',
    'threejs_mcp_connector',
    'R3fMcp',
    'r3f_mcp',
    'DreiMcp',
    'drei_mcp',
]

SCAN_DIRS = ['services', 'models', 'controllers']


def _scan_production_code():
    hits = []
    for sub in SCAN_DIRS:
        root = os.path.join(MODULE_ROOT, sub)
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                if not fn.endswith('.py'):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                for ident in FORBIDDEN_IDENTIFIERS:
                    if ident in content:
                        hits.append((path, ident))
    return hits


class TestNegativeArchitecture(unittest.TestCase):

    def test_d_s_no_forbidden_parallel_architecture(self):
        hits = _scan_production_code()
        self.assertEqual(hits, [], f'Forbidden architecture identifiers found: {hits}')

    def test_f_single_rendering_provider_registry(self):
        registry_classes = []
        providers_dir = os.path.join(MODULE_ROOT, 'services', 'design', 'providers')
        for fn in os.listdir(providers_dir):
            if not fn.endswith('.py'):
                continue
            with open(os.path.join(providers_dir, fn), 'r', encoding='utf-8') as fh:
                content = fh.read()
            registry_classes += re.findall(r'^class\s+(\w*Registry\w*)\s*[(:]', content, flags=re.M)
        self.assertEqual(registry_classes, ['RenderingProviderRegistry'])

    def test_t_single_generation_owners(self):
        def count_class(name):
            found = []
            for sub in SCAN_DIRS:
                root = os.path.join(MODULE_ROOT, sub)
                for dirpath, _d, filenames in os.walk(root):
                    for fn in filenames:
                        if not fn.endswith('.py'):
                            continue
                        path = os.path.join(dirpath, fn)
                        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                            content = fh.read()
                        if re.search(rf'^class\s+{name}\s*[(:]', content, flags=re.M):
                            found.append(path)
            return found

        for cls in ['GenerationCoordinator', 'WebsiteGenerationPipeline', 'GenerationRuntime',
                    'CodeGenerationEngine', 'WorkspaceGeneratorEngine', 'DesignOrchestrationEngine',
                    'ComponentRankingEngine', 'ComponentIntelligenceEngine']:
            found = count_class(cls)
            self.assertEqual(len(found), 1, f'Expected exactly one {cls}, found: {found}')

    def test_no_direct_external_clients_in_generation(self):
        gen_root = os.path.join(MODULE_ROOT, 'services', 'generation')
        offenders = []
        for dirpath, _d, filenames in os.walk(gen_root):
            for fn in filenames:
                if not fn.endswith('.py'):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                if re.search(r'^\s*(import requests|import httpx|from requests|from httpx|urllib\.request\.urlopen)', content, flags=re.M):
                    offenders.append(path)
        self.assertEqual(offenders, [])

    def test_no_new_connector_or_mcp_registry_entries(self):
        data_dir = os.path.join(MODULE_ROOT, 'data')
        connector_files = sorted(f for f in os.listdir(data_dir) if f.startswith('connector_'))
        # The six canonical connector definition files plus the pre-existing
        # health cron (baseline commit d662a11). U8 must not add any more.
        self.assertEqual(connector_files, [
            'connector_context7_data.xml',
            'connector_firecrawl_data.xml',
            'connector_github_data.xml',
            'connector_gosom_data.xml',
            'connector_health_cron.xml',
            'connector_penpot_data.xml',
            'connector_tavily_data.xml',
        ])

    def test_renderer_mcp_entries_remain_disabled_and_unused(self):
        """U8 must not create or enable Spline/Three.js/R3F/Drei MCP servers.

        These entries pre-exist U8 in config/mcp_registry.json as
        enabled=False / lifecycle=planned reference stubs. U8 neither touches
        the file nor wires the rendering providers to them. This test pins
        that invariant so a future change cannot silently enable them.
        """
        with open(os.path.join(MODULE_ROOT, 'config', 'mcp_registry.json'), 'r', encoding='utf-8') as fh:
            registry = json.load(fh)
        servers = registry.get('mcpServers', {})

        renderer_related = ['spline_mcp', 'threejs_docs_mcp', 'r3f_docs_mcp', 'drei_docs_mcp']
        for name in renderer_related:
            self.assertIn(name, servers, f'{name} unexpectedly removed from registry')
            entry = servers[name]
            self.assertFalse(entry.get('enabled'), f'{name} must remain disabled (U8 must not enable it)')
            self.assertEqual(entry.get('lifecycle'), 'planned', f'{name} must remain lifecycle=planned')

        # No renderer-related server may be enabled.
        enabled = [k for k, v in servers.items() if v.get('enabled')]
        for name in enabled:
            self.assertNotIn(name, renderer_related, f'U8 enabled a forbidden renderer MCP: {name}')

        # The rendering providers must not use any MCP client/transport. We
        # match concrete usage patterns (imports / client calls), not the bare
        # word "mcp", which legitimately appears in architecture docstrings.
        usage_patterns = (
            'import mcp', 'from mcp', 'stdio_client', 'clientsession',
            'multiservermcpclient', 'mcp_client', 'call_tool', 'run_mcp',
            'spline_mcp', 'threejs_docs', 'r3f_docs', 'drei_docs',
        )
        providers_dir = os.path.join(MODULE_ROOT, 'services', 'design', 'providers')
        for fn in ('react_provider.py', 'react_three_fiber_provider.py', 'spline_provider.py',
                   'rendering_provider.py', 'provider_registry.py'):
            with open(os.path.join(providers_dir, fn), 'r', encoding='utf-8') as fh:
                content = fh.read().lower()
            for token in usage_patterns:
                self.assertNotIn(token, content,
                                 f'{fn} must not use MCP transport/client ({token})')


if __name__ == '__main__':
    unittest.main()
