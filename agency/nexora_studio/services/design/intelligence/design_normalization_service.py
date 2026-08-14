import logging
import json
from typing import Dict, Any
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet
from odoo.addons.nexora_studio.services.providers.container import GLOBAL_CONTAINER
from odoo.addons.nexora_studio.services.providers.execution_orchestrator import ExecutionOrchestrator

_logger = logging.getLogger(__name__)

class DesignNormalizationService:
    @classmethod
    def execute(cls, payload: Dict[str, Any], session_context: Any) -> Dict[str, Any]:
        """Normalizes tokens into Nexora standard format without AI."""
        tokens = payload.get("tokens", {})
        normalized = {}
        for key, value in tokens.items():
            if isinstance(value, str) and value.startswith("#") and len(value) == 4:
                # Convert #abc to #aabbcc
                normalized[key] = "#" + "".join([c*2 for c in value[1:]])
            else:
                normalized[key] = value
        return {"normalized_tokens": normalized}
