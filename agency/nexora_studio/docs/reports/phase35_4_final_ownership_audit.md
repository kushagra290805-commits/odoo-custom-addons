# Final Ownership Audit (Pre-Implementation)

Based on direct inspection of the CURRENT codebase (`nexora_connector.py`, `mcp_onboarding_service.py`, `dispatcher.py`, `capability_discovery.py`, `health_monitor.py`):

| Responsibility | Current Codebase Owner | Planned Changes for Phase 35.4 |
|---|---|---|
| **Registration / Odoo Config Mapping** | `McpOnboardingService.register_connector()` | Remains. Will delegate transport init to Dispatcher. |
| **Transport Creation** | `ConnectorDispatcher._get_or_create_connector()` | Will be exposed via canonical `initialize_and_verify()`. |
| **MCP Handshake** | `McpOnboardingService.register_connector()` (manual call to `_execute_on_connector('tools.list')`) | Moves to `ConnectorDispatcher.initialize_and_verify()`. |
| **Capability Discovery** | `McpCapabilityDiscoveryService.discover()` (invoked via `action_discover_mcp_capabilities`) | Will be invoked synchronously by `register_connector` / `recovery`. |
| **Failure Classification** | None (does not exist in `domain/models.py`) | Introducing `ConnectorFailureClass` (Recoverable vs Non-recoverable). |
| **Failure Detection** | `ConnectorDispatcher.dispatch()`, `ConnectorHealthMonitor` | Unchanged. |
| **Recovery** | None | Introducing `ConnectorRuntime.handle_transport_failure()` and `_attempt_recovery()` with `threading.Timer`. |
| **Capability Index** | `ConnectorRuntime.capability_index` | Will invalidate on transport failure. |
| **Persistence Uniqueness** | `_sql_constraints` in `nexora_connector.py` | Verified physical database constraint (`nexora_connector_id_uniq`). |

**Conclusion:** No duplicate Phase 35.4 logic exists. I am cleared to proceed with implementing the canonical transport initialization, failure classification, and `ConnectorRuntime` recovery mechanisms, using the existing components without introducing new orchestrators.
