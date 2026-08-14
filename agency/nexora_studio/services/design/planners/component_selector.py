from typing import Any
from ..blueprint_models import RawRequirement, ComponentBlueprint

class ComponentSelector:
    """
    Selects abstract component families based on project requirements.
    """
    def select(self, requirement: RawRequirement) -> ComponentBlueprint:
        blueprint = ComponentBlueprint()
        
        # Abstract mapping
        if "landing page" in requirement.intent.lower():
            blueprint.abstract_components.extend(["hero_section", "feature_grid", "footer"])
            
        if requirement.preferences.get("rendering") == "webgl":
            blueprint.abstract_components.append("3d_canvas_container")
            
        if not blueprint.abstract_components:
            blueprint.abstract_components.append("generic_content_block")
            
        return blueprint
