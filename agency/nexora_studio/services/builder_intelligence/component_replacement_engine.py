# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet
from odoo.addons.nexora_studio.services.source_framework.component_ranking_pipeline import ComponentRankingPipeline

_logger = logging.getLogger(__name__)

class ComponentReplacementEngine:
    """
    Allows surgical live replacement of a single component node via Design Intelligence,
    using ComponentRankingPipeline to find the most compatible replacement.
    """
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.ranking_pipeline = ComponentRankingPipeline()

    def replace_component(self, current_component_id: str, new_requirements: str, session: Any) -> Dict[str, Any]:
        _logger.info(f"ComponentReplacementEngine searching for replacement: {new_requirements}")
        
        # 1. Search Design Intelligence
        features = ProviderFeatureSet(supports_json_mode=False)
        res = self.orchestrator.execute(ProviderCategory.COMPONENT, "search_components", {"query": new_requirements}, features, session)
        
        if not res.success or not res.data.get("components"):
            return {"success": False, "error": "No components found."}
            
        components = res.data["components"]
        
        # 2. Rank alternatives using existing pipeline
        _logger.info(f"Ranking {len(components)} alternatives via ComponentRankingPipeline")
        
        # Extract active constraints based on session's current theme/framework
        constraints = {"framework": "react", "styling": "tailwind", "accessibility": "wcag2aa"}
        ranked = self.ranking_pipeline.rank_components(components)
        
        if not ranked:
            return {"success": False, "error": "No components passed ranking/compatibility."}
            
        best_match = ranked[0]
        new_component_id = best_match.get("component_id")
        
        # 3. Import Candidate
        fetch_res = self.orchestrator.execute(ProviderCategory.COMPONENT, "import_component", {"component_id": new_component_id, "style": "default"}, features, session)
        
        if not fetch_res.success:
            return {"success": False, "error": "Failed to fetch component code."}
            
        return {
            "success": True,
            "replaced_component_id": current_component_id,
            "new_component_id": new_component_id,
            "code": fetch_res.data.get("code"),
            "ranking_score": best_match.get("score")
        }
