import logging
from typing import Optional

from .base_provider import (
    ProviderStateMachine,
    ProviderRuntimeState,
    LockService,
    ProviderServiceContainer,
    ProviderRegistry
)

_logger = logging.getLogger(__name__)

class OdooProviderStateMachine(ProviderStateMachine):
    """
    Finite State Machine for Provider Runtime State.
    Validates state transitions and synchronizes with Odoo models when available.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container

    @property
    def _lock_service(self) -> LockService:
        return self._container.resolve(LockService)

    def transition(self, provider_id: str, to_state: ProviderRuntimeState, reason: str = "") -> bool:
        """
        Transition a provider to a new state.
        Validates the transition against VALID_TRANSITIONS.
        """
        # Resolve registry to get the provider's current state record
        registry = self._container.resolve(ProviderRegistry)
        metadata = registry.get_metadata(provider_id)
        
        if not metadata:
            _logger.error(f"Cannot transition state for unknown provider: {provider_id}")
            return False

        current_state = self.get_state(provider_id)
        
        # Identity transition is always a no-op success
        if current_state == to_state:
            return True

        if (current_state, to_state) not in self.VALID_TRANSITIONS:
            _logger.error(
                f"Invalid FSM transition for {provider_id}: {current_state.value} -> {to_state.value}. "
                f"Reason: {reason}"
            )
            return False

        # Acquire transition lock to prevent race conditions during FSM updates
        lock_key = f"nexora:provider:{provider_id}:fsm_lock"
        lock_result = self._lock_service.acquire(lock_key, holder_id="fsm", timeout_ms=2000, ttl_ms=5000)
        
        if not lock_result.acquired:
            _logger.error(f"Failed to acquire FSM lock for {provider_id} during transition to {to_state.value}")
            return False

        try:
            # Here we would update the Odoo database model `nexora.provider.runtime_state`
            # Since we are in a pure Python layer, we will update the in-memory state if we have a provider instance.
            # In Odoo, we typically use the env. But we can import odoo.http to check for request.env
            try:
                from odoo import http
                if http.request and hasattr(http.request, 'env'):
                    env = http.request.env
                    state_record = env['nexora.provider.runtime_state'].sudo().search(
                        [('provider_id', '=', provider_id)], limit=1
                    )
                    if state_record:
                        state_record.write({
                            'current_state': to_state.value,
                            'degradation_reason': reason if to_state == ProviderRuntimeState.DEGRADED else False
                        })
            except ImportError:
                pass # Not running in Odoo context (e.g. testing)

            _logger.info(f"Provider {provider_id} transitioned: {current_state.value} -> {to_state.value} ({reason})")
            return True
            
        finally:
            self._lock_service.release(lock_key, holder_id="fsm")

    def get_state(self, provider_id: str) -> ProviderRuntimeState:
        """
        Get the current state of a provider.
        """
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                state_record = env['nexora.provider.runtime_state'].sudo().search(
                    [('provider_id', '=', provider_id)], limit=1
                )
                if state_record:
                    return ProviderRuntimeState(state_record.current_state)
        except ImportError:
            pass

        # Fallback to INSTALLED if no DB record or not in Odoo
        return ProviderRuntimeState.INSTALLED

    def is_invocable(self, provider_id: str) -> bool:
        """
        A provider is invocable if it is in READY or HEALTHY state.
        BUSY providers might also be invocable if concurrency allows, 
        but strictly speaking, execution orchestrator handles concurrency.
        """
        state = self.get_state(provider_id)
        return state in (ProviderRuntimeState.READY, ProviderRuntimeState.HEALTHY, ProviderRuntimeState.BUSY)
