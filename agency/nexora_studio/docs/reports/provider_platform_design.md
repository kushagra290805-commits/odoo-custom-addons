# Provider Platform Design — Unified Architecture (ADR-0029 + ADR-0030 + ADR-0031 + ADR-0032)

**Date:** July 2026
**Type:** Architecture Design Document — Full Topology, Class Hierarchy, and Service Topology

---

## 1. Three-Tier Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER — Nexora Developer Console (React + TanStack + Zustand)  │
│  Provider Mgmt Dashboard │ Model Selector │ Asset Browser │ Marketplace UI   │
│  Metrics Dashboard │ Migration Control │ Compatibility Report Viewer          │
└───────────────────────────┬───────────────────────────────────────────────────┘
                            │ REST HTTP / SSE / WebSocket
┌───────────────────────────▼───────────────────────────────────────────────────┐
│  ORCHESTRATION & GOVERNANCE KERNEL — Odoo Backend OS                         │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  ProviderServiceContainer (DI Composition Root — ADR-0032)              │ │
│  └────────────────────────────────┬─────────────────────────────────────────┘ │
│                                   │ resolves                                  │
│  ┌─────────────────┐  ┌───────────▼─────────┐  ┌─────────────────────────┐  │
│  │  LockService    │  │  ProviderEventBus   │  │ ProviderStateMachine    │  │
│  │  PG/Redis/Mem   │  │  Async ThreadPool   │  │ 9-State FSM             │  │
│  └─────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │CompatibilitySvc │  │  ProviderDiscovery  │  │ ProviderDependencyGraph │  │
│  │ 7 Validators    │  │  4 Source Types     │  │ Kahn's BFS              │  │
│  └─────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │ProviderRegistry │  │  ProviderFactory    │  │ CapabilityResolver      │  │
│  │ SQL + LRU Cache │  │  Instantiation Only │  │ Feature + Policy Rank   │  │
│  └─────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │ HealthService   │  │ TelemetryService    │  │ MetricsService          │  │
│  │ Probes+Breaker  │  │ Spans+Audit+WS      │  │ Rolling-Window Agg      │  │
│  └─────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │ CapabilityCache │  │ ProviderCache L1/2/3│  │ CostQuotaService        │  │
│  │ 24h Manifest TTL│  │ Memory/Redis/VFS    │  │ 5-Dimension Accounting  │  │
│  └─────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │MigrationService │  │ ExecutionOrchestrat.│  │ ProviderSession (Scoped)│  │
│  │Upgrade+Rollback │  │ Master Coordinator  │  │ Per-Request Container   │  │
│  └─────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
                            │ executes via BaseProvider contract
┌───────────────────────────▼───────────────────────────────────────────────────┐
│  ADAPTER BRIDGE LAYER — Polymorphic Sandboxed Adapters                       │
│  AI (OpenAI, Claude, Gemini, Ollama, NVIDIA)    — SandboxProfile.TRUSTED     │
│  MCP External Servers                           — SandboxProfile.DEVELOPMENT  │
│  MCP Internal Tools                             — SandboxProfile.WORKSPACE    │
│  Asset Providers (Unsplash, Pixabay, Fonts)     — SandboxProfile.WORKSPACE    │
│  Design Providers (Penpot, React UI Kits)       — SandboxProfile.WORKSPACE    │
│  Preview Providers (Vite, HTTP Servers)         — SandboxProfile.DEVELOPMENT  │
│  Storage Providers (VFS, Cloud S3)              — SandboxProfile.TRUSTED      │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete Service Class Hierarchy

```mermaid
classDiagram
    class ProviderServiceContainer {<<abstract>> register() resolve() create_scope() build()}
    class LockService {<<abstract>> acquire() release() extend() is_held() get_backend()}
    class ProviderEventBus {<<abstract>> publish() subscribe() drain()}
    class ProviderStateMachine {<<abstract>> VALID_TRANSITIONS transition() get_state() is_invocable()}
    class ProviderDependencyGraph {<<abstract>> add_dependency() resolve_startup_order() detect_cycles()}
    class ProviderCompatibilityService {<<abstract>> validate() validate_platform_version() validate_odoo_version() validate_manifest_schema()}
    class ProviderDiscovery {<<abstract>> discover_builtin() discover_community() discover_marketplace() validate_and_register()}
    class ProviderRegistry {<<abstract>> register_provider() get_metadata() list_providers() unregister_provider()}
    class ProviderFactory {<<abstract>> create_provider() resolve_provider_for_capability()}
    class ProviderHealthService {<<abstract>> probe_health() get_health() schedule_probes()}
    class ProviderTelemetryService {<<abstract>> start_span() end_span() emit_event()}
    class ProviderMetricsService {<<abstract>> record_request() record_cache_event() record_selection() get_snapshot()}
    class CapabilityCache {<<abstract>> get() set() invalidate() refresh() get_or_refresh()}
    class ProviderCache {<<abstract>> get() set() invalidate()}
    class UnifiedCostQuotaService {<<abstract>> check_quota() record_expenditure()}
    class CapabilityResolver {<<abstract>> resolve() resolve_all()}
    class ProviderMigrationService {<<abstract>> plan_upgrade() execute_upgrade() rollback_upgrade() get_migration_history()}
    class ExecutionOrchestrator {<<abstract>> execute() execute_streaming() execute_parallel()}
    class BaseProvider {<<abstract>> metadata sandbox state initialize() authenticate() check_health() discover_capabilities() search() fetch() execute() cleanup() +8 lifecycle hooks +4 migration hooks}

    ProviderServiceContainer --> LockService
    ProviderServiceContainer --> ProviderEventBus
    ProviderServiceContainer --> ProviderStateMachine
    ProviderStateMachine --> LockService
    ProviderDiscovery --> ProviderCompatibilityService
    CapabilityResolver --> CapabilityCache
    CapabilityResolver --> ProviderMetricsService
    ExecutionOrchestrator --> CapabilityResolver
    ExecutionOrchestrator --> ProviderStateMachine
    ExecutionOrchestrator --> LockService
    ExecutionOrchestrator --> ProviderTelemetryService
    ExecutionOrchestrator --> ProviderMetricsService
    ExecutionOrchestrator --> UnifiedCostQuotaService
    ExecutionOrchestrator --> ProviderCache
    ProviderMigrationService --> LockService
    ProviderMigrationService --> ProviderStateMachine
    ProviderMigrationService --> ProviderCompatibilityService
    ProviderMigrationService --> CapabilityCache
```

