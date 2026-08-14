from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass(frozen=True)
class ToolDescriptor:
    """Immutable metadata layer for a tool."""
    tool_id: str
    provider_id: str
    category: str
    version: str
    description: str
    required_capabilities: List[str]
    supported_operations: List[str]
    estimated_cost: float
    estimated_latency: float
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
