"""
Connector Platform Domain Models
=================================
Part 2 of Phase 26.1 — Universal Connector Platform Foundation Refinement.

All models are provider-independent, pure Python value objects and state aggregates.
No Odoo, no MCP, no REST, no GitHub, no provider-specific assumptions.

ADR-0050 defines the full contract for each model.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Primitive Enumerations
# ---------------------------------------------------------------------------

class ConnectorLifecycleState(str, Enum):
    REGISTERED = "registered"
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    INSTALLED = "installed"
    CONFIGURED = "configured"
    AUTHENTICATED = "authenticated"
    VALIDATED = "validated"
    HEALTHY = "healthy"
    RUNNING = "running"
    PAUSED = "paused"
    DISABLED = "disabled"
    FAILED = "failed"
    UPDATING = "updating"
    REMOVED = "removed"


class ConnectorHealthStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class ConnectorEventSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ConnectorExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class ConnectorFailureClass(str, Enum):
    CONFIGURATION_ERROR = "configuration_error"
    CREDENTIAL_ERROR = "credential_error"
    PROCESS_EXIT = "process_exit"
    TRANSPORT_ERROR = "transport_error"
    SSE_DISCONNECT = "sse_disconnect"
    TIMEOUT = "timeout"
    HANDSHAKE_ERROR = "handshake_error"
    PROTOCOL_ERROR = "protocol_error"
    CAPABILITY_DISCOVERY_ERROR = "capability_discovery_error"
    UNKNOWN_ERROR = "unknown_error"

    def is_recoverable(self) -> bool:
        """Returns True if the failure is unconditionally recoverable (e.g. transient transport death)."""
        return self in (
            ConnectorFailureClass.PROCESS_EXIT,
            ConnectorFailureClass.TRANSPORT_ERROR,
            ConnectorFailureClass.SSE_DISCONNECT,
            ConnectorFailureClass.TIMEOUT,
        )

    def is_conditionally_recoverable(self) -> bool:
        """Returns True if the failure is recoverable but requires external changes or limited retries."""
        return self in (
            ConnectorFailureClass.CREDENTIAL_ERROR,
            ConnectorFailureClass.CAPABILITY_DISCOVERY_ERROR,
            ConnectorFailureClass.HANDSHAKE_ERROR,
        )


class CredentialType(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    SSH_KEY = "ssh_key"
    CERTIFICATE = "certificate"
    CUSTOM = "custom"


class ConnectorDependencyType(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONFLICTS_WITH = "conflicts_with"


class ConnectorSourceType(str, Enum):
    MARKETPLACE = "marketplace"
    GIT = "git"
    LOCAL = "local"
    ENTERPRISE = "enterprise"
    UPLOAD = "upload"


class ConnectorEnvironmentType(str, Enum):
    LOCAL = "local"
    WORKSPACE = "workspace"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    VPS = "vps"
    CLOUD = "cloud"
    CUSTOMER = "customer"
    CI_RUNNER = "ci_runner"


# ---------------------------------------------------------------------------
# Value Objects (frozen=True — immutable after construction)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConnectorSource:
    """A generic source from which connectors can be discovered and installed."""
    source_id: str
    name: str
    source_type: ConnectorSourceType
    url: str = ""
    auth_type: str = "none"
    is_official: bool = False
    priority: int = 10
    enabled: bool = True


@dataclass(frozen=True)
class ConnectorCatalogEntry:
    """An entry for a connector in a specific source."""
    connector_id: str
    source_id: str
    name: str
    connector_type_id: str
    publisher: str = ""
    description: str = ""
    latest_version: str = ""
    download_url: str = ""
    verified: bool = False


@dataclass(frozen=True)
class CapabilityDefinition:
    """
    The canonical definition of a capability.
    Exists independently of the connectors that implement it.
    """
    namespace: str
    display_name: str
    version: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    is_read_only: bool = True
    requires_authentication: bool = False


@dataclass(frozen=True)
class ConnectorCapabilityImplementation:
    """
    A connector's specific implementation of a capability definition.
    """
    namespace: str
    connector_id: str
    priority: int = 10
    estimated_latency_ms: int = 1000
    estimated_cost_usd: float = 0.0
    enabled: bool = True


@dataclass(frozen=True)
class ConnectorCredentialReference:
    credential_key: str
    credential_type: CredentialType
    display_name: str
    is_required: bool = True
    scope: str = ""
    description: str = ""


@dataclass(frozen=True)
class ConnectorDependency:
    depends_on_connector_id: str
    dependency_type: ConnectorDependencyType = ConnectorDependencyType.REQUIRED
    version_constraint: str = "*"
    description: str = ""


@dataclass(frozen=True)
class ConnectorManifest:
    """
    The complete, immutable declaration of a connector.
    """
    connector_id: str
    display_name: str
    connector_type_id: str
    sdk_version: str = "1.0.0"
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    publisher: str = ""
    license_type: str = ""
    homepage_url: str = ""
    documentation_url: str = ""
    capabilities: List[str] = field(default_factory=list)  # List of namespaces
    transports: List[str] = field(default_factory=lambda: ["local_subprocess"])
    credential_requirements: List[ConnectorCredentialReference] = field(default_factory=list)
    dependencies: List[ConnectorDependency] = field(default_factory=list)
    configuration_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorRelease:
    """
    A published artifact version of a connector manifest.
    """
    release_id: str
    connector_id: str
    version_string: str
    released_at: datetime
    changelog: str = ""
    checksum: str = ""
    download_url: str = ""
    source_id: str = ""


@dataclass(frozen=True)
class ConnectorEnvironment:
    """
    A runtime environment where a connector is installed.
    """
    environment_id: str
    name: str
    slug: str
    environment_type: ConnectorEnvironmentType
    description: str = ""
    active: bool = True

    # Runtime Characteristics
    operating_system: str = ""
    architecture: str = ""
    python_version: str = ""
    runtime_version: str = ""
    container_runtime: str = ""

    # Execution Constraints
    internet_access: bool = True
    filesystem_access: bool = True
    max_memory_mb: int = 1024
    max_cpu_cores: float = 1.0
    max_execution_time_s: int = 300

    # Configuration
    environment_variables: Dict[str, str] = field(default_factory=dict)
    default_configuration: Dict[str, Any] = field(default_factory=dict)
    secret_provider_reference: str = ""

    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Mutable State Objects
# ---------------------------------------------------------------------------

@dataclass
class ConnectorHealth:
    """
    Expanded health structured telemetry for an active connector instance.
    """
    connector_id: str
    status: ConnectorHealthStatus = ConnectorHealthStatus.UNKNOWN
    availability: float = 1.0                # 0.0 to 1.0 (uptime ratio)
    latency_ms: float = 0.0
    auth_status: str = "unknown"
    quota_status: str = "ok"                 # ok, near_limit, exhausted
    rate_limit_status: str = "ok"            # ok, near_limit, exhausted
    version_drift: bool = False              # True if release version differs from installation
    config_drift: bool = False               # True if live config differs from intended
    heartbeat_timestamp: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    last_successful_execution: Optional[datetime] = None
    error_detail: str = ""
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    telemetry_metadata: Dict[str, Any] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        return self.status == ConnectorHealthStatus.HEALTHY

    def is_degraded(self) -> bool:
        return self.status == ConnectorHealthStatus.DEGRADED

    def record_success(self, latency_ms: float) -> None:
        self.status = ConnectorHealthStatus.HEALTHY
        self.latency_ms = latency_ms
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.error_detail = ""
        self.last_checked = datetime.utcnow()
        self.heartbeat_timestamp = datetime.utcnow()

    def record_failure(self, error_detail: str) -> None:
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.error_detail = error_detail
        self.last_checked = datetime.utcnow()
        if self.consecutive_failures >= 3:
            self.status = ConnectorHealthStatus.FAILED
        else:
            self.status = ConnectorHealthStatus.DEGRADED


@dataclass
class ConnectorConfiguration:
    """
    Expanded configuration state with schema, defaults, overrides, and environment vars.
    """
    connector_id: str
    schema: Dict[str, Any] = field(default_factory=dict)
    default_values: Dict[str, Any] = field(default_factory=dict)
    user_overrides: Dict[str, Any] = field(default_factory=dict)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    secret_references: Dict[str, str] = field(default_factory=dict)
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    validation_metadata: Dict[str, Any] = field(default_factory=dict)

    def get_resolved_values(self) -> Dict[str, Any]:
        """Resolves configuration by overlaying defaults, overrides, env, and secrets."""
        resolved = dict(self.default_values)
        resolved.update(self.user_overrides)
        resolved.update(self.environment_variables)
        resolved.update(self.secret_references)
        return resolved


@dataclass
class ConnectorInstallation:
    """
    Mutable installation record for a connector deployed instance.
    Linked to a specific ConnectorRelease.
    """
    connector_id: str
    release_id: str = ""
    environment_id: str = ""
    installation_path: str = ""
    install_log: str = ""
    installed_at: Optional[datetime] = None
    installed_by: str = "system"
    is_installed: bool = False
    installation_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    connector_id: str = ""
    credential_type: CredentialType = CredentialType.NONE
    access_token: str = ""
    token_expiry: Optional[datetime] = None
    refresh_token: str = ""
    session_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_expired(self) -> bool:
        if self.token_expiry is None:
            return False
        return datetime.utcnow() >= self.token_expiry

    def requires_refresh(self) -> bool:
        return self.is_expired() and bool(self.refresh_token)


@dataclass(frozen=True)
class ConnectorRuntimeContext:
    connector_id: str
    session_id: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resolved_credentials: Dict[str, str] = field(default_factory=dict)
    configuration_snapshot: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorExecutionRequest:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    capability_namespace: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    context: ConnectorRuntimeContext = field(default_factory=lambda: ConnectorRuntimeContext(connector_id="", session_id=""))
    timeout_seconds: float = 60.0
    cancellation_requested: bool = False
    dispatched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConnectorExecutionResult:
    request_id: str
    status: ConnectorExecutionStatus
    data: Any = None
    error: Optional[str] = None
    error_code: str = ""
    execution_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    logged_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def success(self) -> bool:
        return self.status == ConnectorExecutionStatus.SUCCESS

    @classmethod
    def ok(cls, request_id: str, data: Any, execution_ms: float = 0.0) -> "ConnectorExecutionResult":
        return cls(request_id=request_id, status=ConnectorExecutionStatus.SUCCESS, data=data, execution_ms=execution_ms)

    @classmethod
    def fail(cls, request_id: str, error: str, error_code: str = "", execution_ms: float = 0.0) -> "ConnectorExecutionResult":
        return cls(request_id=request_id, status=ConnectorExecutionStatus.FAILURE, error=error, error_code=error_code, execution_ms=execution_ms)

    @classmethod
    def timeout(cls, request_id: str, execution_ms: float = 0.0) -> "ConnectorExecutionResult":
        return cls(request_id=request_id, status=ConnectorExecutionStatus.TIMEOUT, error="Execution timed out", execution_ms=execution_ms)


@dataclass
class ConnectorEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    connector_id: str = ""
    event_type: str = ""
    severity: ConnectorEventSeverity = ConnectorEventSeverity.INFO
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str = ""
    source: str = "connector_runtime"


# ---------------------------------------------------------------------------
# Root Aggregate
# ---------------------------------------------------------------------------

@dataclass
class Connector:
    """
    Root aggregate for a Connector Platform entity.
    """
    manifest: ConnectorManifest
    lifecycle_state: ConnectorLifecycleState = ConnectorLifecycleState.REGISTERED
    health: Optional[ConnectorHealth] = None
    configuration: Optional[ConnectorConfiguration] = None
    installation: Optional[ConnectorInstallation] = None
    active_session: Optional[ConnectorSession] = None
    error_message: str = ""
    registered_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    capabilities_impl: List[ConnectorCapabilityImplementation] = field(default_factory=list)

    @property
    def connector_id(self) -> str:
        return self.manifest.connector_id

    @property
    def is_running(self) -> bool:
        return self.lifecycle_state == ConnectorLifecycleState.RUNNING

    @property
    def is_healthy(self) -> bool:
        return self.health is not None and self.health.is_healthy()

    @property
    def has_valid_session(self) -> bool:
        return self.active_session is not None and not self.active_session.is_expired()

    def get_capabilities(self) -> List[ConnectorCapabilityImplementation]:
        return list(self.capabilities_impl)

    def get_capability(self, namespace: str) -> Optional[ConnectorCapabilityImplementation]:
        for cap in self.capabilities_impl:
            if cap.namespace == namespace:
                return cap
        return None

    def __repr__(self) -> str:
        return (
            f"Connector(id={self.connector_id!r}, "
            f"type={self.manifest.connector_type_id!r}, "
            f"state={self.lifecycle_state.value!r})"
        )
