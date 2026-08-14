"""
Connector Lifecycle State Machine
===================================
Part 4 of Phase 26 — Universal Connector Platform Foundation.

Defines the explicit transition map, guards, and TransitionResult.
All state changes in the Connector Platform route through this state machine.
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set

from ..domain.models import ConnectorLifecycleState

_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Transition Result
# ---------------------------------------------------------------------------

@dataclass
class TransitionResult:
    """The outcome of a requested state transition."""
    success: bool
    previous_state: ConnectorLifecycleState
    new_state: ConnectorLifecycleState
    error: str = ""

    @classmethod
    def ok(cls, previous: ConnectorLifecycleState, new: ConnectorLifecycleState) -> "TransitionResult":
        return cls(success=True, previous_state=previous, new_state=new)

    @classmethod
    def fail(cls, previous: ConnectorLifecycleState, attempted: ConnectorLifecycleState, reason: str) -> "TransitionResult":
        return cls(success=False, previous_state=previous, new_state=previous, error=reason)


# ---------------------------------------------------------------------------
# Transition Map
# ---------------------------------------------------------------------------

# Each key is a source state.
# Each value is the set of valid target states from that source.
_TRANSITION_MAP: Dict[ConnectorLifecycleState, FrozenSet[ConnectorLifecycleState]] = {
    ConnectorLifecycleState.REGISTERED: frozenset({
        ConnectorLifecycleState.DISCOVERED,
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.REMOVED,
    }),
    ConnectorLifecycleState.DISCOVERED: frozenset({
        ConnectorLifecycleState.DOWNLOADED,
        ConnectorLifecycleState.INSTALLED,  # Skip download for locally present connectors
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.REGISTERED,  # Revert if manifest invalid
    }),
    ConnectorLifecycleState.DOWNLOADED: frozenset({
        ConnectorLifecycleState.INSTALLED,
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.DISCOVERED,  # Revert
    }),
    ConnectorLifecycleState.INSTALLED: frozenset({
        ConnectorLifecycleState.CONFIGURED,
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.DISCOVERED,  # Revert
    }),
    ConnectorLifecycleState.CONFIGURED: frozenset({
        ConnectorLifecycleState.AUTHENTICATED,
        ConnectorLifecycleState.VALIDATED,   # Skip auth for no-auth connectors
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.INSTALLED,   # Revert
    }),
    ConnectorLifecycleState.AUTHENTICATED: frozenset({
        ConnectorLifecycleState.VALIDATED,
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.CONFIGURED,  # Revert
    }),
    ConnectorLifecycleState.VALIDATED: frozenset({
        ConnectorLifecycleState.HEALTHY,
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.AUTHENTICATED,  # Revert
    }),
    ConnectorLifecycleState.HEALTHY: frozenset({
        ConnectorLifecycleState.RUNNING,
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.DISABLED,
    }),
    ConnectorLifecycleState.RUNNING: frozenset({
        ConnectorLifecycleState.PAUSED,
        ConnectorLifecycleState.FAILED,
        ConnectorLifecycleState.DISABLED,
        ConnectorLifecycleState.UPDATING,
        ConnectorLifecycleState.HEALTHY,   # Reconnect / re-validate
    }),
    ConnectorLifecycleState.PAUSED: frozenset({
        ConnectorLifecycleState.RUNNING,
        ConnectorLifecycleState.DISABLED,
        ConnectorLifecycleState.FAILED,
    }),
    ConnectorLifecycleState.FAILED: frozenset({
        ConnectorLifecycleState.DISCOVERED,   # Full re-install path
        ConnectorLifecycleState.INSTALLED,    # Re-configure path
        ConnectorLifecycleState.CONFIGURED,   # Re-auth path
        ConnectorLifecycleState.DISABLED,
        ConnectorLifecycleState.REMOVED,
    }),
    ConnectorLifecycleState.UPDATING: frozenset({
        ConnectorLifecycleState.INSTALLED,    # Re-enter install→configure path
        ConnectorLifecycleState.FAILED,
    }),
    ConnectorLifecycleState.DISABLED: frozenset({
        ConnectorLifecycleState.CONFIGURED,   # Re-enable path
        ConnectorLifecycleState.REMOVED,
    }),
    ConnectorLifecycleState.REMOVED: frozenset(),  # Terminal — no transitions out
}


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------

class ConnectorLifecycleStateMachine:
    """
    Enforces valid state transitions for connectors.

    Rules:
    - Only transitions defined in _TRANSITION_MAP are allowed.
    - Guards are checked before any transition is committed.
    - The machine is stateless — it validates and reports but does not store state.
      State storage is handled by ConnectorRegistry (Odoo-backed).
    """

    def can_transition(
        self,
        current_state: ConnectorLifecycleState,
        target_state: ConnectorLifecycleState,
    ) -> bool:
        """Returns True if the transition is structurally allowed."""
        allowed = _TRANSITION_MAP.get(current_state, frozenset())
        return target_state in allowed

    def get_allowed_transitions(
        self,
        current_state: ConnectorLifecycleState,
    ) -> List[ConnectorLifecycleState]:
        """Returns all valid target states from current_state."""
        return list(_TRANSITION_MAP.get(current_state, frozenset()))

    def validate_transition(
        self,
        connector_id: str,
        current_state: ConnectorLifecycleState,
        target_state: ConnectorLifecycleState,
    ) -> TransitionResult:
        """
        Validates a requested state transition.
        Returns TransitionResult.ok() if valid, TransitionResult.fail() with reason if not.
        Does NOT commit the transition — call apply_transition() after validation.
        """
        if current_state == ConnectorLifecycleState.REMOVED:
            return TransitionResult.fail(
                current_state, target_state,
                f"Connector '{connector_id}' is in REMOVED state — no further transitions permitted."
            )

        if not self.can_transition(current_state, target_state):
            allowed = self.get_allowed_transitions(current_state)
            return TransitionResult.fail(
                current_state, target_state,
                f"Invalid transition for connector '{connector_id}': "
                f"{current_state.value!r} → {target_state.value!r}. "
                f"Allowed targets: {[s.value for s in allowed]}"
            )

        return TransitionResult.ok(current_state, target_state)

    def apply_transition(
        self,
        connector_id: str,
        current_state: ConnectorLifecycleState,
        target_state: ConnectorLifecycleState,
    ) -> TransitionResult:
        """
        Validates and logically applies a state transition.
        Callers must persist the new state to the registry after receiving TransitionResult.ok().
        """
        result = self.validate_transition(connector_id, current_state, target_state)
        if result.success:
            _logger.info(
                "Connector '%s' lifecycle transition: %s → %s",
                connector_id, current_state.value, target_state.value
            )
        else:
            _logger.warning(
                "Rejected lifecycle transition for connector '%s': %s",
                connector_id, result.error
            )
        return result

    def get_forward_path(
        self,
        current_state: ConnectorLifecycleState,
        target_state: ConnectorLifecycleState,
    ) -> Optional[List[ConnectorLifecycleState]]:
        """
        Returns the shortest valid path from current_state to target_state using BFS.
        Returns None if no path exists.
        Useful for automated re-installation workflows.
        """
        if current_state == target_state:
            return [current_state]

        visited: Set[ConnectorLifecycleState] = set()
        queue: List[List[ConnectorLifecycleState]] = [[current_state]]

        while queue:
            path = queue.pop(0)
            state = path[-1]

            if state == target_state:
                return path

            if state in visited:
                continue
            visited.add(state)

            for next_state in _TRANSITION_MAP.get(state, frozenset()):
                if next_state not in visited:
                    queue.append(path + [next_state])

        return None
