from typing import Dict, Any, List
import uuid

class DocumentModel:
    """
    The Canonical Project State.
    Represents the serializable AST of the entire design project.
    """
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.version = 0
        # Flat dictionary of nodes for fast O(1) lookup. Tree is implied by parent/child references.
        self._nodes: Dict[str, Dict[str, Any]] = {
            "root": {
                "id": "root",
                "type": "core.templates.page",
                "children": [],
                "properties": {}
            }
        }
        
    def generate_id(self) -> str:
        return f"node_{uuid.uuid4().hex[:8]}"
        
    def get_node(self, node_id: str) -> Dict[str, Any]:
        if node_id not in self._nodes:
            raise KeyError(f"Node {node_id} does not exist.")
        return self._nodes[node_id]
        
    def get_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        return self._nodes

    def apply_raw_patch(self, node_id: str, patch_data: Dict[str, Any]) -> None:
        """
        DANGEROUS: Should only be called by the PatchEngine.
        Modifies the DocumentModel directly.
        """
        if node_id not in self._nodes and "id" in patch_data:
            # Create new node
            self._nodes[node_id] = patch_data
        else:
            # Update existing node
            self._nodes[node_id].update(patch_data)
        self.version += 1

    def serialize(self) -> str:
        import json
        return json.dumps({
            "project_id": self.project_id,
            "version": self.version,
            "nodes": self._nodes
        })
