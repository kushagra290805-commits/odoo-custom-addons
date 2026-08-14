from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class ToolExecutionContext:
    """Isolated execution context strictly for Tool Runtime operations."""
    tool_id: str
    provider_id: str
    execution_id: str
    timeout: float
    retry_count: int
    budget_remaining: int
    cancellation_token: Any
    telemetry: Dict[str, Any] = field(default_factory=dict)
    runtime_metadata: Dict[str, Any] = field(default_factory=dict)

    def evolve(self, **kwargs) -> 'ToolExecutionContext':
        current_state = {
            'tool_id': self.tool_id,
            'provider_id': self.provider_id,
            'execution_id': self.execution_id,
            'timeout': self.timeout,
            'retry_count': self.retry_count,
            'budget_remaining': self.budget_remaining,
            'cancellation_token': self.cancellation_token,
            'telemetry': dict(self.telemetry),
            'runtime_metadata': dict(self.runtime_metadata)
        }
        current_state.update(kwargs)
        return ToolExecutionContext(**current_state)
