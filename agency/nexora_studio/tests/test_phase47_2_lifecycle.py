"""Odoo-level lifecycle tests for Phase 47.2 U1/U2."""

import shutil
import tempfile
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    GenerationContext, GenerationState,
)


@tagged('-at_install', 'post_install', 'phase47_2')
class TestPhase472Lifecycle(TransactionCase):
    def setUp(self):
        super().setUp()
        self.config = self.env['nexora.builder_configuration'].create({
            'name': 'Phase 47.2 Test Configuration',
        })
        self.workspace_path = tempfile.mkdtemp(prefix='nexora-phase47-2-')
        self.session = self.env['nexora.builder_session'].create({
            'name': 'Phase 47.2 Test Session',
            'builder_configuration_id': self.config.id,
            'project_name': 'Fallback project name',
            'target_workspace_path': self.workspace_path,
        })

    def tearDown(self):
        shutil.rmtree(self.workspace_path, ignore_errors=True)
        super().tearDown()

    def test_fresh_session_reaches_coordinator_with_requirements(self):
        captured = {}

        class FakeCoordinator:
            def __init__(self, orchestrator):
                captured['orchestrator'] = orchestrator

            def start_generation(self, raw_requirements, session, context_id):
                captured['requirements'] = raw_requirements
                captured['context_id'] = context_id
                captured['session_id'] = session.id
                return GenerationContext(
                    context_id=context_id,
                state=GenerationState.COMPLETED,
            )

        with patch(
            'odoo.addons.nexora_studio.services.generation.core.generation_coordinator.GenerationCoordinator',
            FakeCoordinator,
        ):
            self.env['nexora.builder_session_service'].run_generation(
                self.session,
                requirements='Build a healthcare landing page with an appointment CTA.',
            )

        self.assertEqual(self.session.status, 'ai_reviewing')
        self.assertEqual(
            captured['requirements'],
            'Build a healthcare landing page with an appointment CTA.',
        )
        self.assertEqual(captured['session_id'], self.session.id)
        self.assertTrue(self.session.workspace_id)
        self.assertEqual(self.session.workspace_id.workspace_path, self.workspace_path)

    def test_generation_rejects_already_generating_session(self):
        self.session.write({'status': 'generating'})
        with self.assertRaises(ValidationError):
            self.env['nexora.builder_session_service'].run_generation(
                self.session,
                requirements='A second generation must be rejected.',
            )
