from typing import List, Dict, Set
from .plan_models import ExecutionPlan, ExecutionStep

class DependencyResolver:
    """
    Resolves the execution order of a graph, detects cycles, and identifies missing nodes.
    """
    
    def __init__(self):
        pass

    def build_adjacency_list(self, plan: ExecutionPlan) -> Dict[str, List[str]]:
        adj = {step_id: [] for step_id in plan.graph.steps}
        for dep in plan.graph.dependencies:
            if dep.from_step_id in adj:
                adj[dep.from_step_id].append(dep.to_step_id)
        return adj
        
    def build_in_degree(self, plan: ExecutionPlan) -> Dict[str, int]:
        in_degree = {step_id: 0 for step_id in plan.graph.steps}
        for dep in plan.graph.dependencies:
            if dep.to_step_id in in_degree:
                in_degree[dep.to_step_id] += 1
        return in_degree

    def resolve_execution_order(self, plan: ExecutionPlan) -> List[str]:
        """
        Returns a topologically sorted list of step_ids.
        Raises ValueError if a cycle is detected or if missing dependencies exist.
        """
        # Check missing nodes
        known_steps = set(plan.graph.steps.keys())
        for dep in plan.graph.dependencies:
            if dep.from_step_id not in known_steps:
                raise ValueError(f"Missing dependency node: {dep.from_step_id}")
            if dep.to_step_id not in known_steps:
                raise ValueError(f"Missing dependency node: {dep.to_step_id}")

        adj = self.build_adjacency_list(plan)
        in_degree = self.build_in_degree(plan)
        
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        execution_order = []
        
        while queue:
            curr = queue.pop(0)
            execution_order.append(curr)
            
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        if len(execution_order) != len(plan.graph.steps):
            raise ValueError("Cycle detected in ExecutionGraph. Cannot resolve topological order.")
            
        return execution_order

    def detect_cycles(self, plan: ExecutionPlan) -> bool:
        try:
            self.resolve_execution_order(plan)
            return False
        except ValueError as e:
            if "Cycle detected" in str(e):
                return True
            raise e
