# Provider Contract Specification — Canonical Reference (ADR-0029 + ADR-0030 + ADR-0031 + ADR-0032)

**Date:** July 2026
**Type:** Authoritative Python Interface Specification
**Status:** Architecture-Validated — Approved for Phase 15B Implementation

---

## Module 1: Enumerations

```python
from enum import Enum

# ADR-0029
class ProviderCategory(str, Enum):
    AI = "ai"; ASSET = "asset"; COMPONENT = "component"
    DESIGN = "design"; MCP = "mcp"; PREVIEW = "preview"
    STORAGE = "storage"; CUSTOM = "custom"

# ADR-0030
class ProviderRuntimeState(str, Enum):
    INSTALLED = "installed"; CONFIGURED = "configured"
    AUTHENTICATED = "authenticated"; HEALTHY = "healthy"
    READY = "ready"; BUSY = "busy"; DEGRADED = "degraded"
    DISABLED = "disabled"; ARCHIVED = "archived"

class ProviderEventChannel(str, Enum):
    TELEMETRY = "telemetry"; WEBSOCKET = "websocket"
    METRICS = "metrics"; LOGGING = "logging"
    AUDIT = "audit"; NOTIFICATIONS = "notifications"

# ADR-0031
class SandboxProfile(str, Enum):
    RESTRICTED = "restricted"; WORKSPACE = "workspace"
    DEVELOPMENT = "development"; TRUSTED = "trusted"
    PRIVILEGED = "privileged"

# ADR-0032
class ServiceLifetime(str, Enum):
    SINGLETON = "singleton"; SCOPED = "scoped"; TRANSIENT = "transient"

class LockBackend(str, Enum):
    POSTGRESQL = "postgresql"; REDIS = "redis"; MEMORY = "memory"

class MigrationStatus(str, Enum):
    PENDING = "pending"; RUNNING = "running"; COMPLETED = "completed"
    FAILED = "failed"; ROLLED_BACK = "rolled_back"

class ExecutionPolicyType(str, Enum):
    FASTEST = "fastest"; CHEAPEST = "cheapest"
    HIGHEST_QUALITY = "highest_quality"; PREFERRED = "preferred"
    BALANCED = "balanced"; CUSTOM = "custom"
```

---

## Module 2: Core Domain Dataclasses

### 2.1 `ConcurrencyPolicy` (ADR-0032)
```python
@dataclass(frozen=True)
class ConcurrencyPolicy:
    max_parallel_requests: int = 10
    max_queue_size: int = 50
    max_concurrent_streams: int = 5
    queue_timeout_ms: int = 30000
    reject_on_queue_full: bool = True
```

### 2.2 `ProviderMetadata` (ADR-0029 + ADR-0030 marketplace + ADR-0032 concurrency)
```python
@dataclass(frozen=True)
class ProviderMetadata:
    # Core identity (ADR-0029)
    provider_id: str; name: str; category: ProviderCategory
    provider_version: str; manifest_version: str; api_version: str
    vendor_url: str; priority_weight: int = 10
    dependencies: List[str] = field(default_factory=list)
    # Marketplace (ADR-0030)
    author: str = "Nexora Studio Core Team"
    homepage_url: Optional[str] = None; documentation_url: Optional[str] = None
    license: str = "MIT"; support_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    compatibility_matrix: Dict[str, str] = field(default_factory=lambda: {"odoo": ">=16.0", "python": ">=3.10"})
    minimum_platform_version: str = "2026.1"
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    # Concurrency (ADR-0032)
    concurrency_policy: ConcurrencyPolicy = field(default_factory=ConcurrencyPolicy)
```

### 2.3 `ProviderStateRecord` (ADR-0030)
```python
@dataclass
class ProviderStateRecord:
    provider_id: str
    current_state: ProviderRuntimeState = ProviderRuntimeState.INSTALLED
    active_locks: int = 0; last_latency_ms: float = 0.0
    error_rate_24h: float = 0.0; consecutive_failures: int = 0
    last_state_transition: datetime = field(default_factory=datetime.utcnow)
    degradation_reason: Optional[str] = None
```

