from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.orchestration.orchestration_event_bus import OrchestrationEventBus

class OrchestrationHealthService:
    """
    Maintains a rolling state of swarm health for Admin Dashboards.
    Listens passively to the OrchestrationEventBus.
    """
    def __init__(self, event_bus: OrchestrationEventBus):
        self._bus = event_bus
        self._metrics = {
            "active_workflows": 0,
            "paused_workflows": 0,
            "failed_workflows": 0,
            "total_nodes_executed": 0,
            "total_human_approvals_requested": 0
        }
        self._bind_events()
        
    def _bind_events(self):
        self._bus.subscribe("WorkflowStarted", self._on_workflow_started)
        self._bus.subscribe("WorkflowCompleted", self._on_workflow_completed)
        self._bus.subscribe("WorkflowPaused", self._on_workflow_paused)
        self._bus.subscribe("WorkflowFailed", self._on_workflow_failed)
        self._bus.subscribe("AgentCompleted", self._on_node_executed)
        self._bus.subscribe("ReviewRequested", self._on_review_requested)
        
    def _on_workflow_started(self, payload: Dict[str, Any]):
        self._metrics["active_workflows"] += 1
        
    def _on_workflow_completed(self, payload: Dict[str, Any]):
        self._metrics["active_workflows"] = max(0, self._metrics["active_workflows"] - 1)
        
    def _on_workflow_paused(self, payload: Dict[str, Any]):
        self._metrics["paused_workflows"] += 1
        
    def _on_workflow_failed(self, payload: Dict[str, Any]):
        self._metrics["failed_workflows"] += 1
        
    def _on_node_executed(self, payload: Dict[str, Any]):
        self._metrics["total_nodes_executed"] += 1
        
    def _on_review_requested(self, payload: Dict[str, Any]):
        self._metrics["total_human_approvals_requested"] += 1

    def system_status(self) -> Dict[str, Any]:
        """Return snapshot of swarm health."""
        return self._metrics.copy()
