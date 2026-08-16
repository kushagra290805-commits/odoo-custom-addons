# Phase 35.4 Final Pre-Flight Architecture Verification

## Observed Call Paths (Current Implementation)

This audit is based on a strict static analysis of the Phase 35.4 production code without applying any modifications.

### 1. Recovery Entry Point
- **Method:** `ConnectorRuntime._attempt_recovery(connector_id)`
- **Trigger:** Invoked asynchronously by a `threading.Timer` spawned inside `handle_transport_failure`.
- **Behavior:** Executes a clean slate shutdown via `dispatcher.shutdown_connector(connector_id)`, then synchronously delegates to `dispatcher.initialize_and_verify`. If successful, it rebuilds capabilities and transitions the connector back to `RUNNING`.

### 2. Failure Detection Entry Points
- **Execution Failures:** `ConnectorDispatcher.dispatch(request)` intercepts underlying transport or payload failures, encapsulates them into a `ConnectorExecutionResult.FAILURE`, and returns.
- **Runtime Interception:** `ConnectorRuntime.dispatch` checks the returned result. If it indicates a `TRANSPORT_ERROR`, `CONNECTOR_EXECUTION_ERROR`, or `TIMEOUT`, it extracts the `connector_id` and forwards the signal to `handle_transport_failure`.
- **Initialization Failures:** Handled inside `initialize_and_verify`, returning a `FAILURE` status.

### 3. Capability Invalidation Path
- **Method:** `CapabilityIndex.remove(connector_id)`
- **Triggered By:** Immediate execution within `handle_transport_failure` *before* the recovery debounce timer is even scheduled.
- **Result:** The connector is instantly un-routable across the platform, preventing subsequent capability dispatch storms during the backoff window.

### 4. Recovery Scheduling Path
- **Method:** `ConnectorRuntime.handle_transport_failure`
- **Mechanism:** Acquires `_recovery_locks[connector_id]`. If `_recovery_state` is not `IN_PROGRESS`, it transitions it to `IN_PROGRESS` and launches a `threading.Timer(2.0, self._attempt_recovery, args=[connector_id])`.
- **Constraints:** Ensures exact single-flight semantic per worker process.

### 5. Initialization Path (Canonical Primitive)
- **Method:** `ConnectorDispatcher.initialize_and_verify(connector, context)`
- **Responsibility:** Bootstraps the subprocess/SSE transport, creates the SDK session, performs the MCP handshake (`tools.list`), and enforces timeout constraints.
- **Usage:** Shared identically by `McpOnboardingService.register_connector` and `ConnectorRuntime._attempt_recovery`.

### 6. Health Failure Path
- **Monitor:** `ConnectorHealthMonitor` periodically probes health and records successes/failures.
- **Event Bus:** Upon reaching the failure threshold, it emits `health.failed`.
- **Event Handler:** `ConnectorRuntime.handle_event` routes this to `_on_health_change(..., ConnectorLifecycleState.FAILED)`.
- **Observation / Known Risk (Phase J Focus):** The current implementation of `_on_health_change` transitions the state to `FAILED` and rebuilds the global capability index, effectively dropping the connector's capabilities. **However**, it does *not* invoke `handle_transport_failure` or schedule `_attempt_recovery`.
- **Expected Outcome:** Phase J of the audit is expected to uncover this empirically as a defect. We will not fix it beforehand, honoring the adversarial isolation rule.

### 7. Shutdown Path
- **Method:** `ConnectorRuntime.shutdown()`
- **Safety Measures:** Sets `self._is_shutting_down = True` (blocking any new failures from initiating recovery), iterates over `self._recovery_timers`, and executes `.cancel()` on all pending delayed recoveries before shutting down the active dispatcher sessions.
