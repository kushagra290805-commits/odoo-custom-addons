from typing import List
from .blueprint_models import WebsiteBlueprint

class DesignValidator:
    """
    Validates blueprint consistency before planning begins.
    Catches conflicting configurations (e.g. demanding WebGL while setting tiny bundle limits).
    """
    def validate(self, blueprint: WebsiteBlueprint) -> WebsiteBlueprint:
        errors: List[str] = []
        
        # Performance vs Rendering check
        if blueprint.rendering.strategy in ["webgl", "immersive"]:
            if blueprint.performance.max_bundle_size_kb < 150:
                errors.append(f"Performance budget too tight for {blueprint.rendering.strategy}. Minimum 150kb bundle required.")
                
        # Layout vs Animation check
        if blueprint.animation.strategy == "timeline_orchestrated":
            if blueprint.layout.strategy != "vertical_scroll":
                errors.append("Orchestrated timelines generally require vertical scroll layouts.")
                
        if errors:
            blueprint.is_valid = False
            blueprint.validation_errors = errors
        else:
            blueprint.is_valid = True
            
        return blueprint
