import logging
import uuid
import time
from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.orchestration.models import AgentExecutionResult, AgentMessage
from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import AgentRole
from odoo.addons.nexora_studio.services.generation.core.generation_runtime import GenerationRuntime

_logger = logging.getLogger(__name__)

class BuilderAgent:
    """
    Reference Implementation.
    Reads the Planner's specs and writes the code.
    """
    def execute(self, runtime: GenerationRuntime, context: Dict[str, Any], **kwargs) -> AgentExecutionResult:
        _logger.info("BuilderAgent: Starting execution")
        
        # 1. Read inbox (Planner's messages)
        inbox = context.get("inbox", [])
        spec = None
        for msg in inbox:
            if msg.source_role == AgentRole.PLANNER:
                spec = msg.payload.get("specification")
                
        if not spec:
            return AgentExecutionResult(
                success=False,
                agent_role=AgentRole.BUILDER,
                node_id="builder_node",
                messages_to_emit=[],
                state_mutations={},
                error_context="No specification received from Planner."
            )
            
        # 2. Emulate AI tool execution
        # runtime.tools.execute("write_file", ...)
        _logger.info(f"BuilderAgent: Building code for spec: {spec}")
        
        # 3. Formulate Review Request
        msg = AgentMessage(
            message_id=str(uuid.uuid4()),
            source_role=AgentRole.BUILDER,
            target_role=AgentRole.REVIEWER,
            payload={"code_to_review": "<div>Built Code</div>"},
            timestamp=time.time(),
            correlation_id=kwargs.get("generation_id", "local")
        )
        
        return AgentExecutionResult(
            success=True,
            agent_role=AgentRole.BUILDER,
            node_id="builder_node",
            messages_to_emit=[msg],
            state_mutations={"components_built": 1}
        )
