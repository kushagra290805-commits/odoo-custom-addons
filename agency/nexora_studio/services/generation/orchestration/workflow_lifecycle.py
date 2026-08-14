import logging
from typing import Dict, Any, Optional

from odoo.addons.nexora_studio.services.generation.orchestration.workflow_registry import WorkflowRegistry
from odoo.addons.nexora_studio.services.generation.orchestration.workflow_engine import WorkflowInstance
from odoo.addons.nexora_studio.services.generation.orchestration.shared_workspace import SharedWorkspace
from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import WorkflowState
from odoo.addons.nexora_studio.services.generation.orchestration.multi_agent_orchestrator import MultiAgentOrchestrator
from odoo.addons.nexora_studio.services.generation.core.runtime_interfaces import StateRuntimeAdapter
from odoo.addons.nexora_studio.services.generation.orchestration.orchestration_event_bus import OrchestrationEventBus

_logger = logging.getLogger(__name__)

class WorkflowLifecycleManager:
    """
    Controls the high-level transitions of a workflow instance and persists state.
    """
    def __init__(self, 
                 registry: WorkflowRegistry, 
                 orchestrator: MultiAgentOrchestrator,
                 event_bus: OrchestrationEventBus,
                 state_adapter: StateRuntimeAdapter):
        self._registry = registry
        self._orchestrator = orchestrator
        self._bus = event_bus
        self._state_adapter = state_adapter
        
    def start_workflow(self, workflow_id: str, generation_id: str, generation_runtime: Any) -> Optional[WorkflowInstance]:
        definition = self._registry.get_workflow(workflow_id)
        if not definition:
            _logger.error(f"Workflow {workflow_id} not found in registry.")
            return None
            
        instance = WorkflowInstance(generation_id, definition)
        workspace = SharedWorkspace(generation_id)
        instance.state = WorkflowState.RUNNING
        
        self._bus.publish("WorkflowStarted", {"instance_id": generation_id, "workflow_id": workflow_id})
        
        # Loop until blocked, paused, or completed
        while instance.state == WorkflowState.RUNNING:
            self._orchestrator.step(instance, workspace, generation_runtime)
            
            if instance.state == WorkflowState.PAUSED:
                self._pause(instance, workspace)
                break
                
        return instance
        
    def resume_workflow(self, instance: WorkflowInstance, workspace: SharedWorkspace, generation_runtime: Any) -> None:
        """Called externally (e.g. via Odoo webhook) when human approval is granted."""
        if instance.state != WorkflowState.PAUSED:
            _logger.warning("Cannot resume a workflow that is not paused.")
            return
            
        _logger.info(f"Resuming workflow {instance.instance_id} after human approval.")
        
        # Mark the human approval node as completed
        if instance.paused_at_node_id:
            self._orchestrator._engine.advance_node(instance, instance.paused_at_node_id)
            instance.paused_at_node_id = None
            
        instance.state = WorkflowState.RUNNING
        
        while instance.state == WorkflowState.RUNNING:
            self._orchestrator.step(instance, workspace, generation_runtime)
            
            if instance.state == WorkflowState.PAUSED:
                self._pause(instance, workspace)
                break
                
    def _pause(self, instance: WorkflowInstance, workspace: SharedWorkspace) -> None:
        """Flush state to Odoo."""
        _logger.info("Workflow paused. Checkpointing state to ERP.")
        self._bus.publish("WorkflowPaused", {"instance_id": instance.instance_id})
        
        payload = {
            "completed_nodes": list(instance.completed_node_ids),
            "messages": [msg.__dict__ for msg in workspace._messages],
            "shared_state": workspace._state
        }
        self._state_adapter.checkpoint(payload)
