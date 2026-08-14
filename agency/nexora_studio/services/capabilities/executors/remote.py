from .base import ExecutionTarget
from ..models import CapabilityResult
from ..remote.transport import TransportLayer

class RemoteToolExecutor(ExecutionTarget):
    def __init__(self, transport: TransportLayer):
        self.transport = transport
        
    def execute(self, payload: dict) -> CapabilityResult:
        # Delegates to transport
        response = self.transport.send(payload)
        return CapabilityResult(success=True, result=response, logs=["Remote execution success"])