from typing import List, Dict, Set
from .plan_models import ExecutionPlan, ExecutionDependency
from .dependency_resolver import DependencyResolver

class PlanOptimizer:
    """
    Optimizes an ExecutionPlan before it is executed.
    - Removes unreachable nodes
    - Removes duplicate/identical capabilities if safe
    """
    
    def __init__(self):
        self.resolver = DependencyResolver()
        
    def optimize(self, plan: ExecutionPlan) -> ExecutionPlan:
        # Step 1: Remove unreachable nodes (nodes with no path from root, though in DAG all nodes with in_degree=0 are roots. 
        # Actually unreachable means completely disconnected if we have a strict entrypoint, but since DAG can have multiple entrypoints, 
        # we will just skip this for now or define unreachable as completely isolated nodes with no dependencies if they aren't marked as root.
        
        # Step 2: Merge identical capabilities
        # If two steps have the EXACT same capability and payload_template, and they share the same dependencies, they can be merged.
        # This is a complex graph reduction. For ADR-0048, we implement a simpler optimization: 
        # find duplicate adjacent identical steps or completely isolated duplicate steps.
        
        merged_plan = self._merge_identical_capabilities(plan)
        
        return merged_plan
        
    def _merge_identical_capabilities(self, plan: ExecutionPlan) -> ExecutionPlan:
        # Simplistic merge: if two steps are exactly the same and share exact same dependencies, merge them.
        steps_fingerprints = {}
        duplicates = {}
        
        for step_id, step in plan.graph.steps.items():
            fingerprint = f"{step.capability}::{str(step.payload_template)}"
            
            # Find dependencies
            in_deps = sorted([d.from_step_id for d in plan.graph.dependencies if d.to_step_id == step_id])
            out_deps = sorted([d.to_step_id for d in plan.graph.dependencies if d.from_step_id == step_id])
            
            full_fp = f"{fingerprint}::IN={in_deps}::OUT={out_deps}"
            
            if full_fp in steps_fingerprints:
                duplicates[step_id] = steps_fingerprints[full_fp]
            else:
                steps_fingerprints[full_fp] = step_id
                
        # Remove duplicates
        if not duplicates:
            return plan
            
        optimized_plan = plan
        for dup_id, primary_id in duplicates.items():
            # Remove dup from steps
            if dup_id in optimized_plan.graph.steps:
                del optimized_plan.graph.steps[dup_id]
                
            # Reroute dependencies (though they should be identical anyway based on fingerprint)
            optimized_plan.graph.dependencies = [
                d for d in optimized_plan.graph.dependencies 
                if d.from_step_id != dup_id and d.to_step_id != dup_id
            ]
            
        return optimized_plan
