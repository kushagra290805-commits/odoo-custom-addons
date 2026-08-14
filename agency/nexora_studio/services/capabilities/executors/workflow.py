from .base import ExecutionTarget
from ..models import CapabilityResult

class WorkflowExecutor(ExecutionTarget):
    def execute(self, payload: dict) -> CapabilityResult:
        return CapabilityResult(success=True, result="Workflow executed")