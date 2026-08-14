from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ProviderExecutionRequest:
    namespace: str
    payload: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    runtime: Optional[Any] = None
    execution_metadata: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 60.0
    cancellation_token: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class ProviderExecutionResult:
    success: bool
    data: Any
    error: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_ms: float = 0.0
