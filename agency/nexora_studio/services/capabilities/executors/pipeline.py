from .base import ExecutionTarget
from ..models import CapabilityResult

class PipelineExecutor(ExecutionTarget):
    def execute(self, payload: dict) -> CapabilityResult:
        return CapabilityResult(success=True, result="Pipeline executed")