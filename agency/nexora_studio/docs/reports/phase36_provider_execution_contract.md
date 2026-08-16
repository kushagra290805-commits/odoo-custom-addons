# Phase 36.2: Provider Execution Contract Compatibility

**Date**: 2026-08-16

## Comparison Matrix

| Property | Legacy API (`McpToolRouter`) | Canonical API (`ConnectorRuntime`) | Migration Path |
| :--- | :--- | :--- | :--- |
| **Method Signature** | `execute_capability(tool_name: str, args: Dict) -> Any` | `dispatch(request: ConnectorExecutionRequest) -> ConnectorExecutionResult` | Providers wrap inputs in `ConnectorExecutionRequest`. |
| **Request Target** | `tool_name` (e.g., `"github_read_file"`) | `capability_namespace` (e.g., `"tools.call"`) + `payload` | Use `"tools.call"` as namespace; nest `tool_name` inside `payload['name']` and `args` in `payload['arguments']`. |
| **Result Structure** | Directly returns raw result dict (`await client.call_tool(...)`). | Returns `ConnectorExecutionResult`. | Check `result.success`. If true, extract `result.data` (which maps to MCP provider format). |
| **Error Semantics** | Raises `RuntimeError` or `ValueError` directly on the event loop. | Never raises. Returns `result.status == FAILURE` with `error_code` and `error`. | Providers must inspect `result.success` and map `result.error` back to Generation Engine exception models if required. |
| **Authentication** | `SecurityContext.validate_filesystem_args(args)` hardcoded in router. | Managed cleanly by UCP connector configuration logic (Phase 27+). | N/A (Handled downstream). |
| **Timeout/Retry** | None at the router level. | Implemented via `ConnectorDispatcher` and telemetry wrappers. | Implicitly improved. |
| **Recovery** | Hard fail. | Triggers single-flight local recovery via `handle_transport_failure()`. | Implicitly improved. |

## Contract Execution Mapping

**Legacy Implementation in Provider:**
```python
adapter = runtime.get_runtime('mcp_runtime')
future = asyncio.run_coroutine_threadsafe(
    adapter.router.execute_capability(mcp_tool, request.payload), 
    adapter._loop
)
result = future.result(timeout=60.0)
```

**Canonical Implementation in Provider:**
```python
from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionRequest
from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap

bootstrap = ConnectorPlatformBootstrap.get_instance()
runtime = bootstrap.connector_runtime

exec_req = ConnectorExecutionRequest(
    capability_namespace="tools.call",
    payload={
        "name": mcp_tool,
        "arguments": request.payload
    },
    context=ExecutionContext(
        session_id=str(request.session_id)
    )
)
result = runtime.dispatch(exec_req)
if not result.success:
    raise RuntimeError(f"Tool execution failed: {result.error}")
return result.data
```

## Conclusion
The Canonical UCP API is fully compatible and structurally superior (non-raising, strongly typed, contextualized). No intermediate translation orchestration layer is needed. Providers can natively construct the UCP request and handle the UCP result object.
