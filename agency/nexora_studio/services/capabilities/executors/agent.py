from .base import ExecutionTarget
from ..models import CapabilityResult

class AgentExecutor(ExecutionTarget):
    def execute(self, payload: dict) -> CapabilityResult:
        return CapabilityResult(success=True, result="Agent executed")