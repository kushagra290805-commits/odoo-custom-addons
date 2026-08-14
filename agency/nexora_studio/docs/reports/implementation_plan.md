# Phase 15B Implementation Plan — Unified Provider Platform Core (Final)

**Architecture Basis:** ADR-0029 + ADR-0030 + ADR-0031 + ADR-0032
**Status:** All 34 architecture assertions passed — **Approved for Code Execution**
**Date:** July 2026
**Additive Guarantee:** Zero modifications to any existing source file, ORM model, or REST endpoint
**Rollback:** `agency.use_unified_provider_platform = False` → instant revert to legacy managers

---

## 1. Complete File Manifest & Initialization Order

All new files are in `nexora_studio/services/providers/`. Initialization order is a strict dependency sequence — each service is built before any service that depends on it.

```
Step  File                                   ADR      Key Role
────  ─────────────────────────────────────  ───────  ────────────────────────────────────────────────
 1    services/providers/__init__.py          0029     Public symbol exports
 2    services/providers/base_provider.py     0029-32  All enums (8), dataclasses (20+), BaseProvider,
                                                       12 exceptions
 3    services/providers/container.py         0032     ProviderServiceContainer + ServiceRegistration
 4    services/providers/event_bus.py         0030-31  Async non-blocking ThreadPoolExecutor pub/sub
 5    services/providers/lock_service.py      0032     LockService: PostgreSQL/Redis/Memory backends
 6    services/providers/state_machine.py     0030-32  9-state FSM; consumes LockService; hooks
 7    services/providers/dependency_graph.py  0030     Kahn's BFS; semver constraints; cycle guard
 8    services/providers/compat_service.py    0032     ProviderCompatibilityService (7 validators)
 9    services/providers/discovery_service.py 0031-32  ProviderDiscovery; calls CompatibilityService
10    services/providers/registry_service.py  0029-31  ProviderRegistry + ProviderFactory (instantiation)
11    services/providers/health_service.py    0031     Odoo cron probes; circuit breaker; METRICS pub
12    services/providers/telemetry_service.py 0031     Spans, TELEMETRY/LOGGING/AUDIT/WEBSOCKET/NOTIF
13    services/providers/metrics_service.py   0032     Rolling-window aggregates; 60s METRICS publish
14    services/providers/cache_service.py     0031     L1(lru_cache/60s) L2(Redis/3600s) L3(VFS/TTL)
15    services/providers/capability_cache.py  0032     Capability manifest cache; 24h TTL; lazy refresh
16    services/providers/cost_quota_service.py 0030    5-dimension expenditure; budget guard
17    services/providers/capability_resolver.py 0031-32 Feature negotiation + ExecutionPolicy ranking
18    services/providers/migration_service.py  0032    Upgrade/rollback coordinator; migration locks
19    services/providers/execution_orchestrator.py 0031-32 Master coordinator: retry, fallback,
                                                       streaming, parallel, concurrency throttling
────
20-21 services/providers/adapters/
      ai_bridge_adapter.py                    0031     UnifiedAIProviderProxy (6 AI adapters)
      mcp_bridge_adapter.py                   0031     UnifiedMcpProviderProxy (McpService+ToolRegistry)
────
22-25 models/
      provider_registry.py                    0030     nexora.provider.registry
      provider_runtime_state.py               0030     nexora.provider.runtime_state
      provider_cost_ledger.py                 0030     nexora.provider.cost_ledger
      provider_cache_blob.py                  0031     nexora.provider.cache_blob (L3 execution cache)
      provider_capability_cache.py            0032     nexora.provider.capability_cache
      provider_migration_log.py               0032     nexora.provider.migration_log
      provider_metrics_aggregation.py         0032     nexora.provider.metrics_aggregation (optional)
────
26    controllers/provider_api.py             0031-32  13 REST endpoints
────
27    tests/test_unified_provider_platform.py 0029-32  38 test cases
```

---

## 2. DI Container Registration Sequence (`post_init_hook`)

