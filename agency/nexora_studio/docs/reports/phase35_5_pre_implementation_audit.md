# Phase 35.5 Pre-Implementation Audit

## 1. Defect P0: Global Lifecycle Mutation on Local Failure

### Trace: `ConnectorRuntime.handle_transport_failure()`
When a transport failure occurs during execution, the following path is invoked:
1. `ConnectorRuntime.handle_transport_failure(connector_id, ...)` is called.
2. It removes the capabilities: `self.capability_index.remove(connector_id)`.
3. It performs a state transition: `self.lifecycle_manager.transition(connector, ConnectorLifecycleState.FAILED, reason=error_message)`.
4. It sets up the recovery timer.
5. If recovery succeeds, `_attempt_recovery` sets the state back to `ConnectorLifecycleState.RUNNING`.

### Trace: `lifecycle_manager.transition()` & Persistence
`ConnectorLifecycleManager.transition()` updates the domain model's `lifecycle_state` attribute.
**Finding:** Currently, this state mutation remains largely in-memory within the `ConnectorRegistry` because there is no active synchronous database adapter polling it on every local transition (the transition logic does not currently force `OdooConnectorPersistenceAdapter.save_connector`). However, because the Domain Model itself changes to `FAILED`, any reconciliation loops or UI fetches querying the registry will reflect `FAILED`. In a true multi-worker environment, this means the local memory of Worker A considers the connector FAILED, while Worker B considers it RUNNING. If Worker A's state is ever persisted or synced, it will overwrite the global intent.

**Required Fix:**
`handle_transport_failure` must **not** transition the `lifecycle_state` to `FAILED` at all. It should only invalidate the `capability_index` and use its internal `_recovery_state` map to track the local recovery process. The domain state must remain `RUNNING` or `HEALTHY` to reflect the global operator intent.

## 2. Defect P1: HealthMonitor Bypass of Recovery

### Trace: `ConnectorHealthMonitor` emission
1. `ConnectorHealthMonitor` probes the connection. If failures exceed the threshold, it emits a `health.failed` event.
2. `ConnectorRuntime.handle_event()` intercepts `health.failed` and routes it to `_on_health_change(connector_id, ConnectorLifecycleState.FAILED)`.
3. `_on_health_change()` calls `self.lifecycle_manager.transition(connector, FAILED)` and rebuilds the capability index (dropping the capabilities).
4. **Finding:** The execution stops here. There is no call to `handle_transport_failure()` or `_attempt_recovery()`. The connector is permanently disabled until an operator intervenes.

**Required Fix:**
`_on_health_change` (or `handle_event` directly) should intercept `health.failed`, classify it as a recoverable transport failure, and route it to `handle_transport_failure()` exactly like execution errors. It should not transition the lifecycle to FAILED.
