from abc import ABC, abstractmethod
from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.agents.agent_context import AgentContext, AgentExecutionResult

class Agent(ABC):
    """
    Abstract base class for all Autonomous Agents in Phase 18.5+.
    Agents return strongly typed structures across their lifecycle.
    """
    
    @abstractmethod
    def initialize(self, context: AgentContext, runtime: Any) -> AgentContext:
        """Setup initial context and load persistent memory."""
        pass

    @abstractmethod
    def plan(self, context: AgentContext, runtime: Any) -> AgentContext:
        """Formulate a step-by-step execution plan based on the goal."""
        pass

    @abstractmethod
    def execute(self, context: AgentContext, runtime: Any) -> AgentContext:
        """Execute the current step of the plan."""
        pass

    @abstractmethod
    def observe(self, context: AgentContext, runtime: Any) -> AgentContext:
        """Observe the results of the execution (e.g., parsing outputs, visual verification)."""
        pass

    @abstractmethod
    def review(self, context: AgentContext, runtime: Any) -> AgentContext:
        """Self-reflect on observations and decide if the goal is met or needs adjustment."""
        pass

    @abstractmethod
    def cleanup(self, context: AgentContext, runtime: Any) -> AgentExecutionResult:
        """Finalize execution, package results, and emit final telemetry."""
        pass
