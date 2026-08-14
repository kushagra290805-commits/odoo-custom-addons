import time
import uuid
from typing import Type, Any, Dict
import logging

from odoo.addons.nexora_studio.services.generation.agents.agent_context import AgentContext, AgentExecutionResult
from odoo.addons.nexora_studio.services.generation.agents.agent_lifecycle import AgentState
from odoo.addons.nexora_studio.services.generation.agents.base_agent import Agent
from odoo.addons.nexora_studio.services.generation.events.events import (
    AgentCreated, AgentInitialized, AgentPlanning, AgentExecuting,
    AgentObserving, AgentReviewing, AgentCompleted, AgentFailed, AgentCancelled
)

_logger = logging.getLogger(__name__)

class AgentContextFactory:
    """Responsible for constructing immutable AgentContexts."""
    @staticmethod
    def create_context(agent_name: str, generation_id: str, budget: int = 1000) -> AgentContext:
        return AgentContext(
            agent_id=f"agent_{agent_name}_{uuid.uuid4().hex[:8]}",
            execution_id=uuid.uuid4().hex,
            generation_id=generation_id,
            correlation_id=uuid.uuid4().hex,
            runtime_metadata={},
            execution_budget=budget,
            cancellation_token=None,  # Placeholder for future Phase 18.x cancellation system
            persistent_memory={},
            working_memory={},
            scratchpad="",
            execution_history=[]
        )

class AgentLifecycleManager:
    """Manages explicit lifecycle transitions and emits events."""
    def __init__(self, event_bus: Any):
        self.event_bus = event_bus
        
    def transition(self, agent_id: str, context: AgentContext, state: AgentState, error: str = None):
        """Transition agent state and publish standard events."""
        event_cls = self._get_event_for_state(state)
        
        # Build kwargs for the event (e.g. session_id might need to come from context or fallback)
        session_id = context.runtime_metadata.get('session_id', 'unknown_session')
        
        kwargs = {
            "session_id": session_id,
            "generation_id": context.generation_id,
            "correlation_id": context.correlation_id,
            "current_state": state.value,
            "agent_id": agent_id,
            "metadata": {"budget": context.execution_budget}
        }
        
        if error and state == AgentState.FAILED:
            kwargs["error"] = error
            
        event = event_cls(**kwargs)
        if self.event_bus:
            self.event_bus.publish(event)
            
        _logger.info(f"Agent {agent_id} transitioned to {state.value}")

    def _get_event_for_state(self, state: AgentState):
        mapping = {
            AgentState.CREATED: AgentCreated,
            AgentState.INITIALIZED: AgentInitialized,
            AgentState.PLANNING: AgentPlanning,
            AgentState.EXECUTING: AgentExecuting,
            AgentState.OBSERVING: AgentObserving,
            AgentState.REVIEWING: AgentReviewing,
            AgentState.COMPLETED: AgentCompleted,
            AgentState.FAILED: AgentFailed,
            AgentState.CANCELLED: AgentCancelled
        }
        return mapping[state]

class AgentExecutor:
    """Executes the specific steps of an Agent in a safe envelope."""
    def __init__(self, lifecycle_manager: AgentLifecycleManager):
        self.lifecycle = lifecycle_manager
        
    def execute_agent(self, agent: Agent, initial_context: AgentContext, scoped_runtime: Any) -> AgentExecutionResult:
        context = initial_context
        agent_id = context.agent_id
        start_time = time.time()
        
        try:
            # Init
            self.lifecycle.transition(agent_id, context, AgentState.INITIALIZED)
            context = agent.initialize(context, scoped_runtime)
            
            # Plan
            self.lifecycle.transition(agent_id, context, AgentState.PLANNING)
            context = agent.plan(context, scoped_runtime)
            
            # Execute loop (simplified for foundation phase)
            self.lifecycle.transition(agent_id, context, AgentState.EXECUTING)
            context = agent.execute(context, scoped_runtime)
            
            # Observe
            self.lifecycle.transition(agent_id, context, AgentState.OBSERVING)
            context = agent.observe(context, scoped_runtime)
            
            # Review
            self.lifecycle.transition(agent_id, context, AgentState.REVIEWING)
            context = agent.review(context, scoped_runtime)
            
            # Cleanup & Complete
            result = agent.cleanup(context, scoped_runtime)
            self.lifecycle.transition(agent_id, context, AgentState.COMPLETED)
            
            # Telemetry tracking for total time
            result.metrics['total_time_sec'] = time.time() - start_time
            return result
            
        except Exception as e:
            _logger.exception(f"Agent execution failed: {e}")
            self.lifecycle.transition(agent_id, context, AgentState.FAILED, error=str(e))
            return AgentExecutionResult(
                status="failed",
                outputs={},
                observations=[],
                metrics={"total_time_sec": time.time() - start_time},
                execution_time=time.time() - start_time,
                token_usage={},
                warnings=[],
                errors=[str(e)],
                telemetry={}
            )

class AgentRuntime:
    """
    The orchestrator that integrates with WebsiteGenerationPipeline.
    Injects ScopedRuntimeProxy and delegates to internal managers.
    """
    def __init__(self, capability_registry: Any, event_bus: Any):
        self.capability_registry = capability_registry
        self.event_bus = event_bus
        self.lifecycle_manager = AgentLifecycleManager(self.event_bus)
        self.executor = AgentExecutor(self.lifecycle_manager)
        
    def invoke(self, agent_class: Type[Agent], generation_runtime: Any, generation_id: str, **kwargs) -> AgentExecutionResult:
        """
        Invoked by Pipeline Engines. Instantiates the Agent, creates context,
        resolves capabilities, and runs the executor.
        """
        agent = agent_class()
        
        # Resolve capabilities using ScopedRuntimeProxy logic from GenerationRuntime
        # Instead of directly using RuntimeScopeRegistry, we ask GenerationRuntime to build a view
        # We need the GenerationRuntime to accept custom capability sets, or we update ScopedRuntimeProxy.
        from odoo.addons.nexora_studio.services.generation.core.runtime_scope import ScopedRuntimeProxy
        allowed = self.capability_registry.get_capabilities(agent_class)
        scoped_proxy = ScopedRuntimeProxy(generation_runtime, allowed)
        
        context = AgentContextFactory.create_context(agent_class.__name__, generation_id)
        
        # Create
        self.lifecycle_manager.transition(context.agent_id, context, AgentState.CREATED)
        
        return self.executor.execute_agent(agent, context, scoped_proxy)
