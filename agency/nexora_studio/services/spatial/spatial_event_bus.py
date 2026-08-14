from typing import Dict, Callable, List, Any
import logging

_logger = logging.getLogger(__name__)

class SpatialEventBus:
    """
    Publish/Subscribe bus exclusively for high-frequency Spatial UI events.
    Completely isolated from the Core AI OrchestrationEventBus.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        
    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        
    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        if event_type not in self._subscribers:
            return
        for handler in self._subscribers[event_type]:
            try:
                handler(payload)
            except Exception as e:
                _logger.error(f"Error in SpatialEventBus handler for {event_type}: {e}")
