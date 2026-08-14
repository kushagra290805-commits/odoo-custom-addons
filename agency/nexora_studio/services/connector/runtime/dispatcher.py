"""
Connector Dispatcher
====================
Part 5 of Phase 26 — Universal Connector Platform Foundation.

Dispatches ConnectorExecutionRequests to the correct connector instance.
Handles timeout, failure wrapping, and telemetry.
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
import time
from typing import Optional

from ..domain.models import (
    Connector,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    ConnectorExecutionStatus,
)
from ..registry.connector_registry import ConnectorRegistry
from ..registry.capability_index import ConnectorCapabilityIndex
from ..sdk.context import ExecutionContext
from ..sdk.telemetry_port import ConnectorTelemetryPort
from .telemetry_recorder import InMemoryTelemetryRecorder

_logger = get_logger(__name__)


class ConnectorDispatcher:
    """
    Routes ConnectorExecutionRequests to the appropriate connector.

    Rules:
    - Only dispatches to RUNNING connectors
    - If no connector is running for a namespace, returns a failure result
    - Execution errors are wrapped in ConnectorExecutionResult — never raised
    - Telemetry (latency, errors) is recorded but not emitted here (delegate to event bus)

    Future enhancements (Phase 27+):
    - Failover: try next connector in capability index if first fails
    - Circuit breaker: skip connectors with consecutive failures
    - Timeout enforcement: per-connector configurable timeouts
    """

    def __init__(
        self,
        registry: ConnectorRegistry,
        capability_index: ConnectorCapabilityIndex,
        factory=None,
        telemetry: Optional[ConnectorTelemetryPort] = None,
    ) -> None:
        self._registry = registry
        self._capability_index = capability_index
        self._connector_factory = factory
        self.telemetry = telemetry or InMemoryTelemetryRecorder()
        self._active_connectors = {}

    def dispatch(
        self,
        request: ConnectorExecutionRequest,
    ) -> ConnectorExecutionResult:
        """
        Dispatch an execution request to the best available connector.

        Returns ConnectorExecutionResult — never raises.
        """
        start_time = time.monotonic()
        self.telemetry.record_counter("dispatch.count", tags={"namespace": request.capability_namespace})
        namespace = request.capability_namespace
        request_id = request.request_id

        # 1. Resolve exact or primary connector
        connector = self._resolve_connector(request)
        if connector is None:
            self.telemetry.record_counter("dispatch.failure", tags={"error": "CONNECTOR_NOT_FOUND"})
            latency_ms = (time.monotonic() - start_time) * 1000
            self.telemetry.record_histogram("dispatch.latency_ms", latency_ms)
            return ConnectorExecutionResult.fail(
                request_id=request_id,
                error=f"No RUNNING connector found for capability namespace '{namespace}'.",
                error_code="CONNECTOR_NOT_FOUND",
                execution_ms=latency_ms,
            )

        # 2. Check cancellation
        if request.cancellation_requested:
            return ConnectorExecutionResult(
                request_id=request_id,
                status=ConnectorExecutionStatus.CANCELLED,
                error="Execution cancelled before dispatch.",
                execution_ms=(time.monotonic() - start_time) * 1000,
            )

        # 3. Delegate to connector execution (Phase 27+ connectors implement _execute)
        try:
            result = self._execute_on_connector(connector, request)
        except Exception as exc:
            execution_ms = (time.monotonic() - start_time) * 1000
            self.telemetry.record_counter("dispatch.failure", tags={"error": type(exc).__name__})
            self.telemetry.record_histogram("dispatch.latency_ms", execution_ms)
            _logger.error(
                "ConnectorDispatcher: unhandled exception dispatching to connector '%s': %s",
                connector.connector_id, exc, exc_info=True
            )
            return ConnectorExecutionResult.fail(
                request_id=request_id,
                error=str(exc),
                error_code="CONNECTOR_EXECUTION_ERROR",
                execution_ms=execution_ms,
            )

        latency_ms = (time.monotonic() - start_time) * 1000
        result.execution_ms = latency_ms
        self.telemetry.record_histogram("dispatch.latency_ms", latency_ms)
        return result

    def probe_health(self, connector_id: str, context: ExecutionContext) -> tuple[bool, float, str]:
        """
        Execute the lower-level health check on the specified connector instance.
        Returns a tuple of (success, latency_ms, error_message).
        Does NOT update HealthMonitor directly.
        """
        start_time = time.monotonic()
        try:
            connector = self._registry.get(connector_id)
            if not connector:
                return False, 0.0, "Connector not found in registry."
                
            # Re-uses the exact same connector instance and lifecycle resolution
            sdk_connector = self._get_or_create_connector(connector, context)
            if sdk_connector is None:
                return False, 0.0, "Connector instance could not be created or is not running."
                
            is_healthy = sdk_connector.check_health(context)
            latency_ms = (time.monotonic() - start_time) * 1000
            
            if is_healthy:
                return True, latency_ms, ""
            else:
                return False, latency_ms, "Underlying health probe returned False."
                
        except Exception as exc:
            latency_ms = (time.monotonic() - start_time) * 1000
            _logger.warning("ConnectorDispatcher: health probe failed for '%s': %s", connector_id, exc)
            return False, latency_ms, str(exc)

    def _resolve_connector(self, request: ConnectorExecutionRequest) -> Optional[Connector]:
        """
        Find the appropriate RUNNING connector.
        - If request.context.connector_id is present, routes exactly to that connector.
        - Otherwise falls back to capability-based routing.
        """
        import logging
        _log = logging.getLogger(__name__)
        namespace = request.capability_namespace
        connector_id = request.context.connector_id if request.context else None
        
        if connector_id:
            _log.info(f"DISPATCHER: explicit routing to connector '{connector_id}' for '{namespace}'")
            connector = self._registry.get(connector_id)
            if not connector or not connector.is_running:
                _logger.warning("ConnectorDispatcher: explicit connector '%s' not found or not running.", connector_id)
                return None
            if connector_id not in self._capability_index.get_all(namespace):
                _logger.warning("ConnectorDispatcher: explicit connector '%s' does not support namespace '%s'.", connector_id, namespace)
                return None
            return connector

        primary_id = self._capability_index.get_primary(namespace)
        _log.info(f"DISPATCHER: resolving '{namespace}', primary_id={primary_id}")
        if primary_id is None:
            c = self._registry.find_for_capability(namespace)
            _log.info(f"DISPATCHER: fallback scan for '{namespace}' found: {c}")
            return c

        connector = self._registry.get(primary_id)
        _log.info(f"DISPATCHER: registry.get('{primary_id}') = {connector}")
        if connector is not None:
            _log.info(f"DISPATCHER: connector state = {connector.lifecycle_state}, is_running = {connector.is_running}")
            
        if connector is None or not connector.is_running:
            # Primary is down — try next in failover chain
            for fallback_id in self._capability_index.get_all(namespace)[1:]:
                fallback = self._registry.get(fallback_id)
                if fallback and fallback.is_running:
                    _logger.warning(
                        "ConnectorDispatcher: primary '%s' not running for '%s', using fallback '%s'.",
                        primary_id, namespace, fallback_id,
                    )
                    return fallback
            return None

        return connector

    def _get_or_create_connector(self, connector: Connector, context: ExecutionContext) -> Optional[object]:
        if not self._connector_factory:
            return None
        if connector.connector_id not in self._active_connectors:
            try:
                config_dict = connector.configuration.get_resolved_values() if connector.configuration else {}
                sdk_connector = self._connector_factory.create_connector(connector.manifest.connector_type_id, config_dict)
                sdk_connector.initialize(context)
                self._active_connectors[connector.connector_id] = sdk_connector
            except Exception as e:
                _logger.error(f"Failed to create/initialize connector {connector.connector_id}: {e}")
                return None
        return self._active_connectors.get(connector.connector_id)

    def _execute_on_connector(
        self,
        connector: Connector,
        request: ConnectorExecutionRequest,
    ) -> ConnectorExecutionResult:
        """
        Delegate execution to the connector instance via the ConnectorFactory.
        """
        if not self._connector_factory:
            return ConnectorExecutionResult.fail(
                request_id=request.request_id,
                error=(
                    f"Connector '{connector.connector_id}' (type={connector.manifest.connector_type_id}) "
                    "does not have an execution adapter registered. "
                    "Connector execution adapters are implemented in Connector Platform Phase 2."
                ),
                error_code="NO_EXECUTION_ADAPTER",
            )
            
        try:
            sdk_connector = self._get_or_create_connector(connector, request.context)
            if not sdk_connector:
                return ConnectorExecutionResult.fail(
                    request_id=request.request_id,
                    error="Failed to create or initialize the underlying SDK connector.",
                    error_code="NO_EXECUTION_ADAPTER",
                )
            
            try:
                data = sdk_connector.execute(
                    capability_namespace=request.capability_namespace,
                    parameters=request.payload,
                    context=request.context
                )
                return ConnectorExecutionResult.ok(request.request_id, data)
            except Exception as inner_e:
                # If a transport/fatal error occurs, we should evict it so it reconnects on next request
                self._active_connectors.pop(connector.connector_id, None)
                try:
                    sdk_connector.shutdown(request.context)
                except Exception:
                    pass
                raise inner_e
                
        except Exception as exc:
            raise exc

    def shutdown_connector(self, connector_id: str, context: Optional[ExecutionContext] = None) -> None:
        """Shutdown and remove an active connector instance from the cache."""
        sdk_connector = self._active_connectors.pop(connector_id, None)
        if sdk_connector:
            try:
                sdk_connector.shutdown(context)
            except Exception as e:
                _logger.warning(f"Error shutting down connector {connector_id}: {e}")

    def shutdown_all(self) -> None:
        """Shutdown all active connector instances."""
        for connector_id in list(self._active_connectors.keys()):
            self.shutdown_connector(connector_id)