### 2.4 `ProviderSandboxPolicy` (ADR-0030 + ADR-0031 profiles)
```python
@dataclass(frozen=True)
class ProviderSandboxPolicy:
    filesystem_whitelist: Dict[str, List[str]] = field(default_factory=lambda: {"read": ["/workspace/project"], "write": ["/workspace/project/assets"]})
    network_cidr_whitelist: List[str] = field(default_factory=lambda: ["0.0.0.0/0"])
    allow_shell: bool = False; allow_dynamic_python: bool = False
    allow_docker: bool = False; allow_gpu: bool = False; max_memory_mb: int = 512

    @classmethod
    def default_restricted(cls) -> 'ProviderSandboxPolicy':
        return cls(allow_shell=False, allow_dynamic_python=False, allow_docker=False)

    @classmethod
    def from_profile(cls, profile: SandboxProfile, overrides: Optional[Dict[str, Any]] = None) -> 'ProviderSandboxPolicy':
        _PROFILES = {
            SandboxProfile.RESTRICTED:  dict(allow_shell=False, allow_docker=False, allow_gpu=False, max_memory_mb=256),
            SandboxProfile.WORKSPACE:   dict(allow_shell=False, allow_docker=False, allow_gpu=False, max_memory_mb=512),
            SandboxProfile.DEVELOPMENT: dict(allow_shell=True,  allow_docker=False, allow_gpu=False, max_memory_mb=1024),
            SandboxProfile.TRUSTED:     dict(allow_shell=True,  allow_docker=False, allow_gpu=True,  max_memory_mb=4096),
            SandboxProfile.PRIVILEGED:  dict(allow_shell=True,  allow_docker=True,  allow_gpu=True,  max_memory_mb=16384),
        }
        params = _PROFILES[profile].copy()
        if overrides: params.update(overrides)
        return cls(**params)
```

### 2.5 `ProviderFeatureSet` (ADR-0031) + `ProviderCapability` (ADR-0030 + ADR-0031 feature flags)
```python
@dataclass(frozen=True)
class ProviderFeatureSet:
    supports_streaming: bool = False; supports_vision: bool = False
    supports_tool_calling: bool = False; supports_json_mode: bool = False
    supports_function_calling: bool = False; supports_embeddings: bool = False
    supports_image_generation: bool = False
    min_context_window_tokens: int = 0; max_output_tokens: int = 0
    custom_features: Dict[str, Any] = field(default_factory=dict)

    def is_satisfied_by(self, capability: 'ProviderCapability') -> bool:
        return (
            (not self.supports_streaming or capability.supports_streaming) and
            (not self.supports_vision or capability.supports_vision) and
            (not self.supports_tool_calling or capability.supports_tool_calling) and
            (not self.supports_json_mode or capability.supports_json_mode) and
            capability.min_context_window_tokens >= self.min_context_window_tokens
        )

@dataclass(frozen=True)
class ProviderCapability:
    capability_id: str; operation_type: str
    capability_version: str; supported_revisions: List[str]; deprecated_revisions: List[str]
    parameter_schema: Dict[str, Any]; output_schema: Dict[str, Any]; rate_limits: Dict[str, int]
    supports_streaming: bool = False; supports_vision: bool = False
    supports_tool_calling: bool = False; supports_json_mode: bool = False
    supports_function_calling: bool = False; supports_embeddings: bool = False
    min_context_window_tokens: int = 0; max_output_tokens: int = 0
```

### 2.6 Auth, Config, Health, Event
```python
@dataclass(frozen=True)
class ProviderAuthentication:
    auth_type: str; credentials_vault_key: str
    additional_headers: Dict[str, str] = field(default_factory=dict)
    token_expiry: Optional[datetime] = None

@dataclass(frozen=True)
class ProviderConfiguration:
    timeout_seconds: float = 30.0; max_retries: int = 3
    retry_backoff_factor: float = 1.5; cache_ttl_seconds: int = 3600
    environment_variables: Dict[str, str] = field(default_factory=dict)
    project_overrides: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ProviderHealth:
    status: str; latency_ms: float; error_rate_24h: float; last_checked: datetime
    details: str = ""; circuit_breaker_open: bool = False

@dataclass(frozen=True)
class ProviderEvent:
    event_id: str; timestamp: datetime; provider_id: str; event_type: str
    channel: ProviderEventChannel; session_uuid: Optional[str]; duration_ms: float
    payload: Dict[str, Any]
```

