from typing import List, Dict
from .plan_models import ExecutionPlan
from .dependency_resolver import DependencyResolver

class PlanValidator:
    """
    Validates structural integrity of an ExecutionPlan.
    """
    def __init__(self):
        self.resolver = DependencyResolver()
        
    def validate(self, plan: ExecutionPlan) -> List[str]:
        """
        Returns a list of validation error strings. Empty list means valid.
        """
        errors = []
        
        # 1. Empty plan
        if not plan.graph.steps:
            errors.append("Plan contains no execution steps.")
            return errors
            
        # 2. Unknown dependencies or missing nodes
        known_steps = set(plan.graph.steps.keys())
        for dep in plan.graph.dependencies:
            if dep.from_step_id not in known_steps:
                errors.append(f"Dependency references unknown source step: {dep.from_step_id}")
            if dep.to_step_id not in known_steps:
                errors.append(f"Dependency references unknown target step: {dep.to_step_id}")
                
        # 3. Duplicate capability steps (optional warning, but let's allow it in general unless identical IDs exist)
        # Identical IDs handled by dict natively, but let's just check for valid capabilities
        for step_id, step in plan.graph.steps.items():
            if not step.capability:
                errors.append(f"Step {step_id} is missing a required capability definition.")
                
        # 4. Circular dependencies
        try:
            self.resolver.resolve_execution_order(plan)
        except ValueError as e:
            errors.append(str(e))
            
        return errors
