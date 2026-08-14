from abc import ABC, abstractmethod
from typing import Any
import logging

from odoo.addons.nexora_studio.services.generation.agents.base_agent import Agent
from odoo.addons.nexora_studio.services.generation.agents.agent_context import AgentContext, AgentExecutionResult

_logger = logging.getLogger(__name__)

class ReviewStrategy(ABC):
    @abstractmethod
    def execute(self, code_payload: str, runtime: Any) -> Any:
        pass

class SelfReflectionStrategy(ReviewStrategy):
    def execute(self, code_payload: str, runtime: Any) -> Any:
        _logger.info("Executing SelfReflectionStrategy via Agent Runtime...")
        operation_payload = {
            "task": "Review and reflect on the generated codebase for logical errors, best practices, and edge cases.",
            "code": code_payload
        }
        # Explicitly use the AI capability of the runtime
        response = runtime.ai.generate(
            operation="ai_self_reflection",
            payload=operation_payload
        )
        if not getattr(response, "success", True): # Depending on ProviderResult
            return {"status": "failed", "feedback": []}
        return getattr(response, "data", {"status": "success", "feedback": []})

class BugFixStrategy(ReviewStrategy):
    def execute(self, issues: list, code_payload: str, runtime: Any) -> Any:
        _logger.info("Executing BugFixStrategy via Agent Runtime...")
        if not issues:
            return {"status": "success", "patches": []}
            
        operation_payload = {
            "task": "Generate patches to fix the provided issues.",
            "issues": issues,
            "code": code_payload
        }
        
        response = runtime.ai.generate(
            operation="ai_bug_fixing",
            payload=operation_payload
        )
        if not getattr(response, "success", True):
            return {"status": "failed", "patches": []}
        return getattr(response, "data", {"status": "success", "patches": []})


class ReviewAgent(Agent):
    """
    Agent responsible for reviewing code and applying fixes.
    Delegates actual review logic to ReviewStrategy implementations.
    """
    
    def initialize(self, context: AgentContext, runtime: Any) -> AgentContext:
        # Load any rules or guidelines into working memory
        return context.evolve(working_memory={"strategies_loaded": True})

    def plan(self, context: AgentContext, runtime: Any) -> AgentContext:
        # Determine which strategy to use based on inputs (e.g. if issues exist, bug fix)
        return context

    def execute(self, context: AgentContext, runtime: Any) -> AgentContext:
        inputs = context.working_memory.get("inputs", {})
        mode = inputs.get("mode", "self_reflection")
        code = inputs.get("code", "")
        
        if mode == "self_reflection":
            strategy = SelfReflectionStrategy()
            result = strategy.execute(code, runtime)
        elif mode == "bug_fix":
            issues = inputs.get("issues", [])
            strategy = BugFixStrategy()
            result = strategy.execute(issues, code, runtime)
        else:
            result = {"error": f"Unknown mode: {mode}"}
            
        working_mem = dict(context.working_memory)
        working_mem["execution_result"] = result
        return context.evolve(working_memory=working_mem)

    def observe(self, context: AgentContext, runtime: Any) -> AgentContext:
        # Parse the execution result
        return context

    def review(self, context: AgentContext, runtime: Any) -> AgentContext:
        # Self-reflect on if the review was successful
        return context

    def cleanup(self, context: AgentContext, runtime: Any) -> AgentExecutionResult:
        result_data = context.working_memory.get("execution_result", {})
        return AgentExecutionResult(
            status="completed" if "error" not in result_data and result_data.get("status") != "failed" else "failed",
            outputs=result_data,
            observations=[],
            metrics={},
            execution_time=0.0,
            token_usage={},
            warnings=[],
            errors=[result_data["error"]] if "error" in result_data else [],
            telemetry={}
        )
