from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

@dataclass(frozen=True)
class AgentContext:
    """Immutable context isolated per agent execution."""
    agent_id: str
    execution_id: str
    generation_id: str
    correlation_id: str
    runtime_metadata: Dict[str, Any]
    execution_budget: int
    cancellation_token: Any
    persistent_memory: Dict[str, Any] = field(default_factory=dict)
    working_memory: Dict[str, Any] = field(default_factory=dict)
    scratchpad: str = ""
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def evolve(self, **kwargs) -> 'AgentContext':
        """Create a new context with updated fields."""
        current_state = {
            'agent_id': self.agent_id,
            'execution_id': self.execution_id,
            'generation_id': self.generation_id,
            'correlation_id': self.correlation_id,
            'runtime_metadata': self.runtime_metadata,
            'execution_budget': self.execution_budget,
            'cancellation_token': self.cancellation_token,
            'persistent_memory': dict(self.persistent_memory),
            'working_memory': dict(self.working_memory),
            'scratchpad': self.scratchpad,
            'execution_history': list(self.execution_history)
        }
        current_state.update(kwargs)
        return AgentContext(**current_state)


@dataclass(frozen=True)
class AgentExecutionResult:
    """Strongly typed result from an agent execution."""
    status: str
    outputs: Dict[str, Any]
    observations: List[Any]
    metrics: Dict[str, Any]
    execution_time: float
    token_usage: Dict[str, int]
    warnings: List[str]
    errors: List[str]
    telemetry: Dict[str, Any]
