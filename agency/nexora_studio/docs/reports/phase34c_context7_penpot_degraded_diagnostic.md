# Phase 34C: Context7 + Penpot Degraded Health Root-Cause Diagnostic

## 1. What "DEGRADED" Actually Means
The exact canonical mapping in `ConnectorHealthMonitor` and `ConnectorHealth` is based on consecutive failure tracking:
- `DEGRADED_AFTER_FAILURES = 1`
- `FAILED_AFTER_FAILURES = 3`
- `HEALTHY_AFTER_SUCCESSES = 2`

A `degraded` state strictly means the health probe failed **1 or 2 times consecutively**. It has not reached the 3-failure threshold to become `failed`. Once degraded, a connector requires **2 consecutive successful probes** (`HEALTHY_AFTER_SUCCESSES = 2`) to transition back to `healthy`.

## 2 & 3. Context7 & Penpot Inspection Results
**Context7 (`context7_mcp`)**:
- Transport: `stdio`
- Command: `npx.cmd -y --quiet @upstash/context7-mcp`
- Credential: `CONTEXT7_API_KEY` (Present and successfully bound)

**Penpot (`penpot_mcp`)**:
- Transport: `sse`
- Command/Endpoint: `http://localhost:9001/mcp/sse`
- Auth: `query` (`userToken`)
- Credential: `PENPOT_API_KEY` (Present and successfully bound)

**Root Cause of Degradation**:
Both connectors suffered from the **exact same ephemeral startup race condition** identified in Phase 34B. 
During Odoo startup, `ConnectorPlatformBootstrap` loads connectors synchronously with `configuration=None`. If the `_cron_check_health` triggers before `McpStartupReconciliationThread` finishes resolving their configurations, `ConnectorDispatcher.probe_health` attempts to instantiate the connectors using an empty config dict (`{}`). 

For both Context7 and Penpot, the empty config causes `McpTransport` to default to `stdio` with an empty `command=""`. This throws an OS-level exception (`[WinError 87] The parameter is incorrect`) when attempting to spawn the subprocess, resulting in the exact generic error: `"Connector instance could not be created or is not running"`.

## 4. Compare with Healthy Connectors
GitHub and Firecrawl are currently `Healthy` because they happened to complete their 2 consecutive successful health probes (`HEALTHY_AFTER_SUCCESSES`) after the race condition, or they were processed by the health cron *after* their configurations were successfully reconciled.

## 5 & 6. Credentials and Shared vs Connector-Specific
- **Context7**: Credential is PRESENT and resolution succeeds at runtime.
- **Penpot**: Credential is PRESENT and resolution succeeds at runtime.
- **Classification**: This is a **shared generic defect** (the startup race condition). It is NOT a Context7-specific stdio issue, nor a Penpot-specific SSE issue. Credential absence is definitively eliminated as the root cause.

## 7. Runtime Connectivity Status (Actual Health)
Isolated runtime tests bypassing the uninitialized registry state prove that both connectors are fully operational:
- **Context7**: Successfully starts the stdio process, completes the MCP handshake, and returns `Health: True`.
- **Penpot**: Successfully connects to `http://localhost:9001/mcp/sse` with the injected `userToken`, completes the MCP handshake, and returns `Health: True`.

## 8. Degradation: Genuine or Classification Bug?
The degradation is a **classification bug / race condition side-effect**. The connectors themselves are healthy and reachable. The `degraded` status is merely persisting in the UI because the Odoo cron has not yet executed the 2 consecutive successful health probes required by `ConnectorHealthMonitor` to clear the 1 failure caused by the startup race condition.

## 9 & 10. Generic Defect and Proposed Fix
A generic production-code defect exists: The `ConnectorDispatcher._get_or_create_connector` attempts to instantiate SDK connectors even when `connector.configuration` is `None` (passing `{}`), which inevitably crashes the transport layer.

**Minimal Proposed Fix (DO NOT IMPLEMENT YET):**
In `services/connector/runtime/dispatcher.py` -> `_get_or_create_connector`:
```python
        if connector.connector_id not in self._active_connectors:
            # Prevent attempting to initialize an unresolved connector skeleton
            if not connector.configuration:
                _logger.warning(f"Connector {connector.connector_id} has no resolved configuration yet.")
                return None
                
            try:
                config_dict = connector.configuration.get_resolved_values()
```

**DIAGNOSTIC ONLY — NO PRODUCTION CHANGES REQUIRED**
