# Architecture Validation — Canonical Reference (ADR-0029 + ADR-0030 + ADR-0031 + ADR-0032)

**Date:** July 2026
**Status:** All 34 Assertions Passed — Approved for Phase 15B Code Execution

---

## Summary Table

| Range | ADR | Assertions | Result |
|:---:|:---:|:---:|:---:|
| 1–8 | ADR-0029 | Foundational platform safety | 🟢 8/8 |
| 9–16 | ADR-0030 | Runtime governance & type-safety | 🟢 8/8 |
| 17–26 | ADR-0031 | Service decomposition & orchestration | 🟢 10/10 |
| 27–34 | ADR-0032 | Enterprise infrastructure enhancements | 🟢 8/8 |
| **Total** | | | **🟢 34/34** |

---

## Part 1: ADR-0029 Baseline Assertions (1–8) — All Passed

| # | Assertion | Status |
|:---:|:---|:---:|
| 1 | No duplicated responsibilities across tiers | 🟢 PASSED |
| 2 | No circular dependencies — DAG topology | 🟢 PASSED |
| 3 | No provider-specific abstractions in callers | 🟢 PASSED |
| 4 | No vendor lock-in — SDK isolation in adapters | 🟢 PASSED |
| 5 | No framework-specific assumptions | 🟢 PASSED |
| 6 | No duplicated authentication logic | 🟢 PASSED |
| 7 | No duplicated health monitoring | 🟢 PASSED |
| 8 | No duplicated configuration systems | 🟢 PASSED |

---

## Part 2: ADR-0030 Extension Assertions (9–16) — All Passed

| # | Assertion | Status |
|:---:|:---|:---:|
| 9 | `ProviderCategory(str, Enum)` type-safe routing with backward compat | 🟢 PASSED |
| 10 | Metadata / runtime state in separate SQL tables, zero lock contention | 🟢 PASSED |
| 11 | FSM 15 valid transitions exhaustively defined; busy-lock prevents illegal admin transitions | 🟢 PASSED |
| 12 | Event bus channels independently isolated — subscriber failure does not block other channels | 🟢 PASSED |
| 13 | Dependency graph Kahn's BFS; cycle detection aborts module init | 🟢 PASSED |
| 14 | Sandbox default-deny; elevated permissions explicitly declared and audited | 🟢 PASSED |
| 15 | Unified 5-dimension cost accounting; no provider self-tracks expenditure | 🟢 PASSED |
| 16 | Marketplace manifest channel-neutral (no distribution platform assumption) | 🟢 PASSED |

---

## Part 3: ADR-0031 Refinement Assertions (17–26) — All Passed

| # | Assertion | Status |
|:---:|:---|:---:|
| 17 | `CapabilityResolver` / `ProviderFactory` clean SRP split | 🟢 PASSED |
| 18 | `ProviderDiscovery` covers 4 source types through unified `validate_and_register()` | 🟢 PASSED |
| 19 | `ProviderHealthService` / `ProviderTelemetryService` domain separation | 🟢 PASSED |
| 20 | Feature negotiation via `ProviderFeatureSet.is_satisfied_by()` — sole evaluation path | 🟢 PASSED |
| 21 | Lifecycle hooks are optional no-ops; failures publish to AUDIT without aborting FSM | 🟢 PASSED |
| 22 | Named sandbox profiles have ordered permissions; PRIVILEGED audited; overrides audited | 🟢 PASSED |
| 23 | `ProviderEventBus.publish()` returns in ≤ 1ms; thread-pool delivery; `drain()` available | 🟢 PASSED |
| 24 | `ProviderSession` is SQL-free; `to_execution_context()` produces deterministic frozen snapshot | 🟢 PASSED |
| 25 | Multi-level cache waterfall (L1→L2→L3); consistent write and invalidation propagation | 🟢 PASSED |
| 26 | `ExecutionOrchestrator` is the sole entry point for all provider execution | 🟢 PASSED |

---

## Part 4: ADR-0032 Enterprise Assertions (27–34)

