import logging
from typing import Dict, List, Optional
from odoo.addons.nexora_studio.services.generation.platform.models import RuntimeDescriptor, Runtime

_logger = logging.getLogger(__name__)

class RuntimeRegistry:
    """
    Central registry for discovering and resolving runtimes.
    """
    def __init__(self):
        self._descriptors: Dict[str, RuntimeDescriptor] = {}
        self._instances: Dict[str, Runtime] = {}
        
    def register_runtime(self, instance: Runtime) -> None:
        descriptor = instance.descriptor
        if descriptor.runtime_id in self._descriptors:
            _logger.warning(f"Runtime {descriptor.runtime_id} is already registered. Overwriting.")
            
        self._descriptors[descriptor.runtime_id] = descriptor
        self._instances[descriptor.runtime_id] = instance
        _logger.debug(f"Registered Runtime: {descriptor.runtime_id} v{descriptor.version}")
        
    def get_descriptor(self, runtime_id: str) -> Optional[RuntimeDescriptor]:
        return self._descriptors.get(runtime_id)
        
    def get_instance(self, runtime_id: str) -> Optional[Runtime]:
        return self._instances.get(runtime_id)
        
    def get_all_descriptors(self) -> List[RuntimeDescriptor]:
        return list(self._descriptors.values())
        
    def validate_dependencies(self) -> bool:
        """
        Verify that all requested dependencies exist in the registry.
        Does NOT perform topological cycle detection, simply ensures presence.
        """
        valid = True
        for runtime_id, descriptor in self._descriptors.items():
            for dep in descriptor.dependencies:
                if dep not in self._descriptors:
                    _logger.error(f"Runtime '{runtime_id}' is missing dependency '{dep}'")
                    valid = False
        return valid

    def get_startup_order(self) -> List[str]:
        """
        Computes the topological startup order of all runtimes using a Directed Acyclic Graph (DAG).
        Raises ValueError if a circular dependency is detected.
        """
        graph = {d.runtime_id: set(d.dependencies) for d in self._descriptors.values()}
        ordered_ids = []
        visited = set()
        
        while len(ordered_ids) < len(self._descriptors):
            progress_made = False
            for runtime_id, deps in graph.items():
                if runtime_id not in visited and deps.issubset(visited):
                    ordered_ids.append(runtime_id)
                    visited.add(runtime_id)
                    progress_made = True
                    
            if not progress_made:
                raise ValueError("Cyclic dependency detected in RuntimeRegistry DAG.")
                
        return ordered_ids
