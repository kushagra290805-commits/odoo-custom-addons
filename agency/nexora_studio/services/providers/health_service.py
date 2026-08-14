import logging
from typing import Dict, Any
from datetime import datetime

from .base_provider import (
    ProviderHealthService,
    ProviderHealth,
    ProviderServiceContainer,
    ProviderRegistry,
    ProviderFactory,
    ProviderStateMachine,
    ProviderRuntimeState,
    ProviderEventBus,
    ProviderEvent,
    ProviderEventChannel,
    ProviderConfiguration,
    ProviderAuthentication
)

_logger = logging.getLogger(__name__)

class OdooProviderHealthService(ProviderHealthService):
    """
    Monitors provider health, implementing a 3-failure circuit breaker.
    Publishes health events to the METRICS channel.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container
        self._consecutive_failures: Dict[str, int] = {}
        self._CIRCUIT_BREAKER_THRESHOLD = 3

    @property
    def _registry(self) -> ProviderRegistry:
        return self._container.resolve(ProviderRegistry)

    @property
    def _factory(self) -> ProviderFactory:
        return self._container.resolve(ProviderFactory)

    @property
    def _state_machine(self) -> ProviderStateMachine:
        return self._container.resolve(ProviderStateMachine)

    @property
    def _event_bus(self) -> ProviderEventBus:
        return self._container.resolve(ProviderEventBus)

    def probe_health(self, provider_id: str) -> ProviderHealth:
        """
        Actively checks the health of a provider by instantiating it and calling check_health().
        Updates the circuit breaker state accordingly.
        """
        metadata = self._registry.get_metadata(provider_id)
        if not metadata:
            return ProviderHealth(
                status="unknown", latency_ms=0.0, error_rate_24h=0.0, 
                last_checked=datetime.utcnow(), details="Provider not found"
            )

        start_time = datetime.utcnow()
        try:
            # We use dummy config/auth just to probe if not provided.
            # In a real Odoo setup, these would be fetched from Vault/Settings.
            config = ProviderConfiguration()
            auth = ProviderAuthentication(auth_type="probe", credentials_vault_key="")
            
            provider = self._factory.create_provider(provider_id, config, auth)
            health = provider.check_health()
            
            # Reset failure count on success
            self._consecutive_failures[provider_id] = 0
            
            # Transition to HEALTHY if it was DEGRADED but is now recovered
            current_state = self._state_machine.get_state(provider_id)
            if current_state == ProviderRuntimeState.DEGRADED:
                self._state_machine.transition(provider_id, ProviderRuntimeState.READY, reason="Health probe recovered")

            # Update state machine's state record logic internally if needed (handled by transition)

        except Exception as e:
            _logger.warning(f"Health probe failed for {provider_id}: {e}")
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Increment failures
            failures = self._consecutive_failures.get(provider_id, 0) + 1
            self._consecutive_failures[provider_id] = failures
            
            cb_open = failures >= self._CIRCUIT_BREAKER_THRESHOLD
            
            health = ProviderHealth(
                status="degraded",
                latency_ms=latency,
                error_rate_24h=0.0, # This would be fetched from MetricsService
                last_checked=datetime.utcnow(),
                details=str(e),
                circuit_breaker_open=cb_open
            )
            
            # Open circuit breaker -> Degraded state
            if cb_open:
                current_state = self._state_machine.get_state(provider_id)
                if current_state != ProviderRuntimeState.DEGRADED:
                    self._state_machine.transition(provider_id, ProviderRuntimeState.DEGRADED, reason=f"Circuit breaker open ({failures} failures)")

        self._publish_health_event(provider_id, health)
        return health

    def get_health(self, provider_id: str) -> ProviderHealth:
        """
        Returns the last known health state without actively probing.
        (For this singleton, we return a constructed placeholder or latest cached. 
        In Odoo, this might query nexora.provider.runtime_state)
        """
        # A full implementation would cache the last ProviderHealth object.
        # Here we do a fast query to the DB if available, else return placeholder.
        current_state = self._state_machine.get_state(provider_id)
        failures = self._consecutive_failures.get(provider_id, 0)
        
        return ProviderHealth(
            status=current_state.value,
            latency_ms=0.0,
            error_rate_24h=0.0,
            last_checked=datetime.utcnow(),
            circuit_breaker_open=failures >= self._CIRCUIT_BREAKER_THRESHOLD
        )

    def schedule_probes(self) -> None:
        """
        Invoked by Odoo ir.cron. Probes all active providers.
        """
        active_providers = self._registry.list_providers(active_only=True)
        for metadata in active_providers:
            self.probe_health(metadata.provider_id)

    def _publish_health_event(self, provider_id: str, health: ProviderHealth) -> None:
        event = ProviderEvent(
            event_id=f"health_{provider_id}_{health.last_checked.timestamp()}",
            timestamp=health.last_checked,
            provider_id=provider_id,
            event_type="HEALTH_CHECK_RESULT",
            channel=ProviderEventChannel.METRICS,
            session_uuid=None,
            duration_ms=health.latency_ms,
            payload={
                "status": health.status,
                "circuit_breaker_open": health.circuit_breaker_open,
                "details": health.details
            }
        )
        self._event_bus.publish(event)
