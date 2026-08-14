from enum import Enum

class AgentState(Enum):
    """Explicit lifecycle transitions for an agent."""
    CREATED = "Created"
    INITIALIZED = "Initialized"
    PLANNING = "Planning"
    EXECUTING = "Executing"
    OBSERVING = "Observing"
    REVIEWING = "Reviewing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
