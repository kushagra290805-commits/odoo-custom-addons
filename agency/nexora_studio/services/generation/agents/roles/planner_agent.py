import logging
import uuid
import time
from typing import Dict, Any, List
from odoo.addons.nexora_studio.services.generation.orchestration.models import AgentExecutionResult, AgentMessage
from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import AgentRole
from odoo.addons.nexora_studio.services.generation.core.generation_runtime import GenerationRuntime

_logger = logging.getLogger(__name__)

class PlannerAgent:
    """
    Reference Implementation.
    Analyzes the user prompt and breaks it down into structured specifications.
    """
    def execute(self, runtime: GenerationRuntime, context: Dict[str, Any], **kwargs) -> AgentExecutionResult:
        _logger.info("PlannerAgent: Starting execution")
        
        # 1. Access read-only shared state
        shared_state = context.get("shared_state", {})
        prompt = shared_state.get("user_prompt", "Build a website")
        
        # 2. Emulate AI reasoning
        # In a real agent, this would use runtime.ai.generate()
        spec = f"Specification for: {prompt}"
        
        # 3. Formulate outgoing message
        msg = AgentMessage(
            message_id=str(uuid.uuid4()),
            source_role=AgentRole.PLANNER,
            target_role=AgentRole.BUILDER,
            payload={"specification": spec},
            timestamp=time.time(),
            correlation_id=kwargs.get("generation_id", "local")
        )
        
        _logger.info("PlannerAgent: Emitting specification to BUILDER.")
        
        # 4. Return result to Orchestrator (NOT mutating Workspace directly)
        return AgentExecutionResult(
            success=True,
            agent_role=AgentRole.PLANNER,
            node_id="planner_node", # Should be injected, simplified for reference
            messages_to_emit=[msg],
            state_mutations={"has_plan": True}
        )
