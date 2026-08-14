from ..blueprint_models import RawRequirement, AnimationBlueprint

class AnimationPlanner:
    def plan(self, requirement: RawRequirement) -> AnimationBlueprint:
        blueprint = AnimationBlueprint()
        
        if requirement.preferences.get("animation") == "complex":
            blueprint.strategy = "timeline_orchestrated"
            blueprint.abstract_requirements = ["scroll_trigger", "staggered_entrance"]
        else:
            blueprint.strategy = "css_transitions"
            blueprint.abstract_requirements = ["fade_in"]
            
        return blueprint