### 2.7 Execution Dataclasses (ADR-0029 + ADR-0031 + ADR-0032)
```python
@dataclass(frozen=True)
class ProviderExecutionContext:
    session_uuid: str; user_id: int; workspace_path: str; project_manifest: Dict[str, Any]
    cost_budget_usd: float; trace_id: str
    sandbox_policy: ProviderSandboxPolicy = field(default_factory=ProviderSandboxPolicy.default_restricted)

@dataclass
class ProviderSession:
    session_id: str; user_id: int; workspace_path: str
    provider: 'BaseProvider'; auth: ProviderAuthentication; config: ProviderConfiguration
    sandbox: ProviderSandboxPolicy; quota: 'UnifiedCostQuotaService'
    cost_budget_usd: float; cost_consumed_usd: float = 0.0
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_execution_context(self) -> ProviderExecutionContext: ...
    def charge(self, usd_cost: float, units: float, unit_type: str) -> None: ...

@dataclass(frozen=True)
class ProviderSearchResult:
    resource_id: str; title: str; category: str
    thumbnail_url: Optional[str]; metadata: Dict[str, Any]; score: float = 1.0

@dataclass(frozen=True)
class ProviderResponse:
    success: bool; data: Any; metadata: Dict[str, Any]
    execution_ms: float; token_cost_usd: float = 0.0
    error: Optional['ProviderException'] = None

@dataclass(frozen=True)
class ExecutionRequest:
    category: ProviderCategory; operation: str; payload: Dict[str, Any]
    required_features: ProviderFeatureSet
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

# ADR-0032
@dataclass(frozen=True)
class ExecutionPolicy:
    policy_type: ExecutionPolicyType
    preferred_provider_ids: List[str] = field(default_factory=list)
    custom_ranker: Optional[Callable] = None
    fallback_policy: Optional['ExecutionPolicy'] = None

@dataclass(frozen=True)
class LockAcquisitionResult:
    acquired: bool; lock_key: str; holder_id: Optional[str]
    acquired_at: Optional[datetime]; expires_at: Optional[datetime]

@dataclass
class MigrationRecord:
    provider_id: str; from_version: str; to_version: str; status: MigrationStatus
    started_at: datetime; completed_at: Optional[datetime] = None; error_detail: Optional[str] = None

@dataclass(frozen=True)
class CompatibilityReport:
    is_compatible: bool; provider_id: str
    failures: List[str]; warnings: List[str]; checked_at: datetime

@dataclass(frozen=True)
class ProviderMetricsSnapshot:
    provider_id: str; window_seconds: int
    request_count: int; success_count: int; error_count: int
    fallback_count: int; retry_count: int
    avg_latency_ms: float; p50_latency_ms: float; p95_latency_ms: float; p99_latency_ms: float
    cache_hit_count: int; cache_miss_count: int; cache_hit_ratio: float
    selection_count: int; total_tokens_consumed: int; total_asset_bytes_consumed: int
    concurrent_executions: int; utilization_pct: float

@dataclass
class ServiceRegistration:
    service_type: Type; implementation_type: Type
    lifetime: ServiceLifetime; factory: Optional[Callable] = None
```

---

## Module 3: Exception Hierarchy

```python
class ProviderException(Exception):
    def __init__(self, message, provider_id, error_code="ERR_PROVIDER_GENERAL", details=None):
        super().__init__(message)
        self.provider_id = provider_id; self.error_code = error_code; self.details = details or {}

class ProviderAuthenticationError(ProviderException): pass
class ProviderHealthDegradedError(ProviderException): pass
class ProviderRateLimitError(ProviderException):
    def __init__(self, message, provider_id, retry_after_seconds=60, **kwargs):
        super().__init__(message, provider_id, error_code="ERR_RATE_LIMIT", **kwargs)
        self.retry_after_seconds = retry_after_seconds
class ProviderExecutionError(ProviderException): pass
class ProviderTimeoutError(ProviderException): pass
class ProviderConfigurationError(ProviderException): pass
class ProviderSecurityException(ProviderException): pass
class ProviderFeatureNotSupportedError(ProviderException): pass
class ProviderDiscoveryError(ProviderException): pass
class ProviderMigrationError(ProviderException): pass        # ADR-0032
class ProviderLockTimeoutError(ProviderException): pass      # ADR-0032
class ProviderCompatibilityError(ProviderException): pass    # ADR-0032
```

