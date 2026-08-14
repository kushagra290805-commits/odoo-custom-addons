from .plan_models import ExecutionGraph, ExecutionStep, ExecutionDependency

class ExecutionGraphBuilder:
    """
    Utility for fluently constructing ExecutionGraphs.
    """
    
    def __init__(self):
        self.graph = ExecutionGraph()
        
    def add_step(self, step: ExecutionStep) -> 'ExecutionGraphBuilder':
        self.graph.steps[step.step_id] = step
        return self
        
    def add_dependency(self, from_step_id: str, to_step_id: str, condition: str = None) -> 'ExecutionGraphBuilder':
        dep = ExecutionDependency(from_step_id=from_step_id, to_step_id=to_step_id, condition=condition)
        self.graph.dependencies.append(dep)
        return self
        
    def build(self) -> ExecutionGraph:
        return self.graph
