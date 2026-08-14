from abc import ABC, abstractmethod
from ..models import CapabilityResult

class ExecutionTarget(ABC):
    @abstractmethod
    def execute(self, payload: dict) -> CapabilityResult:
        pass