import time
import logging
from typing import Dict, Any

from odoo.addons.nexora_studio.services.generation.tools.tool_provider import BaseTool
from odoo.addons.nexora_studio.services.generation.tools.tool_execution_context import ToolExecutionContext
from odoo.addons.nexora_studio.services.generation.tools.tool_result import ToolExecutionResult

_logger = logging.getLogger(__name__)

class CancellationToken:
    """Soft cancellation mechanism for tools."""
    def __init__(self):
        self._is_cancelled = False
        
    def cancel(self):
        self._is_cancelled = True
        
    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

class ToolRuntime:
    """
    Executes tools within the isolated boundaries of the GenerationRuntime.
    Enforces soft cancellations and capability scoping.
    """
    
    def execute(self, tool: BaseTool, payload: Dict[str, Any], context: ToolExecutionContext, scoped_runtime: Any) -> ToolExecutionResult:
        """
        Executes the tool. 
        Note: The tool itself is responsible for periodically checking context.cancellation_token.is_cancelled
        if it runs long blocking operations (e.g., polling).
        """
        start_time = time.time()
        
        try:
            # Check timeout immediately
            if context.timeout > 0 and (time.time() - start_time) > context.timeout:
                raise TimeoutError("Execution timed out before starting.")
                
            if context.cancellation_token and context.cancellation_token.is_cancelled:
                raise InterruptedError("Execution cancelled by engine.")
                
            result = tool.execute(payload, context, scoped_runtime)
            return result
            
        except InterruptedError as e:
            return ToolExecutionResult(
                status="cancelled",
                outputs={},
                metadata={},
                duration=time.time() - start_time,
                errors=[str(e)]
            )
        except Exception as e:
            _logger.exception(f"Tool execution failed: {e}")
            return ToolExecutionResult(
                status="failed",
                outputs={},
                metadata={},
                duration=time.time() - start_time,
                errors=[str(e)]
            )
