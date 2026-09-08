"""Focused tests for Phase 47.4 U4 state, retry, and progress integrity."""

import ast
from dataclasses import asdict
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    ArchitectureModel,
    Assets,
    ComponentTree,
    Content,
    GenerationContext,
    GenerationProgress,
    GenerationState,
    PreviewArtifacts,
    RequirementModel,
    TemplateResolution,
    Theme,
    ValidationReport,
    WebsiteGenerationArtifact,
    Workspace,
)
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import (
    GenerationStateManager,
)
from odoo.addons.nexora_studio.services.generation.engines.base_engine import (
    EngineExecutionResult,
)
from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import (
    PipelineEventBus,
)
from odoo.addons.nexora_studio.services.generation.pipeline.website_generation_pipeline import (
    WebsiteGenerationPipeline,
)


ROOT = Path(__file__).resolve().parents[1]


class Phase474StateIntegrityTests(unittest.TestCase):
    def _context(self):
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(
                raw_input='Build a complete site', domain='Agency',
                target_audience='Owners', goals=['Convert'],
                features=['Blog'], branding={'color': '#fff'},
                seo={'title': 'Agency'}, accessibility={'wcag': 'AA'},
            ),
            research={'businesses': [{'id': 'place-1'}]},
            knowledge={'documents': [{'id': 'doc-1'}]},
            architecture=ArchitectureModel(
                layout_strategy='Grid', responsive_behavior={'mobile': True},
                design_system='system', component_hierarchy={'home': {'type': 'page'}},
                relationships=[{'from': 'home', 'to': 'hero'}],
            ),
            component_tree=ComponentTree(
                nodes=[{'component_id': 'hero'}], dependencies=['react'],
            ),
            theme=Theme(
                design_tokens={'primary': '#000'}, typography_scale={'h1': '3rem'},
                spacing_system={'md': '1rem'}, colors={'primary': '#000'},
                radius='4px', shadows='none', motion={'duration': 100},
            ),
            assets=Assets(
                images=[{'id': 'hero'}], icons=[{'id': 'menu'}],
                fonts=[{'family': 'Inter'}],
            ),
            content=Content(pages={'/': {'title': 'Home'}}),
            template=TemplateResolution(
                template_id=1, template_name='Vite', template_path='D:/workspace',
                template_source='local', template_metadata={'kind': 'react'},
                template_capabilities=['spa'], template_variables={'name': 'Site'},
            ),
            design={'provider': 'react'},
            validation=ValidationReport(
                passed=True, accessibility_score=95, seo_score=90,
                performance_score=85, issues=[{'type': 'warning'}],
            ),
            previews=PreviewArtifacts(
                desktop_url='http://desktop', tablet_url='http://tablet',
                mobile_url='http://mobile', dom_snapshot='<main/>',
            ),
            workspace=Workspace(
                session_id='1', project_path='D:/workspace', is_ready=True,
            ),
            generation_metadata={'candidate_components': [{'id': 'hero'}]},
        )
        return GenerationContext(
            context_id='context-1', artifact=artifact,
            metadata={'trace': {'id': 1}},
            progress=GenerationProgress(
                percentage=50.0, current_step='ARCHITECTURE_COMPLETED',
                messages=['completed'], started_at=1.0, updated_at=2.0,
            ),
            state=GenerationState.ARCHITECTURE_COMPLETED,
        )

    def test_checkpoint_round_trip_preserves_complete_context(self):
        manager = GenerationStateManager()
        original = self._context()
        manager.save_checkpoint(original)
        restored = manager.load_checkpoint(original.context_id)

        self.assertEqual(asdict(restored), asdict(original))
        self.assertIsNot(restored, original)
        self.assertIsNot(restored.artifact, original.artifact)

    def test_corrupt_checkpoint_fails_clearly(self):
        manager = GenerationStateManager()
        manager._checkpoints['bad'] = {
            'context_id': 'bad', 'artifact': {'requirements': {}},
            'metadata': {}, 'progress': {}, 'state': 'PENDING',
        }
        with self.assertRaisesRegex(ValueError, 'Invalid generation checkpoint'):
            manager.load_checkpoint('bad')

    def test_failed_partial_context_does_not_replace_valid_checkpoint(self):
        manager = GenerationStateManager()
        original = self._context()
        manager.save_checkpoint(original)

        partial = original.evolve(
            artifact=original.artifact.evolve(research={'partial': True}),
            state=GenerationState.FAILED,
        )
        manager.save_checkpoint(partial)
        restored = manager.rollback(original.context_id)

        self.assertEqual(restored.state, original.state)
        self.assertEqual(restored.artifact.research, original.artifact.research)
        self.assertEqual(manager._metadata_store[original.context_id]['retry_count'], 1)

    def test_cancellation_without_http_request_is_safe(self):
        manager = GenerationStateManager()
        self.assertFalse(manager.check_interruption('context-1'))
        manager.interrupt('context-1')
        self.assertTrue(manager.check_interruption('context-1'))

    def test_retry_reuses_one_runtime_and_restores_valid_boundary(self):
        state_manager = GenerationStateManager()
        event_bus = PipelineEventBus()
        pipeline = WebsiteGenerationPipeline(MagicMock(), state_manager, event_bus)

        class RetryEngine:
            calls = 0

            def execute(self, artifact, runtime):
                self.calls += 1
                if self.calls == 1:
                    artifact.research['partial'] = True
                    raise RuntimeError('first attempt fails')
                self.assert_restored = 'partial' not in artifact.research
                return EngineExecutionResult(True, artifact, {}, None)

        engine = RetryEngine()
        pipeline.registry = {
            GenerationState.PENDING: (engine, GenerationState.REQUIREMENTS_CAPTURED),
        }
        runtime = MagicMock()
        runtime.metadata.session_id = '1'
        runtime.get_scoped_view.return_value = runtime
        context = GenerationContext(context_id='retry-1')
        state_manager.save_checkpoint(context)

        result = pipeline.run(context, runtime)

        self.assertEqual(engine.calls, 2)
        self.assertTrue(engine.assert_restored)
        self.assertEqual(result.state, GenerationState.REQUIREMENTS_CAPTURED)
        self.assertEqual(runtime.get_scoped_view.call_count, 2)

    def test_u4_files_do_not_use_http_request_or_new_persistence(self):
        state_source = (ROOT / 'services/generation/core/generation_state_manager.py').read_text(encoding='utf-8')
        self.assertNotIn('odoo.http', state_source)
        self.assertNotIn('request.env', state_source)
        for banned in ('redis', 'checkpoint_model', 'job_queue'):
            self.assertNotIn(banned, state_source.lower())
        ast.parse(state_source)


if __name__ == '__main__':
    unittest.main()
