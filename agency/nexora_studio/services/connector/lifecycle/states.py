"""
Connector Lifecycle States
===========================
Part 4 of Phase 26 — Universal Connector Platform Foundation.

Defines the canonical lifecycle state enum and state metadata.
"""
from ..domain.models import ConnectorLifecycleState

# Re-export for convenience
__all__ = ["ConnectorLifecycleState", "TERMINAL_STATES", "ACTIVE_STATES", "TRANSITION_ALLOWED_STATES"]

# States from which no further automatic transition occurs without operator/system intervention
TERMINAL_STATES = frozenset({
    ConnectorLifecycleState.DISABLED,
    ConnectorLifecycleState.REMOVED,
})

# States in which the connector is considered "available" for execution dispatch
ACTIVE_STATES = frozenset({
    ConnectorLifecycleState.RUNNING,
})

# States from which a connector can accept a pause signal
PAUSABLE_STATES = frozenset({
    ConnectorLifecycleState.RUNNING,
})

# States from which a connector can be forcibly disabled
DISABLEABLE_STATES = frozenset({
    ConnectorLifecycleState.RUNNING,
    ConnectorLifecycleState.PAUSED,
    ConnectorLifecycleState.HEALTHY,
    ConnectorLifecycleState.FAILED,
})

# States from which removal is permitted
REMOVABLE_STATES = frozenset({
    ConnectorLifecycleState.DISABLED,
    ConnectorLifecycleState.FAILED,
})

# States considered "in-progress" (installation, validation, etc.)
IN_PROGRESS_STATES = frozenset({
    ConnectorLifecycleState.DISCOVERED,
    ConnectorLifecycleState.DOWNLOADED,
    ConnectorLifecycleState.INSTALLED,
    ConnectorLifecycleState.CONFIGURED,
    ConnectorLifecycleState.AUTHENTICATED,
    ConnectorLifecycleState.VALIDATED,
    ConnectorLifecycleState.UPDATING,
})

# All states that are allowed to have a transition target (excludes REMOVED)
TRANSITION_ALLOWED_STATES = frozenset(ConnectorLifecycleState) - frozenset({ConnectorLifecycleState.REMOVED})
