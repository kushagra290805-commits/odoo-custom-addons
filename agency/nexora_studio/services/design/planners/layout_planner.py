from ..blueprint_models import RawRequirement, LayoutBlueprint

class LayoutPlanner:
    def plan(self, requirement: RawRequirement) -> LayoutBlueprint:
        blueprint = LayoutBlueprint()
        
        # Determine layout strategy
        if "landing page" in requirement.intent.lower():
            blueprint.strategy = "vertical_scroll"
            blueprint.hierarchy = ["hero", "features", "testimonials", "cta"]
        else:
            blueprint.strategy = "standard_document"
            blueprint.hierarchy = ["header", "content", "footer"]
            
        return blueprint
