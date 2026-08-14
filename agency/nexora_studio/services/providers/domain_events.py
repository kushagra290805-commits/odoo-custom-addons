from dataclasses import dataclass
from typing import List, Callable, Dict, Type

@dataclass
class DomainEvent:
    """Base class for all domain events."""
    pass

@dataclass
class ProviderRegistered(DomainEvent):
    provider_id: str
    category: str

@dataclass
class ProviderEnabled(DomainEvent):
    provider_id: str

@dataclass
class ProviderDisabled(DomainEvent):
    provider_id: str

@dataclass
class ProviderInstalled(DomainEvent):
    provider_id: str
    version: str

@dataclass
class ProviderRemoved(DomainEvent):
    provider_id: str

@dataclass
class ProviderExecutionStarted(DomainEvent):
    provider_id: str
    session_uuid: str
    operation: str

@dataclass
class ProviderExecutionCompleted(DomainEvent):
    provider_id: str
    session_uuid: str
    operation: str
    latency_ms: float

@dataclass
class ProviderExecutionFailed(DomainEvent):
    provider_id: str
    session_uuid: str
    operation: str
    error_detail: str

@dataclass
class ProviderMigrationStarted(DomainEvent):
    provider_id: str
    from_version: str
    to_version: str

@dataclass
class ProviderMigrationCompleted(DomainEvent):
    provider_id: str
    to_version: str

@dataclass
class ProviderMigrationFailed(DomainEvent):
    provider_id: str
    error_detail: str

@dataclass
class ProviderCacheInvalidated(DomainEvent):
    provider_id: str

@dataclass
class ProviderCapabilityChanged(DomainEvent):
    provider_id: str


class DomainEventPublisher:
    """
    Internal Event Bus for purely Domain-driven events.
    Bridges to the ProviderEventBus for external transport.
    """
    _handlers: Dict[Type[DomainEvent], List[Callable[[DomainEvent], None]]] = {}

    @classmethod
    def subscribe(cls, event_type: Type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        if event_type not in cls._handlers:
            cls._handlers[event_type] = []
        cls._handlers[event_type].append(handler)

    @classmethod
    def publish(cls, event: DomainEvent) -> None:
        event_type = type(event)
        if event_type in cls._handlers:
            for handler in cls._handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    # Log but do not interrupt execution
                    import logging
                    logging.getLogger(__name__).error(f"Error handling domain event {event_type.__name__}: {e}")

    @classmethod
    def clear(cls) -> None:
        cls._handlers.clear()
