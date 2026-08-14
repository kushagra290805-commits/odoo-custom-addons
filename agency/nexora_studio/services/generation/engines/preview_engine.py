import logging
import json
import base64
import uuid
from typing import Any
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, PreviewArtifacts

_logger = logging.getLogger(__name__)

class PreviewEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing PreviewEngine (Canonical UCEL Architecture)...")
        
        # 1. Compile real component payload for the Preview Engine
        # We will pass the structured tree to be encoded for preview consumption.
        preview_payload = {
            "theme": artifact.theme.design_tokens if hasattr(artifact.theme, 'design_tokens') else {},
            "colors": artifact.theme.colors if hasattr(artifact.theme, 'colors') else {},
            "components": artifact.component_tree.nodes if hasattr(artifact.component_tree, 'nodes') else [],
            "content": artifact.content.pages if hasattr(artifact.content, 'pages') else []
        }
        
        # Serialize to JSON for preview injection
        preview_data = json.dumps(preview_payload)
        
        # 2. Generate multi-device base64 URIs natively to avoid provider bypass
        def _generate_b64_url(component_code: str, device: str) -> str:
            device_widths = {"desktop": "100%", "tablet": "768px", "mobile": "375px"}
            width = device_widths.get(device, "100%")
            html_wrapper = f"<html><body style='margin:0;padding:0;width:{width};'>{component_code}</body></html>"
            encoded = base64.b64encode(html_wrapper.encode('utf-8')).decode('utf-8')
            return f"data:text/html;base64,{encoded}"
        
        desktop_url = _generate_b64_url(preview_data, "desktop")
        tablet_url = _generate_b64_url(preview_data, "tablet")
        mobile_url = _generate_b64_url(preview_data, "mobile")
        
        model = PreviewArtifacts(
            desktop_url=desktop_url,
            tablet_url=tablet_url,
            mobile_url=mobile_url,
            dom_snapshot=preview_data
        )
        return EngineExecutionResult(success=True, artifact=artifact.evolve(previews=model), metadata={}, error=None)

