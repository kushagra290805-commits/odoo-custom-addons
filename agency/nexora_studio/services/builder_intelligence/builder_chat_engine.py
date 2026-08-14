# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict
from .intelligence_engine import IntelligenceEngine
from .change_planning_engine import ChangePlanningEngine

_logger = logging.getLogger(__name__)

class BuilderChatEngine:
    """
    Orchestrator for Contextual AI Chat.
    It ONLY orchestrates planning, never modifies workspaces directly.
    Chat -> Intelligence -> Planning -> Validation -> Preview -> Approval -> Execution
    """
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.intelligence_engine = IntelligenceEngine(orchestrator)
        self.planning_engine = ChangePlanningEngine(orchestrator)

    def process_chat_request(self, user_prompt: str, builder_session: Any) -> Any:
        _logger.info(f"BuilderChatEngine received: {user_prompt}")
        
        active_version = builder_session.active_version_id
        
        # 1. Intelligence Engine (Analyze)
        impact = self.intelligence_engine.analyze_instruction(user_prompt, active_version, builder_session)
        
        # 2. Change Planning Engine (Generate Execution Plan)
        plan_record = self.planning_engine.generate_plan(impact, builder_session)
        
        # We stop here. The system returns the plan_record so the UI can prompt for Human Approval.
        # Strict enforcement: BuilderChatEngine does NOT execute the plan.
        return plan_record
