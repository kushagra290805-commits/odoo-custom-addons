# UCP Connector Architecture Forensic Audit

## 1. Executive Summary

A forensic audit of the Universal Connector Platform (UCP) architecture has revealed the root cause behind the observed anomalies (RUNNING state + FAILED health, high manual test latency, and test success despite health failure). 

The core issue stems from an architectural split between **Global Persistent State** and **Worker-Local Ephemeral Execution**. The Odoo model (`nexora.connector`) and UI are unintentionally blending two entirely different execution models: a persistent singleton runtime that tracks process liveness, and an ephemeral isolated runtime that executes one-off tests.

## 2. Canonical Ownership Model

The system correctly attempts to enforce a single source of truth:
*   **Orchestration layer:** `ConnectorRuntime` is the global singleton responsible for the lifecycle and routing.
*   **Dispatch layer:** `ConnectorDispatcher` caches active `sdk_connector` instances (`_active_connectors`) and multiplexes executions over existing transports.
*   **Persistence layer:** `OdooConnectorPersistenceAdapter` is the sole boundary meant to synchronize in-memory state (`lifecycle_state`) back to the Odoo database.

## 3. Forensic Findings: The Anomalies Explained

### 3.1. Manual Test Success vs. Health Check Failure

**The Root Cause:** Manual tests and Health Checks do not use the same execution path or process.

*   **Manual Tests (`McpConnectionTester`):** When a user clicks "Test Connection", the Odoo backend (`action_test_mcp_connection`) spawns a completely fresh, isolated `ConnectorRuntime` (an **ephemeral runtime**). It injects credentials, starts a brand new Node.js/Python subprocess, performs the `tools.list` handshake, records the result, and immediately shuts down the subprocess. This will succeed as long as the configuration is valid at that exact moment.
*   **Health Checks (`_cron_check_health`):** The Odoo cron job calls `probe_health` on the **global** `ConnectorRuntime`. The global runtime routes this to `ConnectorDispatcher.probe_health`, which delegates to the *existing cached `sdk_connector` instance*. If that persistent subprocess crashed, disconnected, or its background asyncio event loop failed after startup, the `transport.list_tools()` call fails. It does not auto-respawn the process for a health check.

### 3.2. Manual Test Latency

The high latency (multi-second delay) on manual tests is the direct result of the ephemeral architecture. Every test incurs the overhead of:
1. Bootstrapping a new Odoo environment bridge.
2. Initializing a new `ConnectorRuntime`.
3. Starting an OS-level subprocess (`stdio` transport) or SSE connection.
4. Spawning a new background thread for the `asyncio` event loop.
5. Performing the MCP JSON-RPC handshake.
6. Tearing down the thread and killing the process.

### 3.3. Lifecycle RUNNING + Health FAILED Paradox

This paradox is explicitly engineered into the `ConnectorRuntime`, but poorly reflected in the Odoo UI.

1. When a health check fails, `ConnectorHealthMonitor` emits a `health.failed` event with a `suggested_state` of `FAILED`.
2. `ConnectorRuntime.handle_event` explicitly intercepts this event and prevents it from reaching the `ConnectorLifecycleManager`.
3. The runtime routes it to `handle_transport_failure()`, which contains the following explicit directive:
   > *"Do NOT transition to FAILED here. A worker-local transport failure must not mutate the global persistent lifecycle state. It remains globally RUNNING/HEALTHY, but locally unavailable."*
4. Because the `lifecycle_manager` is bypassed, the `OdooConnectorPersistenceAdapter` is never told to update the `state` column.
5. However, the Odoo cron job (`_cron_check_health`) explicitly bypasses the lifecycle manager and writes the raw `health.status` directly to the `health_status` column in the database (`record.write({'health_status': 'failed'})`).

This results in the database reading `state='running'` but `health_status='failed'`.

## 4. Credential Injection Mechanism

Credential injection follows a strict, secure path that does not leak into Odoo state:
1. `McpOnboardingService._build_mcp_configuration` requests secrets via `OdooCredentialResolver`.
2. The resolver looks up `nexora.mcp_credential` records matching the connector ID.
3. For `stdio` transports, secrets are dynamically injected directly into the `subprocess.env` dictionary.
4. For `sse` transports, they are mapped to HTTP authentication headers or query parameters.
5. Credentials are never written to the `nexora.mcp_server_config` record or logs.

## 5. Architectural Recommendations

To resolve the inconsistencies without violating the architectural freeze:

1. **Unify Test Execution:** `McpConnectionTester` should optionally route tests through the global `ConnectorRuntime` if the connector is already in a `RUNNING` state, rather than always creating an ephemeral runtime. This would provide an accurate test of the live transport and eliminate latency for active connectors.
2. **UI Clarification:** The Odoo UI must be updated to visually distinguish between "Global Lifecycle Intent" (e.g., "Configured to Run") and "Local Worker Health" (e.g., "Process Crashed"). 
3. **Single-flight Recovery Optimization:** The `ConnectorRuntime` already attempts single-flight recovery (`_attempt_recovery`) when intercepting `health.failed`. If recovery continually fails, there must be an escalation path that eventually downgrades the global lifecycle state to `FAILED`, rather than leaving it in an infinite `RUNNING` zombie state.
