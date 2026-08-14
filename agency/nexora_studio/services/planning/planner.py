import os
from typing import Optional, List
from .plan_models import ExecutionPlan, ExecutionContext
from .composition.engine import CapabilityCompositionEngine

class IntelligentCapabilityPlanner:
    """
    Decomposes high-level objectives into deterministic ExecutionPlans using dynamic capability composition.
    """
    
    def __init__(self):
        registry_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'config', 'capability_registry.json'
        )
        self.composition_engine = CapabilityCompositionEngine(os.path.normpath(registry_path))
        
    def plan(self, objective: str, target_outputs: Optional[List[str]] = None, blueprint=None) -> ExecutionPlan:
        # For ADR-0050, we extract the target outputs based on the Design Blueprint if provided
        
        telemetry = {
            "objective": objective,
            "heuristic_fallback_used": False,
            "target_outputs": target_outputs
        }
        
        if target_outputs is None:
            telemetry["heuristic_fallback_used"] = True
            target_outputs = []
            if blueprint and blueprint.is_valid:
                # Look at rendering blueprint to decide if 3D targets are needed
                if blueprint.rendering.strategy in ["webgl", "immersive", "css_3d", "canvas"]:
                    target_outputs = ["validation_report"]
                else:
                    target_outputs = ["search_results"]
            else:
                if "3d" in objective.lower() or "landing page" in objective.lower():
                    target_outputs = ["validation_report"]  # End goal of the 3D generation flow
                elif "research" in objective.lower():
                    target_outputs = ["repo_metadata"] # End goal of research flow
                else:
                    target_outputs = ["search_results"]
            telemetry["target_outputs"] = target_outputs
            
        result = self.composition_engine.compose(objective, target_outputs)
        
        if not result.success:
            raise ValueError(f"Failed to compose capability plan: {result.diagnostics.messages} Conflicts: {result.diagnostics.conflicting_capabilities}")
            
        plan = result.plan
        
        # Inject the confidence score into validation status for observability
        plan.validation_status = f"Composed dynamically. Confidence: {result.confidence.overall:.2f}"
        
        # Inject telemetry into plan context
        plan.context.metadata["planner_telemetry"] = telemetry

        
        return plan
