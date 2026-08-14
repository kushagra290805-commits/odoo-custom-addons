# ADR-0031: Provider Service Decomposition & Advanced Orchestration

**Status:** Proposed & Architecture-Validated (Phase 15B Pre-Implementation Architecture-First Refinement)  
**Date:** July 2026  
**Authors:** Nexora Studio Advanced Architecture & Governance Team  
**Extends / Supplements:** ADR-0029 (Unified Provider Platform), ADR-0030 (Provider Runtime & Lifecycle Governance)  
**Strictly Additive:** Zero breaking changes to ADR-0029 or ADR-0030 contracts  

---

## 1. Context & Motivation

ADR-0029 established the foundational polymorphic provider hierarchy and 10-stage lifecycle. ADR-0030 introduced type-safe enumerations, a 9-state FSM, a 6-channel event bus, dependency graph, sandbox policies, and unified cost/quota accounting.

Before any Phase 15B source code is written, a final round of architectural simulation — driven by production scenarios modeled against the Nexora Studio AI generation, asset resolution, and MCP tool execution pipelines — has identified ten concerns where the current design would produce overloaded components, blocking side effects, untested execution paths, and poor observability isolation:

1. **`ProviderFactory` Overloading:** ADR-0030 assigned both provider *instantiation* and *selection-by-capability* to `ProviderFactory`. These are distinct concerns; coupling them violates Single Responsibility and makes fallback routing logic invisible to callers and tests.
2. **Absent Provider Discovery:** Provider registration is assumed to happen at module import time, but there is no defined service responsible for discovering, validating, deduplicating, and registering providers from multiple sources (built-in, community, marketplace).
3. **Health Monitoring / Telemetry Conflation:** The `ProviderEventBus` mixes diagnostic health data (`METRICS`, `AUDIT`) with operational side-effects (`WEBSOCKET`, `NOTIFICATIONS`). Health probe results, circuit breaker logic, and execution telemetry require separate ownership, TTLs, and failure semantics.
4. **Revision-Only Capability Matching:** The current `resolve_provider_for_capability(operation_type, capability_version)` API selects providers by revision string only. Production AI workloads require feature-set negotiation (e.g., "I need a provider supporting vision *and* JSON-mode *and* a context window ≥ 128k tokens").
5. **Missing Lifecycle Hooks:** Provider installation, activation, upgrade, and removal are state machine transitions, but callers have no sanctioned way to inject pre/post logic (e.g., schema migrations, warmup calls, cache clearing).
6. **Per-Provider Sandbox Definitions:** Requiring every adapter author to declare individual sandbox flags (`allow_shell = True/False`) invites inconsistency and security policy drift. Named, auditable sandbox profiles should be the primary interface.
7. **Blocking Event Bus:** The ADR-0030 event bus specification did not mandate non-blocking delivery. A slow database insert in the `TELEMETRY` subscriber or a failed websocket push in the `WEBSOCKET` subscriber can delay provider `execute()` response times.
8. **Absent Per-Session Runtime Isolation:** Authentication tokens, cost quotas, cache namespaces, and telemetry trace IDs are currently properties of `ProviderExecutionContext`, which is a frozen dataclass with no lifecycle of its own. Execution sessions need a mutable, lifecycle-aware container.
9. **Single-Level Provider Cache:** `ProviderCache` was specified as a single logical layer. High-frequency capability manifest lookups need in-process memory speed; asset binary blobs need persistent disk durability. A single caching layer cannot optimally serve both.
10. **Absent Execution Orchestrator:** The complex cross-service coordination required for retries, parallel provider execution, fallback routing, cancellation, streaming multiplexing, and circuit breaker integration is currently expected to be implemented independently by each calling service (`GenerationOrchestrator`, `DesignOrchestrator`). This produces duplicated orchestration logic.

---

## 2. Decision

We introduce **ten strictly-additive architectural refinements** that decompose overloaded components and introduce purpose-built services. All existing abstract classes, dataclasses, and enumerations from ADR-0029 and ADR-0030 remain intact.

### 2.1 `CapabilityResolver` — Dedicated Provider Selection

The `ProviderFactory` is refocused on provider *instantiation only*. A new `CapabilityResolver` service owns provider *selection* based on capability requirements, feature negotiation, FSM state checks, priority weights, and fallback routing.

```
CapabilityResolver.resolve(
    category: ProviderCategory,
    operation_type: str,
    required_features: ProviderFeatureSet,
    context: ProviderExecutionContext
) → BaseProvider
```

`ProviderFactory.create_provider()` and `ProviderFactory.resolve_provider_for_capability()` are retained for backward compatibility but `resolve_provider_for_capability()` becomes a thin delegation to `CapabilityResolver`.

### 2.2 `ProviderDiscovery` — Multi-Source Provider Discovery

A new `ProviderDiscovery` service is responsible for discovering, validating, deduplicating, and registering providers from four source types:

