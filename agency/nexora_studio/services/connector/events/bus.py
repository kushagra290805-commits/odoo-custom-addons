"""
Connector Event Bus
===================
Part 7 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from abc import ABC, abstractmethod
from typing import List, Callable, Dict

from ..domain.models import ConnectorEvent
from ..sdk.telemetry_port import ConnectorTelemetryPort
from ..runtime.telemetry_recorder import InMemoryTelemetryRecorder

_logger = get_logger(__name__)


class EventSubscriber(ABC):
    """
    Abstract base class for components that want to subscribe to ConnectorEvents.
    """
    @abstractmethod
    def handle_event(self, event: ConnectorEvent) -> None:
        """Process the incoming event."""


class ConnectorEventBus:
    """
    Platform-wide event bus for all connector events.
    Replaces direct coupling between components (LifecycleManager, HealthMonitor, etc).
    Synchronous execution in Phase 26.1; no external message broker.
    """

    def __init__(self, telemetry: ConnectorTelemetryPort = None):
        self._subscribers: List[EventSubscriber] = []
        self._event_handlers: Dict[str, List[Callable[[ConnectorEvent], None]]] = {}
        self.telemetry = telemetry or InMemoryTelemetryRecorder()

    def subscribe(self, subscriber: EventSubscriber) -> None:
        """Register a subscriber for all events."""
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)
            _logger.debug("EventBus: Registered subscriber %s", type(subscriber).__name__)

    def unsubscribe(self, subscriber: EventSubscriber) -> None:
        """Remove a subscriber."""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def on(self, event_type: str, handler: Callable[[ConnectorEvent], None]) -> None:
        """Register a function handler for a specific event type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        _logger.debug("EventBus: Registered handler for %s", event_type)

    def publish(self, event: ConnectorEvent) -> None:
        """
        Publish an event to all subscribers and specific event handlers.
        """
        self.telemetry.record_counter("events.published", tags={"event_type": event.event_type})
        _logger.debug(
            "EventBus: Publishing event [type=%s, connector=%s]",
            event.event_type, event.connector_id
        )
        
        # Dispatch to global subscribers
        for subscriber in self._subscribers:
            try:
                subscriber.handle_event(event)
            except Exception as e:
                self.telemetry.record_counter("events.dispatch.failure", tags={"event_type": event.event_type})
                _logger.error(
                    "EventBus: Error dispatching event %s to %s: %s",
                    event.event_id, type(subscriber).__name__, e,
                    exc_info=True
                )

        # Dispatch to specific handlers
        handlers = self._event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self.telemetry.record_counter("events.dispatch.failure", tags={"event_type": event.event_type})
                _logger.error(
                    "EventBus: Error dispatching event %s to handler %s: %s",
                    event.event_id, handler.__name__, e,
                    exc_info=True
                )
