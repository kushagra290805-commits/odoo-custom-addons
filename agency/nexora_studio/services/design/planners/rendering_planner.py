from ..blueprint_models import RawRequirement, RenderingBlueprint

class RenderingPlanner:
    def plan(self, requirement: RawRequirement) -> RenderingBlueprint:
        blueprint = RenderingBlueprint()
        
        pref = requirement.preferences.get("rendering", "none")
        if pref in ["css_3d", "canvas", "webgl", "immersive"]:
            blueprint.strategy = pref
            if pref == "webgl":
                blueprint.budget_polygon_count = 100000
        else:
            blueprint.strategy = "none"
            
        return blueprint
