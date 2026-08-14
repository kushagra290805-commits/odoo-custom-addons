from typing import Optional
from .blueprint_models import WebsiteBlueprint, DesignBlueprint
from .requirement_analyzer import RequirementAnalyzer
from .planners import ComponentSelector, AnimationPlanner, RenderingPlanner, PerformancePlanner, LayoutPlanner
from .validator import DesignValidator

class DesignIntelligenceEngine:
    """
    Transforms client requirements into a provider-agnostic WebsiteBlueprint.
    Acts as the master orchestrator for the design phase.
    """
    def __init__(self):
        self.analyzer = RequirementAnalyzer()
        self.component_selector = ComponentSelector()
        self.animation_planner = AnimationPlanner()
        self.rendering_planner = RenderingPlanner()
        self.performance_planner = PerformancePlanner()
        self.layout_planner = LayoutPlanner()
        self.validator = DesignValidator()
        
    def generate_blueprint(self, raw_intent: str) -> WebsiteBlueprint:
        # 1. Analyze Requirements
        req = self.analyzer.analyze(raw_intent)
        
        # 2. Initialize Blueprint
        blueprint = WebsiteBlueprint(intent=raw_intent)
        
        # 3. Design Language
        lang = req.preferences.get("design_language", "minimal")
        blueprint.design = DesignBlueprint(language=lang)
        
        # 4. Modular Planners
        blueprint.layout = self.layout_planner.plan(req)
        blueprint.component = self.component_selector.select(req)
        blueprint.animation = self.animation_planner.plan(req)
        blueprint.rendering = self.rendering_planner.plan(req)
        blueprint.performance = self.performance_planner.plan(req)
        
        # 5. Validate
        blueprint = self.validator.validate(blueprint)
        
        return blueprint
