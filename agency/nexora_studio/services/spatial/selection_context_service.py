from typing import Dict, Any
from odoo.addons.nexora_studio.services.spatial.document_model import DocumentModel

class SelectionContextService:
    """
    Generates AI-ready payloads based on the user's canvas selection.
    """
    def __init__(self, document: DocumentModel):
        self.document = document
        
    def extract_semantic_subtree(self, selected_node_id: str) -> Dict[str, Any]:
        """
        Traverses upward or downward to capture enough context for the AI.
        E.g., if a Button is selected, this might extract the entire parent Form.
        """
        try:
            target_node = self.document.get_node(selected_node_id)
        except KeyError:
            return {}
            
        # In a real implementation, we would traverse parents to find the nearest Organism.
        # Here we just return the node itself for demonstration.
        return {
            "focus_node": target_node,
            "context_prompt": f"The user is focused on a {target_node.get('type')}. Maintain design consistency."
        }
