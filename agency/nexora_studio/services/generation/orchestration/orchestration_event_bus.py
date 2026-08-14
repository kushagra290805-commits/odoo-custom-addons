import logging
from typing import Dict, Any, Callable, List

_logger = logging.getLogger(__name__)

class OrchestrationEventBus:
    """
    Dedicated Event Bus for tracking workflow nodes, approvals, and swarm behavior.
    Distinct from PipelineEventBus (overall progress) and KnowledgeEventBus (syncs).
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        
    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        
    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        _logger.debug(f"OrchestrationEventBus published: {event_type}")
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                try:
                    handler(payload)
                except Exception as e:
                    _logger.error(f"Error in OrchestrationEventBus handler for {event_type}: {e}")
