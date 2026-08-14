from .models import CapabilityResult
from .executors.base import ExecutionTarget
from .strategy import ExecutionStrategy

class ExecutionScheduler:
    def __init__(self, strategy: ExecutionStrategy):
        self.strategy = strategy
        
    def schedule_and_execute(self, target: ExecutionTarget, payload: dict) -> CapabilityResult:
        # Implements queueing, limits, etc. Currently synchronous.
        return self.strategy.execute(target, payload)