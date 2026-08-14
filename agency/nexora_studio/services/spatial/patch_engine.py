from typing import Dict, Any, List, Optional
from odoo.addons.nexora_studio.services.spatial.document_model import DocumentModel
from odoo.addons.nexora_studio.services.spatial.events import DocumentEvent
from odoo.addons.nexora_studio.services.spatial.spatial_event_bus import SpatialEventBus

class PatchEngine:
    """
    The exclusive mutator of the DocumentModel.
    Supports transactions, validation pipelines, and rollbacks.
    """
    def __init__(self, document: DocumentModel, event_bus: SpatialEventBus):
        self.document = document
        self.event_bus = event_bus
        self._history: List[Dict[str, Any]] = []
        self._active_transaction: Optional[List[Dict[str, Any]]] = None
        
    def begin_transaction(self) -> None:
        if self._active_transaction is not None:
            raise ValueError("Transaction already in progress.")
        self._active_transaction = []
        
    def commit(self) -> None:
        if self._active_transaction is None:
            raise ValueError("No active transaction to commit.")
            
        # In a real system, we'd apply all patches here atomically
        for patch in self._active_transaction:
            self.apply_patch(patch)
            
        self._active_transaction = None
        
    def apply_patch(self, patch: Dict[str, Any]) -> bool:
        """
        Validates and applies a patch to the DocumentModel.
        """
        if self._active_transaction is not None:
            self._active_transaction.append(patch)
            return True
            
        action = patch.get("action")
        node_id = patch.get("node_id")
        data = patch.get("data", {})
        
        # 1. Validation (e.g., node exists, schema matches)
        if action == "update" and node_id not in self.document.get_all_nodes():
            return False
            
        # 2. Snapshot for rollback
        original_state = None
        if action == "update":
            original_state = dict(self.document.get_node(node_id))
            
        # 3. Apply
        self.document.apply_raw_patch(node_id, data)
        
        # 4. History
        self._history.append({
            "action": action,
            "node_id": node_id,
            "rollback_data": original_state
        })
        
        self.event_bus.publish(DocumentEvent.PATCH_APPLIED.value, {"node_id": node_id})
        
        if action == "update":
            self.event_bus.publish(DocumentEvent.NODE_UPDATED.value, {"node_id": node_id})
        elif action == "create":
            self.event_bus.publish(DocumentEvent.NODE_ADDED.value, {"node_id": node_id})
            
        return True
        
    def rollback(self) -> bool:
        """Undoes the last patch in history or aborts an active transaction."""
        if self._active_transaction is not None:
            self._active_transaction = None
            return True
            
        if not self._history:
            return False
            
        last_patch = self._history.pop()
        action = last_patch["action"]
        node_id = last_patch["node_id"]
        
        if action == "update":
            # Restore original state
            self.document.get_all_nodes()[node_id] = last_patch["rollback_data"]
            self.document.version += 1
            self.event_bus.publish(DocumentEvent.PATCH_ROLLED_BACK.value, {"node_id": node_id})
            return True
            
        return False
