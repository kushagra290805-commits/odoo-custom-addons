# ADR-0051 — Connector MCP Onboarding Platform

## 1. Status
**Accepted** — Phase 28

---

## 2. Context

Phase 27.2 certified the MCP Connector and Universal Connector Platform with 57 verified tests. ADR-0050 defines the frozen Universal Connector Platform architecture.

The platform currently requires a Python connector class for each MCP server, meaning adding a new MCP server (e.g., GitHub MCP, Penpot MCP, Filesystem MCP) requires writing a new Python file and redeploying the module. This is unscalable.

The objective of Phase 28 is to turn the existing Connector Runtime + MCP Connector into an **operator-facing onboarding platform** where real MCP servers can be added, configured, authenticated, tested, enabled, disabled, and monitored through Nexora Studio/Odoo **without writing new Python connector code**.

ADR-0050 remains architecturally frozen. This ADR defines the data-driven onboarding layer on top of it.

---

## 3. Decision

Introduce a **Connector MCP Onboarding Platform** as a thin operator-facing data and service layer on top of the existing Universal Connector Platform.

**Core principle:** MCP server instances are DATA/CONFIGURATION, not Python classes.

```
One McpConnector Python implementation
    +
N Odoo nexora.mcp_server_config records
    +
Dynamic capability discovery
    =
N independently managed MCP servers
```

---

## 4. Architectural Layer

```
OPERATOR (Odoo UI / API)
     │
     ▼
nexora.mcp_server_config  [NEW]  — MCP server configuration record
nexora.mcp_credential     [NEW]  — Encrypted per-connector secret
nexora.mcp_discovered_tool [NEW] — Discovered tool schema per MCP server
     │
     ▼
McpOnboardingService      [NEW]  — Translates Odoo records → domain objects
McpConnectionTester       [NEW]  — Ephemeral test sessions
McpCapabilityDiscoveryService [NEW] — tools/resources/prompts discovery
ConnectorRuntimeSynchronizer  [NEW] — Odoo ORM hooks → Runtime sync
     │
     ▼
OdooSecretsProvider       [NEW]  — Implements SecretsProvider ABC (ADR-0050)
OdooCredentialResolver    [NEW]  — Implements CredentialResolver ABC (ADR-0050)
     │
     ▼
ConnectorRegistrationPipeline [EXISTING — UNCHANGED]
ConnectorRuntime               [EXISTING — FROZEN]
McpConnector                   [EXISTING — FROZEN]
McpTransport                   [EXISTING — FROZEN]
McpProvider                    [EXISTING — FROZEN]
```

---

## 5. Decision: Connector Definition Model (§1)

Each onboarded MCP server maps to one `nexora.connector` record (existing model) plus one `nexora.mcp_server_config` record (new).

The `nexora.connector.connector_id` field is the unique identifier used throughout the runtime. The `nexora.mcp_server_config` record provides the MCP-specific configuration (command, args, env, secrets).

When the runtime needs to execute a capability, the existing `McpConnector` is used with a `ConnectorConfiguration` built from the Odoo data records. No per-server Python class is required.

---

## 6. Decision: Connector Types (§2)

The existing `nexora.connector_type` model already stores connector types with `type_code`. The `mcp` type_code will be seeded as a built-in type.

Phase 28 onboarding is specific to the `mcp` type. Future REST, GitHub, Slack connectors will follow the same onboarding pattern — each will add their own server config model alongside `nexora.mcp_server_config`.

No per-protocol runtime architecture changes are needed.

---

## 7. Decision: MCP Server Configuration Storage (§3)

**Model: `nexora.mcp_server_config`**

| Field | Type | Purpose |
|---|---|---|
| `connector_id` | Many2one nexora.connector | Parent connector record |
| `command` | Char(required) | Executable command (e.g., "npx", "/usr/bin/python") |
| `args_json` | Text | JSON array of string arguments |
| `working_directory` | Char | Optional working directory |
| `env_vars_json` | Text | JSON dict of non-secret env vars |
| `timeout_seconds` | Integer | Per-connector request timeout (default: 60) |
| `startup_policy` | Selection(lazy/eager) | When to establish connection |
| `last_test_result_json` | Text | Sanitized last test result |
| `last_tested_at` | Datetime | Timestamp of last test |
| `discovered_capabilities_count` | Integer (computed) | Tool count from last discovery |

