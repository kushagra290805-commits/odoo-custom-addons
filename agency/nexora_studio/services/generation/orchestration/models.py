from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import AgentRole, NodeType

@dataclass(frozen=True)
class WorkflowDescriptor:
    """Metadata representing a workflow definition."""
    workflow_id: str
    version: str
    name: str
    description: str
    supported_roles: List[AgentRole]
    required_capabilities: List[str]
    approval_points: List[str]
    estimated_cost: float
    estimated_duration: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class AgentMessage:
    """Immutable payload passed between agents via the SharedWorkspace."""
    message_id: str
    source_role: AgentRole
    target_role: AgentRole
    payload: Dict[str, Any]
    timestamp: float
    correlation_id: str

@dataclass(frozen=True)
class WorkflowNode:
    """A node inside the Workflow DAG."""
    node_id: str
    node_type: NodeType
    agent_role: Optional[AgentRole] = None
    depends_on: List[str] = field(default_factory=list)
    retry_count: int = 3
    timeout_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentExecutionResult:
    """Phase 18.8 extension point from AgentRuntime."""
    success: bool
    agent_role: AgentRole
    node_id: str
    messages_to_emit: List[AgentMessage]
    state_mutations: Dict[str, Any]
    error_context: Optional[str] = None
