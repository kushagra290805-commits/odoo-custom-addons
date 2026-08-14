import logging
from typing import Any, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

class KnowledgeEnrichmentEngine(BaseGenerationEngine):
    """
    Transform raw research into structured planning knowledge.
    Communicates exclusively through UCEL (runtime.ai).
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing KnowledgeEnrichmentEngine (Phase 21E.2 Canonical Engine)...")
        
        raw_research = artifact.research
        
        # We transform raw_research into a normalized structure for PlanningEngine
        # Even if raw_research is empty, we still generate a baseline structure
        
        payload = {
            "prompt": "Transform the following raw research into structured business planning knowledge. If research is empty, infer based on domain.",
            "research": raw_research,
            "domain": artifact.requirements.domain,
            "response_format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "business_summary": {"type": "string"},
                        "usp": {"type": "string"},
                        "target_audience": {"type": "string"},
                        "brand_personality": {"type": "string"},
                        "industry_insights": {"type": "array", "items": {"type": "string"}},
                        "competitor_summary": {"type": "string"},
                        "seo_keywords": {"type": "array", "items": {"type": "string"}},
                        "trust_signals": {"type": "array", "items": {"type": "string"}},
                        "faq_suggestions": {"type": "array", "items": {"type": "string"}},
                        "cta_suggestions": {"type": "array", "items": {"type": "string"}},
                        "service_classification": {"type": "array", "items": {"type": "string"}},
                        "strengths": {"type": "array", "items": {"type": "string"}},
                        "weaknesses": {"type": "array", "items": {"type": "string"}},
                        "content_recommendations": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        }
        
        try:
            result = runtime.ai.generate("knowledge_enrichment", payload)
            knowledge_struct = result.get("knowledge", {})
            if isinstance(knowledge_struct, str):
                import json
                try: knowledge_struct = json.loads(knowledge_struct)
                except: knowledge_struct = {}
        except Exception as e:
            _logger.warning(f"KnowledgeEnrichmentEngine: AI generation failed, using defaults: {e}")
            knowledge_struct = {
                "business_summary": f"Default summary for {artifact.requirements.domain}",
                "usp": "Quality and Reliability",
                "seo_keywords": [artifact.requirements.domain.lower()]
            }

        return EngineExecutionResult(
            success=True, 
            artifact=artifact.evolve(knowledge=knowledge_struct), 
            metadata={"knowledge_keys": list(knowledge_struct.keys())}, 
            error=None
        )
