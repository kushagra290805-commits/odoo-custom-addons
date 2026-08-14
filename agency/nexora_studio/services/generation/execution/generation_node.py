from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class NodeType(Enum):
    WEBSITE = "website"
    PAGE = "page"
    COMPONENT = "component"
    ASSET = "asset"

@dataclass
class GenerationNode:
    """
    Represents a single atomic unit of work in the GenerationGraph.
    """
    node_id: str
    node_type: NodeType
    status: NodeStatus = NodeStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    execution_time: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    
    def complete(self, outputs: Dict[str, Any], exec_time: float) -> None:
        self.status = NodeStatus.COMPLETED
        self.outputs = outputs
        self.execution_time = exec_time
        self.completed_at = datetime.utcnow().isoformat()
        
    def fail(self) -> None:
        self.status = NodeStatus.FAILED
        self.completed_at = datetime.utcnow().isoformat()
