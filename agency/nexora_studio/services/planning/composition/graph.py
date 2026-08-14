import json
import logging
from typing import Dict, List, Optional, Set
from .models import CapabilityMetadata, CapabilityNode

_logger = logging.getLogger(__name__)

class CapabilityGraph:
    """
    Represents the directed graph of capabilities based on their I/O and prerequisites.
    """
    def __init__(self, registry_path: str):
        self.registry_path = registry_path
        self.nodes: Dict[str, CapabilityNode] = {}
        self._load_registry()
        
    def _load_registry(self):
        try:
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
            
            capabilities = data.get('capabilities', [])
            
            # Step 1: Create nodes
            for cap_data in capabilities:
                metadata = CapabilityMetadata(**cap_data)
                self.nodes[metadata.id] = CapabilityNode(metadata=metadata)
                
            # Step 2: Build dependencies (Prerequisites + Data Flow)
            self._build_edges()
            
        except Exception as e:
            _logger.error(f"Failed to load Capability Registry: {e}")
            raise
            
    def _build_edges(self):
        # We need to link nodes where Node A produces an output required by Node B,
        # or Node A is an explicit prerequisite of Node B.
        
        # Mapping from output_name to list of nodes that produce it
        output_providers: Dict[str, List[str]] = {}
        for node_id, node in self.nodes.items():
            for out in node.metadata.produced_outputs:
                if out not in output_providers:
                    output_providers[out] = []
                output_providers[out].append(node_id)
                
        for node_id, node in self.nodes.items():
            deps = set()
            
            # 1. Explicit prerequisites
            for prereq in node.metadata.prerequisites:
                if prereq in self.nodes:
                    deps.add(prereq)
                    
            # 2. Data flow dependencies (Required Inputs)
            for req_in in node.metadata.required_inputs:
                if req_in in output_providers:
                    for provider in output_providers[req_in]:
                        if provider != node_id:
                            deps.add(provider)
                            
            node.dependencies = list(deps)
            
            # Back-propagate to dependents
            for dep in deps:
                if dep in self.nodes:
                    if node_id not in self.nodes[dep].dependents:
                        self.nodes[dep].dependents.append(node_id)

    def get_node(self, capability_id: str) -> Optional[CapabilityNode]:
        return self.nodes.get(capability_id)
        
    def get_all_nodes(self) -> List[CapabilityNode]:
        return list(self.nodes.values())