---

## Module 4: `BaseProvider` Abstract Class

```python
class BaseProvider(abc.ABC):
    def __init__(self, metadata: ProviderMetadata, sandbox: Optional[ProviderSandboxPolicy] = None):
        self._metadata = metadata
        self._sandbox = sandbox or ProviderSandboxPolicy.default_restricted()
        self._state = ProviderStateRecord(provider_id=metadata.provider_id)

    @property
    def metadata(self) -> ProviderMetadata: return self._metadata
    @property
    def state(self) -> ProviderStateRecord: return self._state
    @property
    def sandbox(self) -> ProviderSandboxPolicy: return self._sandbox

    # Core 10-stage lifecycle (ADR-0029) — abstract
    @abc.abstractmethod
    def initialize(self, config: ProviderConfiguration) -> None: ...
    @abc.abstractmethod
    def authenticate(self, auth: ProviderAuthentication) -> bool: ...
    @abc.abstractmethod
    def check_health(self) -> ProviderHealth: ...
    @abc.abstractmethod
    def discover_capabilities(self) -> List[ProviderCapability]: ...
    @abc.abstractmethod
    def search(self, query: str, filters: Dict[str, Any]) -> List[ProviderSearchResult]: ...
    @abc.abstractmethod
    def fetch(self, resource_id: str, context: ProviderExecutionContext) -> ProviderResponse: ...
    @abc.abstractmethod
    def execute(self, operation: str, payload: Dict[str, Any], context: ProviderExecutionContext) -> ProviderResponse: ...
    @abc.abstractmethod
    def cleanup(self) -> None: ...

    # Lifecycle hooks (ADR-0031) — optional no-ops
    def before_install(self) -> None: pass
    def after_install(self) -> None: pass
    def before_enable(self) -> None: pass
    def after_enable(self) -> None: pass
    def before_remove(self) -> None: pass
    def after_remove(self) -> None: pass
    def before_upgrade(self, from_version: str, to_version: str) -> None: pass
    def after_upgrade(self, from_version: str, to_version: str) -> None: pass

    # Migration hooks (ADR-0032) — optional no-ops
    def validate_upgrade(self, from_version: str, to_version: str) -> bool: return True
    def validate_downgrade(self, from_version: str, to_version: str) -> bool: return True
    def migrate(self, from_version: str, to_version: str) -> None: pass
    def rollback(self, version: str) -> None: pass
```

---

## Module 5: Governance Service Interfaces

