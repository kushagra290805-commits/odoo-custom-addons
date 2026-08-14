import logging
import json
from typing import Any, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, Content

_logger = logging.getLogger(__name__)

class ContentEngine(BaseGenerationEngine):
    def _validate_schema(self, content_data: Dict[str, Any]) -> bool:
        # Enforce structural strictness
        if "pages" not in content_data: return False
        for page_id, data in content_data["pages"].items():
            if "seo" not in data or "metadata" not in data or "sections" not in data:
                return False
            if "title" not in data["seo"]: return False
        return True

    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ContentEngine (Deterministic + Schema Validation)...")
        
        req = artifact.requirements
        pages_structure = {}
        
        component_hierarchy = artifact.architecture.component_hierarchy if hasattr(artifact.architecture, "component_hierarchy") else {}
        for comp_id, comp_data in component_hierarchy.items():
            if comp_data.get("type") != "page": continue
            path = comp_data.get("path", "/")
            pages_structure[path] = comp_data.get("sections", ["Hero", "Content"])
            
        payload = {
            "prompt": f"Generate structured editable content for {req.domain}. Map: {json.dumps(pages_structure)}. MUST strictly follow response schema.",
            "response_format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "pages": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "properties": {
                                    "seo": {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "description": {"type": "string"}
                                        },
                                        "required": ["title", "description"]
                                    },
                                    "metadata": {"type": "object"},
                                    "sections": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string"},
                                                "semantic_heading": {"type": "string"},
                                                "aria_label": {"type": "string"},
                                                "body": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "required": ["seo", "metadata", "sections"]
                            }
                        }
                    },
                    "required": ["pages"]
                }
            }
        }
        
        result = runtime.ai.generate("generate_content", payload)
        parsed = result.get("analysis", {})
        if isinstance(parsed, str):
            try: parsed = json.loads(parsed)
            except: parsed = {}
            
        # Validation
        if not self._validate_schema(parsed):
            _logger.warning("AI Content generation failed schema validation. Falling back to deterministic generation.")
            parsed = {"pages": {}}
            for comp_id, comp_data in component_hierarchy.items():
                if comp_data.get("type") != "page": continue
                path = comp_data.get("path", "/")
                sections = comp_data.get("sections", ["Hero", "Content"])
                parsed["pages"][path] = {
                    "seo": {"title": f"{req.domain} - {path}", "description": f"Welcome to {req.domain}"},
                    "metadata": {"status": "draft"},
                    "sections": [
                        {
                            "type": sec, 
                            "semantic_heading": f"h2", 
                            "aria_label": f"{sec} section", 
                            "body": f"Editable content for {sec}"
                        } for sec in sections
                    ]
                }
                
        model = Content(pages=parsed.get("pages", {}))
        return EngineExecutionResult(success=True, artifact=artifact.evolve(content=model), metadata={}, error=None)
