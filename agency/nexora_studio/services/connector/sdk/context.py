"""
Connector SDK Context
=====================
Part 8 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ExecutionContext:
    """
    Provides context to a connector during capability execution.
    Abstracts away the underlying engine (Generation Platform, CLI, etc).
    """
    request_id: str
    connector_id: str
    capability_namespace: str
    
    # Resolved configuration (merged defaults + user overrides + secrets)
    configuration: Dict[str, Any] = field(default_factory=dict)
    
    # Active session credentials (if any)
    credentials: Optional[Dict[str, Any]] = None
    
    # Telemetry and tracing
    trace_id: Optional[str] = None
    
    # Execution constraints
    timeout_seconds: int = 30
    
    # Cancellation token (stubbed for future)
    is_cancelled: bool = False
