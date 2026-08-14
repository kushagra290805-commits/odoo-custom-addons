from abc import ABC, abstractmethod
from typing import List, Any
from odoo.addons.nexora_studio.services.generation.execution.generation_graph import GenerationGraph
from odoo.addons.nexora_studio.services.generation.execution.generation_node import GenerationNode, NodeStatus

class ResourceLimits:
    """Interface exposed for resource-aware scheduling (Refinement 3)."""
    max_concurrent_tasks: int = 5
    max_memory_mb: int = 1024

class ExecutionScheduler(ABC):
    """
    Evaluates the GenerationGraph and schedules ready nodes.
    Designed for both dependency and resource-aware scheduling.
    """
    def __init__(self, resource_limits: ResourceLimits = ResourceLimits()):
        self.resource_limits = resource_limits
        
    @abstractmethod
    def schedule(self, graph: GenerationGraph) -> None:
        """Schedules and executes ready nodes."""
        pass
        
class BasicExecutionScheduler(ExecutionScheduler):
    """Dependency-aware synchronous scheduler for immediate use."""
    def schedule(self, graph: GenerationGraph) -> None:
        while not graph.is_completed() and not graph.has_failed():
            ready_nodes = graph.get_ready_nodes()
            if not ready_nodes:
                # Potential deadlock or waiting for async tasks to finish
                break
                
            for node in ready_nodes:
                node.status = NodeStatus.RUNNING
                # In a real environment, this invokes the appropriate Generator
                node.complete({}, 0.1)
