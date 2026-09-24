# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
from odoo.addons.nexora_studio.services.generation.core.generation_coordinator import GenerationCoordinator
from odoo.addons.nexora_studio.services.generation.core.generation_context import GenerationContext, WebsiteGenerationArtifact, GenerationState, RequirementModel, SupervisorPrepareContract, SupervisorEvaluateContract
import json

from odoo.tests import tagged

@dataclass
class MockState:
    name: str

@tagged('post_install', '-at_install')
class TestPhase48SupervisorEvaluation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.orchestrator = MagicMock()
        self.orchestrator.env = MagicMock()
        self.orchestrator.env.context = {}
        self.state_manager = MagicMock()
        self.event_bus = MagicMock()
        
        self.session = MagicMock()
        self.session.id = 1
        
        self.coordinator = GenerationCoordinator(self.session)
        self.coordinator.orchestrator = self.orchestrator
        self.coordinator.state_manager = self.state_manager
        self.coordinator.event_bus = self.event_bus
        
        # We also need a fake pipeline that returns COMPLETED
        self.pipeline = MagicMock()
        self.coordinator.pipeline = self.pipeline
        self.session.workspace_id = MagicMock()
        self.session.workspace_id.workspace_path = "/tmp/workspace"
        self.context_id = "test-context"
        
        # Setup mock GenerationContext that pipeline returns
        self.ctx = GenerationContext(
            context_id=self.context_id, 
            artifact=WebsiteGenerationArtifact(
                requirements=RequirementModel(raw_input="test requirements")
            ),
            state=GenerationState.PENDING
        )
        self.state_manager.load_checkpoint.return_value = self.ctx
        
        # Setup the pipeline run to return COMPLETED context
        self.completed_ctx = self.ctx.evolve(state=GenerationState.COMPLETED)
        self.pipeline.run.return_value = self.completed_ctx

    @patch('odoo.addons.nexora_studio.services.generation.core.generation_runtime.GenerationRuntime')
    def test_supervisor_prepare_rejection(self, MockRuntime):
        """Test that generation raises an error if PREPARE rejects the requirement."""
        self.orchestrator.route_request.return_value = {
            "response": '{"is_valid": false, "instruction": null, "rejection_reason": "Too vague"}'
        }
        
        with self.assertRaises(Exception) as exc:
            self.coordinator.start_generation("test requirements", self.session, self.context_id)
            
        self.assertIn("Too vague", str(exc.exception))
        self.assertEqual(self.pipeline.run.call_count, 0)
        
    @patch('odoo.addons.nexora_studio.services.generation.core.generation_runtime.GenerationRuntime')
    def test_supervisor_evaluate_acceptance(self, MockRuntime):
        """Test that if EVALUATE accepts on first try, execution stops."""
        def route_request_side_effect(task_type, prompt, parameters):
            if task_type == "supervisor_prepare":
                return {"response": '{"is_valid": true, "instruction": "do this", "rejection_reason": null}'}
            if task_type == "supervisor_evaluate":
                return {"response": '{"satisfies_requirements": true, "improvement_instruction": null}'}
            return {}
            
        self.orchestrator.route_request.side_effect = route_request_side_effect
        
        self.coordinator.start_generation("test requirements", self.session, self.context_id)
        
        self.assertEqual(self.pipeline.run.call_count, 1)

    @patch('odoo.addons.nexora_studio.services.generation.core.generation_runtime.GenerationRuntime')
    def test_supervisor_improvement_loop(self, MockRuntime):
        """Test that supervisor can trigger improvements up to the cap."""
        # PREPARE valid, EVALUATE rejects twice then accepts
        responses = [
            {"response": '{"is_valid": true, "instruction": "prep", "rejection_reason": null}'}, # PREPARE
            {"response": '{"satisfies_requirements": false, "improvement_instruction": "fix 1"}'}, # EVAL 1
            {"response": '{"satisfies_requirements": false, "improvement_instruction": "fix 2"}'}, # EVAL 2
            {"response": '{"satisfies_requirements": true, "improvement_instruction": null}'}, # EVAL 3
        ]
        
        def route_request_side_effect(task_type, prompt, parameters):
            return responses.pop(0)
            
        self.orchestrator.route_request.side_effect = route_request_side_effect
        
        self.coordinator.start_generation("test requirements", self.session, self.context_id)
        
        # Pipeline ran 3 times
        self.assertEqual(self.pipeline.run.call_count, 3)

    @patch('odoo.addons.nexora_studio.services.generation.core.generation_runtime.GenerationRuntime')
    def test_supervisor_manual_mode_cap(self, MockRuntime):
        """Test that mode=MANUAL caps execution at 1 regardless of evaluation."""
        def route_request_side_effect(task_type, prompt, parameters):
            if task_type == "supervisor_prepare":
                return {"response": '{"is_valid": true, "instruction": "prep", "rejection_reason": null}'}
            if task_type == "supervisor_evaluate":
                # Returns rejection, trying to trigger improvement
                return {"response": '{"satisfies_requirements": false, "improvement_instruction": "fix 1"}'}
            return {}
            
        self.orchestrator.route_request.side_effect = route_request_side_effect
        
        self.coordinator.start_generation("test requirements", self.session, self.context_id, mode="MANUAL")
        
        # Even though evaluate rejected, it stops at 1 because mode is MANUAL
        self.assertEqual(self.pipeline.run.call_count, 1)
