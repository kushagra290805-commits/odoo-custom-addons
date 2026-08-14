import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional

from .base_provider import (
    ProviderTelemetryService,
    ProviderSession,
    ProviderExecutionResult,
    ProviderEventBus,
    ProviderEvent,
    ProviderEventChannel,
    ProviderServiceContainer
)

_logger = logging.getLogger(__name__)

class OdooProviderTelemetryService(ProviderTelemetryService):
    """
    Manages telemetry spans and emits events to appropriate channels 
    (TELEMETRY, LOGGING, AUDIT, WEBSOCKET, NOTIFICATIONS).
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container
        self._active_spans: Dict[str, dict] = {}

    @property
    def _event_bus(self) -> ProviderEventBus:
        return self._container.resolve(ProviderEventBus)

    def start_span(self, operation: str, session: ProviderSession) -> str:
        """
        Starts a telemetry span for an execution operation.
        """
        span_id = str(uuid.uuid4())
        start_time = time.time()
        
        self._active_spans[span_id] = {
            "operation": operation,
            "session": session,
            "start_time": start_time,
            "start_dt": datetime.utcnow()
        }

        # Emit span start event to TELEMETRY
        self.emit_event(
            event_type="SPAN_START",
            payload={"span_id": span_id, "operation": operation},
            session=session
        )
        
        return span_id

    def end_span(self, span_id: str, response: ProviderExecutionResult) -> None:
        """
        Ends a telemetry span, calculates duration, and emits completion events.
        """
        if span_id not in self._active_spans:
            _logger.warning(f"end_span called for unknown span_id: {span_id}")
            return

        span_data = self._active_spans.pop(span_id)
        session: ProviderSession = span_data["session"]
        
        duration_ms = (time.time() - span_data["start_time"]) * 1000.0

        # Build payload
        payload = {
            "span_id": span_id,
            "operation": span_data["operation"],
            "success": response.success,
            "token_cost_usd": response.token_cost_usd,
        }
        
        if response.error:
            payload["error_code"] = response.error.error_code
            payload["error_message"] = str(response.error)
            
            # Emit to LOGGING for errors
            self._event_bus.publish(
                ProviderEvent(
                    event_id=f"log_{span_id}",
                    timestamp=datetime.utcnow(),
                    provider_id=session.provider.metadata.provider_id,
                    event_type="PROVIDER_ERROR",
                    channel=ProviderEventChannel.LOGGING,
                    session_uuid=session.session_id,
                    duration_ms=duration_ms,
                    payload=payload
                )
            )

        # Emit span end event to TELEMETRY
        self._event_bus.publish(
            ProviderEvent(
                event_id=f"span_{span_id}",
                timestamp=datetime.utcnow(),
                provider_id=session.provider.metadata.provider_id,
                event_type="SPAN_END",
                channel=ProviderEventChannel.TELEMETRY,
                session_uuid=session.session_id,
                duration_ms=duration_ms,
                payload=payload
            )
        )

    def emit_event(self, event_type: str, payload: Dict[str, Any], session: ProviderSession) -> None:
        """
        Emit a generic telemetry event.
        """
        provider_id = session.provider.metadata.provider_id if session.provider else "unknown"
        
        self._event_bus.publish(
            ProviderEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                timestamp=datetime.utcnow(),
                provider_id=provider_id,
                event_type=event_type,
                channel=ProviderEventChannel.TELEMETRY,
                session_uuid=session.session_id,
                duration_ms=0.0,
                payload=payload
            )
        )
