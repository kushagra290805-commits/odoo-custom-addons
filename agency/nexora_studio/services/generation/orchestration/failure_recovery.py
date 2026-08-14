import logging
from typing import Dict, Any

from odoo.addons.nexora_studio.services.generation.orchestration.models import WorkflowNode
from odoo.addons.nexora_studio.services.generation.orchestration.orchestration_event_bus import OrchestrationEventBus

_logger = logging.getLogger(__name__)

class SupervisorEngine:
    """
    Handles failure recovery, retries, and escalations.
    """
    def __init__(self, event_bus: OrchestrationEventBus):
        self._bus = event_bus
        self._retry_counts: Dict[str, int] = {}
        
    def handle_agent_failure(self, node: WorkflowNode, error_context: str) -> bool:
        """
        Return True if we should retry, False if we should escalate and halt.
        """
        current_retries = self._retry_counts.get(node.node_id, 0)
        
        if current_retries < node.retry_count:
            self._retry_counts[node.node_id] = current_retries + 1
            _logger.warning(f"Agent at node {node.node_id} failed. Retrying ({self._retry_counts[node.node_id]}/{node.retry_count}). Context: {error_context}")
            return True
            
        _logger.error(f"Agent at node {node.node_id} exhausted retries. Escalating.")
        self._bus.publish("AgentFailed", {"node_id": node.node_id, "error": error_context})
        return False
