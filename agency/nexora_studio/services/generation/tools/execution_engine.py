import logging
import uuid
import time
from typing import Dict, Any, List, Optional

from odoo.addons.nexora_studio.services.generation.tools.tool_registry import ToolRegistry
from odoo.addons.nexora_studio.services.generation.tools.tool_runtime import ToolRuntime, CancellationToken
from odoo.addons.nexora_studio.services.generation.tools.tool_execution_context import ToolExecutionContext
from odoo.addons.nexora_studio.services.generation.tools.tool_result import ToolExecutionResult

_logger = logging.getLogger(__name__)

class ToolPlanner:
    def plan_execution(self, tool_id: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Creates a strictly linear execution plan.
        No DAG, no parallel execution.
        """
        # For Phase 18.6, planning a single tool invocation is a 1-step linear list.
        return [{"tool_id": tool_id, "payload": payload}]

class ToolSelector:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        
    def select(self, tool_id: str):
        resolved = self.registry.resolve_tool(tool_id)
        if not resolved:
            raise ValueError(f"Tool {tool_id} not found or provider unhealthy.")
        return resolved

class ToolExecutor:
    def __init__(self, runtime: ToolRuntime):
        self.runtime = runtime
        
    def execute(self, tool: Any, descriptor: Any, payload: Dict[str, Any], context: ToolExecutionContext, scoped_runtime: Any) -> ToolExecutionResult:
        # Check Capabilities (Sandbox preservation)
        # Note: ScopedRuntimeProxy enforces runtime capabilities. 
        # Here we just verify the agent is allowed to execute tools at all.
        if "tools" not in scoped_runtime._allowed_capabilities:
            raise PermissionError("Agent does not have the 'tools' capability profile.")
            
        return self.runtime.execute(tool, payload, context, scoped_runtime)

class RecoveryEngine:
    def __init__(self):
        self.max_retries = 3
        
    def execute_with_recovery(self, executor_func, context: ToolExecutionContext) -> ToolExecutionResult:
        retries = 0
        last_result = None
        
        while retries <= self.max_retries:
            if context.cancellation_token and context.cancellation_token.is_cancelled:
                return ToolExecutionResult(status="cancelled", outputs={}, metadata={}, duration=0.0, errors=["Cancelled by token"])
                
            last_result = executor_func(context)
            if last_result.status == "success":
                return last_result
                
            retries += 1
            if retries <= self.max_retries:
                _logger.warning(f"Tool execution failed. Retrying ({retries}/{self.max_retries}). Backoff...")
                time.sleep(2 ** retries) # Exponential backoff
                
        return last_result

class BudgetManager:
    def check_budget(self, context: ToolExecutionContext, cost_estimate: float):
        if context.budget_remaining < cost_estimate:
            raise PermissionError(f"Insufficient budget. Need {cost_estimate}, have {context.budget_remaining}.")

class ExecutionEngine:
    """
    Coordinates the execution of tools using the modular components.
    """
    def __init__(self, registry: ToolRegistry, runtime: ToolRuntime):
        self.planner = ToolPlanner()
        self.selector = ToolSelector(registry)
        self.executor = ToolExecutor(runtime)
        self.recovery = RecoveryEngine()
        self.budget = BudgetManager()
        
    def run(self, tool_id: str, payload: Dict[str, Any], scoped_runtime: Any, budget: int = 100) -> ToolExecutionResult:
        """Main entry point for Agents to invoke a tool."""
        plan = self.planner.plan_execution(tool_id, payload)
        
        # We execute the plan sequentially
        final_result = None
        for step in plan:
            provider, descriptor = self.selector.select(step["tool_id"])
            
            context = ToolExecutionContext(
                tool_id=descriptor.tool_id,
                provider_id=provider.provider_id,
                execution_id=uuid.uuid4().hex,
                timeout=30.0,
                retry_count=0,
                budget_remaining=budget,
                cancellation_token=CancellationToken()
            )
            
            self.budget.check_budget(context, descriptor.estimated_cost)
            
            tool_instance = provider.get_tool(descriptor.tool_id)
            
            # Wrap execution for recovery
            def _exec_wrap(ctx):
                return self.executor.execute(tool_instance, descriptor, step["payload"], ctx, scoped_runtime)
                
            final_result = self.recovery.execute_with_recovery(_exec_wrap, context)
            
            if final_result.status != "success":
                break # Abort sequence on failure
                
        return final_result