---

## 3. ExecutionOrchestrator Flow (Complete Sequence)

```mermaid
sequenceDiagram
    actor Caller
    participant Orch as ExecutionOrchestrator
    participant Res as CapabilityResolver
    participant Lock as LockService
    participant FSM as ProviderStateMachine
    participant Tel as ProviderTelemetryService
    participant Metrics as ProviderMetricsService
    participant Quota as UnifiedCostQuotaService
    participant Cache as ProviderCache
    participant Provider as BaseProvider

    Caller->>Orch: execute(category, operation, features, session)
    Orch->>Res: resolve(category, operation, features, context, policy)
    Res-->>Orch: provider (ranked by ExecutionPolicy)
    Orch->>Lock: acquire(provider:exec_lock, concurrency check)
    Lock-->>Orch: LockAcquisitionResult(acquired=True)
    Orch->>FSM: transition(BUSY)
    Orch->>Tel: start_span(operation, session)
    Tel-->>Orch: span_id
    Orch->>Quota: check_quota(provider_id, category, estimated_cost)
    Quota-->>Orch: True (within budget)
    Orch->>Provider: execute(operation, payload, context)
    Provider-->>Orch: ProviderResponse(success=True)
    Orch->>Tel: end_span(span_id, response)
    Orch->>Quota: record_expenditure via session.charge()
    Orch->>FSM: transition(READY)
    Orch->>Lock: release(provider:exec_lock)
    Orch->>Cache: set(cache_key, response)
    Orch->>Metrics: record_request(latency, success=True)
    Orch-->>Caller: ProviderResponse
```

---

## 4. Provider Category Specialization Matrix

| Category | Sandbox Profile | discover_capabilities() | execute() primary operation | Cost dimension |
|:---|:---|:---|:---|:---|
| `AI` | `TRUSTED` | LLM model specs (context, vision, tools, cost) | `generate` / `embed` | AI tokens (USD) |
| `ASSET` | `WORKSPACE` | Image/font search schemas | `search` / `fetch` | Bandwidth (MB) |
| `MCP` (external) | `DEVELOPMENT` | Tool schemas from MCP server | `tool-call` | CPU time (ms) |
| `MCP` (internal) | `WORKSPACE` | Odoo tool reflection | `tool-call` | CPU time (ms) |
| `DESIGN` | `WORKSPACE` | Render/synthesis specs | `render` / `synthesize` | AI tokens (USD) |
| `PREVIEW` | `DEVELOPMENT` | Port/process specs | `launch` / `restart` | Uptime (hours) |
| `STORAGE` | `TRUSTED` | Storage quota + path specs | `read` / `write` / `delete` | Storage (bytes) |
| `COMPONENT` | `WORKSPACE` | Component prop schemas | `resolve` / `generate` | AI tokens (USD) |

---

## 5. Odoo SQL Data Model Overview

```mermaid
erDiagram
    nexora_provider_registry {
        string provider_id PK
        string name
        string category
        string provider_version
        string manifest_version
        string api_version
        boolean is_active
        integer priority_weight
        string sandbox_profile
        text concurrency_json
        text capability_json
        text marketplace_json
        text dependency_json
    }
    nexora_provider_runtime_state {
        int id PK
        string provider_id FK
        string current_state
        integer active_locks
        float last_latency_ms
        float error_rate_24h
        integer consecutive_failures
        datetime last_state_transition
        text degradation_reason
    }
    nexora_provider_cost_ledger {
        int id PK
        string session_uuid
        string provider_id FK
        float usd_cost
        float units_consumed
        string unit_type
        datetime timestamp
    }
    nexora_provider_cache_blob {
        int id PK
        string cache_key
        text cache_value_json
        string vfs_path
        datetime expires_at
        boolean is_stale
    }
    nexora_provider_capability_cache {
        int id PK
        string provider_id FK
        text capabilities_json
        datetime cached_at
        datetime expires_at
        boolean is_stale
    }
    nexora_provider_migration_log {
        int id PK
        string provider_id FK
        string from_version
        string to_version
        string status
        datetime started_at
        datetime completed_at
        text error_detail
    }

    nexora_provider_registry ||--o{ nexora_provider_runtime_state : "has state"
    nexora_provider_registry ||--o{ nexora_provider_cost_ledger : "incurs cost"
    nexora_provider_registry ||--o| nexora_provider_capability_cache : "manifests cached"
    nexora_provider_registry ||--o{ nexora_provider_migration_log : "tracks upgrades"
```