SQL constraint: `unique(connector_id)` — one MCP config per connector.

---

## 8. Decision: Secret Management (§4)

### Storage
Secrets are stored in `nexora.mcp_credential` (new model), one record per secret per connector.

The `encrypted_value` field stores a Fernet-encrypted blob. The encryption master key is loaded at runtime from the server-side environment variable `NEXORA_CONNECTOR_SECRET_KEY`. This key is **never** stored in the Odoo database, never logged, and never included in backups.

### Key Derivation
The Fernet key is a URL-safe base64-encoded 32-byte key. On first use, if the environment variable is absent, the system raises a `ConfigurationError` — it does NOT auto-generate a key, to prevent silent security downgrade.

### Key Rotation
Credential rotation is supported via the `McpOnboardingService.rotate_credential(connector_id, key, new_value)` method, which:
1. Re-encrypts the value with the current key
2. Updates `nexora.mcp_credential.encrypted_value`
3. Calls `ConnectorRuntimeSynchronizer.sync_credential_rotation()` to evict the cached session

### Secret Masking
- `encrypted_value` is never returned in any API response
- ORM reads return only `is_set` (bool) and `display_hint` (masked string, e.g., "****abcd")
- Logs never contain decrypted values
- Telemetry records only key name and `is_set` status
- The `OdooSecretsProvider.get_secret()` method is the only authorized decryption path

### Injection
Secrets are injected into `McpConfiguration.env` dict only within `McpOnboardingService._build_mcp_configuration()`. The env dict containing the decrypted value is never persisted.

### Access Control
- Reading/creating/updating credentials: `group_nexora_super_admin` only
- Checking if credential `is_set`: `group_nexora_admin`
- No credential access for `group_nexora_developer` or lower

### Credential Deletion
`OdooSecretsProvider.delete_secret(key)` clears `encrypted_value` and sets `is_set = False`. The corresponding connector is immediately disabled and the runtime session is evicted.

---

## 9. Decision: Registration Pipeline (§5)

```
Operator creates nexora.connector + nexora.mcp_server_config
    │
    ▼
McpOnboardingService.register_connector(connector_record)
    │
    ├── Validate connector_record fields (command, args format)
    ├── OdooCredentialResolver.resolve() → resolved env dict
    ├── ManifestBuilder.build(connector_record) → ConnectorManifest
    ├── ConnectorConfiguration.build(connector_record) → ConnectorConfiguration
    ├── Connector(manifest, configuration) → domain aggregate
    └── ConnectorRegistrationPipeline.execute(connector)
            │
            ├── ManifestValidator.validate()
            ├── SDKVersionValidator.validate()
            ├── ConfigurationValidator.validate()
            ├── DependencyValidator.validate()
            ├── CompatibilityValidator.validate()
            ├── SecurityValidator.validate()
            └── ConnectorRegistry.register()
                    └── ConnectorCapabilityIndex.add()
                            └── Runtime availability confirmed
```

No pipeline stages are bypassed.

---

## 10. Decision: Connection Testing (§6)

`McpConnectionTester.test(connector_record)` creates an isolated ephemeral runtime:

1. Resolve configuration from Odoo record (secrets injected in-process only)
2. Instantiate ephemeral `ConnectorRuntime()` (NOT the global singleton)
3. Register connector through the full pipeline
4. Dispatch `tools.list` (and optionally `resources.list`, `prompts.list`)
5. Build sanitized `ConnectionTestResult` — no secrets, no env vars, no subprocess env
6. `runtime.shutdown()` — ephemeral runtime and all sessions are terminated
7. Update `nexora.mcp_server_config.last_test_result_json` with sanitized result