```python
# ── ADR-0030 ───────────────────────────────────────────────────────────────

class ProviderEventBus(abc.ABC):
    @abc.abstractmethod
    def publish(self, event: ProviderEvent) -> None: ...       # Non-blocking, ≤1ms
    @abc.abstractmethod
    def subscribe(self, channel: ProviderEventChannel, callback: Any) -> None: ...
    @abc.abstractmethod
    def drain(self, timeout_ms: int = 5000) -> None: ...       # Test synchronization

class ProviderStateMachine(abc.ABC):
    VALID_TRANSITIONS = { ... }  # 15 explicit (from, to) pairs
    @abc.abstractmethod
    def transition(self, provider_id: str, to_state: ProviderRuntimeState, reason: str = "") -> bool: ...
    @abc.abstractmethod
    def get_state(self, provider_id: str) -> ProviderRuntimeState: ...
    @abc.abstractmethod
    def is_invocable(self, provider_id: str) -> bool: ...

class ProviderDependencyGraph(abc.ABC):
    @abc.abstractmethod
    def add_dependency(self, provider_id: str, requires: List[str]) -> None: ...
    @abc.abstractmethod
    def resolve_startup_order(self) -> List[str]: ...
    @abc.abstractmethod
    def detect_cycles(self) -> bool: ...

class UnifiedCostQuotaService(abc.ABC):
    @abc.abstractmethod
    def check_quota(self, provider_id: str, category: ProviderCategory, cost_units: float) -> bool: ...
    @abc.abstractmethod
    def record_expenditure(self, session_uuid: str, provider_id: str, usd_cost: float, units: float) -> None: ...

# ── ADR-0031 ───────────────────────────────────────────────────────────────

class ProviderHealthService(abc.ABC):
    @abc.abstractmethod
    def probe_health(self, provider_id: str) -> ProviderHealth: ...
    @abc.abstractmethod
    def get_health(self, provider_id: str) -> ProviderHealth: ...
    @abc.abstractmethod
    def schedule_probes(self) -> None: ...

class ProviderTelemetryService(abc.ABC):
    @abc.abstractmethod
    def start_span(self, operation: str, session: ProviderSession) -> str: ...
    @abc.abstractmethod
    def end_span(self, span_id: str, response: ProviderResponse) -> None: ...
    @abc.abstractmethod
    def emit_event(self, event_type: str, payload: Dict[str, Any], session: ProviderSession) -> None: ...

class ProviderDiscovery(abc.ABC):
    @abc.abstractmethod
    def discover_builtin(self) -> List[Type[BaseProvider]]: ...
    @abc.abstractmethod
    def discover_community(self) -> List[Type[BaseProvider]]: ...
    @abc.abstractmethod
    def discover_marketplace(self, package_dir: str) -> List[Type[BaseProvider]]: ...
    @abc.abstractmethod
    def validate_and_register(self, provider_class: Type[BaseProvider]) -> bool: ...

class CapabilityResolver(abc.ABC):
    @abc.abstractmethod
    def resolve(self, category: ProviderCategory, operation_type: str,
                required_features: ProviderFeatureSet, context: ProviderExecutionContext,
                policy: Optional[ExecutionPolicy] = None) -> BaseProvider: ...        # ADR-0032 policy param
    @abc.abstractmethod
    def resolve_all(self, category: ProviderCategory, operation_type: str,
                    required_features: ProviderFeatureSet) -> List[BaseProvider]: ...

class ProviderRegistry(abc.ABC):
    @abc.abstractmethod
    def register_provider(self, provider_class: Type[BaseProvider]) -> None: ...
    @abc.abstractmethod
    def get_metadata(self, provider_id: str) -> Optional[ProviderMetadata]: ...
    @abc.abstractmethod
    def list_providers(self, category: Optional[ProviderCategory] = None, active_only: bool = True) -> List[ProviderMetadata]: ...
    @abc.abstractmethod
    def unregister_provider(self, provider_id: str) -> bool: ...

class ProviderFactory(abc.ABC):
    """Focused solely on instantiation (ADR-0031). Selection delegated to CapabilityResolver."""
    @abc.abstractmethod
    def create_provider(self, provider_id: str, config: ProviderConfiguration, auth: ProviderAuthentication) -> BaseProvider: ...
    def resolve_provider_for_capability(self, category, operation_type, capability_version, context) -> BaseProvider:
        """Backward-compatible thin delegation to CapabilityResolver."""
        ...

class ExecutionOrchestrator(abc.ABC):
    @abc.abstractmethod
    def execute(self, category: ProviderCategory, operation: str, payload: Dict[str, Any],
                required_features: ProviderFeatureSet, session: ProviderSession) -> ProviderResponse: ...
    @abc.abstractmethod
    def execute_streaming(self, category, operation, payload, required_features, session) -> Generator[ProviderResponse, None, None]: ...
    @abc.abstractmethod
    def execute_parallel(self, requests: List[ExecutionRequest], session: ProviderSession) -> List[ProviderResponse]: ...

# ── ADR-0032 ───────────────────────────────────────────────────────────────

class ProviderServiceContainer(abc.ABC):
    @abc.abstractmethod
    def register(self, registration: ServiceRegistration) -> None: ...
    @abc.abstractmethod
    def resolve(self, service_type: Type[T]) -> T: ...
    @abc.abstractmethod
    def create_scope(self) -> 'ProviderServiceContainer': ...
    @abc.abstractmethod
    def build(self) -> None: ...

class ProviderCompatibilityService(abc.ABC):
    @abc.abstractmethod
    def validate(self, provider_class: Type[BaseProvider]) -> CompatibilityReport: ...
    @abc.abstractmethod
    def validate_platform_version(self, minimum: str) -> bool: ...
    @abc.abstractmethod
    def validate_odoo_version(self, minimum: str) -> bool: ...
    @abc.abstractmethod
    def validate_python_version(self, minimum: str) -> bool: ...
    @abc.abstractmethod
    def validate_manifest_schema(self, metadata: ProviderMetadata) -> List[str]: ...
    @abc.abstractmethod
    def validate_dependency_compatibility(self, dependencies: List[str]) -> List[str]: ...
    @abc.abstractmethod
    def validate_api_version(self, provider_class: Type[BaseProvider]) -> bool: ...
    @abc.abstractmethod
    def validate_future_migration(self, metadata: ProviderMetadata) -> List[str]: ...

class LockService(abc.ABC):
    @abc.abstractmethod
    def acquire(self, lock_key: str, holder_id: str, timeout_ms: int = 5000, ttl_ms: int = 30000) -> LockAcquisitionResult: ...
    @abc.abstractmethod
    def release(self, lock_key: str, holder_id: str) -> bool: ...
    @abc.abstractmethod
    def extend(self, lock_key: str, holder_id: str, ttl_ms: int) -> bool: ...
    @abc.abstractmethod
    def is_held(self, lock_key: str) -> bool: ...
    @abc.abstractmethod
    def get_backend(self) -> LockBackend: ...

class ProviderMigrationService(abc.ABC):
    @abc.abstractmethod
    def plan_upgrade(self, provider_id: str, to_version: str) -> List[MigrationRecord]: ...
    @abc.abstractmethod
    def execute_upgrade(self, provider_id: str, to_version: str) -> MigrationRecord: ...
    @abc.abstractmethod
    def rollback_upgrade(self, provider_id: str, to_version: str) -> MigrationRecord: ...
    @abc.abstractmethod
    def get_migration_history(self, provider_id: str) -> List[MigrationRecord]: ...

class ProviderMetricsService(abc.ABC):
    @abc.abstractmethod
    def record_request(self, provider_id: str, latency_ms: float, success: bool, is_fallback: bool, is_retry: bool) -> None: ...
    @abc.abstractmethod
    def record_cache_event(self, provider_id: str, hit: bool, level: int) -> None: ...
    @abc.abstractmethod
    def record_selection(self, provider_id: str, policy: ExecutionPolicy) -> None: ...
    @abc.abstractmethod
    def get_snapshot(self, provider_id: str, window_seconds: int = 300) -> ProviderMetricsSnapshot: ...
    @abc.abstractmethod
    def get_all_snapshots(self, window_seconds: int = 300) -> List[ProviderMetricsSnapshot]: ...
    @abc.abstractmethod
    def reset(self, provider_id: str) -> None: ...

class CapabilityCache(abc.ABC):
    @abc.abstractmethod
    def get(self, provider_id: str, capability_version: str = "latest") -> Optional[List[ProviderCapability]]: ...
    @abc.abstractmethod
    def set(self, provider_id: str, capabilities: List[ProviderCapability], ttl_seconds: int = 86400) -> None: ...
    @abc.abstractmethod
    def invalidate(self, provider_id: str) -> None: ...
    @abc.abstractmethod
    def invalidate_all(self) -> None: ...
    @abc.abstractmethod
    def refresh(self, provider_id: str, provider: BaseProvider) -> List[ProviderCapability]: ...
    @abc.abstractmethod
    def get_or_refresh(self, provider_id: str, provider: BaseProvider) -> List[ProviderCapability]: ...

class ProviderCache(abc.ABC):
    """L1 Memory / L2 Redis / L3 Persistent — execution result cache (ADR-0031)."""
    @abc.abstractmethod
    def get(self, key: str) -> Optional[Any]: ...
    @abc.abstractmethod
    def set(self, key: str, value: Any, ttl_override: Optional[int] = None) -> None: ...
    @abc.abstractmethod
    def invalidate(self, key: str) -> None: ...
```
