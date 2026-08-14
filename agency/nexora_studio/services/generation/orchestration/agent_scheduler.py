from typing import List, Set, Dict
from odoo.addons.nexora_studio.services.generation.orchestration.workflow_definition import WorkflowDefinition
from odoo.addons.nexora_studio.services.generation.orchestration.models import WorkflowNode

class AgentScheduler:
    """
    Traverses the Workflow DAG and determines which node(s) should execute next.
    Designed for parallelism, but restricted to returning a single node for Phase 18.8 safe orchestration.
    """
    
    def get_next_nodes(self, workflow: WorkflowDefinition, completed_node_ids: Set[str]) -> List[WorkflowNode]:
        """
        Finds all nodes whose dependencies have been met and are not yet completed.
        """
        ready_nodes = []
        for node in workflow.nodes:
            if node.node_id in completed_node_ids:
                continue
                
            # Check if all dependencies are satisfied
            dependencies_met = all(dep in completed_node_ids for dep in node.depends_on)
            
            if dependencies_met:
                ready_nodes.append(node)
                
        # Phase 18.8 constraint: return only the first ready node for strict sequential execution
        if ready_nodes:
            return [ready_nodes[0]]
            
        return []
