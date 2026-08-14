from .base import ExecutionTarget
from ..models import CapabilityResult
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest
from odoo.addons.nexora_studio.services.providers.adapters.provider_compatibility_adapter import ProviderCompatibilityAdapter
import sys

class LocalToolExecutor(ExecutionTarget):
    def __init__(self, tool_registry=None):
        self.tool_registry = tool_registry
        
    def execute(self, payload: dict) -> CapabilityResult:
        if self.tool_registry is None:
            return CapabilityResult(success=True, result="Executed locally (mock)", logs=["Mock local execution"])
            
        tool_id = payload.get("tool_id")
        args = payload.get("args", {})
        
        resolved = self.tool_registry.resolve_tool(tool_id)
        if not resolved:
            return CapabilityResult(success=False, result=None, logs=[f"Local tool {tool_id} not found."])
            
        provider, descriptor = resolved
        try:
            request = ProviderExecutionRequest(
                namespace=tool_id,
                payload=args,
                context=payload.get("context", {})
            )
            adapter = ProviderCompatibilityAdapter(provider)
            exec_result = adapter.execute(request)
            
            if exec_result.success:
                return CapabilityResult(success=True, result=exec_result.data, logs=[f"Local execution of {tool_id} successful."])
            else:
                return CapabilityResult(success=False, result=None, logs=[f"Local execution error: {exec_result.error}"])
        except Exception as e:
            return CapabilityResult(success=False, result=None, logs=[f"Local execution unexpected error: {str(e)}"])