### Assertion 27: Dependency Injection Composition Root
- **Rule:** No service may directly instantiate another service. `ProviderServiceContainer` must be the sole composition root.
- **Verification:**
  - All 20 service registrations are declared in a sealed `post_init_hook` sequence.
  - `ServiceLifetime.SINGLETON` services are wired once at container `build()` time; subsequent `resolve()` calls return the same instance.
  - `ServiceLifetime.SCOPED` (`ProviderSession`) creates one instance per Odoo request via `create_scope()`.
  - `ServiceLifetime.TRANSIENT` (concrete provider adapters) creates a new instance per `resolve()`.
  - Unit tests replace any service via container re-registration before `build()` — zero constructor changes needed.
- **Status:** 🟢 **PASSED (Composition Root Verified)**

### Assertion 28: Compatibility Validation Ownership
- **Rule:** `ProviderDiscovery` must not contain any validation logic. All compatibility checks belong exclusively to `ProviderCompatibilityService`.
- **Verification:**
  - `ProviderDiscovery.validate_and_register()` calls `container.resolve(ProviderCompatibilityService).validate(provider_class)` and registers only if `CompatibilityReport.is_compatible = True`.
  - `ProviderCompatibilityService` exposes 7 discrete validation methods (platform, Odoo, Python, manifest schema, dependency, API version, future migration).
  - All `CompatibilityReport` results are published to `AUDIT` channel regardless of outcome.
  - There is zero compatibility logic in `ProviderDiscovery`, `ProviderRegistry`, or `ProviderFactory`.
- **Status:** 🟢 **PASSED (SRP Ownership Verified)**

### Assertion 29: Distributed Lock Correctness for Multi-Worker
- **Rule:** `ProviderStateMachine` must not implement any locking internally. Lock acquisition must be atomic under concurrent multi-worker Odoo deployment.
- **Verification:**
  - `LockService.acquire()` with `LockBackend.POSTGRESQL` uses `SELECT pg_try_advisory_lock($1)` — atomic at the PostgreSQL level, immune to Odoo transaction isolation issues.
  - `LockService.acquire()` with `LockBackend.REDIS` uses `SET key holder NX PX ttl_ms` with Lua CAS unlock — atomic per Redis single-threaded command queue.
  - `ProviderStateMachine` delegates all locking to `container.resolve(LockService)`.
  - SQL `active_locks` column is retained as an observability counter (read-only to FSM); the column is no longer the concurrency enforcement mechanism.
  - `LockAcquisitionResult.acquired = False` after `timeout_ms` → `ProviderLockTimeoutError` raised; orchestrator treats this as `ProviderRateLimitError`.
- **Status:** 🟢 **PASSED (Multi-Worker Atomic Locking Verified)**

### Assertion 30: Migration Safety & Rollback Recoverability
- **Rule:** Provider upgrades must be transactional — on any failure, the provider must be recoverable to its pre-upgrade state. Concurrent migration attempts on the same provider must be impossible.
- **Verification:**
  - `ProviderMigrationService.execute_upgrade()` acquires `nexora:provider:{id}:migration_lock` before beginning; concurrent attempts block and fail with `ProviderLockTimeoutError`.
  - FSM transitions through `DISABLED` before `migrate()` is called — the provider is traffic-isolated during migration.
  - On any exception in steps 4–8 of the migration sequence, `rollback()` is called, previous registration is restored, and `MigrationRecord(status=ROLLED_BACK)` is persisted.
  - `validate_upgrade()` returning `False` aborts migration before any state change, leaving the provider in `READY`.
  - Full audit trail in `nexora.provider.migration_log` and `AUDIT` event channel.
- **Status:** 🟢 **PASSED (Transactional Migration Verified)**

### Assertion 31: Metrics / Telemetry Isolation
- **Rule:** `ProviderMetricsService` must be operationally independent from `ProviderTelemetryService`. A failure in metrics aggregation must never affect telemetry event delivery, and vice versa.
- **Verification:**
  - `ProviderMetricsService` and `ProviderTelemetryService` are separate services registered independently in the DI container with separate `METRICS` and `TELEMETRY`/`AUDIT`/`WEBSOCKET` subscriber lists on `ProviderEventBus`.
  - Both services subscribe to `ProviderEventBus` channels independently; subscriber isolation (Assertion 23) guarantees a crash in one subscriber does not affect the other.
  - `ProviderMetricsService` publishes aggregated snapshots to `METRICS` channel at 60s intervals; `ProviderTelemetryService` publishes individual span events to `TELEMETRY` channel per execution — these are distinct event types.
- **Status:** 🟢 **PASSED (Metrics / Telemetry Isolation Verified)**

