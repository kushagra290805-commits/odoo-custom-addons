from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class McpState(Enum):
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    RECOVERING = "recovering"
    FAILED = "failed"
    DISABLED = "disabled"

class StartupPolicy(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    DISABLED = "disabled"

class McpLifecycleEvent(Enum):
    MCP_CONNECTED = "McpConnected"
    MCP_DISCONNECTED = "McpDisconnected"
    MCP_RECOVERING = "McpRecovering"
    MCP_READY = "McpReady"
    MCP_DISCOVERED = "McpDiscovered"
    MCP_FAILED = "McpFailed"

@dataclass
class McpMetrics:
    startup_time: float = 0.0
    reconnect_count: int = 0
    active_sessions: int = 0
    failed_sessions: int = 0
    discovered_tools: int = 0
    tool_calls: int = 0
    average_latency: float = 0.0
    total_errors: int = 0

@dataclass
class McpServerConfig:
    id: str
    display_name: str
    transport: str
    enabled: bool = True
    startup_policy: StartupPolicy = StartupPolicy.OPTIONAL
    startup_command: str = ""
    startup_args: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    environment_variables: Dict[str, str] = field(default_factory=dict)
    authentication: Dict[str, str] = field(default_factory=dict)
    health_check: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    capability_filters: List[str] = field(default_factory=list)
    security_profile: str = "default"

@dataclass
class McpCapability:
    mcp_id: str
    tool_name: str
    description: str
    transport: str
    version: str = "1.0.0"
    mcp_version: str = "1.0"
    protocol_version: str = "1.0"
    server_version: str = "1.0"
    tool_schema_hash: str = ""
    discovery_timestamp: float = 0.0
    auth_required: bool = False
    timeout: int = 30
    permission_scope: str = "none"
    runtime_status: McpState = McpState.REGISTERED
    priority: int = 0
    estimated_cost: float = 0.0
    supported_inputs: Dict[str, Any] = field(default_factory=dict)
    supported_outputs: Dict[str, Any] = field(default_factory=dict)
