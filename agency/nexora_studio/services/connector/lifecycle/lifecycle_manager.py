"""
Connector Lifecycle Manager
============================
Orchestrates state transitions, emits events, and coordinates
configuration validation and health checks before key state changes.
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from datetime import datetime
from typing import Callable, List, Optional

from ..domain.models import (
    Connector,
    ConnectorEvent,
    ConnectorEventSeverity,
    ConnectorLifecycleState,
)
from ..events.bus import ConnectorEventBus
from .transitions import ConnectorLifecycleStateMachine, TransitionResult
from ..sdk.telemetry_port import ConnectorTelemetryPort
from ..runtime.telemetry_recorder import InMemoryTelemetryRecorder

_logger = get_logger(__name__)


class ConnectorLifecycleManager:
    """
    Manages connector lifecycle transitions.

    Responsibilities:
    - Validate transitions via ConnectorLifecycleStateMachine
    - Apply guards (configuration validity, session presence, etc.)
    - Emit ConnectorEvents on every transition
    - Delegate health checks and configuration validation to registries (via callbacks)
    - Never contain connector-type-specific logic
    """

    def __init__(
        self,
        state_machine: Optional[ConnectorLifecycleStateMachine] = None,
        event_bus: Optional[ConnectorEventBus] = None,
        telemetry: Optional[ConnectorTelemetryPort] = None,
    ) -> None:
        self._state_machine = state_machine or ConnectorLifecycleStateMachine()
        self._event_bus = event_bus
        self.telemetry = telemetry or InMemoryTelemetryRecorder()
        self._transition_hooks: List[Callable[[Connector, ConnectorLifecycleState, ConnectorLifecycleState], None]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transition(
        self,
        connector: Connector,
        target_state: ConnectorLifecycleState,
        reason: str = "",
    ) -> TransitionResult:
        """
        Attempt to transition a connector to target_state.

        1. Validates the structural transition via state machine.
        2. Applies guards appropriate to the target state.
        3. If all checks pass, updates connector.lifecycle_state.
        4. Emits a lifecycle transition event.
        5. Calls registered transition hooks.

        Returns TransitionResult indicating success or failure.
        Callers must persist the connector state after success.
        """
        current_state = connector.lifecycle_state
        connector_id = connector.connector_id

        # Step 1: Structural transition validation
        result = self._state_machine.validate_transition(connector_id, current_state, target_state)
        if not result.success:
            self._emit_event(connector_id, "lifecycle.transition.rejected", ConnectorEventSeverity.WARNING, {
                "from_state": current_state.value,
                "to_state": target_state.value,
                "reason": result.error,
            })
            return result

        # Step 2: Guards
        guard_error = self._check_guards(connector, target_state)
        if guard_error:
            self._emit_event(connector_id, "lifecycle.transition.guard_failed", ConnectorEventSeverity.WARNING, {
                "from_state": current_state.value,
                "to_state": target_state.value,
                "guard_error": guard_error,
            })
            return TransitionResult.fail(current_state, target_state, guard_error)

        # Step 3: Apply transition
        connector.lifecycle_state = target_state
        connector.updated_at = datetime.utcnow()
        if target_state == ConnectorLifecycleState.FAILED and reason:
            connector.error_message = reason
        elif target_state != ConnectorLifecycleState.FAILED:
            connector.error_message = ""

        # Step 4: Emit event
        self._emit_event(connector_id, "lifecycle.transition", ConnectorEventSeverity.INFO, {
            "from_state": current_state.value,
            "to_state": target_state.value,
            "reason": reason,
        })

        # Step 5: Hooks
        for hook in self._transition_hooks:
            try:
                hook(connector, current_state, target_state)
            except Exception as exc:
                _logger.warning("Lifecycle hook raised exception for connector '%s': %s", connector_id, exc)

        self.telemetry.record_counter("lifecycle.transition", tags={"from": current_state.value, "to": target_state.value})
        _logger.info(
            "Connector '%s' transitioned: %s → %s",
            connector_id, current_state.value, target_state.value
        )
        return result

    def register_transition_hook(
        self,
        hook: Callable[[Connector, ConnectorLifecycleState, ConnectorLifecycleState], None],
    ) -> None:
        """
        Register a callback to be called after every successful transition.
        Hook signature: hook(connector, previous_state, new_state)
        """
        self._transition_hooks.append(hook)

    def get_allowed_transitions(
        self, connector: Connector
    ) -> List[ConnectorLifecycleState]:
        """Returns all structurally valid next states for this connector."""
        return self._state_machine.get_allowed_transitions(connector.lifecycle_state)

    def get_forward_path(
        self,
        connector: Connector,
        target_state: ConnectorLifecycleState,
    ) -> Optional[List[ConnectorLifecycleState]]:
        """Returns the shortest state path to reach target_state from the connector's current state."""
        return self._state_machine.get_forward_path(connector.lifecycle_state, target_state)

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _check_guards(
        self,
        connector: Connector,
        target_state: ConnectorLifecycleState,
    ) -> str:
        """
        Returns an error string if a guard condition is violated, or empty string if all guards pass.
        Guards are checked before structural transitions are committed.
        """
        if target_state == ConnectorLifecycleState.CONFIGURED:
            return self._guard_configuration(connector)

        if target_state == ConnectorLifecycleState.AUTHENTICATED:
            return self._guard_configuration(connector) or self._guard_credentials_defined(connector)

        if target_state == ConnectorLifecycleState.VALIDATED:
            return self._guard_healthy_or_session(connector)

        if target_state == ConnectorLifecycleState.REMOVED:
            return self._guard_removal_precondition(connector)

        return ""

    def _guard_configuration(self, connector: Connector) -> str:
        """Connector must have a non-empty, valid configuration."""
        if connector.configuration is None:
            return f"Connector '{connector.connector_id}' has no configuration. Set configuration before transitioning."
        if not connector.configuration.is_valid:
            errors = "; ".join(connector.configuration.validation_errors)
            return f"Connector '{connector.connector_id}' configuration is invalid: {errors}"
        return ""

    def _guard_credentials_defined(self, connector: Connector) -> str:
        """Connector manifest must declare at least one credential if authentication is required."""
        type_requires_auth = bool(connector.manifest.credential_requirements)
        if type_requires_auth and not connector.manifest.credential_requirements:
            return f"Connector '{connector.connector_id}' requires credentials but none are declared in manifest."
        return ""

    def _guard_healthy_or_session(self, connector: Connector) -> str:
        """
        If the connector type requires a session, an active session must be present.
        """
        requires_session = any(
            cr.is_required for cr in connector.manifest.credential_requirements
        )
        if requires_session and not connector.has_valid_session:
            return (
                f"Connector '{connector.connector_id}' requires an authenticated session "
                "before validation. Authenticate first."
            )
        return ""

    def _guard_removal_precondition(self, connector: Connector) -> str:
        """Connectors may only be removed from DISABLED or FAILED states."""
        removable = {ConnectorLifecycleState.DISABLED, ConnectorLifecycleState.FAILED}
        if connector.lifecycle_state not in removable:
            return (
                f"Connector '{connector.connector_id}' must be DISABLED or FAILED before removal. "
                f"Current state: {connector.lifecycle_state.value}"
            )
        return ""

    # ------------------------------------------------------------------
    # Event Emission
    # ------------------------------------------------------------------

    def _emit_event(
        self,
        connector_id: str,
        event_type: str,
        severity: ConnectorEventSeverity,
        data: dict,
    ) -> None:
        """Create and emit a ConnectorEvent."""
        event = ConnectorEvent(
            connector_id=connector_id,
            event_type=event_type,
            severity=severity,
            message=f"[{event_type}] connector={connector_id}",
            data=data,
            source="lifecycle_manager"
        )
        if self._event_bus:
            self._event_bus.publish(event)
        else:
            _logger.debug(
                "ConnectorEvent: type=%s connector=%s severity=%s data=%s",
                event.event_type, event.connector_id, event.severity.value, event.data
            )
