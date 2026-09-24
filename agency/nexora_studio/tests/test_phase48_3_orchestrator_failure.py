import unittest
from unittest.mock import MagicMock, call
from odoo.addons.nexora_studio.services.generation.orchestration.multi_agent_orchestrator import MultiAgentOrchestrator
from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import WorkflowState
from odoo.addons.nexora_studio.services.generation.orchestration.workflow_engine import WorkflowInstance
from odoo.addons.nexora_studio.services.generation.orchestration.models import WorkflowNode, AgentExecutionResult
from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import AgentRole, WorkflowState
from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.tests import tagged
from odoo.tests.common import BaseCase

@tagged('-at_install', 'post_install')
class TestPhase48_3OrchestratorFailure(BaseCase):
    def setUp(self):
        super().setUp()
        self.workflow_engine = MagicMock()
        self.workflow_engine.is_complete.return_value = False
        self.scheduler = MagicMock()
        self.agent_registry = MagicMock()
        self.event_bus = MagicMock()
        self.message_router = MagicMock()
        self.agent_runtime = MagicMock()
        
        self.orchestrator = MultiAgentOrchestrator(
            workflow_engine=self.workflow_engine,
            scheduler=self.scheduler,
            agent_registry=self.agent_registry,
            event_bus=self.event_bus,
            message_router=self.message_router,
            agent_runtime_adapter=self.agent_runtime
        )
        
        self.instance = WorkflowInstance(
            instance_id="inst-1",
            definition=MagicMock()
        )
        self.instance.state = WorkflowState.RUNNING
        self.instance.current_node_id = "node-1"
        
        self.node = WorkflowNode(
            node_id="node-1",
            node_type="agent_execution",
            agent_role=AgentRole.PLANNER,
            retry_count=1
        )
        
        self.workspace = MagicMock()
        self.generation_runtime = MagicMock()

    def test_agent_failure_retries_and_escalates(self):
        # Setup scheduler to return our node
        self.scheduler.get_next_nodes.return_value = [self.node]
        self.agent_registry.get_agent_class.return_value = MagicMock()
        
        # Setup agent runtime to fail
        self.agent_runtime.execute.return_value = AgentExecutionResult(
            success=False,
            agent_role="planner",
            node_id="node-1",
            messages_to_emit=[],
            state_mutations={},
            error_context="Test error"
        )
        
        # Attempt 1: Should retry (retry_count=1)
        state = self.orchestrator.step(self.instance, self.workspace, self.generation_runtime)
        self.assertEqual(state, WorkflowState.RUNNING)
        self.assertEqual(self.orchestrator._retry_counts["node-1"], 1)
        # Ensure AgentFailed was not published
        failed_calls = [call for call in self.event_bus.publish.call_args_list if call[0][0] == "AgentFailed"]
        self.assertEqual(len(failed_calls), 0)
        
        # Attempt 2: Should exhaust retries, escalate, and fail
        state = self.orchestrator.step(self.instance, self.workspace, self.generation_runtime)
        self.assertEqual(state, WorkflowState.FAILED)
        self.event_bus.publish.assert_called_with("AgentFailed", {"node_id": "node-1", "error": "Test error"})

if __name__ == '__main__':
    unittest.main()
