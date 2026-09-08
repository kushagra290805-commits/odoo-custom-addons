"""Odoo-level progress subscriber tests for Phase 47.4 U4."""

from odoo.tests import TransactionCase, tagged

from odoo.addons.nexora_studio.services.generation.events.events import (
    EngineFailed,
    StateTransitionCompleted,
)
from odoo.addons.nexora_studio.services.generation.events.subscribers.progress_subscriber import (
    ProgressSubscriber,
)


@tagged('-at_install', 'post_install', 'phase47_4')
class TestPhase474ProgressOdoo(TransactionCase):
    def setUp(self):
        super().setUp()
        config = self.env['nexora.builder_configuration'].create({
            'name': 'Phase 47.4 Progress Configuration',
        })
        self.session = self.env['nexora.builder_session'].create({
            'name': 'Phase 47.4 Progress Session',
            'builder_configuration_id': config.id,
        })
        self.subscriber = ProgressSubscriber(env=self.env)

    def test_progress_advances_only_after_completed_transition(self):
        self.subscriber.handle(EngineFailed(
            session_id=str(self.session.id), generation_id='gen',
            correlation_id='gen', current_state='PENDING',
            engine_name='RequirementEngine', error='failed',
        ))
        self.assertEqual(self.session.progress_percent, 0.0)
        self.assertEqual(self.session.completed_stages, 0)
        self.assertEqual(self.session.current_stage, 'Failed: RequirementEngine')

        self.subscriber.handle(StateTransitionCompleted(
            session_id=str(self.session.id), generation_id='gen',
            correlation_id='gen', current_state='REQUIREMENTS_CAPTURED',
            metadata={
                'completed_steps': 1,
                'total_steps': 19,
                'percentage': 99.0,
            },
        ))
        self.assertEqual(self.session.completed_stages, 1)
        self.assertEqual(self.session.total_stages, 19)
        self.assertEqual(self.session.current_stage, 'REQUIREMENTS_CAPTURED')
        self.assertAlmostEqual(self.session.progress_percent, 100.0 / 19)