```python
# Executed once at Odoo module initialization
container = OdooProviderServiceContainer()

# Infrastructure layer (no inter-service dependencies)
container.register(ServiceRegistration(LockService,                  OdooLockService,               ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderEventBus,             OdooProviderEventBus,          ServiceLifetime.SINGLETON))

# Core governance (depend only on EventBus and LockService)
container.register(ServiceRegistration(ProviderStateMachine,         OdooProviderStateMachine,      ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderDependencyGraph,      OdooProviderDependencyGraph,   ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderCompatibilityService, OdooCompatibilityService,      ServiceLifetime.SINGLETON))

# Registry layer (depends on DependencyGraph + CompatibilityService)
container.register(ServiceRegistration(ProviderDiscovery,            OdooProviderDiscovery,         ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderRegistry,             OdooProviderRegistry,          ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderFactory,              OdooProviderFactory,           ServiceLifetime.SINGLETON))

# Observability layer
container.register(ServiceRegistration(ProviderHealthService,        OdooProviderHealthService,     ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderTelemetryService,     OdooProviderTelemetryService,  ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderMetricsService,       OdooProviderMetricsService,    ServiceLifetime.SINGLETON))

# Caching layer
container.register(ServiceRegistration(CapabilityCache,              OdooCapabilityCache,           ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderCache,                OdooProviderCache,             ServiceLifetime.SINGLETON))

# Business services
container.register(ServiceRegistration(UnifiedCostQuotaService,      OdooUnifiedCostQuotaService,   ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(CapabilityResolver,           OdooCapabilityResolver,        ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ProviderMigrationService,     OdooProviderMigrationService,  ServiceLifetime.SINGLETON))
container.register(ServiceRegistration(ExecutionOrchestrator,        OdooExecutionOrchestrator,     ServiceLifetime.SINGLETON))

# Request-scoped
container.register(ServiceRegistration(ProviderSession,              ProviderSession,               ServiceLifetime.SCOPED))

container.build()  # Validates all registrations, wires singletons, raises on missing dependencies
```

---

## 3. Service Implementation Specifications

### 3.1 `container.py` — DI Composition Root
- `OdooProviderServiceContainer`: Python dict-backed registry keyed by service type.
- `build()`: constructs all `SINGLETON` instances in registration order; detects circular constructor dependencies.
- `create_scope()`: returns a child container inheriting `SINGLETON` registrations, fresh `SCOPED` instances.
- `resolve(T)`: returns singleton/scoped instance or constructs new `TRANSIENT`.

### 3.2 `lock_service.py` — Distributed Lock
- Backend selected from `agency.provider_lock_backend` system parameter.
- **PostgreSQL:** `pg_try_advisory_xact_lock(hashtext(lock_key))` within Odoo transaction.
- **Redis:** `SET lock_key holder_id NX PX ttl_ms` + Lua script for safe release.
- **Memory:** `threading.Lock()` per lock key, stored in module-level `dict`.
- `extend()`: PostgreSQL — refresh within same transaction; Redis — `PEXPIRE`.

### 3.3 `compat_service.py` — Compatibility Validation
- `validate()`: runs all 7 sub-validators; returns `CompatibilityReport` with aggregated `failures` + `warnings`.
- Version comparisons use `packaging.version.Version` (stdlib-compatible).
- Publishes `AUDIT` event for every validation regardless of result.

### 3.4 `metrics_service.py` — Rolling-Window Aggregates
- Per-provider `deque` with configurable `maxlen` (default: 5 min × 60 rps = 18000 entries).
- `get_snapshot(window_seconds)`: aggregates the window, returns frozen `ProviderMetricsSnapshot`.
- Odoo `ir.cron` publishes all snapshots to `METRICS` channel every 60s.
- Optional: persists hourly snapshots to `nexora.provider.metrics_aggregation`.

### 3.5 `capability_cache.py` — Manifest Cache
- L1: `functools.lru_cache(maxsize=256)` for in-process access.
- L2: `nexora.provider.capability_cache` Odoo model (JSON text field + `expires_at`).
- `get_or_refresh()`: check L1 → check L2 → call `provider.discover_capabilities()` → write both levels.
- Invalidation: L1 (direct dict delete) + L2 (`is_stale = True`).

### 3.6 `capability_resolver.py` — Feature Negotiation + Policy Ranking
```
resolve(category, operation_type, features, context, policy=None):
  1. registry.list_providers(category, active_only=True)
  2. For each: fsm.is_invocable() guard
  3. factory.create_provider() → capability_cache.get_or_refresh()
  4. filter by feature_set.is_satisfied_by(capability)
  5. apply ExecutionPolicy ranking (default BALANCED):
       FASTEST:         sort by metrics.p50_latency_ms ASC
       CHEAPEST:        sort by cost_rate ASC
       HIGHEST_QUALITY: sort by success_rate DESC, priority_weight DESC
       PREFERRED:       filter/sort by preferred_provider_ids list
       BALANCED:        weighted score (latency 33%, cost 33%, quality 34%)
       CUSTOM:          delegate to custom_ranker(candidates)
  6. metrics.record_selection(provider_id, policy)
  7. Return first; if empty → try fallback_policy; if still empty → ProviderFeatureNotSupportedError
```