| Source Type | Examples | Discovery Mechanism |
|:---|:---|:---|
| **Built-in** | `OpenAIAdapter`, `VitePreviewProvider` | Python class scanning via `__subclasses__()` at Odoo boot |
| **Community packages** | Odoo addon `nexora_openrouter` | Odoo module manifest `provider_exports` key |
| **Marketplace packages** | Installed from Studio Marketplace | Signed manifest JSON in `nexora_marketplace_packages/` directory |
| **External sources** | Future: remote registry CDN | Plugin registry HTTP endpoint (Phase 15D+) |

`ProviderDiscovery` runs before `ProviderRegistry.register_provider()` and enforces manifest schema validation, minimum platform version checks, signature verification (marketplace only), and conflict/duplicate resolution.

### 2.3 Separation of `ProviderHealthService` and `ProviderTelemetryService`

The ADR-0030 `ProviderEventBus` is decomposed into two dedicated services with distinct ownership:

**`ProviderHealthService`** owns:
- Periodic health probe scheduling (Odoo cron-based)
- Circuit breaker tripping and reset logic
- `ProviderStateRecord` updates via `ProviderStateMachine`
- `METRICS` channel publishing for health gauges only

**`ProviderTelemetryService`** owns:
- Execution event lifecycle (`provider.execute.start`, `provider.execute.end`, `provider.execute.error`)
- Distributed tracing (trace ID, span ID, parent-child relationships)
- `TELEMETRY` → `nexora.runtime_event` persistence
- `LOGGING` → Python `_logger` formatted with trace IDs
- `AUDIT` → immutable security compliance log
- `WEBSOCKET` → real-time Console UI push
- `NOTIFICATIONS` → admin alert toasts

`ProviderEventBus` remains as the shared transport mechanism; `ProviderHealthService` and `ProviderTelemetryService` are the structured publishers.

### 2.4 `ProviderFeatureSet` — Feature-Based Capability Negotiation

Capability resolution is elevated from revision-string matching to structured feature negotiation:

```python
@dataclass(frozen=True)
class ProviderFeatureSet:
    supports_streaming: bool = False
    supports_vision: bool = False
    supports_tool_calling: bool = False
    supports_json_mode: bool = False
    min_context_window_tokens: int = 0
    max_output_tokens: int = 0
    supports_function_calling: bool = False
    supports_embeddings: bool = False
    supports_image_generation: bool = False
    custom_features: Dict[str, Any] = field(default_factory=dict)
```

`CapabilityResolver` evaluates all registered active providers for the requested category, filters by `ProviderFeatureSet` satisfaction, then applies priority weight ordering and FSM state checks to return the optimal provider.

### 2.5 Provider Lifecycle Hooks

`BaseProvider` is extended with eight optional lifecycle hook methods. Default implementations are no-ops; adapter authors override only what they need:

```python
class BaseProvider(abc.ABC):
    # --- Lifecycle Hooks (ADR-0031) ---
    def before_install(self) -> None: pass
    def after_install(self) -> None: pass
    def before_enable(self) -> None: pass
    def after_enable(self) -> None: pass
    def before_remove(self) -> None: pass
    def after_remove(self) -> None: pass
    def before_upgrade(self, from_version: str, to_version: str) -> None: pass
    def after_upgrade(self, from_version: str, to_version: str) -> None: pass
```

`ProviderStateMachine` invokes the appropriate hooks when processing lifecycle transitions.

### 2.6 Named Sandbox Profiles

`ProviderSandboxPolicy` is extended with five named profile factories. Per-adapter flag definitions are deprecated in favour of named profiles; field-level overrides remain available for exceptional cases:

```python
class SandboxProfile(str, Enum):
    RESTRICTED   = "restricted"    # Zero permissions; default for untrusted community providers
    WORKSPACE    = "workspace"     # Read/write to project VFS only
    DEVELOPMENT  = "development"   # Workspace + shell execution for dev tools (Preview, MCP)
    TRUSTED      = "trusted"       # Full workspace + network + GPU; for vetted system providers
    PRIVILEGED   = "privileged"    # All permissions; reserved for Nexora Studio Core Team only

class ProviderSandboxPolicy:
    @classmethod
    def from_profile(cls, profile: SandboxProfile, overrides: Dict[str, Any] = None) -> 'ProviderSandboxPolicy':
        ...
```

Each profile maps to a concrete `ProviderSandboxPolicy` instance. All profiles are stored in a sealed registry; the `PRIVILEGED` profile requires a signed Nexora Studio Core Team API key to instantiate.

### 2.7 Non-Blocking Asynchronous `ProviderEventBus`

The `ProviderEventBus` implementation mandate is strengthened: all event delivery **must** be non-blocking from the caller's perspective. The implementation must:
- Dispatch event payloads to an in-process thread pool queue immediately, returning control to the caller.
- Execute each subscriber in an isolated `try/except` block in a background thread.
- Log subscriber failures to Python `_logger.error()` without re-raising.
- Provide a `drain(timeout_ms: int)` method for testing to await pending deliveries synchronously.

### 2.8 `ProviderSession` — Per-Execution Runtime Container

A new `ProviderSession` abstraction encapsulates all mutable runtime state for a single execution session, replacing the frozen `ProviderExecutionContext` as the primary session container. `ProviderExecutionContext` is retained as an immutable snapshot passed into `execute()` calls:

```python
@dataclass
class ProviderSession:
    session_id: str
    user_id: int
    workspace_path: str
    provider: BaseProvider
    auth: ProviderAuthentication
    config: ProviderConfiguration
    sandbox: ProviderSandboxPolicy
    cache: 'ProviderCache'
    telemetry: 'ProviderTelemetryService'
    quota: 'UnifiedCostQuotaService'
    cost_budget_usd: float
    cost_consumed_usd: float = 0.0
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_execution_context(self) -> ProviderExecutionContext:
        """Snapshot the mutable session into an immutable context for execute() calls."""
        ...

    def charge(self, usd_cost: float, units: float, unit_type: str) -> None:
        """Record expenditure against session budget via QuotaService."""
        ...
```

`ProviderSession` is created by `ExecutionOrchestrator` and passed to all downstream services; it is never persisted to SQL — it exists only for the duration of a single request.

### 2.9 Multi-Level `ProviderCache` (L1 / L2 / L3)

`ProviderCache` is extended into a hierarchical three-level cache architecture:

| Level | Name | Backend | Scope | TTL | Use Case |
|:---|:---|:---|:---|:---|:---|
| **L1** | Memory Cache | `functools.lru_cache` / Python dict | In-process | 60s | Capability manifests, provider metadata lookups |
| **L2** | Redis Cache | Odoo `ormcache` / Redis | Cross-process | 3600s | AI completion results, search result sets |
| **L3** | Persistent Cache | VFS disk / Odoo DB JSONB field | Cross-restart | Infinite (TTL-controlled) | Binary asset blobs (images, fonts), large AI outputs |

Cache reads follow a waterfall lookup (L1 → L2 → L3 → Provider). Cache writes populate all applicable levels simultaneously. Cache invalidation is propagated downward from L1 to L3.

### 2.10 `ExecutionOrchestrator` — Master Execution Coordinator

A new `ExecutionOrchestrator` service is the single authoritative entry point for all provider execution flows. No calling service (`GenerationOrchestrator`, `DesignOrchestrator`, etc.) should directly invoke `BaseProvider.execute()` — they coordinate through `ExecutionOrchestrator`:

```python
class ExecutionOrchestrator(abc.ABC):
    @abc.abstractmethod
    def execute(
        self,
        category: ProviderCategory,
        operation: str,
        payload: Dict[str, Any],
        required_features: ProviderFeatureSet,
        session: ProviderSession,
    ) -> ProviderResponse: ...

    @abc.abstractmethod
    def execute_streaming(
        self,
        category: ProviderCategory,
        operation: str,
        payload: Dict[str, Any],
        required_features: ProviderFeatureSet,
        session: ProviderSession,
    ) -> Generator[ProviderResponse, None, None]: ...

    @abc.abstractmethod
    def execute_parallel(
        self,
        requests: List[ExecutionRequest],
        session: ProviderSession,
    ) -> List[ProviderResponse]: ...
```

Internally, `ExecutionOrchestrator` coordinates: `CapabilityResolver → ProviderFactory → ProviderSession → ProviderStateMachine → ProviderSandboxPolicy → ProviderTelemetryService → UnifiedCostQuotaService → BaseProvider.execute()` with full retry, timeout, fallback, cancellation, and circuit-breaker integration.

---

## 3. Backward Compatibility Guarantees

| Component | ADR-0029 / ADR-0030 Contract | ADR-0031 Compatibility |
|:---|:---|:---|
| `BaseProvider` | Abstract lifecycle methods | 8 new hook methods added with default no-op implementations |
| `ProviderFactory.resolve_provider_for_capability()` | Selection by category + capability | Retained; delegates to `CapabilityResolver` internally |
| `ProviderSandboxPolicy` fields | 7 boolean/list fields | All fields retained; `from_profile()` is an additive factory |
| `ProviderExecutionContext` | Frozen dataclass passed to `execute()` | Retained exactly; `ProviderSession.to_execution_context()` generates it |
| `ProviderEventBus` | 6-channel pub/sub | Now asynchronous with thread-pool delivery; subscriber signatures unchanged |
| `ProviderCache` | Single logical cache layer | Promoted to L1/L2/L3 internally; public API (`get`, `set`, `invalidate`) unchanged |
| All existing REST API endpoints | JSON response schemas | Zero schema changes; `ExecutionOrchestrator` replaces internal delegation only |

---

## 4. Consequences & Implementation Notes

- **Phase 15B Execution Scope (Updated):** All ten new services/abstractions are implemented in `services/providers/` with complete automated test coverage before any bridge adapter or REST controller work begins.
- **Service Initialization Order:** `ProviderDiscovery` → `ProviderRegistry` → `ProviderDependencyGraph` → `ProviderStateMachine` → `ProviderHealthService` → `ProviderTelemetryService` → `CapabilityResolver` → `ExecutionOrchestrator`.
- **Existing Code Paths:** All existing `AIProviderManager` callers and Console REST API clients continue to function without modification throughout Phase 15B.
