import logging
import json
from typing import Dict, Any
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet
from odoo.addons.nexora_studio.services.providers.container import GLOBAL_CONTAINER
from odoo.addons.nexora_studio.services.providers.execution_orchestrator import ExecutionOrchestrator

_logger = logging.getLogger(__name__)

class DesignTokenService:
    @classmethod
    def execute(cls, payload: Dict[str, Any], session_context: Any) -> Dict[str, Any]:
        """Extracts colors, typography, spacing using AI provider."""
        orch = GLOBAL_CONTAINER.resolve(ExecutionOrchestrator)
        features = ProviderFeatureSet(supports_vision=True)
        
        ai_payload = {
            "prompt": "Extract design tokens (colors, typography) from this image. Return JSON.",
            "context": payload
        }
        res = orch.execute(ProviderCategory.AI, "extract_tokens", ai_payload, features, session_context)
        if not res.success:
            raise Exception(f"DesignTokenService failed: {res.error}")
            
        data = res.data
        if isinstance(data, str):
            try: data = json.loads(data)
            except: data = {"colors": ["#ffffff", "#000000"], "typography": ["Inter"]}
        
        if "colors" not in data:
            data["colors"] = ["#000000"]
        return data