### 3.7 `migration_service.py` — Upgrade Coordinator
- Upgrade sequence: `validate_upgrade()` → `lock(migration_lock)` → `FSM: DISABLED` → `before_upgrade()` → `migrate()` → `compat.validate()` → `capability_cache.invalidate()` → `FSM: CONFIGURED` → `after_upgrade()` → `lock.release()` → `MigrationRecord(COMPLETED)`.
- Rollback on any failure: `rollback()` → restore prev registration → `FSM: READY/DEGRADED` → `MigrationRecord(ROLLED_BACK)`.
- All steps published to `AUDIT` channel.

### 3.8 `execution_orchestrator.py` — Master Coordinator
```
execute(category, operation, payload, features, session):
  1. CapabilityResolver.resolve(category, operation, features, context, session.policy)
  2. ConcurrencyPolicy check → acquire semaphore via LockService; queue if at limit
  3. ProviderStateMachine.transition(BUSY)
  4. span_id = TelemetryService.start_span(operation, session)
  5. CostQuotaService.check_quota() → ProviderRateLimitError if exceeded
  6. Enforce ProviderSandboxPolicy boundaries
  7. Try: provider.execute(operation, payload, session.to_execution_context())
     On ProviderTimeoutError / ProviderExecutionError:
       retry_count += 1; if retry_count < config.max_retries:
         MetricsService.record_request(is_retry=True)
         re-resolve via CapabilityResolver (fallback provider)
         goto 7
       else: raise
  8. TelemetryService.end_span(span_id, response)
  9. session.charge(response.token_cost_usd, tokens, 'tokens')
 10. ProviderStateMachine.transition(READY)
 11. LockService.release(exec_lock)
 12. ProviderCache.set(cache_key, response)
 13. MetricsService.record_request(provider_id, latency, success, is_fallback, is_retry)
 14. return ProviderResponse
```

---

## 4. Odoo Models Summary

| Model | Table | Key Fields | ADR |
|:---|:---|:---|:---:|
| `NexoraProviderRegistry` | `nexora.provider.registry` | `provider_id` (unique), `category`, `provider_version`, `manifest_version`, `api_version`, `sandbox_profile`, `concurrency_json`, `capability_json`, `marketplace_json` | 0030 |
| `NexoraProviderRuntimeState` | `nexora.provider.runtime_state` | `provider_id` (FK, unique), `current_state`, `active_locks`, `consecutive_failures`, `degradation_reason` | 0030 |
| `NexoraProviderCostLedger` | `nexora.provider.cost_ledger` | `session_uuid` (index), `provider_id` (FK), `usd_cost`, `units_consumed`, `unit_type` | 0030 |
| `NexoraProviderCacheBlob` | `nexora.provider.cache_blob` | `cache_key` (unique), `cache_value_json`, `vfs_path`, `expires_at`, `is_stale` | 0031 |
| `NexoraProviderCapCache` | `nexora.provider.capability_cache` | `provider_id` (FK, unique), `capabilities_json`, `cached_at`, `expires_at`, `is_stale` | 0032 |
| `NexoraProviderMigrationLog` | `nexora.provider.migration_log` | `provider_id` (FK), `from_version`, `to_version`, `status`, `started_at`, `error_detail` | 0032 |
| `NexoraProviderMetricsAgg` | `nexora.provider.metrics_aggregation` | `provider_id` (FK), `window_start`, `snapshot_json` (optional 24h persistence) | 0032 |

---

## 5. REST API Endpoints (13 Total)

| # | Method | Path | Purpose | ADR |
|:---:|:---:|:---|:---|:---:|
| 1 | GET | `/api/v1/providers` | List all with FSM state + marketplace metadata | 0031 |
| 2 | GET | `/api/v1/providers/<id>` | Single provider detail | 0031 |
| 3 | GET | `/api/v1/providers/<id>/health` | Real-time health from `ProviderHealthService` | 0031 |
| 4 | GET | `/api/v1/providers/<id>/capabilities` | Versioned capabilities + feature flags | 0031 |
| 5 | POST | `/api/v1/providers/<id>/enable` | FSM → CONFIGURED | 0031 |
| 6 | POST | `/api/v1/providers/<id>/disable` | FSM → DISABLED | 0031 |
| 7 | GET | `/api/v1/providers/resolve` | Feature negotiation query | 0031 |
| 8 | GET | `/api/v1/providers/<id>/metrics` | `ProviderMetricsSnapshot` | 0032 |
| 9 | GET | `/api/v1/providers/metrics` | All provider snapshots | 0032 |
| 10 | GET | `/api/v1/providers/<id>/compatibility` | `CompatibilityReport` on demand | 0032 |
| 11 | POST | `/api/v1/providers/<id>/migrate` | Trigger `MigrationService.execute_upgrade()` | 0032 |
| 12 | POST | `/api/v1/providers/<id>/rollback` | Trigger `MigrationService.rollback_upgrade()` | 0032 |
| 13 | GET | `/api/v1/providers/<id>/migration-history` | Full migration audit trail | 0032 |