### Assertion 32: Capability Cache Correctness
- **Rule:** `CapabilityCache` must serve capability manifests without live provider contact under normal operation. Invalidation must be triggered on all upgrade, re-enable, and removal events.
- **Verification:**
  - `CapabilityResolver` calls `CapabilityCache.get_or_refresh()` exclusively — never `provider.discover_capabilities()` directly.
  - `get_or_refresh()` returns cached manifests if present and non-expired; calls `refresh()` → `provider.discover_capabilities()` only on cold cache or expiry.
  - Invalidation is triggered by: FSM `transition(CONFIGURED)`, `MigrationService.execute_upgrade()`, and `Registry.unregister_provider()` — covering all upgrade, re-enable, and removal paths.
  - `CapabilityCache` and `ProviderCache` (execution results) are independent services with separate backing stores.
- **Status:** 🟢 **PASSED (Cache Correctness Verified)**

### Assertion 33: Concurrency Enforcement Completeness
- **Rule:** `ExecutionOrchestrator` must enforce all three `ConcurrencyPolicy` limits (`max_parallel_requests`, `max_queue_size`, `max_concurrent_streams`) before dispatching any execution request.
- **Verification:**
  - Before each `execute()` dispatch, the orchestrator reads `provider.metadata.concurrency_policy.max_parallel_requests` and acquires a per-provider semaphore via `LockService`.
  - If `active_executions >= max_parallel_requests` and queue is available, the request is enqueued with `queue_timeout_ms` expiry.
  - If queue is full and `reject_on_queue_full = True`, `ProviderRateLimitError` is raised immediately without any provider contact.
  - `execute_streaming()` tracks `active_streams` separately against `max_concurrent_streams`.
  - `ProviderMetricsService.record_request()` is called with accurate concurrency data for utilization reporting.
- **Status:** 🟢 **PASSED (Concurrency Enforcement Complete)**

### Assertion 34: Execution Policy Correctness & Separation of Concerns
- **Rule:** `CapabilityResolver` must use `ExecutionPolicy` as the sole ranking mechanism. `priority_weight` must remain as one signal, not the sole determinant.
- **Verification:**
  - `CapabilityResolver.resolve(policy=None)` applies `ExecutionPolicyType.BALANCED` by default — 33% latency (from `MetricsService.get_snapshot()`), 33% cost (from `ProviderMetadata` cost-rate attribute), 34% quality (`success_rate` + `priority_weight`).
  - `ExecutionPolicyType.PREFERRED` respects `preferred_provider_ids` allowlist order regardless of metrics signals.
  - `ExecutionPolicyType.CUSTOM` delegates to `custom_ranker` callable — allows caller-defined multi-signal ranking without modifying provider metadata.
  - `ExecutionPolicy.fallback_policy` is applied automatically if primary policy yields zero candidates, ensuring no silent empty-result failures.
  - System default policy is configurable via `agency.default_execution_policy` without code deployment.
- **Status:** 🟢 **PASSED (Policy Correctness & Separation Verified)**

---

## Part 5: Cross-ADR Compatibility Matrix (Complete)

| ADR | Contract | ADR-0032 Impact | Breaking? |
|:---|:---|:---|:---:|
| 0029 | `BaseProvider` 10 abstract methods | 4 migration hooks added as no-ops | **No** |
| 0029 | `ProviderFactory.resolve_provider_for_capability()` | Thin delegation to `CapabilityResolver`; signature unchanged | **No** |
| 0030 | `ProviderMetadata` all fields | `concurrency_policy` added with safe `ConcurrencyPolicy()` default | **No** |
| 0030 | `ProviderSandboxPolicy` 7 flag fields | All retained; no ADR-0032 changes | **No** |
| 0031 | `CapabilityResolver.resolve()` 4 params | `policy=None` optional 5th param added | **No** |
| 0031 | `ProviderDiscovery` 4 methods | Compatibility logic extracted; `validate_and_register()` now calls `CompatibilityService` | **No** |
| 0031 | `ProviderStateMachine` SQL integer locking | Delegates to `LockService`; SQL col retained as observability counter | **No** |
| 0031 | All REST endpoints | 6 new additive endpoints; zero schema changes to existing | **No** |
| All | All Odoo ORM models | 3 new additive models; zero changes to existing tables | **No** |
