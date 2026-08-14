import logging
from typing import Set, List, Optional
from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import WorkflowState
from odoo.addons.nexora_studio.services.generation.orchestration.workflow_definition import WorkflowDefinition
from odoo.addons.nexora_studio.services.generation.orchestration.models import WorkflowNode

_logger = logging.getLogger(__name__)

class WorkflowInstance:
    """The dynamic, stateful instance of a workflow executing."""
    def __init__(self, instance_id: str, definition: WorkflowDefinition):
        self.instance_id = instance_id
        self.definition = definition
        self.state = WorkflowState.PENDING
        self.completed_node_ids: Set[str] = set()
        self.current_node_id: Optional[str] = None
        self.paused_at_node_id: Optional[str] = None

class WorkflowEngine:
    """
    Maintains the state machine of the workflow graph.
    Does not execute agents, purely manages graph progression.
    """
    
    def advance_node(self, instance: WorkflowInstance, node_id: str) -> None:
        """Mark a node as completed."""
        instance.completed_node_ids.add(node_id)
        instance.current_node_id = None
        _logger.debug(f"WorkflowEngine: Node {node_id} marked complete.")
        
    def is_complete(self, instance: WorkflowInstance) -> bool:
        """Check if all nodes in the DAG have finished."""
        total_nodes = len(instance.definition.nodes)
        return len(instance.completed_node_ids) == total_nodes
        
    def get_node_by_id(self, instance: WorkflowInstance, node_id: str) -> Optional[WorkflowNode]:
        for n in instance.definition.nodes:
            if n.node_id == node_id:
                return n
        return None
