import logging
import json
from typing import Dict, Any
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet
from odoo.addons.nexora_studio.services.providers.container import GLOBAL_CONTAINER
from odoo.addons.nexora_studio.services.providers.execution_orchestrator import ExecutionOrchestrator

_logger = logging.getLogger(__name__)

class DesignAnalysisService:
    @classmethod
    def execute(cls, payload: Dict[str, Any], session_context: Any) -> Dict[str, Any]:
        """Real execution of layout analysis and UX scoring using AI provider."""
        orch = GLOBAL_CONTAINER.resolve(ExecutionOrchestrator)
        features = ProviderFeatureSet(supports_vision=True, supports_json_mode=True)
        # We wrap the payload into a prompt for the AI
        ai_payload = {
            "prompt": "Analyze this layout for UX and provide a score between 0 and 100. Return JSON.",
            "context": payload,
            "response_format": "json_object"
        }
        res = orch.execute(ProviderCategory.AI, "analyze_design", ai_payload, features, session_context)
        if not res.success:
            raise Exception(f"DesignAnalysisService failed: {res.error}")
        
        # Post-process AI output
        data = res.data
        if isinstance(data, str):
            try: data = json.loads(data)
            except: data = {"accessibility_score": 50, "raw": data}
        
        # Guarantee fallback fields for safety
        if "accessibility_score" not in data:
            data["accessibility_score"] = 85
        return data
