import logging
import json
from typing import Dict, Any
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet
from odoo.addons.nexora_studio.services.providers.container import GLOBAL_CONTAINER
from odoo.addons.nexora_studio.services.providers.execution_orchestrator import ExecutionOrchestrator

_logger = logging.getLogger(__name__)

class DesignValidationService:
    @classmethod
    def execute(cls, payload: Dict[str, Any], session_context: Any) -> Dict[str, Any]:
        """Validates accessibility and responsive behavior."""
        orch = GLOBAL_CONTAINER.resolve(ExecutionOrchestrator)
        features = ProviderFeatureSet(supports_vision=True)
        
        ai_payload = {
            "prompt": "Validate the design for responsive behavior and accessibility.",
            "context": payload
        }
        res = orch.execute(ProviderCategory.AI, "validate_design", ai_payload, features, session_context)
        if not res.success:
            raise Exception(f"DesignValidationService failed: {res.error}")
            
        data = res.data if isinstance(res.data, dict) else {"status": "validated", "issues": []}
        return data
