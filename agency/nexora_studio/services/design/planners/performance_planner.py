from ..blueprint_models import RawRequirement, PerformanceBlueprint

class PerformancePlanner:
    def plan(self, requirement: RawRequirement) -> PerformanceBlueprint:
        blueprint = PerformanceBlueprint()
        
        if "strict_performance_budget" in requirement.constraints:
            blueprint.max_bundle_size_kb = 100
            blueprint.max_texture_budget_mb = 10
            blueprint.max_animation_budget_ms = 8
            blueprint.core_web_vitals_lcp_ms = 1500
        else:
            blueprint.max_bundle_size_kb = 300
            blueprint.max_texture_budget_mb = 50
            blueprint.max_animation_budget_ms = 16
            blueprint.core_web_vitals_lcp_ms = 2500
            
        return blueprint
