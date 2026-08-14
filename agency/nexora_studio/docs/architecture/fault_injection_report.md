# MCP Fault Injection & Resilience Report

## Overview
This report demonstrates the Universal Connector Platform's resilience to downstream MCP provider failures, validating that isolated connector failures cannot corrupt the central Runtime or Dispatcher state.

## Verified Fault Scenarios
- **Protocol Timeouts:** Long-running tools (e.g. `timeout` sleeping for 100s) are intercepted by the `McpTransport._run_sync` timeout window (60s default). The hanging thread is abandoned, the connection is closed, and the `ConnectorExecutionResult.fail` is bubbled up immediately.
- **Malformed Payloads:** Servers emitting invalid JSON or broken JSON-RPC structures trigger upstream `pydantic` validation exceptions. The invalid stream halts, the Dispatcher evicts the corrupted session from the cache, and a subsequent request triggers a clean reconnect.
- **Abrupt Process Death:** Simulated process exits (`sys.exit(1)`) sever the `stdio` pipe. The resulting `anyio.EndOfStream` exception is caught, the session cache is invalidated, and the connection is cleanly closed without hanging the Runtime loop.
- **Oversized Responses:** Validation tests successfully pushed 5MB continuous JSON payload blobs across the boundary. Memory usage scales proportionally but safely due to the native python JSON parser.
- **Unicode Resilience:** Complete complex UTF-8 encoding (including 4-byte surrogate emojis and null bytes) parses losslessly. 

## Cache Eviction Lifecycle
Failure -> Catch -> `self._active_connectors.pop()` -> Transport Disconnect -> Error Bubbled -> Next Dispatch initiates fresh connection.

## Certification Status
**GO.** The fault boundaries are hermetic. Stale, crashed, or malicious MCP endpoints cannot permanently deny service to the Connector Platform or leak memory cross-session.
