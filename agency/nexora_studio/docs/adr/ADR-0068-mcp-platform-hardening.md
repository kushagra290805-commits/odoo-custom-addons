# ADR 0068: MCP Platform Hardening (Phase 44.2)

## Status
Accepted (Phase 44.2)

## Context
Phase 44.1 (`phase44_1_mcp_architecture_platform_audit.md`) audited the MCP/UCP
platform and concluded it is "architecturally sound and operationally unsafe":
11 P0 findings (G-01…G-11), 52 gaps total. The canonical execution chain exists
but is not truthful end-to-end: SSE/remote capabilities cannot route, dotted
protocol namespaces are corrupted, manifests are wiped on full writes, health is
force-written to `healthy` without probes, and plaintext secrets plus tracebacks
reach persisted/user-facing surfaces.

Phase 44.2 converts those findings into a minimal production implementation
without creating a parallel architecture.

## Canonical Architecture (ratified)

```
UniversalCapabilityRouter (UCEL)
  → ConnectorExecutionTarget (ExecutionTargetType.CONNECTOR)
    → ConnectorRuntime
      → ConnectorDispatcher
        → McpConnector
          → McpProvider
            → McpTransport (global) | SessionTransportPool (session-bound)
              → MCP SDK (sse_client / stdio_client)
                → real MCP server
```

No other production MCP execution path is permitted. Legacy surfaces
(`services/mcp_*.py`, `source_framework/transport/*`, `TransportFactory`,
`ProviderFactory`) are classified non-canonical/dead and are not wired into this
chain.

## Decisions

### 1. Routing model (G-01, G-02)
- Registry-backed MCP capabilities resolve to `ExecutionTargetType.CONNECTOR`,
  never `REMOTE`. Transport kind (stdio/sse) is a connector concern, not a
  target-type concern.
- `RemoteToolExecutor` is deliberately NOT registered. The router already fails
  closed ("Executor not found for …"); that behavior is preserved as the real
  failure semantic.
- Namespace contract: the reserved protocol namespaces
  `tools.list`, `tools.call`, `resources.list`, `resources.read`,
  `prompts.list`, `prompts.get` are matched before any dotted shorthand
  interpretation. Only non-reserved dotted namespaces mean
  `{connector_id}.{tool_name}`. No connector-specific exceptions.

### 2. Security model (G-06, G-07, G-41…G-43)
- Master encryption key: env-only provisioning
  (`NEXORA_CONNECTOR_SECRET_KEY`); plaintext removed from dev config. Proven:
  value never entered git history; no remediation required.
- Credential values never appear in logs, user-facing errors, persisted test
  results, exception serialization, cache keys, or reports. Tracebacks stay in
  server logs; user surfaces get safe messages.
- Raw MCP payloads are not logged. `trace_file` remains opt-in, unset by
  default (accepted risk, debug-only).
- Credential resolution is minimized: only declared credentials are resolved
  and injected (`__INJECT_VIA_NEXORA_MCP_CREDENTIAL__` placeholders); missing
  required credentials fail closed.

### 3. Registry ownership (G-03, G-04, G-08)
- `config/mcp_registry.json` remains the authoritative bootstrap source
  (consumed by production bootstrap). Synchronization is deterministic and
  idempotent; full writes never clobber populated `manifest_json`; the registry
  hash reflects actual file bytes and advances only after successful sync.
- The capability index is rebuilt from persisted manifests of enabled
  connectors, not only from live in-process connectors.

### 4. Lifecycle model (G-05, G-20, G-38)
- `healthy` is evidence, not decoration: it is set only after a real probe
  succeeds (`probe_health` → `ConnectorHealthMonitor`). Registration/enable may
  set lifecycle `running` but health remains `unknown` until probed.
- Lifecycle states (14, per `ConnectorLifecycleState`) and health status
  (unknown/healthy/degraded/failed) are separate axes; `degraded` is a
  health_status value only. Persistence uses the `lifecycle_state` key
  exclusively.
- Connectors whose real server is unavailable report degraded/failed. This is
  expected and correct.

### 5. Context propagation model (ADR-0066 ratified)
- `ConnectorRuntimeContext` is the canonical runtime context of the connector
  subsystem; `ExecutionContext` (UCEL/SDK boundary) carries an explicit
  `request_context` field. No third context type.
- Connection configuration ≠ ephemeral request context. Only allowlisted fields
  (`allowed_request_context_fields`) cross the MCP boundary as `meta` on
  `call_tool`. No hardcoded `userToken`.

### 6. Session transport model (ADR-0067 ratified)
- `SessionTransportPool` (actual class name retained) remains at the
  `McpConnector` level. sha256 token-hashed keys, TTL eviction, lock re-check
  isolation, and shutdown cascade are already implemented and verified.
- Phase 44.2 adds only the missing bound: max pool size with locked eviction on
  overflow. `session_binding="none"` bypasses the pool (GitHub/Tavily/Firecrawl
  unchanged); Penpot session-bound execution unchanged.

### 7. Consolidation strategy (W10/W12)
- `ConnectorFactory` is the single live construction path. `TransportFactory`
  and `ProviderFactory` are dead (zero registration call sites) — deprecation
  notices added, instantiation removed from `ConnectorRuntime`; files retained
  pending 44.3 dependency-proof deletion.
- Legacy `source_framework/transport/*` and top-level `services/mcp_*.py` are
  marked non-canonical; no production wiring; deletion deferred.

### 8. Configuration precedence
- One timeout model: `nexora.mcp_server_config.timeout_seconds` (default 60) →
  runtime configuration → `McpConfiguration` → transport connect/operation
  waits. Hardcoded 60.0 values removed.
- `startup_policy` classified legacy/implicit (eager = registration handshake,
  lazy = on-demand dispatch); `working_directory` wired as stdio cwd.

## Rejected Alternatives
1. Registering `RemoteToolExecutor` to make REMOTE routing "work" — it returns
   unconditional success; violates real-failure semantics.
2. A new registry/store — violates single-source ownership.
3. Renaming the pool to match ADR text — churn without behavior change.
4. Optimistic health to preserve dashboard appearance — falsifies evidence.
5. Reconnection/backoff in transport — out of scope per 44.1 §17.9.
6. Mass deletion of legacy directories — requires dependency proof (44.3).

## Consequences
- Existing connectors may show `unknown`/`degraded`/`failed` until probed —
  correct behavior.
- Failed MCP executions surface as failures end-to-end.
- Phase 44.3 preconditions: G-07 DB parameter remediation, legacy deletion with
  dependency proof, live MCP + production certification test waves.
