import logging
from typing import Any

from odoo.addons.nexora_studio.services.generation.orchestration.workflow_engine import WorkflowEngine, WorkflowInstance
from odoo.addons.nexora_studio.services.generation.orchestration.agent_scheduler import AgentScheduler
from odoo.addons.nexora_studio.services.generation.orchestration.shared_workspace import SharedWorkspace, MessageRouter
from odoo.addons.nexora_studio.services.generation.orchestration.orchestration_event_bus import OrchestrationEventBus
from odoo.addons.nexora_studio.services.generation.orchestration.failure_recovery import SupervisorEngine
from odoo.addons.nexora_studio.services.generation.orchestration.agent_registry import AgentRegistry
from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import NodeType, WorkflowState
from odoo.addons.nexora_studio.services.generation.core.runtime_interfaces import AgentRuntimeAdapter

_logger = logging.getLogger(__name__)

class MultiAgentOrchestrator:
    """
    The central execution loop for the Multi-Agent Platform.
    Strictly owns the SharedWorkspace.
    Delegates to AgentRuntime for actual execution.
    """
    def __init__(self, 
                 workflow_engine: WorkflowEngine, 
                 scheduler: AgentScheduler, 
                 agent_registry: AgentRegistry,
                 supervisor: SupervisorEngine,
                 event_bus: OrchestrationEventBus,
                 message_router: MessageRouter,
                 agent_runtime_adapter: AgentRuntimeAdapter):
                 
        self._engine = workflow_engine
        self._scheduler = scheduler
        self._agent_registry = agent_registry
        self._supervisor = supervisor
        self._bus = event_bus
        self._router = message_router
        self._agent_runtime = agent_runtime_adapter
        
    def step(self, instance: WorkflowInstance, workspace: SharedWorkspace, generation_runtime: Any) -> WorkflowState:
        """
        Executes a single step (node) in the DAG.
        Returns the new state of the workflow.
        """
        if instance.state == WorkflowState.PAUSED:
            _logger.info(f"Workflow {instance.instance_id} is PAUSED. Awaiting human resume.")
            return instance.state
            
        if self._engine.is_complete(instance):
            instance.state = WorkflowState.COMPLETED
            self._bus.publish("WorkflowCompleted", {"instance_id": instance.instance_id})
            return instance.state

        # Get next node
        next_nodes = self._scheduler.get_next_nodes(instance.definition, instance.completed_node_ids)
        if not next_nodes:
            # We are blocked, either waiting for parallel threads (Phase 18.x) or stuck.
            # Since Phase 18.8 is sequential, if not complete and no next nodes, it's a DAG stall.
            instance.state = WorkflowState.FAILED
            self._bus.publish("WorkflowFailed", {"instance_id": instance.instance_id, "reason": "DAG Stall"})
            return instance.state
            
        node = next_nodes[0]
        instance.current_node_id = node.node_id
        
        # Handle Node Types
        if node.node_type == NodeType.HUMAN_APPROVAL:
            self._bus.publish("ReviewRequested", {"node_id": node.node_id})
            instance.state = WorkflowState.PAUSED
            instance.paused_at_node_id = node.node_id
            return instance.state
            
        if node.node_type == NodeType.AGENT_EXECUTION:
            return self._execute_agent_node(instance, workspace, generation_runtime, node)
            
        return instance.state

    def _execute_agent_node(self, instance: WorkflowInstance, workspace: SharedWorkspace, generation_runtime: Any, node: Any) -> WorkflowState:
        self._bus.publish("AgentStarted", {"node_id": node.node_id, "role": node.agent_role.value})
        
        # 1. Resolve Agent
        agent_class = self._agent_registry.resolve(node.agent_role)
        if not agent_class:
            _logger.error(f"No implementation registered for role {node.agent_role.value}")
            instance.state = WorkflowState.FAILED
            return instance.state
            
        # 2. Hydrate Context (Read-Only Copy)
        agent_context = workspace.hydrate_agent_context(node.agent_role)
        
        # 3. Execute via frozen AgentRuntime
        result = self._agent_runtime.execute(
            agent_class=agent_class,
            generation_runtime=generation_runtime,
            generation_id=instance.instance_id,
            context=agent_context
        )
        
        # 4. Handle Failure / Success
        if not result.success:
            should_retry = self._supervisor.handle_agent_failure(node, result.error_context)
            if not should_retry:
                instance.state = WorkflowState.FAILED
                return instance.state
            # Return to let the outer loop try again
            return instance.state
            
        # 5. Mutate SharedWorkspace (Orchestrator ONLY)
        self._router.route(result.messages_to_emit, workspace)
        for k, v in result.state_mutations.items():
            workspace.update_state(k, v)
            
        # 6. Advance Engine
        self._engine.advance_node(instance, node.node_id)
        self._bus.publish("AgentCompleted", {"node_id": node.node_id})
        
        return instance.state
