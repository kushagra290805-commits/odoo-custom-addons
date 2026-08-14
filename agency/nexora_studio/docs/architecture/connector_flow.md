# End-to-End Connector Flow Audit

This audit traces the complete lifecycle of a connector execution from discovery to telemetry.

## Flow Trace

1. **Discovery & Registration**
   - External system creates a `nexora.connector_source`.
   - Sync job discovers `nexora.connector_catalog` entries.
   - User initiates install: creates `ConnectorManifest` and `ConnectorRelease`.
   - System deploys to `ConnectorEnvironment` and records `ConnectorInstallation`.

2. **Platform Boot & Wiring**
   - `ConnectorRegistry` fetches `ConnectorInstallation` via `ConnectorPersistencePort`.
   - `ConnectorRuntime` boots.
   - `ConnectorRuntime` invokes `ConnectorFactory`.
   - `ConnectorFactory` injects `BaseTransport`, `BaseCapabilityProvider`, `BaseAuthenticationProvider` into the `BaseConnector`.
   - `ConnectorRuntime` indexes capabilities in `CapabilityIndex`.

3. **Capability Resolution**
   - `UniversalCapabilityRouter` receives execution request.
   - Router hits `ConnectorExecutionTarget` (EP-004).
   - Target translates to `ConnectorExecutionRequest`.
   - `ConnectorDispatcher` queries `CapabilityIndex` to find `connector_id`.
   - `ConnectorDispatcher` retrieves `BaseConnector` instance from Runtime.

4. **Execution & Telemetry**
   - `BaseConnector` invokes `execute()`.
   - `BaseAuthenticationProvider` ensures valid session context.
   - `BaseCapabilityProvider` delegates to `BaseTransport.send_request()`.
   - Execution yields `ConnectorExecutionResult`.
   - `ConnectorHealthMonitor` intercepts result, updates latency and success counters.
   - `ConnectorEventBus` publishes `health.updated` if status transitions to/from FAILED.

## Validation Result
✅ **PASSED**.
No missing links. The factory architecture effectively bridges the registry state to actionable SDK instances without hardcoded routing.
