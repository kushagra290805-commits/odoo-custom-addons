import inspect
import logging
import time
from typing import Any, Dict, List
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult

_logger = logging.getLogger(__name__)

class ProviderCompatibilityAdapter:
    """
    Temporary adapter to wrap legacy provider signatures and normalize them
    into the canonical ProviderExecutionContract (ADR-0044).
    """
    def __init__(self, provider):
        self.provider = provider
        
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        
        if not isinstance(request, ProviderExecutionRequest):
            return ProviderExecutionResult(success=False, data=None, error="Invalid request type. Expected ProviderExecutionRequest.", execution_ms=0)
            
        try:
            sig = inspect.signature(self.provider.execute)
            params = list(sig.parameters.values())
            
            # Explicit Canonical Contract Check
            if len(params) == 1 and (params[0].annotation == ProviderExecutionRequest or params[0].name == 'request'):
                # Note: We check annotation explicitly, but fallback to name 'request' if annotation is missing for some reason
                # However, ADR-0044 strictly prefers annotation.
                if params[0].annotation != ProviderExecutionRequest and params[0].annotation != inspect.Parameter.empty:
                    _logger.warning(f"Provider {self.provider.__class__.__name__} uses 'request' parameter but misses ProviderExecutionRequest annotation.")
                
                return self.provider.execute(request)
                
            # Emit deprecation warning for legacy signature
            _logger.warning(
                f"DEPRECATED: Provider {self.provider.__class__.__name__} uses a legacy execute() signature. "
                f"Please migrate to canonical ProviderExecutionRequest (ADR-0044)."
            )
            
            return self._execute_legacy(sig, request, start_time)
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ProviderExecutionResult(success=False, data=None, error=str(e), metadata={"legacy_translation_error": True}, execution_ms=duration)

    def _execute_legacy(self, sig: inspect.Signature, request: ProviderExecutionRequest, start_time: float) -> ProviderExecutionResult:
        param_names = set(sig.parameters.keys())
        
        # 1. Native Odoo Provider Models: execute(self, tool_id: str, args: dict)
        if 'tool_id' in param_names and 'args' in param_names:
            tool_id = request.namespace
            args = request.payload
            result = self.provider.execute(tool_id, args)
            return self._normalize_result(result, start_time)

        # 2. Component/Bridge Providers: execute(self, operation: str, payload: Dict[str, Any], context: ProviderExecutionContext)
        elif 'operation' in param_names and 'payload' in param_names and 'context' in param_names:
            operation = request.payload.get('operation') or request.payload.get('action') or request.payload.get('mcp_tool') or request.namespace.split('.')[-1]
            result = self.provider.execute(operation, request.payload, request.context)
            return self._normalize_result(result, start_time)
            
        # 3. Legacy MCP Tools: execute(self, session, command, **kwargs)
        elif 'session' in param_names and 'command' in param_names:
            command = request.payload.get('command') or request.payload.get('mcp_tool') or request.namespace.split('.')[-1]
            result = self.provider.execute(request.runtime, command, **request.payload)
            return self._normalize_result(result, start_time)
            
        # 4. Legacy Tools: execute(self, context, **kwargs)
        elif 'context' in param_names and not 'operation' in param_names and not 'session' in param_names:
            result = self.provider.execute(request.context, **request.payload)
            return self._normalize_result(result, start_time)
            
        else:
            # Deterministic failure instead of blindly passing **kwargs if we can't identify the signature
            has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            if has_kwargs:
                result = self.provider.execute(**request.payload)
                return self._normalize_result(result, start_time)
            
            raise ValueError(f"Unable to route request to legacy signature: {sig}")

    def _normalize_result(self, result: Any, start_time: float) -> ProviderExecutionResult:
        duration = (time.time() - start_time) * 1000
        
        # If it's already a ProviderExecutionResult
        if type(result).__name__ == 'ProviderExecutionResult':
            return result
            
        # ProviderExecutionResult (from BaseProvider)
        if type(result).__name__ == 'ProviderExecutionResult':
            return ProviderExecutionResult(
                success=result.success,
                data=result.data,
                error=result.error,
                metadata=result.metadata,
                execution_ms=duration
            )
            
        # CapabilityResult (from LocalToolExecutor initially, shouldn't reach here but just in case)
        if type(result).__name__ == 'CapabilityResult':
            return ProviderExecutionResult(
                success=result.success,
                data=result.result,
                error=result.logs,
                metadata={},
                execution_ms=duration
            )
            
        # Native Odoo list format
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict) and 'severity' in result[0]:
            success = result[0].get('severity') != 'error'
            data = result[0].get('data') if success else None
            error = result[0].get('message') if not success else None
            return ProviderExecutionResult(success=success, data=data, error=error, metadata={'raw_list': result}, execution_ms=duration)
            
        # Dict format
        if isinstance(result, dict) and 'status' in result:
            success = result.get('status') != 'error'
            return ProviderExecutionResult(success=success, data=result.get('data', result), error=result.get('error', result.get('message')), execution_ms=duration)
            
        # Unstructured return
        return ProviderExecutionResult(success=True, data=result, error=None, metadata={"legacy_normalized": True}, execution_ms=duration)