Return value contains only: `success`, `latency_ms`, `tool_count`, `resource_count`, `prompt_count`, `server_info` (sanitized), `error_message` (user-safe), `tested_at`.

---

## 11. Decision: Capability Discovery (§7)

`McpCapabilityDiscoveryService.discover(connector_record)`:

1. Uses the global `ConnectorRuntime` (connector must be registered and running)
2. Dispatches `tools.list`, `resources.list`, `prompts.list` via existing `ConnectorDispatcher`
3. Persists discovered tools to `nexora.mcp_discovered_tool` (new model):
   - tool name, description, input JSON schema
   - linked to the `nexora.connector` record
   - previous discovery results are replaced (not appended)
4. Updates `nexora.mcp_server_config.discovered_capabilities_count`
5. Does NOT generate Python classes for discovered tools
6. Does NOT permanently hardcode tool names in source code

**Model: `nexora.mcp_discovered_tool`**

| Field | Type | Purpose |
|---|---|---|
| `connector_id` | Many2one nexora.connector | Owning connector |
| `tool_name` | Char | MCP tool name (e.g., "read_file") |
| `description` | Text | Tool description from server |
| `input_schema_json` | Text | Full JSON schema of tool inputs |
| `discovery_source` | Selection(tools/resources/prompts) | Which MCP list it came from |
| `discovered_at` | Datetime | Timestamp |

---

## 12. Decision: Lifecycle (§8)

The existing `ConnectorLifecycleState` enum and `ConnectorLifecycleStateMachine` are used without modification.

For operator-facing onboarding, the effective lifecycle is:

```
(Data created) → CONFIGURED → VALIDATED → RUNNING
                                              │
                              DISABLED ←──────┤
                                              │
                              ERROR (FAILED) ←┘
```

This maps to existing states: `configured` → `validated` → `running` → `disabled`/`failed`.

The Odoo `nexora.connector.state` field is the authoritative state store. The `ConnectorRuntimeSynchronizer` ensures the runtime reflects it.

---

## 13. Decision: Runtime Synchronization (§9)

`ConnectorRuntimeSynchronizer` is called from ORM hooks on `nexora.connector`:

| Trigger | Action |
|---|---|
| `state` → `running` | `sync_enable()` — build + register connector |
| `state` → `disabled` | `sync_disable()` — deregister + evict session |
| `state` → `removed` | `sync_delete()` — deregister + evict session |
| Configuration update | `sync_update()` — deregister + re-register |
| Credential rotation | `sync_credential_rotation()` — deregister + re-register |
| `unlink()` | `sync_delete()` — unconditional cleanup |

**Session eviction** is guaranteed: the `ConnectorDispatcher._active_connectors` dict is cleared for the connector ID before re-registration. Stale sessions cannot persist across configuration changes.

---

## 14. Decision: Security Boundary (§10)

```
OPERATOR
  │ (HTTPS, Odoo session auth)
  ▼
Odoo Controller (group_nexora_admin required)
  │ (ORM access, never returns encrypted_value)
  ▼
nexora.mcp_credential (encrypted_value: never read directly)
  │ (OdooSecretsProvider.get_secret() — only decryption path)
  ▼
McpOnboardingService._build_mcp_configuration()
  │ (env dict with secrets — in-process only, never persisted)
  ▼
McpConfiguration (transient, not stored)
  │ (anyio.open_process, shell=False)
  ▼
MCP Server Process (subprocess, isolated)
```

Secrets never cross the Odoo API boundary. The only authorized decryption path is `OdooSecretsProvider.get_secret()`, which requires the `NEXORA_CONNECTOR_SECRET_KEY` environment variable.

---

## 15. Decision: Multi-Tenant / Client Isolation (§11)

Each `nexora.connector` record has its own `nexora.mcp_server_config` and `nexora.mcp_credential` records. Credentials are scoped by `connector_id`.

The `ConnectorDispatcher` cache is keyed by `connector_id`. One connector's session, process, and credentials cannot access another connector's state.

MCP server processes are separate OS subprocesses per connector instance. There is no shared subprocess.

---

