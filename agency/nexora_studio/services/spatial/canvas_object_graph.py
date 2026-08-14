from typing import Dict, Any
from odoo.addons.nexora_studio.services.spatial.document_model import DocumentModel

class CanvasObjectGraph:
    """
    A visual projection of the DocumentModel.
    Used exclusively for rendering. MUST NOT BE MUTATED directly.
    """
    def __init__(self):
        self.graph: Dict[str, Any] = {}
        self.last_sync_version: int = -1
        
    def sync_from_document(self, document: DocumentModel) -> None:
        """
        Rebuilds the visual graph from the canonical document model.
        In a real application, this would calculate absolute X/Y/Z positions 
        based on the DocumentModel's constraints.
        """
        if self.last_sync_version == document.version:
            return # No changes
            
        self.graph = {}
        for node_id, node_data in document.get_all_nodes().items():
            # Create a visual projection
            self.graph[node_id] = {
                "type": node_data.get("type"),
                "render_rect": {"x": 0, "y": 0, "w": 100, "h": 50}, # Mock rect
                "properties": node_data.get("properties", {})
            }
            
        self.last_sync_version = document.version
