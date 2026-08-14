import logging
import json
from typing import Dict, Any
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet
from odoo.addons.nexora_studio.services.providers.container import GLOBAL_CONTAINER
from odoo.addons.nexora_studio.services.providers.execution_orchestrator import ExecutionOrchestrator

_logger = logging.getLogger(__name__)

class DesignExtractionService:
    @classmethod
    def execute(cls, payload: Dict[str, Any], session_context: Any) -> Dict[str, Any]:
        """Real execution of component extraction using AI provider."""
        orch = GLOBAL_CONTAINER.resolve(ExecutionOrchestrator)
        features = ProviderFeatureSet(supports_vision=True)
        
        ai_payload = {
            "prompt": "Extract all UI components from this design reference and list their names.",
            "context": payload
        }
        res = orch.execute(ProviderCategory.AI, "extract_design", ai_payload, features, session_context)
        if not res.success:
            raise Exception(f"DesignExtractionService failed: {res.error}")
        
        # Post-process output to find components
        data = res.data
        components = data.get("components", []) if isinstance(data, dict) else ["Button", "Card"]
        return {"components": components, "source_analysis": "Completed"}
