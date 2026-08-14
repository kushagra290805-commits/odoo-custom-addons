from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid
import time
from enum import Enum

class ExecutionState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"

@dataclass
class RetryPolicy:
    max_retries: int = 3
    delay_ms: int = 1000
    backoff_multiplier: float = 2.0
    retryable_errors: List[str] = field(default_factory=list)

@dataclass
class ExecutionContext:
    intent: str
    artifacts: Dict[str, Any] = field(default_factory=dict)
    shared_variables: Dict[str, Any] = field(default_factory=dict)
    intermediate_outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class ExecutionStep:
    capability: str
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    payload_template: Dict[str, Any] = field(default_factory=dict)
    state: ExecutionState = ExecutionState.PENDING
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    retries_attempted: int = 0
    result: Optional[Any] = None
    logs: List[str] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

@dataclass
class ExecutionDependency:
    from_step_id: str
    to_step_id: str
    condition: Optional[str] = None

@dataclass
class ExecutionGraph:
    steps: Dict[str, ExecutionStep] = field(default_factory=dict)
    dependencies: List[ExecutionDependency] = field(default_factory=list)

@dataclass
class ExecutionPlan:
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    objective: str = ""
    graph: ExecutionGraph = field(default_factory=ExecutionGraph)
    context: ExecutionContext = field(default_factory=lambda: ExecutionContext(intent=""))
    estimated_cost: float = 0.0
    estimated_duration: float = 0.0
    required_capabilities: List[str] = field(default_factory=list)
    execution_strategy: str = "sequential"
    validation_status: str = "pending"

@dataclass
class PlanExecutionTrace:
    plan_id: str
    steps_completed: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    provider_trace: List[dict] = field(default_factory=list)
    capability_trace: List[dict] = field(default_factory=list)
    execution_time: float = 0.0
    cost: float = 0.0
    retry_history: Dict[str, int] = field(default_factory=dict)
    validation_results: List[str] = field(default_factory=list)
