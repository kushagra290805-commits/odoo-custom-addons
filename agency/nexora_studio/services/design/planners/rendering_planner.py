from ..blueprint_models import RawRequirement, RenderingBlueprint

class RenderingPlanner:
    def plan(self, requirement: RawRequirement) -> RenderingBlueprint:
        blueprint = RenderingBlueprint()
        
        pref = requirement.preferences.get("rendering", "none")
        # Phase 47.9 (U8): 'spline' joins the accepted strategy vocabulary as an
        # explicit embedded-scene renderer selection. Existing strategies are
        # unchanged; 'spline' is only ever set by an explicit Spline requirement
        # (RequirementAnalyzer), never inferred from visual complexity.
        if pref in ["css_3d", "canvas", "webgl", "immersive", "spline"]:
            blueprint.strategy = pref
            if pref == "webgl":
                blueprint.budget_polygon_count = 100000
        else:
            blueprint.strategy = "none"
            
        return blueprint
