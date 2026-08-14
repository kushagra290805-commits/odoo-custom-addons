# ADR-0044: Canonical Provider Execution Contract

## 1. Status
- Proposed

## 2. Context
Following the implementation of Phase 23.29 (Canonical Capability Registry Bootstrap), the Universal Capability Execution Layer (UCEL) and `CapabilityResolver` successfully populate the Odoo SQL registry upon startup and accurately resolve provider endpoints.

However, subsequent Provider Integration Acceptance Testing (PIAT) revealed a severe structural flaw at the execution boundary. When UCEL attempts to execute a resolved capability, the execution crashes with `TypeError` signature mismatches (e.g., `GitHubProvider.execute() got an unexpected keyword argument 'context'`).

An architectural audit confirmed that capability resolution is now functioning correctly, but execution fails because provider implementations currently expose multiple incompatible `execute()` signatures. At least five fragmented execution patterns coexist in the system:

1. **Native Odoo Provider Models**: `execute(self, tool_id: str, args: dict) -> List[Dict[str, Any]]`
2. **Component/Bridge Providers**: `execute(self, operation: str, payload: Dict[str, Any], context: ProviderExecutionContext) -> ProviderResponse`
3. **Legacy Tools**: `execute(self, context, **kwargs) -> Dict[str, Any]`
4. **Legacy MCP Tools**: `execute(self, session, command, **kwargs) -> Dict[str, Any]`
5. **Universal Capability Executors**: `execute(self, payload: dict) -> CapabilityResult`

This fragmentation prevents long-term extensibility, breaks abstraction boundaries, and forces execution orchestrators to guess or shim the signature format for each individual capability.

## 3. Decision
Adopt a single canonical provider execution contract.

Every provider, regardless of underlying transport (Native, MCP, REST, Docker, WebSocket, or future transports), MUST implement:

```python
def execute(
    self,
    request: ProviderExecutionRequest
) -> ProviderExecutionResult
```

No provider may expose transport-specific `execute` signatures. 

## 4. Canonical Request Model

The `ProviderExecutionRequest` object encapsulates all execution context inside a strictly typed structure.

```python
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ProviderExecutionRequest:
    # Routing identity: Identifies the exact capability being invoked (e.g., 'mcp.github')
    namespace: str
    
    # Execution inputs: The business logic parameters required by the provider.
    payload: Dict[str, Any]
    
    # Environment and state context: Ephemeral session variables or state mappings.
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime reference: Allows callback operations or deep integration if permitted.
    runtime: Optional[Any] = None
    
    # Tracing data: Injected correlation IDs, telemetry traces, and debugging info.
    execution_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Execution constraints: Maximum time allowed for the provider to complete execution.
    timeout: float = 60.0
    
    # Graceful shutdown flag: Mechanism to interrupt long-running operations.
    cancellation_token: Optional[Any] = None
    
    # Request lifecycle: Timestamp of when the request was dispatched.
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

**Responsibilities**:
- `namespace`: Routes the capability dispatch predictably without hardcoding operations.
- `payload`: Contains immutable execution parameters.
- `context`: Allows session data injection without modifying signature bounds.
- `runtime`: Connects back to builder sessions / system events.
- `execution_metadata`: Bridges to open-telemetry traces.
- `timeout` / `cancellation_token`: Ensures predictable timeouts and cleanup.
- `timestamp`: Defines execution start boundaries.

## 5. Canonical Result Model

The `ProviderExecutionResult` object standardizes the return boundary to guarantee safe consumption by downstream orchestrators.

```python
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class ProviderExecutionResult:
    # Execution status: True if the business logic succeeded.
    success: bool
    
    # The actual output payload of the capability (or None if failed).
    data: Any
    
    # Error details: Exception, traceback, or string error message (if success=False).
    error: Optional[Any] = None
    
    # Provider-specific metadata: e.g., rate limits remaining, tokens consumed, metrics.
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Latency tracking: The measured duration of the execution in milliseconds.
    execution_ms: float = 0.0
```

**Response Semantics**:
- A response with `success=True` guarantees that `data` contains the expected output format.
- A response with `success=False` guarantees that `error` is populated and handled predictably without crashing the orchestrator.
- Providers must not return raw lists, dicts, or un-encapsulated primitive types.

## 6. Architectural Invariants
This contract establishes the following permanent rules:

- Providers never receive positional arguments.
- Providers never receive `**kwargs`.
- Providers never return raw dicts or lists.
- Providers never expose transport protocols.
- UCEL is the only execution gateway.
- Transport adapters translate protocols.
- Providers implement business logic only.

## 7. Migration Strategy

To safely enforce this contract without destabilizing the system, migration will proceed in distinct phases:

**Phase 1**
Introduce execution models. (`ProviderExecutionRequest`, `ProviderExecutionResult`)

**Phase 2**
Update `ProviderInterface`. Enforce new signatures.

**Phase 3**
Update transport adapters. Migrate UCEL routing layers (e.g. `LocalToolExecutor`).

**Phase 4**
Migrate all providers. Rewrite every single execution implementation to unpack `ProviderExecutionRequest`.

**Phase 5**
Remove legacy signatures. Eliminate temporary backwards-compatible bridges and `**kwargs`.

**Phase 6**
Re-run PIAT. Verify the entire end-to-end execution loop.

## 8. Consequences

**Positive:**
- Stable API.
- Easier transport evolution.
- Cleaner telemetry.
- Better testing.
- Stronger type safety.
- Future multi-agent compatibility.

**Negative:**
- Requires one-time migration of all providers.
- Temporary compatibility layer during migration.

## 9. ADR Relationships

This document explicitly defines the provider execution boundary utilized by:

- **ADR-0029**: Universal Capability Execution Layer
- **ADR-0042**: Generation Runtime Architecture
- **ADR-0043**: Provider Capability Taxonomy

ADR-0044 defines the provider execution boundary used by those ADRs.

## 10. Acceptance Criteria

ADR is accepted only if:

- Every provider implements one `execute()` signature.
- PIAT passes without signature mismatches.
- No legacy execute overloads remain.
- Transport independence remains preserved.
