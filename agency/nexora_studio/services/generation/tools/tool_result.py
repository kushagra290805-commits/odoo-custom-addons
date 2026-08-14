from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass(frozen=True)
class ToolExecutionResult:
    """Strongly typed result from a tool execution."""
    status: str
    outputs: Dict[str, Any]
    metadata: Dict[str, Any]
    duration: float
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    provider: str = "unknown"
    tool_version: str = "1.0"
