from .models import CapabilityResult
from .executors.base import ExecutionTarget

class ExecutionStrategy:
    def execute(self, target: ExecutionTarget, payload: dict) -> CapabilityResult:
        return target.execute(payload)

class FallbackStrategy(ExecutionStrategy):
    def execute(self, target: ExecutionTarget, payload: dict) -> CapabilityResult:
        result = target.execute(payload)
        if not result.success:
            # Fallback logic here
            pass
        return result