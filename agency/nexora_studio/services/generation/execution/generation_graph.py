from typing import Dict, List, Set
from odoo.addons.nexora_studio.services.generation.execution.generation_node import GenerationNode, NodeStatus

class GenerationGraph:
    """
    A dependency-aware Directed Acyclic Graph (DAG) for managing execution order.
    """
    def __init__(self):
        self.nodes: Dict[str, GenerationNode] = {}
        
    def add_node(self, node: GenerationNode) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"Node {node.node_id} already exists.")
        self.nodes[node.node_id] = node
        
    def get_ready_nodes(self) -> List[GenerationNode]:
        """Returns nodes that are PENDING and whose dependencies are COMPLETED."""
        ready = []
        for node in self.nodes.values():
            if node.status == NodeStatus.PENDING:
                if all(self.nodes[dep].status == NodeStatus.COMPLETED for dep in node.dependencies):
                    ready.append(node)
        return ready
        
    def get_node(self, node_id: str) -> GenerationNode:
        return self.nodes[node_id]
        
    def is_completed(self) -> bool:
        return all(node.status == NodeStatus.COMPLETED for node in self.nodes.values())
        
    def has_failed(self) -> bool:
        return any(node.status == NodeStatus.FAILED for node in self.nodes.values())
