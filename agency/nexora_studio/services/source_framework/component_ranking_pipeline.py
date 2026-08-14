# -*- coding: utf-8 -*-
from typing import List, Dict, Any
from .domain_models import ComponentPackage

class ComponentRankingPipeline:
    def __init__(self, profile: str = "default"):
        self.profile = profile
        self.profiles = {
            "default": {
                "quality": 0.3,
                "compatibility": 0.3,
                "performance": 0.1,
                "reliability": 0.1,
                "internal_preference": 0.1,
                "ai_confidence": 0.1
            },
            "strict_internal": {
                "quality": 0.1,
                "compatibility": 0.2,
                "performance": 0.1,
                "reliability": 0.1,
                "internal_preference": 0.5,
                "ai_confidence": 0.0
            }
        }
        
    def rank_components(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        weights = self.profiles.get(self.profile, self.profiles["default"])
        
        for item in components:
            pkg: ComponentPackage = item["package"]
            
            # Extract basic scores
            q_score = item.get("score", 0.5)
            c_score = 1.0 if pkg.compatibility_report and pkg.compatibility_report.get("is_compatible") else 0.0
            i_pref = 1.0 if pkg.provenance and pkg.provenance.provider == "internal" else 0.0
            
            final_score = (q_score * weights["quality"]) + \
                          (c_score * weights["compatibility"]) + \
                          (i_pref * weights["internal_preference"])
                          
            item["final_score"] = final_score
            
        components.sort(key=lambda x: x["final_score"], reverse=True)
        return components
