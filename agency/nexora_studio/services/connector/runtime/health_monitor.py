"""
Connector Health Monitor
=========================
Part 5 of Phase 26 — Universal Connector Platform Foundation.

Manages periodic health checks and degradation detection for running connectors.
Updates ConnectorHealth state and triggers lifecycle transitions on failure.
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from typing import Dict, List, Optional

from ..domain.models import (
    Connector,
    ConnectorHealth,
    ConnectorHealthStatus,
    ConnectorLifecycleState,
    ConnectorEvent,
    ConnectorEventSeverity,
)
from ..events.bus import ConnectorEventBus

_logger = get_logger(__name__)


class ConnectorHealthMonitor:
    """
    Manages health check state for all registered connectors.

    Responsibilities:
    - Record health check results (success/failure)
    - Track consecutive failures to detect degradation and failures
    - Trigger lifecycle transition callbacks when health changes
    - Never perform external calls directly — receives results via record_check()

    Thread safety: health updates are individual connector-level writes;
    callers should not share Connector objects across threads without locks.
    """

    # Default failure thresholds
    DEGRADED_AFTER_FAILURES: int = 1       # Mark as DEGRADED after N failures
    FAILED_AFTER_FAILURES: int = 3          # Mark as FAILED after N failures
    HEALTHY_AFTER_SUCCESSES: int = 2        # Recover to HEALTHY after N successes

    def __init__(
        self,
        event_bus: Optional[ConnectorEventBus] = None,
    ) -> None:
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Health Check Recording
    # ------------------------------------------------------------------

    def record_success(self, connector: Connector, latency_ms: float = 0.0) -> None:
        """
        Record a successful health check for a connector.
        Updates health state and triggers recovery if thresholds met.
        """
        if connector.health is None:
            connector.health = ConnectorHealth(connector_id=connector.connector_id)

        previous_status = connector.health.status
        connector.health.record_success(latency_ms)

        if (
            previous_status != ConnectorHealthStatus.HEALTHY
            and connector.health.consecutive_successes >= self.HEALTHY_AFTER_SUCCESSES
        ):
            _logger.info(
                "Connector '%s' health recovered to HEALTHY after %d successes.",
                connector.connector_id,
                connector.health.consecutive_successes,
            )
            self._emit_event(
                connector.connector_id,
                "health.recovered",
                ConnectorEventSeverity.INFO,
                {"suggested_state": ConnectorLifecycleState.HEALTHY.value}
            )

    def record_failure(self, connector: Connector, error_detail: str = "") -> None:
        """
        Record a failed health check for a connector.
        Updates health state and triggers degradation/failure if thresholds met.
        """
        if connector.health is None:
            connector.health = ConnectorHealth(connector_id=connector.connector_id)

        connector.health.record_failure(error_detail)
        failures = connector.health.consecutive_failures

        if failures >= self.FAILED_AFTER_FAILURES:
            _logger.error(
                "Connector '%s' FAILED after %d consecutive health failures. Last error: %s",
                connector.connector_id, failures, error_detail,
            )
            self._emit_event(
                connector.connector_id,
                "health.failed",
                ConnectorEventSeverity.ERROR,
                {
                    "error": error_detail,
                    "failures": failures,
                    "suggested_state": ConnectorLifecycleState.FAILED.value
                }
            )
        elif failures >= self.DEGRADED_AFTER_FAILURES:
            self._emit_event(
                connector.connector_id,
                "health.degraded",
                ConnectorEventSeverity.WARNING,
                {
                    "error": error_detail,
                    "failures": failures,
                }
            )

    # ------------------------------------------------------------------
    # Health Inspection
    # ------------------------------------------------------------------

    def get_health(self, connector: Connector) -> ConnectorHealth:
        """Returns the current health state for a connector, initializing if absent."""
        if connector.health is None:
            connector.health = ConnectorHealth(connector_id=connector.connector_id)
        return connector.health

    def is_healthy(self, connector: Connector) -> bool:
        """Returns True if connector is HEALTHY."""
        return connector.health is not None and connector.health.is_healthy()

    def get_unhealthy_connectors(self, connectors: List[Connector]) -> List[Connector]:
        """Returns connectors that are not HEALTHY."""
        return [
            c for c in connectors
            if c.health is None or not c.health.is_healthy()
        ]

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    def _emit_event(
        self,
        connector_id: str,
        event_type: str,
        severity: ConnectorEventSeverity,
        data: Dict[str, Any],
    ) -> None:
        if not self._event_bus:
            return
            
        event = ConnectorEvent(
            connector_id=connector_id,
            event_type=event_type,
            severity=severity,
            message=f"[{event_type}] connector={connector_id}",
            data=data,
            source="health_monitor"
        )
        self._event_bus.publish(event)