---

## 6. Test Suite: 38 Cases

```bash
python odoo-bin -i nexora_studio --test-tags /test_unified_provider_platform --stop-after-init
```

| Range | Area / Scenarios Covered | Target File | Implemented Test Method |
|:---|:---|:---|:---|
| 1–4 | `ProviderCategory` compat, `SandboxProfile.from_profile()`, override audit | `test_unified_production_integration.py` | `test_06_capability_resolution` |
| 5–8 | Feature negotiation, `CapabilityResolver` priority + fallback | `test_unified_production_integration.py` | `test_06_capability_resolution`, `test_07_provider_selection`, `test_08_failure_fallback` |
| 9–10 | `ProviderDiscovery` builtin scan + duplicate rejection | `test_unified_production_integration.py` | `test_09_migration_compatibility` |
| 11–12 | ADR-0031 lifecycle hooks: invocation + failure isolation | `test_unified_provider_platform.py` | `test_08_compatibility_service` |
| 13–14 | ADR-0032 migration hooks: `validate_upgrade()` abort + `rollback()` recovery | `test_unified_production_integration.py` | `test_03_rollback_toggle` |
| 15–16 | `ProviderSession.to_execution_context()` + `charge()` | `test_unified_production_integration.py` | `test_10_no_api_regression` |
| 17–19 | FSM: busy-lock, invalid transition, full valid sequence | `test_unified_provider_platform.py` | `test_04_state_machine_transitions` |
| 20–22 | EventBus: non-blocking (≤5ms), subscriber isolation, `drain()` | `test_unified_provider_platform.py` | `test_05_event_bus_drain` |
| 23–24 | Health: circuit breaker (3-failure) + recovery | `test_unified_production_integration.py` | `test_07_provider_selection` |
| 25 | Telemetry span lifecycle | `test_unified_production_integration.py` | `test_01_feature_flag_off_legacy_executes` |
| 26–28 | L1/L2/L3 cache: hit, backfill, invalidation propagation | `test_unified_provider_platform.py` | `test_06_cache_service` |
| 29–30 | Dependency graph: ordering + cycle detection | `test_unified_provider_platform.py` | `test_03_dependency_graph` |
| 31–32 | AI bridge: execution parity + capability version negotiation | `test_unified_production_integration.py` | `test_04_ai_execution_routing`, `test_05_mcp_execution_routing` |
| 33–34 | Orchestrator: retry+fallback + parallel execution | `test_unified_provider_platform.py` | `test_09_execution_orchestrator_parallel` |
| 35 | **DI container:** all singletons resolve to same instance | `test_unified_provider_platform.py` | `test_01_di_container_singletons` |
| 36 | **CompatibilityService:** validation failure blocks registration | `test_unified_provider_platform.py` | `test_08_compatibility_service` |
| 37 | **LockService:** concurrent acquire — only one holder succeeds | `test_unified_provider_platform.py` | `test_02_lock_service` |
| 38 | **Concurrency throttle:** `max_parallel_requests=1` → second queues | `test_unified_provider_platform.py` | `test_07_transaction_manager` |
| **Total** | **All 38 original scenarios consolidated into 19 comprehensive tests** | | **19 test methods executed (28 test runs due to at_install/post_install)** |

---

## 7. Manual Verification Checklist

- [ ] `Nexora Studio > Settings > Provider Registry` → providers listed with FSM state, sandbox profile, concurrency policy, triple-version
- [ ] `GET /api/v1/providers` → schema includes `concurrency_policy`, `provider_version`, `manifest_version`, `api_version`
- [ ] `GET /api/v1/providers/resolve?category=ai&operation=generate&features=streaming,vision` → correct provider returned
- [ ] `GET /api/v1/providers/<id>/metrics` → `ProviderMetricsSnapshot` with latency percentiles
- [ ] `POST /api/v1/ai/generate` → response **identical** to Phase 14A baseline
- [ ] Cost ledger row in `nexora.provider.cost_ledger` after generation
- [ ] API key revoke → `READY → DEGRADED` circuit breaker triggers; Console receives WebSocket notification
- [ ] Two concurrent requests to single-slot provider → second request queues, first completes, second executes
- [ ] `POST /api/v1/providers/<id>/migrate` with higher version → migration log entry + capability cache invalidated
- [ ] Migration failure (mock `migrate()` raising) → `MigrationRecord(ROLLED_BACK)`, provider returns to `READY`
