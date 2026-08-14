from typing import Callable, Dict, List, Any
import logging

_logger = logging.getLogger(__name__)

class KnowledgeEventBus:
    """Decoupled internal event bus for the Knowledge Framework."""
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        
    def subscribe(self, event_name: str, callback: Callable) -> None:
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)
        
    def publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        _logger.debug(f"Knowledge Event Published: {event_name}")
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    callback(payload)
                except Exception as e:
                    _logger.exception(f"Error in knowledge event listener for {event_name}: {e}")
