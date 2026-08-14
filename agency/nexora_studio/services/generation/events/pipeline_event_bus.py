import logging
import traceback
from typing import List, Tuple, Any
from odoo.addons.nexora_studio.services.generation.events.events import PipelineEvent
from odoo.addons.nexora_studio.services.generation.events.subscribers.base_subscriber import PipelineEventSubscriber

_logger = logging.getLogger(__name__)

class PipelineEventBus:
    """
    A lightweight, framework-independent event bus.
    Decouples the WebsiteGenerationPipeline from telemetry, streaming, and UI updates.
    """
    def __init__(self):
        # List of tuples: (priority, subscriber)
        self._subscribers: List[Tuple[int, PipelineEventSubscriber]] = []
        
    def subscribe(self, subscriber: PipelineEventSubscriber, priority: int = 50) -> None:
        """Register a subscriber with a priority (lower number = executes first)."""
        if subscriber not in [s[1] for s in self._subscribers]:
            self._subscribers.append((priority, subscriber))
            # Keep sorted by priority
            self._subscribers.sort(key=lambda x: x[0])
            _logger.debug(f"EventBus: Registered {subscriber.__class__.__name__} with priority {priority}")

    def unsubscribe(self, subscriber: PipelineEventSubscriber) -> None:
        """Remove a registered subscriber."""
        self._subscribers = [s for s in self._subscribers if s[1] != subscriber]
        _logger.debug(f"EventBus: Unregistered {subscriber.__class__.__name__}")

    def publish(self, event: PipelineEvent) -> None:
        """
        Synchronously dispatch an event to all subscribers based on priority.
        Failure of any subscriber is trapped and logged, and will NOT interrupt pipeline execution.
        """
        _logger.debug(f"EventBus: Publishing {event.event_type} [{event.correlation_id}]")
        
        for priority, subscriber in self._subscribers:
            try:
                subscriber.handle(event)
            except Exception as e:
                # Standard Failure Strategy
                _logger.error(f"EventBus: Subscriber {subscriber.__class__.__name__} failed while handling {event.event_type}: {e}")
                _logger.debug(f"Subscriber Exception Traceback:\n{traceback.format_exc()}")
                # Do not retry automatically. Do not interrupt generation.
                continue
