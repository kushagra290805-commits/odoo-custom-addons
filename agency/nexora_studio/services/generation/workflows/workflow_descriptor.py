from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class WorkflowDescriptor:
    """
    Declarative configuration for a workflow definition.
    Allows workflows to be dynamically driven.
    """
    id: str
    name: str
    description: str
    required_capabilities: List[str] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)
