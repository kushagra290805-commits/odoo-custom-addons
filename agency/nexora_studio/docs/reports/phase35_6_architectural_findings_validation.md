# Phase 35.6B: Architectural Findings Validation Report

## Executive Summary
This report validates the critical findings from the Phase 35.6 Architecture Audit. The audit identified suspected parallel MCP runtimes, duplicate ownership, and an `stdio` transport hang during real execution. 

Through strict tracing and execution testing (without modifying production code), we have confirmed that a **True Parallel Runtime exists**. The Generation Engine continues to execute tools against a legacy runtime architecture while the Universal Connector Platform (UCP) manages the lifecycle and configuration. 

**Verdict:** NO-GO for GoSOM Connector Expansion until architectural unification is complete.

---

## 1. Proven Parallel Execution (Findings A, B & C)

### A. Executability & B. Reachability
The legacy `services/runtime/mcp/` subsystem is not just dead code—it is actively instantiated and executed in production.
- **Entry Point:** `models/platform_service.py` (`nexora_studio.platform`) instantiates `McpRuntimeAdapter` and registers it.
- **Reachability:** The core Generation Providers (`models/github_provider.py`, `models/context7_provider.py`, `models/tavily_provider.py`) all explicitly request this adapter:
  ```python
  adapter = runtime.get_runtime('mcp_runtime')
  future = asyncio.run_coroutine_threadsafe(
      adapter.router.execute_capability(mcp_tool, request.payload), 
      adapter._loop
  )
  ```
- **Conclusion:** AI generation directly relies on the legacy MCP runtime, bypassing the UCP's `ConnectorDispatcher` for actual tool execution.

### C. Ownership Duplication
Two independent state machines and registries are running concurrently in memory:
1. **Legacy Stack:** `McpRuntimeManager` -> `McpServerRegistry` -> `McpClient` -> `McpCapabilityCatalog`
2. **UCP Stack:** `ConnectorRuntime` -> `ConnectorRegistry` -> `McpConnector` -> `ConnectorCapabilityIndex`

---

## 2. Real Execution & Transport Diagnostics (Finding D & G)

### D. The `stdio` Hang
The suspected systemic `asyncio` event-loop deadlock with `stdio_client` is **disproven**.
- A custom tracer script (`trace_shell.py`) isolated the `initialize_and_verify` protocol.
- Canonical connectors (`github_mcp`, `context7_mcp`) successfully complete initialization (`Done! True`) without hanging.
- The hang was traced to a specific database fixture: `test.mcp.fail.trans.09bd56c2`. This fixture was created by a previous reliability test (`audit_self_healing_final.py`) and intentionally simulates a broken transport.
- Because `audit_shell.py` looped over *all* connectors sequentially in a synchronous script, hitting the broken test fixture caused a blocking timeout that halted the entire batch.

### G. Real Connector Failure
The claim that "all 14 connectors failed during real execution" was an artifact of the batch test runner hanging on the intentionally broken test fixture. The canonical connectors are functional.

---

## 3. Concurrency & State Isolation (Findings E & F)

### E. Worker Isolation
The Phase 35.5 claim that "worker-local failures do not mutate global PostgreSQL state" is **PROVEN**.
- **Trace Result:** We simulated a transport failure in a secondary worker process which emitted a `health.failed` event.
- **Mechanism:** `ConnectorRuntime.handle_event` routes this to `handle_transport_failure()`, which intentionally *invalidates capabilities locally* and schedules a local recovery thread, but **does NOT** write the `FAILED` state back to the `nexora.connector` table.
- **DB State:** The PostgreSQL state correctly remained `running` and `healthy`. 

### F. Active Health Loops
The application is currently running multiple overlapping daemon threads managing health and discovery:
- `McpEventLoopThread` (`mcp_runtime_adapter.py`)
- `McpStartupReconciliationThread` (`bootstrap.py`)
- `_watch_loop` (`registry_provider.py`)
- `_health_monitor_loop` (`mcp_runtime_manager.py`)

---

## 4. Final Decision Matrix & GoSOM Path

The parallel architecture violates the Universal Connector Platform constraints.

### GoSOM Path (Phase 36 Blockers)
Before we can introduce new GoSOM connectors, we must perform a **Unification & Deletion Phase**:
1. **Migrate Providers:** Refactor `github_provider.py`, `context7_provider.py`, etc., to use `ConnectorDispatcher` instead of `McpRuntimeAdapter`.
2. **Delete Legacy Subsystem:** Safely delete `services/runtime/mcp/` entirely.
3. **Terminate Ghost Threads:** Ensure `McpEventLoopThread`, `_watch_loop`, and `_health_monitor_loop` are permanently removed.
4. **Patch `stdio_client`:** Add strict timeouts to the `stdio` client initialization to prevent hanging on permanently dead subprocesses.
