from abc import ABC, abstractmethod
from typing import List

from odoo.addons.nexora_studio.services.generation.orchestration.models import WorkflowDescriptor, WorkflowNode

class WorkflowDefinition(ABC):
    """
    Abstract declarative Python representation of a DAG.
    Phase 18.8 implements workflows as subclasses of this.
    Phase 19.x will serialize/deserialize this to JSON.
    """
    
    @property
    @abstractmethod
    def descriptor(self) -> WorkflowDescriptor:
        pass
        
    @property
    @abstractmethod
    def nodes(self) -> List[WorkflowNode]:
        pass
        
    def to_dict(self) -> dict:
        """Serializable structure for Phase 19.x."""
        return {
            "descriptor": {
                "workflow_id": self.descriptor.workflow_id,
                "version": self.descriptor.version,
                "name": self.descriptor.name,
                "description": self.descriptor.description
            },
            "nodes": [
                {
                    "node_id": node.node_id,
                    "node_type": node.node_type.value,
                    "agent_role": node.agent_role.value if node.agent_role else None,
                    "depends_on": node.depends_on
                }
                for node in self.nodes
            ]
        }
