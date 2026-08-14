import logging
from typing import Dict, Any

_logger = logging.getLogger(__name__)

class AIReviewFramework:
    """
    DEPRECATED (Phase 18.5): Legacy AI Review Framework.
    This class is now a compatibility adapter wrapping the new ReviewAgent architecture.
    Do NOT use this for new development. Instead, invoke AgentRuntime with ReviewAgent.
    """
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        _logger.warning("AIReviewFramework is deprecated. Migrate to AgentRuntime and ReviewAgent.")
        
    def perform_self_reflection(self, code_payload: str, session: Any) -> Dict[str, Any]:
        """Legacy self-reflection wrapper."""
        _logger.info("Executing AI Self Reflection (Legacy Wrapper)...")
        # In a real environment, we would bridge this to AgentRuntime,
        # but because this is a legacy adapter we fallback to the old orchestrator behavior
        # so we do not break callers that haven't migrated their `session` usage.
        operation_payload = {
            "task": "Review and reflect on the generated codebase for logical errors, best practices, and edge cases.",
            "code": code_payload
        }
        # features mock to avoid importing it if we don't have to
        class DummyFeatures:
            supports_json_mode = True
            
        from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory
        response = self.orchestrator.execute(
            ProviderCategory.AI, 
            "ai_self_reflection", 
            operation_payload, 
            DummyFeatures(), 
            session
        )
        if not response.success:
            return {"status": "failed", "feedback": []}
        return response.data

    def automated_bug_fix(self, issues: list, code_payload: str, session: Any) -> Dict[str, Any]:
        """Legacy automated bug fix wrapper."""
        _logger.info("Executing Automated Bug Fixing (Legacy Wrapper)...")
        if not issues:
            return {"status": "success", "patches": []}
            
        operation_payload = {
            "task": "Generate patches to fix the provided issues.",
            "issues": issues,
            "code": code_payload
        }
        
        class DummyFeatures:
            supports_json_mode = True
            
        from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory
        response = self.orchestrator.execute(
            ProviderCategory.AI, 
            "ai_bug_fixing", 
            operation_payload, 
            DummyFeatures(), 
            session
        )
        if not response.success:
            return {"status": "failed", "patches": []}
        return response.data
