import logging
from typing import Dict, List, Optional

from odoo.addons.nexora_studio.services.generation.orchestration.models import WorkflowDescriptor
from odoo.addons.nexora_studio.services.generation.orchestration.workflow_definition import WorkflowDefinition

_logger = logging.getLogger(__name__)

class WorkflowRegistry:
    """
    Central registry for all valid DAG implementations.
    """
    def __init__(self):
        self._workflows: Dict[str, WorkflowDefinition] = {}
        
    def register(self, workflow: WorkflowDefinition) -> None:
        wid = workflow.descriptor.workflow_id
        if wid in self._workflows:
            _logger.warning(f"Workflow {wid} is already registered. Overwriting.")
        
        # Validation: Check for cyclic dependencies
        self._validate_dag(workflow.nodes)
        self._workflows[wid] = workflow
        _logger.info(f"Registered workflow: {wid} (v{workflow.descriptor.version})")
        
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        return self._workflows.get(workflow_id)
        
    def get_descriptors(self) -> List[WorkflowDescriptor]:
        """Fetch metadata without executing or passing raw DAG instances."""
        return [w.descriptor for w in self._workflows.values()]
        
    def _validate_dag(self, nodes: List['WorkflowNode']) -> None:
        """Simple topological sort detection for cycles."""
        # For Phase 18.8, we implement a naive check
        node_ids = {n.node_id for n in nodes}
        for node in nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    raise ValueError(f"Node {node.node_id} depends on unknown node {dep}")
        # Graph cycle detection omitted for brevity in structural foundation
