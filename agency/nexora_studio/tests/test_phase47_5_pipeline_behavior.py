"""Behavior tests for Phase 47.5 U5 without connector execution."""

import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    ArchitectureModel,
    Content,
    GenerationContext,
    GenerationState,
    RequirementModel,
    TemplateResolution,
    WebsiteGenerationArtifact,
)
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import (
    GenerationStateManager,
)
from odoo.addons.nexora_studio.services.generation.core.workspace_adapter import (
    WorkspaceAdapter,
)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
    ContentEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import (
    RequirementEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.workspace_generator_engine import (
    WorkspaceGeneratorEngine,
)
from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import (
    PipelineEventBus,
)
from odoo.addons.nexora_studio.services.generation.pipeline.website_generation_pipeline import (
    WebsiteGenerationPipeline,
)


class _AI:
    def generate(self, operation, payload):
        if operation == 'ai_code_patch':
            name = payload['task'].split('named ', 1)[1].split(' ', 1)[0]
            return {'full_content': f"function {name}() {{ return <section>{name}</section> }}"}
        if operation == 'generate_content':
            return {'analysis': {'pages': {
                '/': {
                    'seo': {'title': 'Home', 'description': 'Home page'},
                    'metadata': {},
                    'sections': [],
                },
            }}}
        return {'full_content': ''}


class _Tools:
    def execute(self, *args, **kwargs):
        return []


class _Runtime:
    def __init__(self, workspace_path):
        self.workspace = WorkspaceAdapter(workspace_path)
        self.ai = _AI()
        self.tools = _Tools()
        self.metadata = MagicMock(session_id='session-1')


class Phase475PipelineBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.workspace_path = tempfile.mkdtemp(prefix='nexora-phase47-5-')

    def tearDown(self):
        shutil.rmtree(self.workspace_path, ignore_errors=True)

    def _artifact(self):
        return WebsiteGenerationArtifact(
            requirements=RequirementModel(raw_input='Build an agency site', domain='Agency'),
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/', 'sections': ['Hero']},
                'services': {'type': 'page', 'path': '/services', 'sections': ['Services']},
            }),
        )

    def test_content_engine_has_one_registry_instance_and_correct_placement(self):
        pipeline = WebsiteGenerationPipeline(
            MagicMock(), GenerationStateManager(), PipelineEventBus()
        )
        content_engines = [
            engine for engine, _next_state in pipeline.registry.values()
            if isinstance(engine, ContentEngine)
        ]
        self.assertEqual(len(content_engines), 1)
        engine, next_state = pipeline.registry[GenerationState.ASSETS_GENERATED]
        self.assertIsInstance(engine, ContentEngine)
        self.assertEqual(next_state, GenerationState.CONTENT_GENERATED)
        workspace_engine, workspace_state = pipeline.registry[GenerationState.CONTENT_GENERATED]
        self.assertIsInstance(workspace_engine, WorkspaceGeneratorEngine)
        self.assertEqual(workspace_state, GenerationState.WORKSPACE_PREPARED)

    def test_requirement_engine_preserves_explicit_fields(self):
        artifact = WebsiteGenerationArtifact(requirements=RequirementModel(
            raw_input='Build a healthcare site with a blog',
            domain='Healthcare', target_audience='Patients',
            goals=['Book appointments'], features=['ExplicitFeature'],
            branding={'primary': '#123'}, seo={'title': 'Clinic'},
            accessibility={'level': 'AA'},
        ))
        result = RequirementEngine(MagicMock()).execute(artifact, MagicMock())
        self.assertTrue(result.success)
        # Phase 47.32 (canonical): the engine deterministically derives the
        # capability contract from the brief; every explicit field is
        # preserved. (Pre-47.32 this test asserted full-model equality,
        # which the capability contract legitimately extends.)
        evolved = result.artifact.requirements
        self.assertEqual(evolved.domain, 'Healthcare')
        self.assertEqual(evolved.target_audience, 'Patients')
        self.assertEqual(evolved.goals, ['Book appointments'])
        self.assertEqual(evolved.features, ['ExplicitFeature'])
        self.assertEqual(evolved.branding['primary'], '#123')
        self.assertEqual(evolved.seo['title'], 'Clinic')
        self.assertEqual(evolved.accessibility['level'], 'AA')
        self.assertEqual(evolved.capabilities, ['website_content'])
        self.assertTrue(evolved.backend_required)

    def test_workspace_materializes_to_real_runtime_root(self):
        template = Path(self.workspace_path) / 'template'
        target = Path(self.workspace_path) / 'target'
        template.mkdir()
        (template / 'package.json').write_text('{}', encoding='utf-8')
        target.mkdir()
        runtime = _Runtime(str(target))
        artifact = self._artifact().evolve(template=TemplateResolution(
            template_name='Test', template_path=str(template), template_source='local',
        ))
        result = WorkspaceGeneratorEngine(MagicMock()).execute(artifact, runtime)
        self.assertTrue(result.success)
        self.assertEqual(result.artifact.workspace.project_path, str(target.resolve()))
        self.assertTrue((target / '.nexora' / 'workspace_meta.json').exists())

    def test_invalid_workspace_path_fails_materialization(self):
        template = Path(self.workspace_path) / 'template'
        template.mkdir()
        invalid_root = Path(self.workspace_path) / 'not-a-directory'
        invalid_root.write_text('file', encoding='utf-8')
        runtime = _Runtime(str(invalid_root))
        artifact = self._artifact().evolve(template=TemplateResolution(
            template_name='Test', template_path=str(template), template_source='local',
        ))
        result = WorkspaceGeneratorEngine(MagicMock()).execute(artifact, runtime)
        self.assertFalse(result.success)
        self.assertIn('Template materialization failed', result.error)

    def test_code_generation_writes_pages_and_existing_app_entry(self):
        runtime = _Runtime(self.workspace_path)
        result = CodeGenerationEngine(MagicMock()).execute(self._artifact(), runtime)
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.metadata['patches_applied'], 2)
        self.assertTrue(Path(self.workspace_path, 'src/pages/index.tsx').exists())
        self.assertTrue(Path(self.workspace_path, 'src/pages/services.tsx').exists())
        app = Path(self.workspace_path, 'src/App.jsx').read_text(encoding='utf-8')
        self.assertIn("import HomePage from './pages/index'", app)
        self.assertIn("import ServicesPage from './pages/services.tsx'", app)
        self.assertIn("'/services': ServicesPage", app)

    def test_write_failure_fails_stage_without_incrementing_count(self):
        runtime = _Runtime(self.workspace_path)
        runtime.workspace.write_file = MagicMock(side_effect=OSError('disk full'))
        result = CodeGenerationEngine(MagicMock()).execute(self._artifact(), runtime)
        self.assertFalse(result.success)
        self.assertNotIn('patches_applied', result.metadata)
        self.assertIn('disk full', result.error)

    def test_content_failure_propagates(self):
        runtime = _Runtime(self.workspace_path)
        runtime.ai.generate = MagicMock(side_effect=RuntimeError('content unavailable'))
        with self.assertRaisesRegex(RuntimeError, 'content unavailable'):
            ContentEngine(MagicMock()).execute(self._artifact(), runtime)

    def test_u4_checkpoint_round_trip_preserves_generated_content(self):
        context = GenerationContext(
            context_id='u5-content',
            artifact=self._artifact().evolve(content=Content(pages={
                '/': {'seo': {'title': 'Home'}, 'sections': []},
            })),
        )
        manager = GenerationStateManager()
        manager.save_checkpoint(context)
        restored = manager.load_checkpoint(context.context_id)
        self.assertEqual(restored.artifact.content, context.artifact.content)


if __name__ == '__main__':
    unittest.main()
