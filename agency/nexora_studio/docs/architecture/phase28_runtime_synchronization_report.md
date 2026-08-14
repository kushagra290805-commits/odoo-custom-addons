# Phase 28 — Runtime Synchronization Report

## Mechanism
The `ConnectorRuntimeSynchronizer` listens to ORM lifecycle events (`write`, `unlink`) via method overrides on `nexora.connector`, `nexora.mcp_server_config`, and `nexora.mcp_credential`.

## Synchronization Events
1. **Connector state change (running)**: Triggers `McpOnboardingService.register_connector()`.
2. **Connector state change (disabled/failed)**: Triggers `McpOnboardingService.deregister_connector()`.
3. **Configuration modification**: Deregisters the existing connector (if running), then re-registers it to apply the new config.
4. **Credential rotation**: Deregisters the existing connector (if running) and evicts the session cache, then re-registers it with the new decrypted credential values.

## Compliance
This process ensures the active `ConnectorRuntime` registry is always perfectly synchronized with the Odoo configuration without polling, and without mutating runtime internals manually.
