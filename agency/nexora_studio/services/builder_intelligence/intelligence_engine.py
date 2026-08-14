# -*- coding: utf-8 -*-
import logging
import json
from typing import Any, Dict
from .workspace_graph_service import WorkspaceGraphService
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet

_logger = logging.getLogger(__name__)

class IntelligenceEngine:
    """
    Uses ExecutionOrchestrator and AI Provider to parse instructions against a strict JSON schema.
    """
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    def analyze_instruction(self, instruction: str, active_version: Any, session: Any) -> Dict[str, Any]:
        _logger.info(f"IntelligenceEngine analyzing intent via orchestrator: '{instruction}'")
        
        # Fire planning event
        env = getattr(session, 'env', session) if session else None
        if env and 'nexora.runtime_event' in env:
            env['nexora.runtime_event'].create({
                'runtime_type': 'builder',
                'builder_session_id': session.id if hasattr(session, 'id') else session,
                'event_type': 'builder.planning.started',
                'message': f"Analyzing intent: {instruction[:50]}..."
            })

        schema = {
            "type": "object",
            "properties": {
                "affected_pages": {"type": "array", "items": {"type": "string"}},
                "affected_components": {"type": "array", "items": {"type": "string"}},
                "theme_modifications": {"type": "boolean"},
                "layout_modifications": {"type": "boolean"},
                "asset_modifications": {"type": "boolean"},
                "dependency_changes": {"type": "boolean"},
                "ambiguity_detected": {"type": "boolean"},
                "missing_information": {"type": "array", "items": {"type": "string"}},
                "complexity": {"type": "string", "enum": ["low", "medium", "high"]},
                "estimated_cost": {"type": "number"}
            },
            "required": ["affected_pages", "affected_components", "theme_modifications", "layout_modifications", "asset_modifications", "dependency_changes", "ambiguity_detected", "complexity", "estimated_cost"]
        }
        
        features = ProviderFeatureSet(supports_json_mode=True)
        prompt = f"Parse the following user request into the structured JSON schema. Request: '{instruction}'"
        
        payload = {
            "prompt": prompt,
            "response_schema": schema
        }
        
        res = self.orchestrator.execute(ProviderCategory.AI, "generate_structured_data", payload, features, session)
        
        if not res.success or not res.data:
            _logger.error("AI Provider failed to parse intent or returned malformed output.")
            raise ValueError("Malformed or failed AI response during intent parsing.")
            
        intent_data = res.data.get("json", res.data)
        if isinstance(intent_data, str):
            intent_data = json.loads(intent_data)
            
        if intent_data.get("ambiguity_detected"):
            _logger.warning(f"Ambiguity detected: {intent_data.get('missing_information')}")
            
        impact = {
            "instruction": instruction,
            "affected_components": intent_data.get("affected_components", []),
            "affected_pages": intent_data.get("affected_pages", []),
            "theme_changes": intent_data.get("theme_modifications", False),
            "layout_changes": intent_data.get("layout_modifications", False),
            "asset_changes": intent_data.get("asset_modifications", False),
            "complexity": intent_data.get("complexity", "low"),
            "estimated_cost": intent_data.get("estimated_cost", 0.0)
        }
        
        if env and 'nexora.runtime_event' in env:
            env['nexora.runtime_event'].create({
                'runtime_type': 'builder',
                'builder_session_id': session.id if hasattr(session, 'id') else session,
                'event_type': 'builder.planning.completed',
                'message': "Intent parsing completed."
            })
            
        return impact