## 16. Decision: Failure Model (§12)

| Failure | Behavior |
|---|---|
| Invalid configuration | `ManifestValidator` rejects during pipeline; `nexora.connector.state` → `failed` |
| Invalid credentials | `OdooCredentialResolver` raises `CredentialError`; test result returns safe error |
| MCP process crash | `McpTransport` raises; `Dispatcher` evicts session; next dispatch cold-starts |
| Timeout | `_run_sync` 60s timeout raises; session evicted; `ConnectorExecutionResult.timeout()` returned |
| Malformed JSON-RPC | Pydantic validation raises in SDK; session evicted; safe error returned |
| Unavailable server | Cold-start fails; `failed` state propagated |
| Discovery failure | Individual capability missing from results; partial results stored; error logged |
| Credential rotation failure | Old session evicted; new credential stored; runtime re-registered |

---

## 17. Decision: Backward Compatibility (§13)

All existing Phase 26/27 AAT and contract tests must remain green. The following are guaranteed:

- `ConnectorRuntime` public interface unchanged
- `ConnectorRegistrationPipeline.execute()` unchanged
- `McpConnector`, `McpTransport`, `McpProvider` unchanged
- `McpConfiguration` unchanged (secrets injected via env dict, not a new field)
- All existing `nexora.connector_*` Odoo models unchanged (new models are additive)
- Existing `scratch/aat_suite/` tests unchanged

---

## 18. Consequences

### Positive
- Any MCP server can be onboarded through Odoo UI without writing Python code
- Credentials are encrypted at rest with environment-variable-keyed Fernet
- Connection testing validates configuration before enabling a connector
- Dynamic capability discovery stores full tool schemas without hardcoding
- All onboarding flows route through the existing registration pipeline (no bypasses)
- Connector isolation is preserved at process, session, credential, and runtime levels

### Negative
- Requires `NEXORA_CONNECTOR_SECRET_KEY` environment variable on all Odoo server instances
- Runtime synchronization adds ORM write overhead (acceptable for infrequent admin operations)
- Discovery results are full snapshots (previous results replaced on each discovery run)

### Rejected Alternatives
- **Per-server Python connector class**: rejected — unscalable, violates operator-driven onboarding goal
- **Credential storage in `ir.config_parameter`**: rejected — not per-connector scoped, insufficient isolation
- **Lazy runtime sync (on-demand)**: rejected — allows stale state to persist; ORM hooks provide immediate consistency
- **Reuse `nexora.connector_capability` for tool schema**: rejected — that model is for generic namespace registration; MCP tool schemas need full JSON input schemas which are MCP-specific

---

## 19. ADR Relationships

| ADR | Relationship |
|---|---|
| ADR-0050 | Frozen parent architecture — fully preserved |
| ADR-0044 | ConnectorExecutionResult semantics — unchanged |
| Phase 25.1.5 PRE-001 | SecretsProvider ABC — this ADR provides the first implementation |

---

## 20. Acceptance Criteria

- [ ] ADR-0051 created and matches implementation
- [ ] `nexora.mcp_server_config` model exists and is loadable
- [ ] `nexora.mcp_credential` model exists, credentials encrypted at rest
- [ ] `nexora.mcp_discovered_tool` model exists
- [ ] `OdooSecretsProvider` implements `SecretsProvider` ABC
- [ ] `OdooCredentialResolver` implements `CredentialResolver` ABC
- [ ] `McpOnboardingService` registers MCP servers through `ConnectorRegistrationPipeline`
- [ ] `ConnectorRuntimeSynchronizer` ORM hooks work for enable/disable/delete/update
- [ ] `McpConnectionTester.test()` returns sanitized results, no credential leakage
- [ ] `McpCapabilityDiscoveryService.discover()` populates `nexora.mcp_discovered_tool`
- [ ] All credentials: never in logs, API responses, telemetry, or test artifacts
- [ ] No `shell=True` anywhere in the MCP execution path
- [ ] All Phase 26/27 regression tests remain green
- [ ] Phase 28 AAT suite passes
