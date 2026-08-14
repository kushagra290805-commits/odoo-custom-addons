from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum

class ExecutionTargetType(Enum):
    LOCAL = "LOCAL"
    REMOTE = "REMOTE"
    AGENT = "AGENT"
    WORKFLOW = "WORKFLOW"
    PIPELINE = "PIPELINE"

@dataclass(frozen=True)
class CapabilityManifest:
    namespace: str
    display_name: str
    target_type: ExecutionTargetType
    version: str
    aliases: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CapabilityDescriptor:
    manifest: CapabilityManifest
    priority: int
    resolved_provider: Optional[str] = None
    execution_hints: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CapabilityResult:
    success: bool
    result: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    execution_cost: float = 0.0
    emitted_events: List[str] = field(default_factory=list)