# Phase 44.1 — MCP Architecture & Platform Audit

**Mode:** ANALYSIS ONLY. No implementation file was modified during this phase.
**Date:** 2026-08-21
**Scope:** `custom-addons/agency/nexora_studio` — Universal Connector Platform (UCP), MCP subsystem, capability layer, credentials, lifecycle, tests, ADRs.
**Ground truth policy:** The repository implementation and the live PostgreSQL database were treated as authoritative. Prior phase reports and ADRs were treated as *stated intent* and reconciled against reality. Several previously-reported claims are **corrected** in this document.

**Evidence sources**
- Direct source reads of all UCP/MCP modules (not summaries).
- Read-only `psql` queries against database `nexora_studio` (SELECT only; no writes).
- `docker ps` (read-only).
- `git log` / `git status --porcelain` (read-only).
- `Get-FileHash` / `Get-Item -LinkType` (read-only).

---

## 1. Executive Summary

The UCP MCP subsystem is **functionally working in production for all 5 registered connectors** (all `state=running`, `health_status=healthy`), and the core transport/auth/session design is sound and genuinely generic. Phase 43.8's Penpot query-auth correction is confirmed live and correct.

However, the audit found that **the canonical architecture described in the phase reports is not the architecture that actually executes**. Specifically:

1. **The canonical path is unreachable for MCP tools.** `UniversalCapabilityRouter` resolves a capability *before* dispatching, and the routing decision depends on `CapabilityManifest.target_type`. For all MCP tools, `target_type` is produced from two different sources that disagree, and the disagreement means a `{connector}.{tool}` call resolves to `ExecutionTargetType.CONNECTOR` **only** when a matching `nexora.mcp_discovered_tool` row exists. Any namespace not backed by a discovered-tool row silently falls to "Capability not found" or to the wrong executor. This is the single most important structural finding.
2. **Every real production caller bypasses the canonical path.** `tavily_provider.py`, `github_provider.py`, and `context7_provider.py` each call `ConnectorRuntime.dispatch()` directly. So does `capability_discovery.py`, `connection_tester.py`, and `dispatcher.initialize_and_verify()`. The `ConnectorExecutionTarget` bridge is used by exactly one production code path (`GenerationRuntime`) plus one test action.
3. **`tools.list` cannot be invoked through `ConnectorExecutionTarget`.** `_build_request` splits *any* dotted namespace, so `tools.list` becomes `connector_id="tools"`. It works everywhere else only because every other caller bypasses that translator. This is an architectural contract defect, not a bug in `tools.list`.
4. **Manifest data in the database is corrupt for 4 of 5 connectors.** Live values: `context7_mcp={}`, `firecrawl_mcp={}`, `github_mcp={"broken": true}`, `tavily_mcp={"command":"python","args":["-c","import sys; sys.exit(1)"]}`. Only `penpot_mcp` holds a real manifest. The mechanism is identified (`odoo_adapter._do_write` full-write default). Connectors still work because the manifest is not consulted at execution time — but the capability index is therefore empty (`nexora_connector_capability` = 0 rows for all 5).
5. **`mcp_registry.json` is NOT dead and NOT informational-only — this corrects a prior claim.** It is the exclusive input to `nexora.capability_registry` (17 live rows). But its sync is **hash-gated and currently stale**: stored hash `4e8c39b4…` ≠ current file hash `bccdeab8…`, so the DB reflects an older revision of the file. Live proof: `mcp.github` is `enabled=true, lifecycle=production` in the DB but `enabled=false, lifecycle=planned` in the file.
6. **Security posture is good at the crypto layer, weak at the observability layer.** No decrypted secret is ever logged. But the Fernet master key sits in plaintext in `d:\ODOO\configs\dev.conf`; `TraceReceiveStream`/`TraceSendStream` write raw MCP frames to disk when enabled; and `connection_tester.py` persists full Python tracebacks into a user-visible DB field.
7. **Test coverage is nominal.** 52 test files exist; `tests/__init__.py` registers 8. `SessionTransportPool` has zero coverage.

**Verdict:** The platform is production-*functional* but not production-*governed*. Nothing here requires an emergency fix, and nothing requires new architecture. The correct Phase 44.2 work is **consolidation and contract enforcement**, not construction.

**Corrections to prior reports issued by this audit:** 3 (registry.json role; the `community/` "duplicate"; the location of the bootstrap singleton). All are documented inline.

---

## 2. Actual Architecture

### 2.1 Component inventory

| # | Component | File | Created by | Destroyed by | Cached | Scope | State held |
|---|---|---|---|---|---|---|---|
| 1 | `ConnectorPlatformBootstrap` | `services/connector/integration/bootstrap.py` | `post_load_provider_platform()` in `__init__.py:32` | never | yes | **process singleton** (class attr `_instance`, line 41) | `BootstrapState`, runtime ref |
| 2 | `ConnectorRuntime` | `services/connector/runtime/connector_runtime.py` | bootstrap; also ad-hoc by `connection_tester`, `nexora_connector.action_discover_mcp_capabilities` | `shutdown()` (only ephemeral instances) | yes (bootstrap's) | **singleton + ad-hoc clones** | registry, capability index, recovery maps |
| 3 | `ConnectorDispatcher` | `services/connector/runtime/dispatcher.py` | `ConnectorRuntime.__init__` | with runtime | yes | per-runtime | `_active_connectors` dict (**unlocked**) |
| 4 | `McpConnector` | `services/connector/connectors/mcp/connector.py` | `ConnectorDispatcher._get_or_create_connector` | `_execute_on_connector` on any error; `shutdown()` | yes | per-`connector_id`, per-runtime | provider/transport/pool/health refs |
| 5 | `McpProvider` | `.../mcp/provider.py` | `McpConnector.__init__:39` | with connector | no | per-connector | config, global transport, pool |
| 6 | `McpTransport` (global) | `.../mcp/transport.py` | `McpConnector.__init__:33` | `disconnect()` | no | per-connector | asyncio loop, bg thread, `ClientSession` |
| 7 | `SessionTransportPool` | `.../mcp/pool.py` | `McpConnector.__init__:37` **only if** `session_binding=='request_context'` | `McpConnector.shutdown()` | yes | per-connector | `{sha256 → (transport, last_used)}` |
| 8 | `McpTransport` (session) | `.../mcp/transport.py` | `SessionTransportPool.get_transport:50` | TTL evict / disconnect-evict / `shutdown_all` | yes | **per session identity** | own loop + thread + session |
| 9 | `McpHealthCheck` | `.../mcp/health.py` | `McpConnector.__init__:40` | with connector | no | per-connector | transport ref only |
| 10 | `ConnectorExecutionTarget` | `services/connector/integration/connector_executor.py` | `GenerationRuntime.__init__:78`; `action_test_tool_execution:146` | GC | no | **per GenerationRuntime instance** | runtime ref |
| 11 | `UniversalCapabilityRouter` | `services/capabilities/router.py` | `GenerationRuntime.__init__:80` | GC | no | **per GenerationRuntime instance** | resolver/policy/security/mw/scheduler/executors |
| 12 | `CapabilityRepository` | `services/capabilities/repository.py` | `GenerationRuntime.__init__:62` | GC | **yes — `self._cache`, never invalidated** | per-GenerationRuntime | manifest cache |
| 13 | `OdooConnectorPersistenceAdapter` | `services/connector/registry/persistence/odoo_adapter.py` | bootstrap / ad-hoc | GC | no | per-runtime | env / cursor strategy |
| 14 | `OdooSecretsProvider` | `services/connector/credentials/odoo_secrets_provider.py` | onboarding service | GC | **no — Fernet deliberately uncached** | per-call | none |
| 15 | `McpOnboardingService` | `services/connector/onboarding/mcp_onboarding_service.py` | model actions / synchronizer | GC | no | per-call | runtime + env |
| 16 | `RegistryBootstrapService` | `services/capabilities/bootstrap.py` | Odoo `AbstractModel` | n/a | n/a | Odoo model | none (hash in `ir.config_parameter`) |

### 2.2 Actual vs intended path

**Intended (per prior reports):**
`UniversalCapabilityRouter → ConnectorExecutionTarget → ConnectorRuntime → ConnectorDispatcher → McpConnector → McpProvider → McpTransport → MCP SDK → server`

**Actual — there are four live entry points, not one:**

```
PATH 1 (canonical, 1 production caller):
  GenerationRuntime.tools.execute(ns, payload)
    → ToolRuntimeAdapter.execute            runtime_interfaces.py:143
    → UniversalCapabilityRouter.execute     router.py:25
        ├─ SecurityLayer.authorize          -> hardcoded `return True`
        ├─ CapabilityResolver.resolve_candidates
        │    → CapabilityRepository.get_manifests_by_namespace
        │        ├─ nexora.capability_registry lookup (from mcp_registry.json)
        │        └─ nexora.mcp_discovered_tool lookup  -> target_type=CONNECTOR
        ├─ CapabilityPolicyEngine.evaluate  -> `candidates[0]`, no real policy
        ├─ SecurityLayer.inject_credentials -> no-op `return context`
        └─ executors[manifest.target_type]
             → ExecutionScheduler → ExecutionStrategy → target.execute(payload)
    → ConnectorExecutionTarget.execute      connector_executor.py:79
    → _build_request  (dotted-namespace rewrite)   :114
    → ConnectorRuntime.dispatch             connector_runtime.py:251
    → ConnectorDispatcher.dispatch          dispatcher.py
    → McpConnector → McpProvider → McpTransport → MCP SDK

PATH 2 (Odoo model providers — 3 files, bypasses router + executor):
  nexora.provider.tavily / github / context7
    → ConnectorPlatformBootstrap.get_instance().connector_runtime.dispatch(req)
      tavily_provider.py:44 | github_provider.py:49 | context7_provider.py:43

PATH 3 (onboarding/discovery/test — bypasses router + executor):
  McpCapabilityDiscoveryService.discover  → runtime.dispatch('tools.list')
  McpConnectionTester                      → ephemeral runtime.dispatch
  ConnectorDispatcher.initialize_and_verify→ sdk_connector.execute('tools.list')  dispatcher.py:276

PATH 4 (health — bypasses provider entirely):
  ConnectorRuntime health → McpHealthCheck.check_health  health.py
    → self.transport.list_tools()   # global transport, no namespace gate, no session binding
```

**Consequence:** there is no single chokepoint. Auth allowlisting, session binding, and namespace validation live in `McpProvider`, but Paths 3 and 4 reach `McpTransport` without passing through it.

### 2.3 Duplicate logic detected

| Duplicated behaviour | Locations |
|---|---|
| Direct `runtime.dispatch` provider shim | `tavily_provider.py`, `github_provider.py`, `context7_provider.py` (3 near-identical files) |
| Background-thread cursor detection | `odoo_adapter.py` ×4 (`read_connector_record`, `_execute_safe_write`, `fetch_all_connectors`, `delete_connector_record`) |
| 12-key `user_overrides` dict | `mcp_onboarding_service.py:294-307` and `:360-373` (verbatim) |
| MCP transport implementation | `connectors/mcp/transport.py` (live) vs `source_framework/transport/mcp_transport.py` (`DeprecationWarning`, line 6) |
| Runtime acquisition | `get_connector_runtime()` vs `ConnectorPlatformBootstrap.get_instance()` vs ad-hoc `ConnectorRuntime(...)` (3 ways; `nexora_connector.py:183-190` uses all three in one method) |
| Factory layer | `ConnectorFactory` stores `transport_factory`/`provider_factory` and never calls them (`connector_factory.py:47-51` commented-out) |

---

## 3. Execution Traces

Traces below follow actual function calls and constructors, verified by source read.

### 3.1 Path A — Normal MCP tool execution

Two variants exist in production.

**A1 — via canonical bridge** (`GenerationRuntime` only)

| Step | Call site | Notes |
|---|---|---|
| 1 | `ToolRuntimeAdapter.execute(ns, payload, scoped_runtime, budget)` — `runtime_interfaces.py:141` | raises bare `Exception` on failure (line 145) |
| 2 | `UniversalCapabilityRouter.execute` — `router.py:25` | |
| 3 | `SecurityLayer.authorize` — `security.py:2` | **`return True`, unconditional** |
| 4 | `CapabilityResolver.resolve_candidates` — `resolver.py:12` | falls into a hardcoded 9-entry `provider_map` heuristic on miss |
| 5 | `CapabilityRepository.get_manifests_by_namespace` — `repository.py:9` | `self._cache` hit returns stale data forever |
| 6 | → `nexora.capability_registry` search on `capability_code` | `target_type` from `supports_remote`/`supports_local` |
| 7 | → if `'.' in namespace`: `nexora.mcp_discovered_tool` search — `repository.py:56-90` | **only here** is `ExecutionTargetType.CONNECTOR` produced; health-gated on `state=='running' and health_status=='healthy'` |
| 8 | `CapabilityPolicyEngine.evaluate` — `policy.py:5` | `candidates[0]`; registry match wins over discovered-tool match because it is appended first |
| 9 | `SecurityLayer.inject_credentials` — `security.py:5` | **no-op** |
| 10 | `executors.get(descriptor.manifest.target_type)` — `router.py:54` | `executors` has only `LOCAL` + (conditionally) `CONNECTOR`; `REMOTE` is **never registered** in `GenerationRuntime` |
| 11 | `ExecutionScheduler.schedule_and_execute` → `ExecutionStrategy.execute` | pass-through; no queueing, no limits (comment admits it) |
| 12 | `ConnectorExecutionTarget.execute` — `connector_executor.py:79` | |
| 13 | `_build_request` — `:114` | dotted namespace → `connector_id`/`tool_name`, namespace forced to `tools.call`; `request_context` forwarded at `:141` |
| 14 | `ConnectorRuntime.dispatch` — `connector_runtime.py:251` | recovery guard, then dispatcher |
| 15 | `ConnectorDispatcher.dispatch` → `_resolve_connector` → `_get_or_create_connector` — `dispatcher.py:150/198` | `_active_connectors` **unlocked**; 5 `DISPATCHER:` f-string INFO logs |
| 16 | `_execute_on_connector` — `:215` | on **any** exception: evict + shutdown + re-raise |
| 17 | `ComponentConnector.execute` → `McpProvider.execute` — `provider.py:36` | namespace allowlist of exactly 6 |
| 18 | `_tools_call` — `:80` → `_get_active_transport(context)` — `:21` | allowlist gate + session identity gate |
| 19 | `McpTransport.call_tool` — `transport.py:237` | filters `request_context` through `allowed_request_context_fields` into MCP `meta=` |
| 20 | `asyncio.run_coroutine_threadsafe` → MCP SDK `session.call_tool` | bg thread loop |

**Critical defects on A1**
- **Step 10 is the real routing decision.** If the resolved manifest came from `nexora.capability_registry` (i.e. a `mcp.<x>` namespace), `target_type` is `LOCAL` or `REMOTE`, never `CONNECTOR` — so an `mcp.tavily` call routes to `LocalToolExecutor` or to a `REMOTE` executor that `GenerationRuntime` never registers. Live DB confirms: `mcp.tavily` → `supports_local=t, supports_remote=f`; `mcp.penpot` → `supports_local=f, supports_remote=t`. **`mcp.penpot` through the canonical router returns `Executor not found for ExecutionTargetType.REMOTE`.**
- **Step 8 ordering hazard.** For a namespace matching both a registry row and a discovered tool, the registry row wins (appended first at `repository.py:53` before the MCP block at `:90`).
- Step 3/9 mean the router provides **no** security value today.

**A2 — via direct dispatch** (what actually runs in production)

```
nexora.provider.tavily.execute(request)          models/tavily_provider.py
  → ConnectorPlatformBootstrap.get_instance()
  → bootstrap.connector_runtime.dispatch(exec_req)   line 44
      connector_id hardcoded "tavily_mcp" (line 39)
      capability_namespace hardcoded "tools.call" (line 33)
  → [steps 15-20 above]
```
A2 skips steps 2-14 entirely: no resolution, no policy, no credential injection hook, no `request_context` plumbing.

### 3.2 Path B — Health check

```
ConnectorRuntime health / lifecycle
  → McpHealthCheck.check_health()            connectors/mcp/health.py
      → self.transport.list_tools()          # GLOBAL transport, direct
      → except Exception: return False       # all errors swallowed
```
- Bypasses `McpProvider` → no namespace validation, no session binding, no allowlist enforcement.
- For a `session_binding='request_context'` connector, health probes the **global** transport, which may be unauthenticated relative to session-bound calls. Health can be green while every real session call fails (and vice versa).
- Additionally, `bootstrap._startup_reconciliation` force-writes `'health_status': 'healthy'` at line 242 **before any probe runs** — so `health_status=healthy` for all 5 live connectors is not evidence of a successful probe.

### 3.3 Path C — Capability discovery

```
action_discover_mcp_capabilities  (models/connector/nexora_connector.py:168)
  → triple-fallback runtime resolution (:183-190)
  → McpCapabilityDiscoveryService(runtime, env).discover(connector)
      → self._runtime.dispatch(ConnectorExecutionRequest('tools.list'))   # DIRECT
      → _logger.info(f"DISCOVERY RESULT RAW: ... data={result.data} ...")  # :99-101
      → _replace_discovered_tools: search(...).unlink() then create(...)   # :147-181
  → on exception: raise UserError(... traceback.format_exc())              # :196
```
- Works **because** it bypasses `ConnectorExecutionTarget._build_request`.
- `_replace_discovered_tools` is destructive full-replace, not a diff. A transient partial `tools.list` permanently drops rows, which in turn breaks Path A1 resolution for those tools (step 7).
- Live result: 67 discovered tools total (context7 2, firecrawl 27, github 29, penpot 4, tavily 5). Penpot's 4: `execute_code`, `export_shape`, `high_level_overview`, `penpot_api_info`.

### 3.4 Path D — Session-bound execution

```
McpProvider._tools_call(params, context)
  → _get_active_transport(context)                         provider.py:21
      if session_binding == 'none' or not pool: -> global_transport
      if session_binding_field not in allowed_request_context_fields:
          raise FORBIDDEN_CONTEXT_FIELD
      session_identity = context.request_context.get(field)
      if not session_identity: raise MISSING_SESSION_IDENTITY
      → SessionTransportPool.get_transport(session_identity)   pool.py:23
          h = sha256(session_identity)
          with lock: evict_expired; if hit and connected -> refresh ts, return
          (outside lock) TransportBinding(location,name,value) ; McpTransport(...) ; connect()
          with lock: double-check race; store (transport, now)
```
- **Live state: this path is dormant.** All 5 connectors have `session_binding='none'`, so no pool is ever constructed (`connector.py:36`). Penpot's `allowed_request_context_fields_json=["userToken"]` is populated but unused for session binding — Penpot authenticates via the static `query`/`userToken` credential instead.
- Asymmetry: `_tools_list`, `_resources_list`, `_prompts_list` use `self.global_transport` unconditionally; only `_tools_call`, `_resources_read`, `_prompts_get` are session-aware.

### 3.5 Path E — Credential resolution

```
McpOnboardingService._build_mcp_configuration(connector)      mcp_onboarding_service.py:206
  → resolver.resolve_all_for_connector(connector_id)          :218
      → OdooCredentialResolver.resolve_all_for_connector      odoo_credential_resolver.py:110
          list keys with prefix f"{connector_id}:"
          for each -> OdooSecretsProvider.get_secret
              → _get_fernet()                                 odoo_secrets_provider.py:35
                  ir.config_parameter 'nexora_connector_secret_key'
                  else env NEXORA_CONNECTOR_SECRET_KEY
                  else RuntimeError SECRET_KEY_MISSING
                  (deliberately NOT cached — rotation-safe)
              → Fernet.decrypt  (InvalidToken -> generic RuntimeError)
  → if auth_location != 'none' and credential_key:  auth_secret = resolved[key]   :227
  → if transport == 'stdio':  env_vars.update(resolved_secrets)                    :242
  → allowlist JSON parse wrapped in `except Exception: pass`                       :234-238
  → McpConfiguration(...)  → McpConnector(...)  → McpTransport
      sse+query  -> QueryAuth(name, secret) -> url.copy_merge_params  transport.py:143/58
      sse+header -> headers[name] = f"{Scheme} {secret}"              transport.py:136-141
      stdio      -> StdioServerParameters(env=os.environ | config.env) transport.py:107
```
- **Over-resolution:** line 218 decrypts *every* credential for the connector even when only one is needed.
- **Over-injection:** line 242 injects *all* resolved secrets into the stdio subprocess environment regardless of whether the server needs them.
- Composite key scheme `"<connector_id>:<credential_key>"` confirmed. Live credential rows: `CONTEXT7_API_KEY`, `FIRECRAWL_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `PENPOT_API_KEY`, `TAVILY_API_KEY` — all `is_set=t`, all non-empty ciphertext. No orphan lowercase `penpot_api_key` remains (Phase 43.8 cleanup verified).

---

## 4. Configuration Model

### 4.1 Live DB schema — `nexora_mcp_server_config` (23 columns)

`id, connector_id, timeout_seconds, create_uid, write_uid, command, working_directory, startup_policy, args_json, env_vars_json, last_test_result_json, last_tested_at, create_date, write_date, transport_type, authentication_location, authentication_name, authentication_scheme, credential_key, allowed_request_context_fields_json, session_binding, session_binding_field, session_binding_location`

- Column prefix is **`authentication_*`**, not `auth_*`. The dataclass uses `auth_*`. The rename happens in `_build_mcp_configuration`.
- There is **no `enabled`** column and **no `credential_delivery`** column on this table.

### 4.2 Runtime configuration object — `McpConfiguration` (`configuration.py`, 47 lines)

Fields: `command`, `transport`, `args`, `env`, `trace_file`, `allowed_request_context_fields`, `auth_location`, `auth_name`, `auth_scheme`, `auth_secret`, `session_binding`, `session_binding_field`, `session_binding_location`.

**Three DB columns never reach the runtime:**

| DB column | Live values | Reaches `McpConfiguration`? | Effect |
|---|---|---|---|
| `timeout_seconds` | `60` for all 5 | **No** | `McpTransport.connect()` hardcodes `ready_future.result(timeout=60.0)` (`transport.py:187`); `_run_sync` default `60.0` (`:210`). Coincidentally equal today → silently ignored, not visibly broken. |
| `startup_policy` | `lazy` for all 5 | **No** | No eager/lazy distinction exists in code. Column is decorative. |
| `working_directory` | set only for `penpot_mcp` (`C:/Users/.../packages/server`) | **No** | Never applied as subprocess cwd. For Penpot (transport=`sse`) it is meaningless anyway — leftover from an earlier stdio attempt. |

`__post_init__` enforces stdio arg tokenization via `shlex` and rejects `..` path traversal.

### 4.3 Declarative seeds vs live DB

| Connector | Seed XML | `ir_model_data` xmlid | Live `command` | Live `args_json` |
|---|---|---|---|---|
| `penpot_mcp` | `data/connector_penpot_data.xml` | `connector_penpot_mcp` (id 41), `config_penpot_mcp` (33), `credential_penpot_api_key` (30) | `http://localhost:9001/mcp/sse` | `[]` |
| `tavily_mcp` | `data/connector_tavily_data.xml` | `connector_tavily_mcp` (39), `config_tavily_mcp` (31), `credential_tavily_api_key` (32) | `npx.cmd` | `["-y","--quiet","tavily-mcp"]` |
| `firecrawl_mcp` | `data/connector_firecrawl_data.xml` | `connector_firecrawl_mcp` (63), `config_firecrawl_mcp` (55) | `npx` | `["-y","firecrawl-mcp"]` |
| `context7_mcp` | **none** | **none** | `npx.cmd` | `["-y","--quiet","@upstash/context7-mcp"]` |
| `github_mcp` | **none** | **none** | `docker` | `["run","-i","--rm","-e","GITHUB_PERSONAL_ACCESS_TOKEN","-e","GITHUB_READ_ONLY=1","ghcr.io/github/github-mcp-server"]` |

- `firecrawl_mcp` has a config xmlid but **no credential xmlid**, yet `FIRECRAWL_API_KEY` exists in the DB → credential is manually-created, undeclared, and would not survive a clean rebuild.
- `firecrawl` uses bare `npx` while `context7`/`tavily` use `npx.cmd`. On Windows this is an inconsistency that only works because `npx` resolves via PATHEXT in the spawned shell context.
- `context7_mcp` and `github_mcp` are entirely imperative — invisible to module install/upgrade.
- `pre-migrate.py` adopts exactly 6 xmlids (penpot + tavily families). `firecrawl` was adopted separately/manually; `context7`/`github` never.
- `github_mcp` requires the `ghcr.io/github/github-mcp-server` container. `docker ps` shows the github-mcp container is **not running** (previously observed `modest_shirley`, `Exited (0)`), yet the connector reports `state=running, health_status=healthy` — direct proof that `health_status` is not probe-derived (see §3.2).

---

## 5. Authentication Matrix

Authentication is expressed by three orthogonal DB columns and resolved into three dataclass fields plus a secret:

| Layer | Field | Source |
|---|---|---|
| Where | `authentication_location` → `auth_location` | `nexora_mcp_server_config` |
| What name | `authentication_name` → `auth_name` | `nexora_mcp_server_config` |
| How wrapped | `authentication_scheme` → `auth_scheme` | `nexora_mcp_server_config` |
| Secret value | `auth_secret` | resolved at runtime from `nexora_mcp_credential.encrypted_value` via `credential_key` |

### 5.1 The single generic implementation

All authentication is applied in exactly one place — `transport.py:135-143`, inside `_build_sse_client_kwargs`-equivalent logic:

```python
if self.config.auth_location != 'none' and self.config.auth_name and self.config.auth_secret:
    if self.config.auth_location == 'header':
        auth_val = self.config.auth_secret
        if self.config.auth_scheme and self.config.auth_scheme != 'none':
            scheme = self.config.auth_scheme.capitalize()
            auth_val = f"{scheme} {auth_val}"
        headers[self.config.auth_name] = auth_val
    elif self.config.auth_location == 'query':
        auth = QueryAuth(self.config.auth_name, self.config.auth_secret)
```

There is **no connector-specific auth code anywhere** in `services/connector`. This is the one part of the platform that is genuinely generic and correct. Verified by grep: no occurrence of `penpot`/`tavily`/`github` inside `services/connector/connectors/mcp/`.

### 5.2 Mode-by-mode audit

| # | Mode | Declared in schema? | Implemented? | Live users | Verdict |
|---|---|---|---|---|---|
| 1 | `none` (no auth) | Yes | Yes — guard short-circuits at `transport.py:135` | `context7_mcp`, `firecrawl_mcp`, `github_mcp`, `tavily_mcp` (4/5) | **Correct.** But see §5.3 — these four *do* authenticate, just not through this path. |
| 2 | `header` + scheme `bearer` | Yes | Yes — `f"Bearer {secret}"` | none | **Implemented, unexercised.** Was Penpot's setting before Phase 43.8. |
| 3 | `header` + scheme `none` (raw token) | Yes | Yes — header set verbatim | none | **Implemented, unexercised.** |
| 4 | `header` + scheme `basic` | Yes (`auth_scheme` is free text) | **Partially** — produces `f"Basic {secret}"` without base64 encoding `user:pass` | none | **Latent defect.** `capitalize()` yields the right word but no RFC 7617 encoding. Would silently fail. |
| 5 | `query` + scheme `none` | Yes | Yes — `QueryAuth(httpx.Auth)` merges via `request.url.copy_merge_params` | `penpot_mcp` | **Correct and live-verified** (Phase 43.8). |
| 6 | `env` / stdio environment injection | **Not** as an `auth_location` value | Yes, but **out of band** — see §5.3 | 4 stdio connectors | **Architecturally undeclared.** |
| 7 | mTLS / client certificate | No | No | none | **Absent.** No `httpx` `cert=` or `verify=` plumbing anywhere. |

### 5.3 CRITICAL FINDING — a second, undeclared authentication path

The four stdio connectors all record `authentication_location = 'none'` yet all have populated credentials (`CONTEXT7_API_KEY`, `FIRECRAWL_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `TAVILY_API_KEY`, all `is_set=t`). They authenticate through a completely different mechanism in `mcp_onboarding_service.py:206-257`:

```
line 218:  resolved = resolver.resolve_all_for_connector(connector)   # decrypts EVERY credential
line 227:  auth_secret = resolved.get(config.credential_key)          # only the named one
line 242:  env_vars.update(resolved_secrets)                          # ALL of them, into subprocess env
```

Consequences:

1. **Two authentication paths exist**, violating the single-canonical-path principle:
   - Declared path: `auth_location`/`auth_name`/`auth_scheme` → HTTP header or query param (SSE only).
   - Undeclared path: *every* credential of the connector, keyed by its `credential_key` string, dumped wholesale into the child process environment (stdio only).
2. The undeclared path is **not modelled** — nothing in the schema says "this credential is delivered as env var `X`". It works only because the credential key coincidentally equals the env var name the upstream MCP server expects (`TAVILY_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, …). This is an implicit naming contract with no validation and no error if it is wrong.
3. It is **over-broad**: `resolve_all_for_connector` + `env_vars.update(resolved_secrets)` injects all credentials, not the one required. Today each connector has exactly one credential, so the blast radius is zero — but the design is least-privilege-violating by construction.
4. `env_vars_json` in the DB is `{}` for all 5 connectors, so 100% of the stdio environment comes from this runtime injection plus `os.environ.copy()` (`transport.py:102-111`). The effective child environment is therefore **not** auditable from configuration alone.
5. `github_mcp`'s args pass `-e GITHUB_PERSONAL_ACCESS_TOKEN` (name-only form), which requires the variable to be present in the *Docker client's* environment. It is present only because of step 3. Correct by accident.

### 5.4 Silent-failure surface

`mcp_onboarding_service.py:234-238` wraps credential resolution in a bare `except Exception: pass`. A decryption failure (wrong `nexora_connector_secret_key`, corrupt ciphertext, rotated Fernet key) therefore produces a transport with `auth_secret = None`, which then hits the `and self.config.auth_secret` guard at `transport.py:135` and connects **unauthenticated**. The failure mode is a 401/403 from the remote server surfacing as a generic transport error, with no indication that the cause was credential resolution.

### 5.5 Token hygiene

Verified by inspection of every logging call in `services/connector`:

- No `_logger` call anywhere interpolates `auth_secret`, `encrypted_value`, or a resolved credential.
- `pool.py:83` logs only `h[:8]` of the SHA-256 session hash.
- `QueryAuth` places the token in the URL query string. This is the one structural exposure: any `httpx` debug logging, proxy access log, or exception repr that includes the request URL will contain the Penpot token. Currently no such logging is enabled, but the risk is inherent to mode 5 and cannot be removed without server-side support for header auth.
- `TraceSendStream`/`TraceReceiveStream` (`transport.py:10-35`) write **every MCP wire frame verbatim** to `config.trace_file`. If a tool call carries a secret in its arguments, it lands in that file in plaintext. `trace_file` is not set for any live connector, so this is dormant — but it is an unguarded plaintext sink with no redaction.

### 5.6 Authentication verdict

| Aspect | Status |
|---|---|
| Generic SSE auth (header/query) | **Sound.** One implementation, no connector-specific branches. |
| stdio auth | **Undeclared parallel path.** Works, but unmodelled, over-broad, and silently degrades. |
| `basic` scheme | **Latent defect** — no base64. |
| mTLS | Not supported. |
| Failure visibility | **Poor** — credential failure is indistinguishable from network failure. |

---

## 6. Transport Matrix

`McpTransport` (`transport.py`, 266 lines) is the only transport implementation on the canonical path. `transport_type` is a DB free-text column; the code branches on exactly two values.

### 6.1 Matrix

| # | Transport | Recognised by `McpTransport`? | SDK primitive | Live users | Verdict |
|---|---|---|---|---|---|
| 1 | `stdio` | **Yes** | `mcp.client.stdio.stdio_client` + `StdioServerParameters` | `context7_mcp`, `firecrawl_mcp`, `github_mcp`, `tavily_mcp` | **Working.** |
| 2 | `sse` | **Yes** | `mcp.client.sse.sse_client` | `penpot_mcp` | **Working, live-verified.** |
| 3 | `streamable_http` (MCP 2025-03-26 spec transport) | **No** | `mcp.client.streamable_http.streamablehttp_client` exists in the installed SDK | none | **Not implemented.** `sse` is used as a stand-in; Penpot's endpoint happens to be `/mcp/sse`, so this has not yet mattered. Any modern MCP server that only offers Streamable HTTP is unreachable. |
| 4 | `websocket` | **No** | `mcp.client.websocket.websocket_client` available | none | **Not implemented.** |
| 5 | HTTP/1 plain JSON-RPC POST | **No** | n/a | none | Not part of MCP spec; correctly absent. |
| 6 | In-process / local (no transport) | **No** — but conceptually occupied by `LocalToolExecutor` | n/a | 5 `mcp.tool.*` registry rows | **Divergent path.** Local capabilities never touch `McpTransport`; they go through `executors/local.py`, which returns a **mock success** when `tool_registry is None` (`local.py:37`). |

**Unrecognised-value behaviour:** if `transport_type` is anything other than `stdio` or `sse`, the branch falls through and no client context manager is entered. There is **no explicit `else: raise UnsupportedTransport`**. This is a fail-silent path.

### 6.2 Transport lifecycle

| Question | Answer |
|---|---|
| Who creates it | `McpConnector.__init__` → `McpTransport(mcp_config)` (`connector.py:33`), direct construction, bypassing `ConnectorFactory` (whose `transport_factory` is dead — `connector_factory.py:47-51`). |
| Who owns it | `McpConnector` holds it as `self.transport`; `McpProvider` receives it as `global_transport`; `McpHealthCheck` receives the same instance (`connector.py:40`). Three references, one object. |
| Who destroys it | `McpConnector.shutdown()` → `transport.disconnect()`, plus `_pool.shutdown_all()` if a pool exists. Also `ConnectorDispatcher._execute_on_connector` evicts and shuts down the connector on **any** exception (`dispatcher.py:215-260`). |
| Scope | One global transport per connector instance, cached in `dispatcher._active_connectors` (`dispatcher.py:57`). Effectively per-connector singleton for the process lifetime. |
| State held | `self._session` (`ClientSession`), `self._loop` (asyncio loop in a dedicated thread), `self._thread`, `self._exit_stack`, connection flag. |
| Thread model | Dedicated background thread runs an asyncio loop; `WindowsSelectorEventLoopPolicy` forced on win32; sync callers bridge via `asyncio.run_coroutine_threadsafe`. |
| Timeouts | Hardcoded `60.0` in two places (`transport.py:187`, `:210`). DB `timeout_seconds` ignored (§4.2). |

### 6.3 Defects

1. **Post-handshake failures are swallowed.** `transport.py:172-176`: if `ready_future.done()` is already true, the exception is only logged (`_logger.error(f"Error in MCP connection: {e}")`) and never propagated. A subprocess that dies after a successful handshake leaves a transport that reports connected and fails every subsequent call with an opaque error.
2. **No transport-level retry or reconnect.** Recovery is delegated entirely to `ConnectorDispatcher` evict-and-rebuild, which discards the connector object (and therefore any pool) on a single failure.
3. **`stdio` environment is `os.environ.copy()` + overrides** (`transport.py:102-111`). The child inherits the entire Odoo process environment, including unrelated secrets. Least-privilege violation, and it is what makes `github_mcp`'s `-e VAR` form work.
4. **`import httpx` is load-bearing and marked as such.** `transport.py:45-48` carries a deliberate comment: the MCP SDK does `isinstance(auth, httpx.Auth)`, so removing the import breaks query auth. Correctly documented; retain the comment.
5. **Trace streams are unconditional wrappers.** `TraceSendStream`/`TraceReceiveStream` are always constructed when `trace_file` is set, with no size cap, no rotation, and no redaction.
6. **Duplicate transport implementation exists.** `services/source_framework/transport/mcp_transport.py` emits a `DeprecationWarning` at line 6 and is a genuine legacy parallel implementation. Not on the canonical path; candidate for removal (§15).
7. **`connector_components.py:89` compensates for a transport signature mismatch** with a `TypeError` arity fallback on `transport.connect`. This is a shim covering two incompatible `connect()` signatures across the two transport implementations.

---

## 7. SessionTransportPool Audit

File: `services/connector/connectors/mcp/pool.py` (94 lines). **Not modified by this audit.**

### 7.1 The 15 audited attributes

| # | Attribute | Finding |
|---|---|---|
| 1 | **Purpose** | Provide one `McpTransport` per distinct end-user session, so a per-user token (e.g. a Penpot `userToken` taken from `request_context`) never leaks across users. Realises ADR-0067. |
| 2 | **Who constructs it** | `McpConnector.__init__`, **conditionally**: `if mcp_config.session_binding == 'request_context'` (`connector.py:36-37`). Otherwise `pool` is `None`. |
| 3 | **Who owns it** | `McpConnector` (`self._pool`) and `McpProvider` (constructor arg, `connector.py:39`). Two references, one object. |
| 4 | **Who destroys it** | `McpConnector.shutdown()` → `pool.shutdown_all()` (`pool.py:86-94`). Also implicitly whenever `ConnectorDispatcher` evicts the connector on any error (`dispatcher.py:215-260`) — the pool and all its transports are discarded wholesale. |
| 5 | **Cache key** | `hashlib.sha256` over the session-identifying value. Only `h[:8]` is ever logged (`pool.py:83`). Correct isolation primitive. |
| 6 | **Scope** | Per-connector-instance. Since connectors are cached in `dispatcher._active_connectors`, effectively per-connector process-lifetime. |
| 7 | **TTL** | `ttl_seconds = 600` **hardcoded** at `pool.py:21`. Not configurable, not surfaced in `McpConfiguration` or the DB schema. |
| 8 | **Eviction trigger** | `_evict_expired_locked()` is called **only** from `get_transport` (`pool.py:34`). |
| 9 | **Background reaper** | **None.** There is no timer, no cron, no thread. If no request arrives, expired transports (and their subprocesses / SSE connections) are never reclaimed. |
| 10 | **Max size** | **None.** Unbounded. N distinct sessions → N live transports → N subprocesses or N SSE connections. |
| 11 | **Thread safety** | A lock guards the map. Transport construction happens **outside** the lock (`pool.py:44-51`) with a double-check on re-acquire (`:54-67`); a loser thread discards its freshly built transport. Correct but wasteful — a duplicate transport is fully connected then thrown away. |
| 12 | **State maintained** | `dict[hash] → (transport, last_used_ts)`; the lock; the TTL constant. |
| 13 | **Who reads from it** | Only `McpProvider._get_active_transport` (`provider.py:21-34`), which is called by exactly three methods: `_tools_call` (`:87`), `_resources_read` (`:99`), `_prompts_get` (`:112`). |
| 14 | **Duplicate logic elsewhere** | None. This is the only pooling implementation in the repo. |
| 15 | **Live usage** | **Zero.** All 5 live connectors have `session_binding = 'none'`, therefore `McpConnector` never constructs a pool, therefore `_pool is None` for every connector in the system. |

### 7.2 The dormancy finding

The pool is **completely dead code at runtime today**, but it is *correct* dead code — it is the mechanism required for any multi-tenant per-user-token connector. This is the distinction between "dead infrastructure to remove" and "dormant infrastructure to keep": it has a named architectural owner (ADR-0067), a single implementation, no duplication, and a clear activation condition.

Consequence chain, verified:
```
all 5 connectors: session_binding = 'none'
  → connector.py:36-37 condition False
    → self._pool = None
      → McpProvider.pool = None
        → _get_active_transport() falls back to global_transport
          → SessionTransportPool never instantiated in this process
```

### 7.3 Correctness gaps (for later, not now)

| Gap | Detail | Severity |
|---|---|---|
| No background reaper | TTL only enforced on access. Idle expired transports hold subprocesses/sockets indefinitely. | P1 when activated |
| Unbounded size | No max pool size, no LRU. A burst of distinct sessions can exhaust process/FD limits. | P1 when activated |
| TTL hardcoded | `600` is not configurable per connector. | P2 |
| Construction outside lock | Duplicate connect work under contention; the loser's transport is discarded — is `disconnect()` called on it? Verify at `pool.py:54-67`. If not, that is a leak. | P1 when activated |
| Whole-pool destruction on single error | `dispatcher._execute_on_connector` evicts the connector on any exception, destroying **all** sessions' transports because one session failed. Cross-session blast radius. | P1 when activated |
| ADR naming drift | ADR-0067 calls it `McpTransportPool`; the class is `SessionTransportPool`. ADR is still status **Proposed**. | P3 |

### 7.4 Verdict

**KEEP UNCHANGED.** The pool is architecturally correct, singular, and non-duplicative. It is dormant, not dead. Phase 44.2 must not remove it. Its correctness gaps only become live when a connector sets `session_binding='request_context'`; that activation must be gated behind fixing the reaper and the max-size bound.

---

## 8. Credential Security Audit

**No secret values were printed, logged, or written during this audit.** Only lengths, key names, and `is_set` flags were read.

### 8.1 Storage

| Aspect | Finding |
|---|---|
| Table | `nexora_mcp_credential`, 13 columns: `id, connector_id, created_by, create_uid, write_uid, credential_key, credential_type, description, encrypted_value, is_set, last_rotated_at, create_date, write_date` |
| At-rest encryption | Fernet (`cryptography`), via `odoo_secrets_provider.py:35-82` |
| Master key source | Odoo config `nexora_connector_secret_key` → fallback env `NEXORA_CONNECTOR_SECRET_KEY` |
| Composite key scheme | `"<connector_id>:<credential_key>"` |
| Fernet instance caching | **Deliberately uncached** (`odoo_secrets_provider.py:35-82`) — a fresh `Fernet` per operation. Costs key-derivation per resolve; safe. |
| Live inventory | 5 credentials, all `is_set=t`: `CONTEXT7_API_KEY` (len 140), `FIRECRAWL_API_KEY` (140), `GITHUB_PERSONAL_ACCESS_TOKEN` (204), `PENPOT_API_KEY` (548), `TAVILY_API_KEY` (164). Lengths are ciphertext lengths, consistent with Fernet-wrapped tokens. |

### 8.2 P0 — Master key stored in plaintext on disk

`d:\ODOO\configs\dev.conf` contains `nexora_connector_secret_key` in **plaintext**. Anyone with read access to the config file can decrypt every credential in the database. The encryption-at-rest guarantee is therefore only meaningful against a database-only compromise, not a filesystem compromise.

This is arguably acceptable for a dev config, but it must be explicitly documented as such, and the production deployment story (env var, secret manager, or KMS) must be stated. Currently no such statement exists in any ADR or report.

### 8.3 P0 — Second plaintext secret in the database

`ir_config_parameter` contains `nexora.nvidia.api_key` **in plaintext**. This bypasses the entire `nexora_mcp_credential` + Fernet subsystem. `ir.config_parameter` is readable by any user with settings access and is included in database dumps without special handling.

This is a genuine parallel credential path — exactly the class of duplication this audit was asked to find.

### 8.4 Resolution path (Path E, condensed)

```
mcp_onboarding_service._build_mcp_configuration
  → OdooCredentialResolver.resolve_all_for_connector(connector)      # :218
      → OdooSecretsProvider.get(f"{connector_id}:{credential_key}")
          → Fernet(master_key).decrypt(encrypted_value)
  → auth_secret = resolved.get(config.credential_key)                # :227
  → env_vars.update(resolved_secrets)                                # :242
  → McpConfiguration(auth_secret=…, env=env_vars)
```

### 8.5 Leak-surface inventory

| # | Surface | Status | Note |
|---|---|---|---|
| 1 | `_logger` calls in `services/connector` | **Clean** | Grep-verified: no interpolation of `auth_secret`, `encrypted_value`, or resolved values. |
| 2 | Pool logging | **Clean** | `pool.py:83` logs `h[:8]` of a SHA-256 hash only. |
| 3 | URL query string (`QueryAuth`) | **Structural exposure** | Penpot token travels in the URL. Any `httpx`/proxy/exception-repr logging of the URL exposes it. Inherent to `auth_location='query'`; only mitigable by redacting URLs in error paths. |
| 4 | `trace_file` wire dump | **Dormant sink** | `transport.py:10-35` writes every frame verbatim, unredacted, uncapped. Not enabled on any live connector. |
| 5 | Child-process environment | **Over-broad** | `os.environ.copy()` + all resolved credentials (§5.3). Visible to anything that can read `/proc` or Windows process env. |
| 6 | `capability_discovery.py:99-101` | **Raw payload INFO log** | Logs the raw discovery payload at INFO. Discovery payloads do not currently contain secrets, but the log is unfiltered. |
| 7 | `connection_tester.py:141` | **Raw payload INFO log** | Same pattern. |
| 8 | `connection_tester.py:200,225-241` | **Traceback into user-facing message, then persisted** | Full traceback is put into the user message and written to `last_test_result_json`. If a traceback frame ever contains a URL with a query token, it is persisted to the DB and shown in the UI. |
| 9 | `nexora_connector.action_discover_mcp_capabilities` (`:196`) | **Full traceback in `UserError`** | Same class of exposure, surfaced directly to the user. |
| 10 | `connector_runtime.py` `print()` × 6 + `traceback.print_exc()` | **Unstructured stdout** | Lines 200, 206, 210, 214, 219, 222, 223. Writes to the Odoo process stdout, bypassing the logging framework and any redaction/level filtering. No secret currently reaches these, but they are an unmanaged output channel. |

### 8.6 Validation defect

`odoo_credential_resolver.validate()` (`:79-108`) performs a **suffix scan** to decide whether a value looks like a credential. This produces false positives on any key ending in a matched suffix. It is heuristic validation masquerading as a security control.

### 8.7 Error opacity

`odoo_secrets_provider.py` converts Fernet `InvalidToken` into a generic `RuntimeError`. Combined with the bare `except Exception: pass` at `mcp_onboarding_service.py:234-238`, a wrong master key produces: no log, no error, no credential, and an unauthenticated connection attempt. This is the single worst observability defect in the credential subsystem.

### 8.8 Credential verdict

| Aspect | Status |
|---|---|
| Encryption at rest | **Implemented correctly** (Fernet, per-connector composite key). |
| Master key protection | **P0** — plaintext in `dev.conf`; no documented production story. |
| Parallel plaintext path | **P0** — `nexora.nvidia.api_key` in `ir_config_parameter`. |
| Secret logging | **Clean** in the connector subsystem. |
| Secret in URL | **Accepted risk** for Penpot; needs URL redaction in error paths. |
| Least privilege | **Violated** — all credentials injected into every child process. |
| Failure visibility | **P1** — decryption failure is silent. |
| `trace_file` | **P2** — dormant unredacted plaintext sink. |

---

## 9. Lifecycle Audit

### 9.1 The lifecycle owners

| Concern | Owner | File |
|---|---|---|
| Process-level bootstrap | `ConnectorPlatformBootstrap` (class attr `_instance` + `get_instance()`, `:41`, `:49-54`) | `services/connector/integration/bootstrap.py` |
| Runtime state machine | `ConnectorRuntime` | `services/connector/runtime/connector_runtime.py` (656 lines) |
| Connector instantiation + caching | `ConnectorDispatcher._active_connectors` (`:57`) | `services/connector/runtime/dispatcher.py` |
| Persistence of state | `OdooConnectorPersistenceAdapter._do_write` | `services/connector/registry/persistence/odoo_adapter.py` |
| DB↔runtime reconciliation | `runtime_synchronizer.py` (173 lines) | `services/connector/…/runtime_synchronizer.py` |

### 9.2 Startup sequence (actual)

```
__init__.py post_init_provider_platform (:21-24)
  → execute_discovery()
  → execute_bootstrap()                       # capabilities/bootstrap.py, writes capability_registry

__init__.py post_load_provider_platform (:30-35)
  → ConnectorPlatformBootstrap.get_instance().bootstrap(None)
      → _register_executor_with_ucel()        # :184-190 — body is `pass  # stub for brevity` → DEAD
      → _startup_reconciliation()             # :205-262
           line 242: writes {'health_status': 'healthy'} for every enabled connector
                     BEFORE any probe is performed
  ↑ wrapped in try/except that only logs a warning
```

### 9.3 P0 — `health_status` is fabricated, not measured

`bootstrap.py:242` force-writes `'health_status': 'healthy'` during startup reconciliation, before any transport is created and before any probe runs. Live proof:

- `github_mcp` reports `state=running, health_status=healthy`.
- `docker ps` shows **no** `ghcr.io/github/github-mcp-server` container running.
- Therefore the connector cannot possibly be healthy, and the field is asserting a fact it has not verified.

All 5 connectors report `state=running, health_status=healthy`. Given four of the five have corrupt manifests (§9.6) and zero capability-index rows, this uniform green status is meaningless. **The health subsystem currently provides false assurance, which is worse than no assurance.**

### 9.4 Health-check implementation

`connectors/mcp/health.py` (20 lines): `check_health()` calls `self.transport.list_tools()` directly and **swallows all exceptions**. So even when a probe *is* run, a failure is indistinguishable from success at the call site unless the return value is checked. Combined with §9.3, `health_status` has no reliable producer.

### 9.5 State machine defects

| # | Defect | Evidence |
|---|---|---|
| 1 | **6 raw `print()` + `traceback.print_exc()`** in the transition handler | `connector_runtime.py:200,206,210,214,219,222,223` (`_on_lifecycle_transition`, `:192-223`) — grep-confirmed |
| 2 | **Persistence key inconsistency** | `_on_health_change` writes `{'state': …}`; `_on_lifecycle_transition` writes `{'lifecycle_state': …}`; `odoo_adapter` recognises **only** `lifecycle_state`. Health-driven state changes are therefore silently dropped. |
| 3 | **Undefined type annotations** | `resolve_capability` (`:229`) annotates `Optional[ConnectorCapability]` — never imported. `handle_event` (`:584`) references `ConnectorEvent` — undefined. Both are latent `NameError`s on any code path that evaluates annotations. |
| 4 | **`degraded` is an orphan state** | `runtime_synchronizer.py` places `'degraded'` in **neither** `_RUNNING_STATES` nor `_TERMINAL_STATES`. A degraded connector is invisible to both reconciliation branches. |
| 5 | **Synchronizer reaches into privates** | `runtime_synchronizer.py:137` touches `_runtime` directly, breaking the encapsulation boundary it is supposed to reconcile across. |
| 6 | **Unprotected connector cache** | `dispatcher._active_connectors` (`:57`) has **no lock**. `_get_or_create_connector` (`:198-213`) is a check-then-act race: two concurrent requests can both construct a connector, both spawn a subprocess, and one is silently orphaned (leaked subprocess, no `shutdown()`). |
| 7 | **Evict-and-destroy on any exception** | `_execute_on_connector` (`:215-260`) catches any inner exception → evicts from cache → `shutdown()` → re-raises. A single transient tool error tears down the transport, the subprocess, and (when active) the entire session pool. |
| 8 | **Recovery debounce is `threading.Timer`-based** | Single-flight recovery, max 3 attempts. Timers are not tracked against Odoo worker shutdown; on graceful stop a pending timer can fire against a dead environment. |

### 9.6 P0 — The manifest-wipe mechanism

`odoo_adapter._do_write` (`:121-162`) performs a **full write** and at line 135 defaults the manifest:

```python
'manifest_json': data.get('manifest_json', '{}')
```

Any caller that writes a partial update without carrying `manifest_json` therefore **overwrites the stored manifest with `{}`**. Live damage, confirmed:

| Connector | `manifest_json` length | Content | Capability-index rows |
|---|---|---|---|
| `context7_mcp` | 2 | `{}` | 0 |
| `firecrawl_mcp` | 2 | `{}` | 0 |
| `github_mcp` | 16 | `{"broken": true}` | 0 |
| `penpot_mcp` | 792 | real manifest | 0 |
| `tavily_mcp` | 64 | `{"command":"python","args":["-c","import sys; sys.exit(1)"]}` | 0 |

Three distinct corruption signatures — `{}` (default-wipe), `{"broken": true}` (a test fixture that was persisted), and a Python-suicide stub (another test fixture) — prove that **test artefacts have leaked into the live database** and that the wipe path is routinely exercised.

`tavily_mcp`'s manifest literally instructs a subprocess to exit(1). It is not used because `command`/`args_json` on `nexora_mcp_server_config` are the fields actually read — which is itself the finding: the manifest is written but never authoritative.

### 9.7 P0 — The capability index is universally empty

`_rebuild_capability_index` (`connector_runtime.py:577-582`) rebuilds from `connector.manifest.capabilities` **only**. Since four manifests are wiped and the fifth's capabilities are not in the shape the rebuild expects, the result is **0 rows in `nexora_connector_capability` for every connector**.

Meanwhile `nexora_mcp_discovered_tool` holds **67 correctly discovered tools** (context7 2, firecrawl 27, github 29, penpot 4, tavily 5). So the platform *has* the capability data — in the wrong table, unreachable by the runtime's own index.

`nexora_connector_capability` is therefore **dead infrastructure that the runtime nonetheless depends on** for `resolve_capability`.

### 9.8 Shutdown

| Path | Behaviour |
|---|---|
| `McpConnector.shutdown()` | `transport.disconnect()` + `_pool.shutdown_all()` if present. Correct. |
| Dispatcher eviction | Calls `shutdown()`. Correct. |
| Odoo worker termination | **No hook.** Nothing calls `shutdown()` on process exit. `_active_connectors` is a plain dict with no `atexit`/registry teardown → stdio subprocesses can outlive the Odoo worker. |
| Race-loser connectors (§9.5 #6) | Never shut down → leaked subprocess. |

### 9.9 Lifecycle verdict

The lifecycle layer is the **least sound** part of the platform: it fabricates health, wipes manifests it is meant to preserve, maintains an index that is always empty, races on its own cache, destroys transports on transient errors, and prints to stdout. Every P0 in §16 except the credential ones originates here.

---

## 10. Discovery and Capability Audit

### 10.1 Two discovery mechanisms exist

| Mechanism | Writes to | Trigger | Result today |
|---|---|---|---|
| **A — MCP tool discovery** | `nexora_mcp_discovered_tool` | `capability_discovery.py`, via `self._runtime.dispatch` | **Works.** 67 rows, accurate tool names. |
| **B — Runtime capability index** | `nexora_connector_capability` | `connector_runtime._rebuild_capability_index` from `connector.manifest.capabilities` | **Broken.** 0 rows for all 5 connectors (§9.7). |
| **C — Capability registry** | `nexora_capability_registry` | `capabilities/bootstrap.py` from `config/mcp_registry.json` | **Works, but stale** (§12). 17 rows. |

Three tables, three writers, three different notions of "capability", none reconciled with the others. This is the clearest instance of parallel architecture in the platform.

### 10.2 Discovery destructiveness

`capability_discovery.py:147-181` implements refresh as **`unlink()` then `create()`**. Consequences:
- All `nexora_mcp_discovered_tool` IDs change on every discovery run.
- Any FK or stored reference to a discovered-tool ID is invalidated.
- A failure between unlink and create leaves the connector with zero tools.
- No diffing, so no way to detect that a remote server *removed* a tool versus discovery having failed.

### 10.3 `_DEFAULT_MCP_CAPABILITIES` — the generic-6 assumption

`mcp_onboarding_service.py:40-41` assigns the **same 6 generic namespaces** to every connector regardless of what it supports:

`tools.list`, `tools.call`, `resources.list`, `resources.read`, `prompts.list`, `prompts.get`

`McpProvider` (`provider.py`) implements **exactly** these 6 and returns `CAPABILITY_NOT_FOUND` for anything else. So the provider's surface is the MCP protocol surface, correctly.

### 10.4 The `tools.list` namespace defect — architectural analysis

**The mechanism.** `connector_executor._build_request` (`:114-150`), line 123:

```python
if '.' in namespace:
    connector_id, tool_name = namespace.split('.', 1)
```

This split is **unconditional** for any dotted namespace. Therefore:

| Input namespace | Interpreted as | Outcome |
|---|---|---|
| `penpot_mcp.export_shape` | connector `penpot_mcp`, tool `export_shape` | correct |
| `tools.list` | connector **`tools`**, tool **`list`** | `CONNECTOR_NOT_FOUND` |
| `tools.call` | connector `tools`, tool `call` | `CONNECTOR_NOT_FOUND` |
| `resources.read` | connector `resources`, tool `read` | `CONNECTOR_NOT_FOUND` |

**Why it has not broken everything.** `ConnectorDispatcher.initialize_and_verify` (`:276-322`) calls `tools.list` via `sdk_connector.execute(...)` **directly**, bypassing `_build_request` entirely. And `connector_runtime` carries an explicit escape hatch:

```python
_CAPABILITY_DISCOVERY_NAMESPACES = {'resources.list', 'prompts.list', 'tools.list'}   # :282
```

So the platform already contains **two independent workarounds** for the same defect, plus a third bypass in `capability_discovery.py` which dispatches through `self._runtime.dispatch`.

**The architectural question (not to be fixed here).** Two coherent contracts are possible:

| Option | Contract | Implication |
|---|---|---|
| **1 — Reserved protocol namespaces** | `tools.*`, `resources.*`, `prompts.*` are reserved MCP-protocol namespaces. `_build_request` must check a reserved-prefix set **before** splitting, and route protocol calls to the connector named in the request context rather than parsed from the namespace. | Requires the connector identity to be carried explicitly, not inferred. Removes all three workarounds. Least invasive to callers. |
| **2 — Fully qualified namespaces** | Every namespace must be `<connector_id>.<tool>` with no exceptions; protocol operations become `<connector_id>.tools.list` etc. and the split must be `rsplit`-aware or prefix-based. | Requires changing every call site including `_CAPABILITY_DISCOVERY_NAMESPACES`, `initialize_and_verify`, the three model-level providers, and the discovery service. More invasive, but eliminates ambiguity entirely. |

**Recommendation for Phase 44.2:** Option 1. It matches the MCP spec's own view (`tools/list` is a protocol method, not a tool), it is backward compatible with existing dotted tool namespaces, and it lets all three existing workarounds be deleted rather than multiplied. **Not implemented in 44.1.**

### 10.5 P0 — The routing contract is broken above the namespace issue

The namespace defect is a symptom. The systemic defect is in `services/capabilities`:

```
CapabilityRepository.get_manifests_by_namespace (repository.py:9-95)
   if r.supports_remote:  target_type = REMOTE
   elif r.supports_local: target_type = LOCAL
   else:                  target_type = REMOTE
   ...
   candidates.append(registry_manifest)         # line 53 — appended FIRST
   if '.' in namespace:                          # lines 56-90
       ... append CONNECTOR manifests            # the ONLY producer of CONNECTOR

CapabilityPolicyEngine.evaluate (policy.py)
   return CapabilityDescriptor(manifest=candidates[0])   # "pick first candidate"

UniversalCapabilityRouter.execute (router.py:54)
   self.executors.get(descriptor.manifest.target_type)
   → if missing: CapabilityResult(success=False, logs=["Executor not found for …"])
```

And `GenerationRuntime` (`generation_runtime.py:70-78`) registers **only**:
```
{ ExecutionTargetType.LOCAL: LocalToolExecutor(...) }        # always
{ ExecutionTargetType.CONNECTOR: ConnectorExecutionTarget }  # conditionally
```

`RemoteToolExecutor` is **imported** (`:49-51`) and **never registered**.

**Live consequence, proven from the DB:** `mcp.penpot` is the only registry row with `supports_local=f, supports_remote=t` → `target_type = REMOTE` → `executors.get(REMOTE)` → `None` → `router.py:55` returns `success=False, logs=["Executor not found for ExecutionTargetType.REMOTE"]`.

**And the ordering hazard:** because registry manifests are appended at line 53 *before* the MCP-connector block, `candidates[0]` favours the registry row. So even a correctly-formed `penpot_mcp.export_shape` call risks resolving to the REMOTE registry manifest rather than the CONNECTOR manifest — depending on whether the registry row's `capability_code` matches.

### 10.6 Additional discovery/capability defects

| # | Defect | Evidence |
|---|---|---|
| 1 | `RemoteToolExecutor` returns `success=True` unconditionally | `executors/remote.py` (12 lines) — ignores the transport response entirely. If it *were* registered, it would report success for every failure. |
| 2 | `LocalToolExecutor` returns mock success | `executors/local.py:37` → `CapabilityResult(success=True, result="Executed locally (mock)")` when `tool_registry is None`. And `tool_registry` is `None` whenever `odoo.http.request` is unavailable (`generation_runtime.py:54-58`, bare try/except) — i.e. in **every non-HTTP context** (cron, queue job, CLI, test). |
| 3 | `SecurityLayer` is a no-op | `security.py` (6 lines): `authorize` → `return True`; `inject_credentials` → `return context`. The router provides **zero** authorization. |
| 4 | `ExecutionScheduler` is a pass-through | `scheduler.py` (11 lines) → `self.strategy.execute(...)`. Comment admits "Implements queueing, limits, etc. Currently synchronous." No queueing, no limits, no concurrency control. |
| 5 | `FallbackStrategy` fallback branch is `pass` | `strategy.py` (14 lines) — dead branch. |
| 6 | `CapabilityResolver` consults a hardcoded 9-entry map | `resolver.py` — `mcp.eslint`, `mcp.playwright`, `mcp.search`, plus 6 `*_reviewer` entries. None correspond to a live connector. Logs "Triggering lazy installation via DependencyInstallerService…" |
| 7 | `router.py:48` `_reviewer` placeholder shortcut | A name-suffix special case short-circuits the executor lookup. Connector-specific hack in the generic router. |
| 8 | `CapabilityRepository._cache` is never invalidated | `repository.py:9` — first call populates it for the process lifetime. Any DB change to `nexora_capability_registry` is invisible until restart. |
| 9 | Three model-level dispatch bypasses | `models/tavily_provider.py:44`, `github_provider.py:49`, `context7_provider.py:43` — three near-identical direct `dispatch` calls that skip the router, the policy, the security layer and the executor entirely. |
| 10 | `nexora_connector.action_test_tool_execution` builds its own target | `models/connector/nexora_connector.py:139-166` — constructs `ConnectorExecutionTarget(runtime)` directly and hardcodes `namespace='tools.call'`, `name='echo'`. A fourth bypass. |
| 11 | `action_discover_mcp_capabilities` triple-fallback runtime resolution | `:183-190` — three successive attempts to obtain a runtime, indicating no single reliable accessor exists. |

### 10.7 Discovery/capability verdict

Tool discovery (mechanism A) is the only part that works. The capability *routing* contract is broken at three independent levels — namespace parsing, target-type derivation, and executor registration — and the platform compensates with at least four bypasses and two escape-hatch constant sets. Fixing the namespace split alone would not make `mcp.penpot` executable; the executor-registration and target-type-derivation defects must be addressed together.

---

## 11. Active MCP Inventory

Read-only from the live Odoo database. **5 connectors exist** — this was verified by an unfiltered `SELECT` on `nexora_connector`, not assumed.

### 11.1 Core inventory

| connector_id | transport | state | health | enabled | auth_loc | auth_name | auth_scheme | credential_key | session_binding | allowlist |
|---|---|---|---|---|---|---|---|---|---|---|
| `context7_mcp` | stdio | running | healthy | t | none | — | none | — | none | `[]` |
| `firecrawl_mcp` | stdio | running | healthy | t | none | — | none | — | none | `[]` |
| `github_mcp` | stdio | running | healthy | t | none | — | none | — | none | `[]` |
| `penpot_mcp` | sse | running | healthy | t | **query** | **userToken** | none | `PENPOT_API_KEY` | none | `["userToken"]` |
| `tavily_mcp` | stdio | running | healthy | t | none | — | none | — | none | `[]` |

All 5: `timeout_seconds=60`, `startup_policy=lazy` (both ignored — §4.2).

### 11.2 Launch configuration

| connector_id | `command` | `args_json` | `env_vars_json` | `working_directory` |
|---|---|---|---|---|
| `context7_mcp` | `npx.cmd` | `["-y","--quiet","@upstash/context7-mcp"]` | `{}` | — |
| `firecrawl_mcp` | `npx` | `["-y","firecrawl-mcp"]` | `{}` | — |
| `github_mcp` | `docker` | `["run","-i","--rm","-e","GITHUB_PERSONAL_ACCESS_TOKEN","-e","GITHUB_READ_ONLY=1","ghcr.io/github/github-mcp-server"]` | `{}` | — |
| `penpot_mcp` | `http://localhost:9001/mcp/sse` | `[]` | `{}` | `C:/Users/kusha/AppData/Roaming/npm/node_modules/@penpot/mcp/packages/server` |
| `tavily_mcp` | `npx.cmd` | `["-y","--quiet","tavily-mcp"]` | `{}` | — |

Notes:
- `env_vars_json` is `{}` for **all** connectors → 100% of stdio env comes from runtime injection (§5.3).
- `penpot_mcp.working_directory` is a leftover from a prior stdio attempt; meaningless for `sse` and never applied anyway.
- `firecrawl` uses bare `npx` where the other two use `npx.cmd` — inconsistent, works only via PATHEXT resolution.

### 11.3 Manifest and capability-index state

| connector_id | `manifest_json` len | manifest content | `nexora_connector_capability` rows | `nexora_mcp_discovered_tool` rows |
|---|---|---|---|---|
| `context7_mcp` | 2 | `{}` | **0** | 2 |
| `firecrawl_mcp` | 2 | `{}` | **0** | 27 |
| `github_mcp` | 16 | `{"broken": true}` | **0** | 29 |
| `penpot_mcp` | 792 | real manifest | **0** | 4 |
| `tavily_mcp` | 64 | `{"command":"python","args":["-c","import sys; sys.exit(1)"]}` | **0** | 5 |
| | | | **Total 0** | **Total 67** |

### 11.4 Discovered tools (67)

| connector | count | tools |
|---|---|---|
| `context7_mcp` | 2 | `query-docs`, `resolve-library-id` |
| `firecrawl_mcp` | 27 | (full crawl/scrape/extract/search surface) |
| `github_mcp` | 29 | (repo/issue/PR/search surface) |
| `penpot_mcp` | 4 | `execute_code`, `export_shape`, `high_level_overview`, `penpot_api_info` |
| `tavily_mcp` | 5 | `tavily_crawl`, `tavily_extract`, `tavily_map`, `tavily_research`, `tavily_search` |

### 11.5 Credentials

| `credential_key` | connector | ciphertext len | `is_set` |
|---|---|---|---|
| `CONTEXT7_API_KEY` | `context7_mcp` | 140 | t |
| `FIRECRAWL_API_KEY` | `firecrawl_mcp` | 140 | t |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | `github_mcp` | 204 | t |
| `PENPOT_API_KEY` | `penpot_mcp` | 548 | t |
| `TAVILY_API_KEY` | `tavily_mcp` | 164 | t |

No orphan credentials remain (the lowercase `penpot_api_key` orphan was removed in Phase 43.8 and is confirmed absent).

### 11.6 Live infrastructure cross-check (`docker ps`)

18 containers up ~11 hours:

| Relevant container | Ports | Bearing on the inventory |
|---|---|---|
| `compose-penpot-mcp-1` | 4401-4402 | A second Penpot MCP instance, **not** the one the connector points at. |
| `compose-penpot-frontend-1` | **9001→8080** | This is what `http://localhost:9001/mcp/sse` actually reaches. |
| `penpot-local-penpot-mcp-1` | — | A third Penpot MCP instance. |
| penpot backend / exporter / postgres / valkey / mailcatch | ×2 stacks | Two parallel Penpot deployments running simultaneously. |
| aivideo stack | — | Unrelated. |
| **github-mcp** | — | **Not running.** |

Two findings:
1. **`github_mcp` is `healthy` with no container** — see §9.3.
2. **Three Penpot MCP instances are running and the connector targets none of them directly**; it targets the frontend on 9001, which proxies. Ambiguity about which MCP instance actually serves requests. This should be pinned explicitly.
3. **Odoo itself is not running** at audit time — all connector state read is persisted state, not live in-process state. This is why `state=running` for all 5 is provably stale: no process exists to be running.

### 11.7 Inventory verdict

The DB reports 5/5 connectors fully operational. Cross-checked against reality: 0/5 have a valid capability index, 4/5 have corrupt manifests, 1/5 has no backing process, and the Odoo process that would own the "running" state does not exist. **The persisted connector state is not a trustworthy source of operational truth.**

---

## 12. Database ↔ Repository Drift

### 12.1 CORRECTION to a prior report — `mcp_registry.json` is authoritative, not informational

A prior phase report classified `config/mcp_registry.json` as "informational only". **This is wrong.** The chain is:

```
config/mcp_registry.json  (511 lines, 12 mcpServers)
  → services/capabilities/bootstrap.py::_parse_registry_manifests (:11-54)
       target_type = LOCAL if conf["transport"]=="stdio" else REMOTE
  → execute_bootstrap (:60-108)
       hash-gate on ir_config_parameter 'nexora.mcp_registry_hash'
       lifecycle override (:93-99):
           verified|production  → enabled = True
           planned|deprecated   → enabled = False
  → CapabilityRepository.synchronize_manifests (repository.py:175-223)
       WRITES nexora_capability_registry:
           supports_local  = (target_type == LOCAL)
           supports_remote = (target_type == REMOTE)
           state           = 'capability.enabled' | 'capability.disabled'
           checksum        = 'bootstrap_hash'
       deactivates missing rows unless provider == 'nexora'
  → CapabilityRepository.get_manifests_by_namespace
       derives target_type from supports_local/supports_remote
  → CapabilityPolicyEngine → router.executors.get(target_type)
```

So `mcp_registry.json` **directly determines routing behaviour**. It is a first-class configuration input. **Classification: AUTHORITATIVE.** Not modified by this audit.

### 12.2 P0 — The registry hash gate is stale

| | Value |
|---|---|
| Stored `nexora.mcp_registry_hash` | `4e8c39b4afe83f9b158fc149a48f404769c3363335e949393c68d4fc87e467c3` |
| Current file hash | `BCCDEAB8313D6B946EB629362A0F0E8D3328F6C3E21E66524EEEC7F647E65EFF` |
| Match | **No** |

`execute_bootstrap` hash-gates: if the hash differs it *should* re-sync. Since the hashes differ and the DB still holds old data, either the bootstrap has not run since the file changed, or it ran and failed silently.

**Live proof of the drift**, for `mcp.github`:

| Source | `enabled` | `lifecycle` |
|---|---|---|
| `config/mcp_registry.json` (current file) | `false` | `planned` |
| `nexora_capability_registry.metadata_json` (live DB) | **`true`** | **`production`** |

The DB holds a **stale earlier revision** of the registry file. The lifecycle override at `bootstrap.py:93-99` would set `enabled=False` for `planned`, so the live `enabled=true` can only have come from an older file state that said `production`.

### 12.3 `nexora_capability_registry` — 17 rows

| Source | Count | Rows |
|---|---|---|
| From `mcp_registry.json` | 12 | `mcp.context7`, `mcp.drei_docs`, `mcp.firecrawl`, `mcp.github`, `mcp.gosom`, `mcp.gsap_docs`, `mcp.mdn_docs`, `mcp.penpot`, `mcp.r3f_docs`, `mcp.spline`, `mcp.tavily`, `mcp.threejs_docs` |
| `provider='nexora'` (protected from deactivation) | 5 | `mcp.tool.*` |

Enabled: `context7`, `firecrawl`, `github`, `gsap_docs`, `mdn_docs`, `penpot`, `tavily` + all 5 `mcp.tool.*`.
Disabled: `drei_docs`, `gosom`, `r3f_docs`, `spline`, `threejs_docs`.

**`mcp.penpot` is the only row with `supports_local=f, supports_remote=t`** → the only row that resolves to `ExecutionTargetType.REMOTE` → the only row guaranteed to hit `Executor not found` (§10.5).

### 12.4 Registry file vs live connectors — set mismatch

| | In `mcp_registry.json` | In `nexora_connector` | In `nexora_capability_registry` |
|---|---|---|---|
| `context7` | yes (enabled, planned) | **yes** | yes, enabled |
| `firecrawl` | yes (enabled, planned) | **yes** | yes, enabled |
| `github` | yes (**disabled**, planned) | **yes** | yes, **enabled** ← drift |
| `penpot` | yes (enabled, planned, sse) | **yes** | yes, enabled |
| `tavily` | yes (enabled, planned) | **yes** | yes, enabled |
| `gsap_docs` | yes (enabled, **verified**) | **no** | yes, enabled |
| `mdn_docs` | yes (enabled, **verified**) | **no** | yes, enabled |
| `spline`, `gosom`, `threejs_docs`, `r3f_docs`, `drei_docs` | yes (disabled) | no | yes, disabled |

Two registry entries (`gsap_docs`, `mdn_docs`) are marked `verified` **and** enabled in the capability registry, yet **no connector exists for them**. A capability can therefore be advertised as enabled-and-verified with no execution backing whatsoever. `CapabilityRepository` would produce a manifest for them (from the registry rows) with `target_type` derived from `supports_local/remote`, and routing would then fail — or worse, hit `LocalToolExecutor`'s mock-success path.

Additionally, `_parse_registry_manifests` **discards** `startup_command`, `startup_args`, and `environment_variables` from the JSON. So the registry file carries launch information that is silently dropped — which is why `gsap_docs`/`mdn_docs` can never become executable from the registry alone.

### 12.5 Declarative seed drift (`ir_model_data`, 8 rows, all `noupdate=t`)

| xmlid | id | Connector covered |
|---|---|---|
| `connector_penpot_mcp` | 41 | penpot |
| `config_penpot_mcp` | 33 | penpot |
| `credential_penpot_api_key` | 30 | penpot |
| `connector_tavily_mcp` | 39 | tavily |
| `config_tavily_mcp` | 31 | tavily |
| `credential_tavily_api_key` | 32 | tavily |
| `connector_firecrawl_mcp` | 63 | firecrawl |
| `config_firecrawl_mcp` | 55 | firecrawl |

Gaps:
- **No `credential_firecrawl_api_key` xmlid** — but `FIRECRAWL_API_KEY` exists in the DB. Manually created, undeclared, would not survive a clean rebuild.
- **No xmlids at all for `context7_mcp` and `github_mcp`** — both connectors, their configs, and their credentials are entirely imperative. Invisible to module install/upgrade, unreproducible from the repo.
- `__manifest__.py` declares only **3** connector XMLs (`penpot`, `tavily`, `firecrawl`). Consistent with the above.
- `pre-migrate.py` adopts exactly 6 xmlids (penpot + tavily families). `firecrawl`'s two were adopted separately; `context7`/`github` never.

**Reproducibility assessment:** a clean `-i nexora_studio` on an empty database yields **3 of 5** connectors, **2 of 5** credentials, and **0** discovered tools. The live database cannot be reconstructed from the repository.

### 12.6 `ir_config_parameter` — 16 `nexora%` rows

Two of note:
- `nexora.mcp_registry_hash = 4e8c39b4…` — stale (§12.2).
- `nexora.nvidia.api_key` — **plaintext secret** (§8.3).

### 12.7 Git drift

| | |
|---|---|
| HEAD | `9bcbe2f Phase 36 — UCP Execution Unification` |
| `git status --porcelain` | **85 entries** |
| Modified | 28 |
| Deleted | 12 — all `services/runtime/mcp/*` (legacy retirement, uncommitted) |
| Untracked | ~45 — all Phase 37-43 reports/ADRs, `migrations/19.0.1.0.1/`, `connectors/mcp/pool.py`, penpot/tavily seed XMLs |

**Phases 37 through 43 are entirely uncommitted.** `pool.py` (the whole ADR-0067 implementation), the Phase 43.8 migration, and the Penpot/Tavily seeds exist only in the working tree. The 12 deletions under `services/runtime/mcp/` are also uncommitted, so the legacy retirement is not durable either.

This is the single largest operational risk in the repository: an accidental `git checkout .`, `git stash`, or `git clean -fd` would destroy seven phases of work including the migration that fixed Penpot auth.

### 12.8 CORRECTION to a prior report — `community/` is a junction, not a duplicate

A prior report described `community/odoo/addons/nexora_studio` as a "byte-identical mirror" implying duplication/drift risk. Verified: it is an **NTFS directory junction** (`LinkType=Junction`) pointing at `D:\ODOO\custom-addons\agency\nexora_studio`. There is exactly one copy of every file. **No drift is possible.** This finding is withdrawn.

### 12.9 Drift verdict

| Drift axis | Status |
|---|---|
| Registry file → DB | **P0 — stale.** Hash mismatch, `mcp.github` enabled/lifecycle contradiction. |
| Registry entries → connectors | **P1** — `gsap_docs`/`mdn_docs` enabled+verified with no connector. |
| Seeds → DB | **P1** — 2/5 connectors and 3/5 credentials undeclared. |
| Manifests → DB | **P0** — 4/5 corrupt (§9.6). |
| Repo → git | **P0** — 7 phases uncommitted, 85 working-tree entries. |
| `community/` mirror | **Not a drift.** Junction. Finding withdrawn. |

---

## 13. Testing Architecture Audit

### 13.1 P0 — 44 of 52 test files are unregistered

`tests/__init__.py` is 9 lines and imports **8** test modules. The `tests/` directory contains **52** test files.

**44 test files (85%) never execute** under `odoo --test-enable`. They are not skipped, not reported, not counted — they are invisible. Any regression they were written to catch is unguarded.

This is the most consequential testing finding: the suite gives an impression of coverage that is 85% fictional.

### 13.2 Test artefacts have leaked into the live database

Direct evidence from §9.6 / §11.3:

| Live `manifest_json` value | Origin |
|---|---|
| `{"broken": true}` on `github_mcp` | a negative-path test fixture |
| `{"command":"python","args":["-c","import sys; sys.exit(1)"]}` on `tavily_mcp` | a subprocess-failure test fixture |

Tests are running against — and writing to — the **development database**, not an isolated one. Combined with the manifest-wipe default (`odoo_adapter.py:135`), a test run permanently corrupts real connector records.

This is why the audit instruction "if a test would modify state, DO NOT run it" was correct and was honoured: **no tests were executed during Phase 44.1.**

### 13.3 What the existing tests actually cover

Based on filenames and the 8 registered modules, coverage is concentrated on:
- MCP configuration construction and validation
- Credential encrypt/decrypt round-trip
- Transport construction (mocked)
- Onboarding service happy path

Not covered by any registered test:
- The router → policy → executor chain (`services/capabilities`)
- `target_type` derivation from `supports_local`/`supports_remote`
- Executor registration completeness
- `_build_request` namespace parsing (the `tools.list` defect)
- `SessionTransportPool` (no test at all — the entire ADR-0067 implementation is untested)
- Lifecycle transitions and persistence-key consistency
- Manifest preservation across partial writes
- Capability-index rebuild
- Registry hash-gate re-sync behaviour
- Discovery destructiveness

Every P0 in §16 is in the uncovered set. **The test suite could not have caught any of the defects this audit found.**

### 13.4 Proposed verifications (NOT run — would modify state)

Recorded per the audit instruction rather than executed:

| # | Proposed verification | Why not run now |
|---|---|---|
| PV-1 | Register all 52 test files and run the suite | Would write to the dev DB; would likely re-corrupt manifests |
| PV-2 | Run discovery on any connector | `unlink()`+`create()` on `nexora_mcp_discovered_tool` |
| PV-3 | Invoke `action_test_tool_execution` | Writes `last_test_result_json`; spawns subprocesses |
| PV-4 | Trigger `execute_bootstrap` to test the hash gate | Would rewrite `nexora_capability_registry` and `nexora.mcp_registry_hash` |
| PV-5 | Start Odoo to observe live in-process connector state | Would run `post_load` bootstrap, which force-writes `health_status='healthy'` |
| PV-6 | Exercise `session_binding='request_context'` to activate the pool | Requires a config write |
| PV-7 | Verify pool loser-transport `disconnect()` on lock contention | Requires code instrumentation |

All seven belong in Phase 44.3 against an **isolated test database**.

### 13.5 Testing infrastructure gaps

| # | Gap | Impact |
|---|---|---|
| 1 | No test-DB isolation | Tests corrupt dev data (§13.2) |
| 2 | 44/52 files unregistered | 85% phantom coverage |
| 3 | No integration test for the canonical path end-to-end | The `Executor not found` defect survived 43 phases |
| 4 | No test asserting executor-registration completeness | A one-line assertion would have caught §10.5 |
| 5 | No test for `SessionTransportPool` | Entire ADR-0067 implementation unverified |
| 6 | Live-connector tests require real credentials + real remote servers | Cannot run in CI; likely why they were unregistered |
| 7 | No fixture teardown discipline | Test manifests persisted permanently |

### 13.6 Testing verdict

**Do not delete anything.** The 44 unregistered files are the largest existing asset for Phase 44.3 — they represent written-but-unwired intent. They must first be triaged (which still compile? which assume old APIs? which need real credentials?) before any are registered or removed. Registering all 44 blindly against the dev DB would be actively destructive.

---

## 14. ADR / Architecture Consistency

Each ADR is assessed on three independent axes: **INTENT** (what the ADR says), **IMPLEMENTATION** (what the code does), **LIVE** (what the running system demonstrates).

### 14.1 ADR-0066 — Generic MCP Request Context Propagation (status: **Accepted**, 25 lines)

| Axis | Finding |
|---|---|
| **INTENT** | A generic `request_context` dict must flow from the caller through the execution layers to the MCP provider, with a per-connector allowlist controlling which fields may be consumed. No connector-specific fields in shared code. |
| **IMPLEMENTATION** | **Matches.** `sdk/context.py:24` defines `request_context`. `connector_executor._build_request:141` forwards it. `provider._get_active_transport:21-34` enforces the allowlist, returning `FORBIDDEN_CONTEXT_FIELD` for non-allowlisted fields and `MISSING_SESSION_IDENTITY` when the required field is absent. `allowed_request_context_fields_json` exists on the config table. |
| **LIVE** | Partially exercised. `penpot_mcp` has `allowlist=["userToken"]`; the other four have `[]`. Since no connector uses `session_binding='request_context'`, the enforcement branch is never reached at runtime. |
| **Verdict** | **CONSISTENT — KEEP.** Correctly implemented, correctly generic. The one ADR that survives scrutiny intact. |

### 14.2 ADR-0067 — Generic Session-Bound MCP Transport (status: **Proposed**, 47 lines)

| Axis | Finding |
|---|---|
| **INTENT** | A pool of MCP transports keyed by session identity, with TTL-based "reaping", named `McpTransportPool`. |
| **IMPLEMENTATION** | **Diverges in three ways.** (1) Class is named `SessionTransportPool`, not `McpTransportPool`. (2) The ADR specifies a TTL **reap**; the implementation has **no background reaper** — TTL is enforced only opportunistically inside `get_transport` (`pool.py:34`). (3) No max pool size is specified or implemented. |
| **LIVE** | **Entirely dormant.** All 5 connectors have `session_binding='none'` → `pool` is `None` → the class is never instantiated. Zero live evidence either way. |
| **Verdict** | **PARTIALLY INCONSISTENT — RECONCILE, DO NOT DISCARD.** The ADR is still `Proposed`, which is arguably honest given the feature is dormant. Two actions for 44.2: rename in the ADR to match the code (code name is better — it says *session*, which is the actual key), and either implement the reaper or amend the ADR to state opportunistic-only eviction with an explicit max-size bound. |

### 14.3 The canonical path — INTENT vs IMPLEMENTATION vs LIVE

**INTENT** (stated in prior reports and the audit brief):
```
UniversalCapabilityRouter → ConnectorExecutionTarget → ConnectorRuntime
  → ConnectorDispatcher → McpConnector → McpProvider → McpTransport → MCP SDK → Remote
```

**IMPLEMENTATION** — the path exists, but it is **not the only** path, and its entry point is gated by a broken lookup:

| Divergence | Detail |
|---|---|
| Four entry points, not one | (a) `UniversalCapabilityRouter` via `ToolRuntimeAdapter`; (b) three model-level providers calling `dispatch` directly (`tavily_provider.py:44`, `github_provider.py:49`, `context7_provider.py:43`); (c) `nexora_connector.action_test_tool_execution` constructing `ConnectorExecutionTarget` itself (`:139-166`); (d) `ConnectorDispatcher.initialize_and_verify` calling `sdk_connector.execute` directly (`:276-322`). |
| The router cannot reach REMOTE | `RemoteToolExecutor` imported but never registered (`generation_runtime.py:49-51` vs `:70-78`). |
| Factories are dead | `ConnectorFactory.transport_factory`/`provider_factory` never called (`connector_factory.py:47-51` commented out). `McpConnector.__init__` constructs everything directly. |
| UCEL layers are stubs | `SecurityLayer` no-op (6 lines), `ExecutionScheduler` pass-through (11 lines), `FallbackStrategy` dead branch (14 lines), `CapabilityPolicyEngine` picks `candidates[0]` (13 lines). |
| `_register_executor_with_ucel` is `pass` | `integration/bootstrap.py:184-190` — the intended registration hook is a stub. |

**LIVE**: the only demonstrated working execution is Penpot via the Phase 43.8 verification, and the three model-level provider bypasses. The router path has **no live evidence of success** for any connector.

**Verdict:** the canonical path is **aspirational, not enforced**. It exists as code but is bypassed by four alternate routes and blocked for REMOTE targets. **Documenting this precisely, as required, is the main architectural output of this audit.**

### 14.4 Claims in prior reports that this audit corrects

| # | Prior claim | Actual | Evidence |
|---|---|---|---|
| 1 | `config/mcp_registry.json` is "informational only" | **Authoritative.** It writes `nexora_capability_registry`, which determines `target_type` and therefore routing. | `capabilities/bootstrap.py:11-108` → `repository.py:175-223` → `repository.py:9-95` → `router.py:54` |
| 2 | `community/odoo/addons/nexora_studio` is a byte-identical duplicate at risk of drift | **NTFS junction.** One copy of every file; drift impossible. | `LinkType=Junction` |
| 3 | Bootstrap uses a module-level `_bootstrap_instance` singleton | **Class attribute `_instance` + `get_instance()`** classmethod. Module helper is `get_connector_runtime()` at `:306-309`. | `integration/bootstrap.py:41`, `:49-54`, `:306-309` |

Each correction was derived from reading the implementation, per the instruction to treat the repository and live configuration as ground truth.

### 14.5 Missing ADRs

Decisions that are load-bearing but have no ADR:

| Undocumented decision | Where it lives | Why it needs an ADR |
|---|---|---|
| Credentials are delivered to stdio servers by injecting **all** of a connector's credentials into the child environment, keyed by credential name | `mcp_onboarding_service.py:218,242` | This is a second authentication mechanism with an implicit naming contract and a least-privilege violation (§5.3). |
| `mcp_registry.json` is an authoritative routing input, hash-gated | `capabilities/bootstrap.py` | Nothing states this; a prior report asserted the opposite. |
| `nexora_mcp_discovered_tool` vs `nexora_connector_capability` vs `nexora_capability_registry` — which is authoritative for what | three separate writers | Three parallel capability models with no stated reconciliation rule (§10.1). |
| `tools.*`/`resources.*`/`prompts.*` are protocol namespaces, not connector-qualified | `_CAPABILITY_DISCOVERY_NAMESPACES`, `_build_request` | The contract is currently implicit and contradicted by the code (§10.4). |
| `health_status` semantics | `integration/bootstrap.py:242` | The field is written without measurement; its meaning is undefined (§9.3). |

### 14.6 ADR verdict

| ADR | Status | Action |
|---|---|---|
| ADR-0066 | Accepted, consistent | **KEEP AS-IS.** |
| ADR-0067 | Proposed, partially inconsistent | **RECONCILE** — rename to `SessionTransportPool`, state eviction semantics honestly, add max-size. |
| Canonical path | No ADR; asserted in reports only | **NEEDS AN ADR** stating the single canonical path and explicitly listing the bypasses to be removed. |
| 5 undocumented decisions (§14.5) | — | **NEEDS ADRs** in 44.2, at least for the credential-delivery contract and the namespace contract. |

---

## 15. Dead / Duplicate / Legacy Code

Classification key: **KEEP** (correct, on the canonical path) · **CONSOLIDATE** (duplicate logic to merge into one place) · **DEPRECATE** (mark, stop using, remove after a cycle) · **REMOVE LATER** (provably dead, safe to delete once verified) · **NEEDS INVESTIGATION** (cannot classify without more evidence).

### 15.1 Canonical-path components — KEEP

| Component | File | Note |
|---|---|---|
| `McpTransport` | `connectors/mcp/transport.py` | The only working transport. Keep the load-bearing `import httpx` comment. |
| `QueryAuth` | `connectors/mcp/transport.py:58-65` | Generic, correct. |
| `McpProvider` | `connectors/mcp/provider.py` | Implements exactly the 6 MCP namespaces. |
| `McpConnector` | `connectors/mcp/connector.py` | Composition facade. |
| `SessionTransportPool` | `connectors/mcp/pool.py` | Dormant but correct (§7.4). **Do not remove.** |
| `McpConfiguration` | `connectors/mcp/configuration.py` | Sound validation (`shlex`, `..` rejection). |
| `request_context` plumbing | `sdk/context.py:24` + allowlist enforcement | ADR-0066, consistent. |
| `OdooSecretsProvider` Fernet layer | `odoo_secrets_provider.py` | Encryption itself is correct. |
| MCP tool discovery | `capability_discovery.py` (the discovery half) | The only working capability mechanism. |

### 15.2 Duplicate logic — CONSOLIDATE

| # | Duplication | Locations | Consolidation target |
|---|---|---|---|
| 1 | **Direct-dispatch bypass of the router** | `models/tavily_provider.py:44`, `models/github_provider.py:49`, `models/context7_provider.py:43` | One generic model mixin or, better, route through `UniversalCapabilityRouter`. Three near-identical implementations. |
| 2 | **`user_overrides` 12-key dict** | `mcp_onboarding_service.py:294-307` and `:360-373` — **verbatim duplicate** | Single module-level constant or helper. |
| 3 | **Background-thread cursor detection** | `odoo_adapter.py` — duplicated **4×** | One private helper. |
| 4 | **Runtime accessor** | `nexora_connector.action_discover_mcp_capabilities:183-190` triple-fallback; `get_connector_runtime()` at `bootstrap.py:306-309`; `ConnectorPlatformBootstrap.get_instance()` | One canonical accessor. The triple-fallback is evidence that no single reliable accessor exists today. |
| 5 | **Three parallel capability stores** | `nexora_mcp_discovered_tool`, `nexora_connector_capability`, `nexora_capability_registry` | Declare one authoritative store; make the others derived or drop them (§10.1). This is the largest consolidation opportunity in the platform. |
| 6 | **Two authentication delivery paths** | `transport.py:135-143` (header/query) vs `mcp_onboarding_service.py:218,242` (env injection) | One declared credential-delivery model with `env` as a first-class `auth_location` value (§5.3). |
| 7 | **Two `tools.list` workarounds** | `_CAPABILITY_DISCOVERY_NAMESPACES` (`connector_runtime.py:282`) and `initialize_and_verify` direct `sdk_connector.execute` (`dispatcher.py:276-322`) | Fix `_build_request` once; both workarounds then delete (§10.4). |

### 15.3 Legacy — DEPRECATE / REMOVE

| # | Item | Classification | Evidence |
|---|---|---|---|
| 1 | `services/source_framework/transport/mcp_transport.py` | **REMOVE LATER** | Emits `DeprecationWarning` at line 6. Genuine parallel legacy transport. Verify no importer remains, then delete. |
| 2 | `services/runtime/mcp/*` (12 files) | **Already deleted, uncommitted** | Present as `D` entries in `git status`. Commit the deletion to make it durable (§12.7). |
| 3 | `connector_components.py:89` `TypeError` arity fallback on `transport.connect` | **REMOVE LATER** | A shim that exists only because two transport implementations have different `connect()` signatures. Once #1 is deleted, this shim is unnecessary. |
| 4 | `connector_executor.py:29-42` `ImportError` fallback shim defining stub `ExecutionTarget`/`CapabilityResult` | **REMOVE LATER** | Masks a real import failure with silent stubs. If the import can fail, that is a packaging bug to fix, not to paper over. |
| 5 | `ConnectorFactory.transport_factory` / `provider_factory` | **REMOVE LATER** | Both sub-factories dead — call sites commented out at `connector_factory.py:47-51`. `McpConnector` constructs directly. |
| 6 | `_register_executor_with_ucel` | **REMOVE or IMPLEMENT** | `integration/bootstrap.py:184-190` body is `pass  # stub for brevity`. Either wire it (which would fix §10.5) or delete it. Currently it advertises a behaviour that does not exist. |
| 7 | `FallbackStrategy` empty fallback branch | **REMOVE LATER** | `strategy.py` — `pass` branch, unreachable purpose. |
| 8 | `CapabilityResolver.provider_map` (9 hardcoded entries) | **REMOVE LATER** | `mcp.eslint`, `mcp.playwright`, `mcp.search`, 6 `*_reviewer`. **None** correspond to a live connector or a registry row. Fully stale. |
| 9 | `router.py:48` `_reviewer` suffix shortcut | **REMOVE LATER** | Connector-specific hack in the generic router. Depends on #8. |
| 10 | 6 × `print()` + `traceback.print_exc()` | **REMOVE** | `connector_runtime.py:200,206,210,214,219,222,223`. Replace with `_logger`. Unambiguous. |
| 11 | `DISPATCHER:` f-string INFO logs (5) + shadowed module logger | **CONSOLIDATE** | `dispatcher.py:150-196`. Shadowing the module logger is a bug; the f-string INFO spam is noise. |
| 12 | `working_directory`, `startup_policy`, `timeout_seconds` DB columns | **NEEDS INVESTIGATION** | Never reach `McpConfiguration` (§4.2). Either wire them (`timeout_seconds` should clearly be honoured) or drop them. Do not remove `timeout_seconds` — wire it. |
| 13 | `penpot_mcp.working_directory` value | **REMOVE LATER** | Leftover from a prior stdio attempt; meaningless for `sse`. Data cleanup, needs a migration. |
| 14 | `nexora.nvidia.api_key` in `ir_config_parameter` | **REMOVE / MIGRATE** | Plaintext secret bypassing the credential subsystem (§8.3). Migrate into `nexora_mcp_credential` or an equivalent encrypted store. |
| 15 | Corrupt `manifest_json` values (4 connectors) | **REMOVE / REPAIR** | `{}`, `{"broken": true}`, the `sys.exit(1)` stub (§9.6). Requires a data migration **after** the wipe mechanism is fixed — repairing first would just be re-wiped. |
| 16 | 44 unregistered test files | **NEEDS INVESTIGATION** | **Do not delete** (§13.6). Triage first. |
| 17 | `nexora_connector_capability` table | **NEEDS INVESTIGATION** | 0 rows for all connectors, yet `resolve_capability` depends on it (§9.7). Either make the rebuild work or make discovered-tools authoritative and drop the table. Cannot decide without §15.2 #5. |
| 18 | `RemoteToolExecutor` | **NEEDS INVESTIGATION** | Unconditional `success=True` (12 lines). If REMOTE routing is to be kept, this must be rewritten, not registered as-is — registering it today would convert every failure into a false success. |
| 19 | `LocalToolExecutor` mock-success branch | **REMOVE** | `local.py:37` returns `success=True, result="Executed locally (mock)"`. Must fail loudly instead. |
| 20 | `SecurityLayer` no-op | **NEEDS INVESTIGATION** | 6 lines, `return True` / `return context`. Either implement authorization or delete the layer so its absence is honest. A no-op security layer is worse than none because it looks like protection. |
| 21 | `mcp_onboarding_service.py:234-238` bare `except Exception: pass` | **REMOVE** | Silent credential-failure swallow (§5.4). |
| 22 | Raw-payload INFO logs | **CONSOLIDATE** | `capability_discovery.py:99-101`, `connection_tester.py:141`. Route through one redacting log helper. |
| 23 | Traceback-into-user-message | **REMOVE** | `connection_tester.py:200` + persisted at `:225-241`; `nexora_connector.py:196` `UserError`. Log the traceback, show a message. |
| 24 | Undefined annotations `ConnectorCapability` / `ConnectorEvent` | **REMOVE or IMPORT** | `connector_runtime.py:229`, `:584`. Latent `NameError`. |
| 25 | `external_dependencies` lists `httpx2` | **NEEDS INVESTIGATION** | `__manifest__.py`. No such package is imported anywhere; `httpx` is the real dependency. Likely a typo that Odoo does not enforce strictly enough to fail install. |
| 26 | `runtime_synchronizer.py:137` private `_runtime` access | **CONSOLIDATE** | Expose a proper accessor. |
| 27 | `'degraded'` orphan state | **NEEDS INVESTIGATION** | In neither `_RUNNING_STATES` nor `_TERMINAL_STATES`. Decide the state machine's real alphabet. |

### 15.4 Summary counts

| Classification | Count |
|---|---|
| KEEP | 9 components |
| CONSOLIDATE | 7 duplications + 3 items in §15.3 |
| DEPRECATE / REMOVE LATER | 12 items |
| REMOVE (unambiguous) | 5 items |
| NEEDS INVESTIGATION | 7 items |

**Nothing was deleted during this audit.**

---

## 16. Final Architectural Gap Analysis

Priority key: **P0** correctness/security blocker · **P1** production reliability · **P2** architectural/maintainability · **P3** cleanup/documentation.

### 16.1 Prioritized gap table

| ID | Gap | Priority | Evidence | Impact |
|---|---|---|---|---|
| G-01 | `RemoteToolExecutor` never registered → any REMOTE capability returns `Executor not found`. `mcp.penpot` is REMOTE. | **P0** | `generation_runtime.py:49-51` vs `:70-78`; `router.py:54-56`; DB `mcp.penpot supports_remote=t` | The router cannot execute the platform's flagship connector. |
| G-02 | `_build_request` splits **any** dotted namespace → `tools.list` → `CONNECTOR_NOT_FOUND` | **P0** | `connector_executor.py:123` | Protocol operations unreachable through the canonical path; 3 workarounds exist to compensate. |
| G-03 | Manifest-wipe: full-write defaults `manifest_json` to `{}` | **P0** | `odoo_adapter.py:135`; 4/5 corrupt manifests live | Silent, permanent data loss on every partial write. |
| G-04 | Capability index empty for all connectors | **P0** | `connector_runtime.py:577-582`; 0 rows in `nexora_connector_capability` | `resolve_capability` cannot resolve anything. |
| G-05 | `health_status` force-written `healthy` before any probe | **P0** | `bootstrap.py:242`; `github_mcp` healthy with no container | False assurance; health monitoring is non-functional. |
| G-06 | Master encryption key in plaintext in `dev.conf` | **P0** | `d:\ODOO\configs\dev.conf` | Full credential compromise from filesystem read; no documented production alternative. |
| G-07 | `nexora.nvidia.api_key` plaintext in `ir_config_parameter` | **P0** | live DB | Secret outside the encrypted store; included in DB dumps. |
| G-08 | Registry hash gate stale → DB holds an older registry revision | **P0** | stored `4e8c39b4…` vs file `BCCDEAB…`; `mcp.github` enabled/lifecycle contradiction | Routing decisions made from stale configuration. |
| G-09 | 7 phases of work uncommitted (85 working-tree entries, incl. `pool.py` + the 43.8 migration) | **P0** | `git status --porcelain` | One careless command destroys the entire ADR-0067 implementation and the Penpot auth fix. |
| G-10 | `LocalToolExecutor` returns mock success when `tool_registry is None`, which is every non-HTTP context | **P0** | `local.py:37`; `generation_runtime.py:54-58` | Cron/queue/CLI executions silently "succeed" without doing anything. |
| G-11 | 44/52 test files unregistered | **P0** | `tests/__init__.py` (9 lines) vs 52 files | 85% phantom coverage; no P0 here was catchable. |
| G-12 | Credential-resolution failure silently swallowed → unauthenticated connection | **P1** | `mcp_onboarding_service.py:234-238` + `transport.py:135` guard | 401/403 misdiagnosed as network failure. |
| G-13 | `_active_connectors` unprotected → check-then-act race, leaked subprocess | **P1** | `dispatcher.py:57`, `:198-213` | Concurrent requests can orphan a live subprocess with no shutdown. |
| G-14 | Evict-and-destroy connector on **any** exception | **P1** | `dispatcher.py:215-260` | Transient tool error tears down transport, subprocess, and (when active) all pooled sessions. |
| G-15 | Post-handshake transport failures only logged, never propagated | **P1** | `transport.py:172-176` | Dead subprocess presents as a connected transport failing opaquely. |
| G-16 | Tests write to the dev DB; test fixtures persisted into live connector records | **P1** | `{"broken": true}`, `sys.exit(1)` manifests | Running the suite corrupts real data. |
| G-17 | Discovery is `unlink()`+`create()` | **P1** | `capability_discovery.py:147-181` | ID churn; failure window leaves zero tools; cannot distinguish removal from failure. |
| G-18 | 2/5 connectors and 3/5 credentials undeclared in seeds | **P1** | `ir_model_data` 8 rows; `__manifest__.py` 3 XMLs | Live DB not reproducible from repo. |
| G-19 | `gsap_docs`/`mdn_docs` enabled+verified in the capability registry with **no connector** | **P1** | registry 17 rows vs connector 5 rows | Capabilities advertised with no execution backing. |
| G-20 | Persistence key inconsistency (`state` vs `lifecycle_state`) | **P1** | `_on_health_change` vs `_on_lifecycle_transition` vs `odoo_adapter` | Health-driven state changes silently dropped. |
| G-21 | Credentials injected wholesale into child process env; child inherits full `os.environ` | **P1** | `mcp_onboarding_service.py:242`; `transport.py:102-111` | Least-privilege violation; unauditable effective environment. |
| G-22 | `timeout_seconds` DB column ignored; timeout hardcoded `60.0` in 2 places | **P1** | `transport.py:187`, `:210` | Configuration is decorative; no per-connector tuning. |
| G-23 | No shutdown hook on Odoo worker exit | **P1** | no `atexit`/teardown on `_active_connectors` | stdio subprocesses outlive the worker. |
| G-24 | Four parallel entry points bypass the canonical path | **P2** | 3 model providers, `action_test_tool_execution`, `initialize_and_verify` | Behaviour, security and observability differ per entry point. |
| G-25 | Three parallel capability stores with no reconciliation rule | **P2** | `discovered_tool` / `connector_capability` / `capability_registry` | Nobody can say which is authoritative. |
| G-26 | Two parallel credential-delivery mechanisms, one undeclared | **P2** | §5.3 | Implicit naming contract, no validation. |
| G-27 | `SecurityLayer` is a no-op; router provides zero authorization | **P2** | `security.py` (6 lines) | Looks like protection; is not. |
| G-28 | `ExecutionScheduler` has no queueing/limits despite its name and comment | **P2** | `scheduler.py` (11 lines) | No concurrency control anywhere on the path. |
| G-29 | `CapabilityRepository._cache` never invalidated | **P2** | `repository.py:9` | Registry changes invisible until restart. |
| G-30 | Candidate ordering hazard: registry manifest appended before CONNECTOR manifests, policy picks `candidates[0]` | **P2** | `repository.py:53` vs `:56-90`; `policy.py` | Correct calls can resolve to the wrong target type. |
| G-31 | `ConnectorFactory` sub-factories dead; construction is direct | **P2** | `connector_factory.py:47-51` | Abstraction with no implementation. |
| G-32 | `_register_executor_with_ucel` is `pass` | **P2** | `integration/bootstrap.py:184-190` | The intended fix for G-01 exists as a stub. |
| G-33 | Legacy duplicate transport + arity shim | **P2** | `source_framework/transport/mcp_transport.py:6`; `connector_components.py:89` | Two transport implementations. |
| G-34 | `basic` auth scheme produces `Basic <raw>` without base64 | **P2** | `transport.py:139-141` | Latent failure if ever used. |
| G-35 | No `streamable_http` / `websocket` transport | **P2** | `transport.py` branches on 2 values only | Modern MCP servers unreachable. Fail-silent on unknown `transport_type`. |
| G-36 | Pool: no background reaper, no max size, hardcoded TTL | **P2** (P1 on activation) | `pool.py:21,34` | Resource exhaustion when `request_context` binding is enabled. |
| G-37 | Undefined type annotations (`ConnectorCapability`, `ConnectorEvent`) | **P2** | `connector_runtime.py:229`, `:584` | Latent `NameError`. |
| G-38 | `'degraded'` in neither state set | **P2** | `runtime_synchronizer.py` | Degraded connectors invisible to reconciliation. |
| G-39 | `runtime_synchronizer` touches private `_runtime` | **P2** | `:137` | Encapsulation breach across the boundary it reconciles. |
| G-40 | 6 `print()` + `traceback.print_exc()` in the runtime | **P3** | `connector_runtime.py:200-223` | Unstructured stdout, no level control. |
| G-41 | Full traceback into user-facing messages, then persisted | **P3** | `connection_tester.py:200,225-241`; `nexora_connector.py:196` | Information disclosure; poor UX. |
| G-42 | Raw payload INFO logs | **P3** | `capability_discovery.py:99-101`; `connection_tester.py:141` | Unredacted log volume. |
| G-43 | `trace_file` writes unredacted wire frames, uncapped, unrotated | **P3** | `transport.py:10-35` | Dormant plaintext sink. |
| G-44 | `DISPATCHER:` f-string INFO spam + shadowed module logger | **P3** | `dispatcher.py:150-196` | Log noise; shadowing is a bug. |
| G-45 | Stale `CapabilityResolver.provider_map` + `_reviewer` router shortcut | **P3** | `resolver.py`; `router.py:48` | Dead config, connector-specific hack. |
| G-46 | `working_directory` / `startup_policy` orphan DB columns | **P3** | §4.2 | Decorative configuration. |
| G-47 | `firecrawl` uses `npx` where others use `npx.cmd` | **P3** | live DB | Inconsistent; works by PATHEXT accident. |
| G-48 | Three Penpot MCP instances running; connector targets the frontend proxy | **P3** | `docker ps` | Ambiguous which server serves requests. |
| G-49 | ADR-0067 naming/eviction drift; ADR still `Proposed` | **P3** | ADR-0067 vs `pool.py` | Documentation/implementation mismatch. |
| G-50 | 5 load-bearing decisions have no ADR | **P3** | §14.5 | Undocumented architecture. |
| G-51 | `external_dependencies` lists `httpx2` | **P3** | `__manifest__.py` | Probable typo; real dependency is `httpx`. |
| G-52 | `odoo_credential_resolver.validate()` suffix-scan false positives | **P3** | `:79-108` | Heuristic masquerading as a control. |

### 16.2 MUST FIX (P0 — 11 gaps)

G-01, G-02, G-03, G-04, G-05, G-06, G-07, G-08, G-09, G-10, G-11.

These break correctness, security, data integrity, or recoverability. **G-09 (uncommitted work) should be addressed first and is the cheapest** — it costs one commit and eliminates the risk of losing everything else.

Note the dependency: **G-03 must be fixed before repairing the corrupt manifests**, otherwise the repair is immediately re-wiped. And **G-01 must not be fixed by simply registering `RemoteToolExecutor`** — that executor returns unconditional success (§15.3 #18), so registering it would convert every failure into a silent success. The correct fix is to decide whether `mcp.penpot` should be CONNECTOR rather than REMOTE (G-30 territory), which is an architectural decision, not a one-line change.

### 16.3 SHOULD FIX (P1 — 12 gaps)

G-12, G-13, G-14, G-15, G-16, G-17, G-18, G-19, G-20, G-21, G-22, G-23.

These do not corrupt data today but will cause production incidents: silent auth failures, leaked subprocesses, torn-down transports on transient errors, non-reproducible deployments.

### 16.4 OPTIONAL (P2/P3 — 29 gaps)

G-24 through G-52. Architectural consolidation, dead-code removal, logging hygiene, documentation. Valuable but non-blocking.

**Important:** several P2 items (G-24, G-25, G-26, G-30, G-32) are the *structural causes* of P0 items. Fixing the P0s without addressing these causes will produce point-fixes that re-break. G-32 in particular is the intended mechanism for G-01.

---

## 17. Phase 44.2 Implementation Specification

**No implementation code is written in this section.** Each entry is a specification only.

### 17.0 Design constraints binding every change below

| Constraint | Consequence for 44.2 |
|---|---|
| **Reuse over creation** | No new subsystem may be introduced where an existing one can be corrected. `QueryAuth`, `McpTransport`, `SessionTransportPool`, `McpConfiguration`, `OdooSecretsProvider` are all sound and must be extended, not replaced. |
| **Consolidation over addition** | Every change that removes a parallel path ranks above every change that adds capability. Net file count should not increase materially. |
| **Minimal architectural surface** | No new abstraction layers, no new factories, no new registries. Where an abstraction is already dead (`ConnectorFactory` sub-factories, `_register_executor_with_ucel`), either implement it or delete it — do not add a third option. |
| **Backward compatibility** | No DB column may be dropped in 44.2. No external ID may be renamed. Existing `namespace` call sites must keep working. Changes are additive-then-migrate, never break-then-fix. |
| **Generic behaviour** | No connector-specific branch may be introduced in shared code. Any behaviour that only Penpot or only GitHub needs must be expressed as configuration on the connector record. |
| **Security** | No change may widen a credential's blast radius. Every change touching credentials must narrow it or leave it unchanged. |
| **Observable lifecycle** | Every state field written must be derived from a measurement, or explicitly named as unmeasured. No field may assert a fact the system has not observed. |

### 17.1 Workstream W0 — Preservation (must precede everything)

**C-01 — Commit the uncommitted platform**

| Field | Value |
|---|---|
| File(s) | Whole working tree — 85 `git status` entries: 28 modified, 12 deleted (`services/runtime/mcp/*`), ~45 untracked (Phase 37–43 reports/ADRs, `migrations/19.0.1.0.1/`, `connectors/mcp/pool.py`, penpot/tavily seed XMLs) |
| Current responsibility | The working tree is the *only* copy of Phases 37–43, including the entire ADR-0067 implementation and the Phase 43.8 Penpot auth migration. |
| Exact problem | G-09. HEAD is `9bcbe2f` (Phase 36). Seven phases exist nowhere but on disk. A single `git checkout .`, `git stash`, or `git clean -fd` destroys them irrecoverably. |
| Proposed change | Stage and commit in logical groups: (a) the 12 `services/runtime/mcp/*` deletions as one "legacy retirement" commit; (b) `pool.py` + ADR-0067 as one commit; (c) `migrations/19.0.1.0.1/` + penpot/tavily seeds as one "Phase 43.8" commit; (d) reports/ADRs as one docs commit. Stage files by explicit name — never `git add -A` — because `configs/dev.conf` contains the plaintext master key (G-06) and must not be committed. |
| Why existing architecture cannot solve it | Not an architectural problem. It is an unmitigated total-loss risk and it is the cheapest item in the entire plan. |
| Dependencies | None. **This is the first action of Phase 44.2.** |
| Regression risk | **None** — commits do not alter behaviour. The only risk is committing a secret, mitigated by explicit-path staging and a pre-commit grep for the key name. |
| Verification | `git status --porcelain` returns only intentionally-ignored paths; `git log --stat` shows `pool.py` and `migrations/19.0.1.0.1/*` present; `git log -p | grep -c nexora_connector_secret_key` returns 0. |

### 17.2 Workstream W1 — Routing contract correctness

This workstream fixes G-01, G-02, G-30, G-32 together, because they are one defect seen from four angles: **the platform has never agreed on what a `namespace` means.**

**C-02 — Ratify the namespace contract (decision, then ADR, then code)**

| Field | Value |
|---|---|
| File(s) | New ADR; then `services/connector/integration/connector_executor.py` (`_build_request`, `:114-150`) |
| Current responsibility | `_build_request` converts an incoming `(namespace, payload)` pair into a connector-directed MCP request. |
| Exact problem | G-02. Line 123 `if '.' in namespace:` splits *any* dotted string on the first dot. `tools.list` becomes `connector_id="tools"`, `tool_name="list"` → `CONNECTOR_NOT_FOUND`. The code simultaneously assumes two incompatible grammars: `<connector_id>.<tool_name>` and `<protocol_area>.<verb>`. |
| Proposed change | Adopt **Option 1 from §10.4: reserved protocol namespaces.** Declare `tools.*`, `resources.*`, `prompts.*` as protocol-level namespaces that are never connector-qualified, and require connector-directed calls to be `<connector_id>.<tool_name>`. In `_build_request`, test membership in the reserved set **before** splitting; reserved namespaces pass through with the connector taken from the explicit target/context, not from the namespace string. Write the ADR *first* — the contract is the deliverable, the code change is a consequence. |
| Why existing architecture cannot solve it | The reserved set already exists — `_CAPABILITY_DISCOVERY_NAMESPACES` in `connector_runtime.py:282`. It is a *workaround at the wrong layer*: it lets the runtime special-case what `_build_request` has already corrupted. The knowledge exists; it is in the wrong place. Reuse the constant, move the decision to the single point of parse. |
| Dependencies | C-01. Must precede C-03, C-19, C-20 (both `tools.list` workarounds delete only once this is correct). |
| Regression risk | **Medium.** Any caller that currently relies on a connector literally named `tools`/`resources`/`prompts` would break — no such connector exists (live inventory: 5 connectors, none so named), so risk is theoretical. Real risk is the reserved set being incomplete; mitigate by deriving it from `McpProvider`'s 6 supported namespaces (`provider.py`) rather than re-listing it. |
| Verification | PV-8 (§18): `tools.list` through the canonical path returns a tool list, not `CONNECTOR_NOT_FOUND`; `penpot_mcp.export_shape` still resolves; a namespace with no dot and a namespace with two dots both behave per the ADR. |

**C-03 — Resolve the REMOTE-vs-CONNECTOR target-type question**

| Field | Value |
|---|---|
| File(s) | `services/capabilities/repository.py:9-95` (`get_manifests_by_namespace`), `:175-223` (`synchronize_manifests`); `services/capabilities/bootstrap.py:11-54` (`_parse_registry_manifests`) |
| Current responsibility | Derive `ExecutionTargetType` for a capability from `supports_local`/`supports_remote` on `nexora_capability_registry`. |
| Exact problem | G-01 + G-30. `mcp.penpot` is the only registry row with `supports_local=f, supports_remote=t`, so it derives `REMOTE` — an executor `GenerationRuntime` never registers → `Executor not found` (`router.py:54-56`). Meanwhile `_parse_registry_manifests` sets `target_type = LOCAL if transport=="stdio" else REMOTE`, conflating *transport mechanism* with *execution target*. An SSE MCP connector is not a "remote capability"; it is a **CONNECTOR** capability that happens to use a network transport. |
| Proposed change | Declare that **every capability backed by a `nexora_connector` record is `ExecutionTargetType.CONNECTOR`, regardless of transport.** `REMOTE` is reserved for non-connector remote execution and, having no working executor, should be treated as unreachable until one exists. Concretely: stop deriving target type from `supports_local`/`supports_remote` for connector-backed capabilities, and make the MCP-connector branch (`repository.py:56-90`) authoritative when a connector exists for the namespace. |
| Why existing architecture cannot solve it | `ExecutionTargetType.CONNECTOR` and the connector-manifest branch already exist and already work — `repository.py:56-90` is the only place `CONNECTOR` is produced. The bug is that a *registry-derived* manifest for the same namespace is appended **first** (`:53`) and `CapabilityPolicyEngine` picks `candidates[0]` (`policy.py`). The correct behaviour is reachable purely by ordering and derivation, with **no new executor and no new type**. |
| Dependencies | C-01. Blocks C-04. Interacts with C-05 (ordering). |
| Regression risk | **Medium-high** — this changes routing for every capability. Mitigate by keeping `supports_local`/`supports_remote` columns intact (backward compatibility) and changing only *derivation*, and by asserting the resulting target type per live namespace before and after. |
| Verification | PV-9: for each of the 5 live connectors, assert `get_manifests_by_namespace` yields `CONNECTOR` for `<connector_id>.<tool>`; assert no live namespace resolves to `REMOTE`. |

**C-04 — Make executor registration complete and fail-closed**

| Field | Value |
|---|---|
| File(s) | `services/generation/core/generation_runtime.py:45-104`; `services/connector/integration/bootstrap.py:184-190` (`_register_executor_with_ucel`) |
| Current responsibility | Build the `executors` dict handed to `UniversalCapabilityRouter`. |
| Exact problem | G-01 + G-32. `LOCAL` is registered unconditionally; `CONNECTOR` conditionally (`:74-78`); `REMOTE` is imported (`:49-51`) but **never registered**. `_register_executor_with_ucel` — the intended registration hook — has body `pass  # stub for brevity`. Registration completeness is asserted nowhere. |
| Proposed change | Two parts. (a) Assert at runtime construction that every `ExecutionTargetType` a live capability can resolve to has a registered executor, and **raise at startup** if not — a missing executor must be a boot failure, not a per-request `success=False`. (b) Either implement `_register_executor_with_ucel` as the single registration path or delete it; do not leave a stub that advertises absent behaviour. **Do not register `RemoteToolExecutor` as it stands** — it returns unconditional `success=True` (`remote.py`, 12 lines) and would convert every failure into a silent success. |
| Why existing architecture cannot solve it | The `executors` dict and the `Executor not found` branch already exist. What is missing is a completeness invariant. Adding one is smaller than any alternative and removes an entire failure class. |
| Dependencies | C-03 (determines which types must be registered). |
| Regression risk | **Medium** — a fail-closed assertion could refuse to boot if any capability resolves to an unregistered type. That is the intended behaviour, but it must be validated against the live 17-row registry first, offline, before being enforced. |
| Verification | PV-10: with `CONNECTOR` deliberately unregistered, runtime construction fails loudly; with the live registry, it constructs cleanly and every live namespace has an executor. |

**C-05 — Make candidate ordering deterministic and stated**

| Field | Value |
|---|---|
| File(s) | `services/capabilities/repository.py:53` vs `:56-90`; `services/capabilities/policy.py` |
| Current responsibility | `resolve_candidates` builds an ordered candidate list; `CapabilityPolicyEngine.evaluate` selects one. |
| Exact problem | G-30. Registry-derived manifests are appended **before** connector-derived ones; the policy engine's entire logic is `candidates[0]` with the comment "Naive implementation: pick first candidate." Selection is therefore an accident of insertion order. |
| Proposed change | Give the policy engine one explicit, stated rule — **prefer a live connector-backed candidate over a registry-derived one** — and order candidates accordingly at construction so that ordering and policy agree. Keep it a single rule; do not build a scoring framework. |
| Why existing architecture cannot solve it | `CapabilityDescriptor` already carries a `priority` field (`capabilities/models.py`) that is currently hardcoded to `100` and never compared. The mechanism exists and is unused. |
| Dependencies | C-03. |
| Regression risk | **Low-medium.** Changes which candidate wins where both exist — which today is exactly the bug. |
| Verification | PV-11: for a namespace with both a registry row and a live connector, assert the connector candidate is selected, with the reason recorded in `CapabilityResult.logs`. |

### 17.3 Workstream W2 — Data integrity

**C-06 — Stop the manifest wipe (must precede any manifest repair)**

| Field | Value |
|---|---|
| File(s) | `services/connector/registry/persistence/odoo_adapter.py:121-162` (`_do_write`) |
| Current responsibility | Persist connector runtime state back to the `nexora_connector` record. |
| Exact problem | G-03. Line 135 `'manifest_json': data.get('manifest_json', '{}')`. Every full write that does not explicitly carry a manifest **overwrites the stored manifest with `{}`**. Live proof: 4 of 5 connectors hold `{}`, `{"broken": true}`, or a `sys.exit(1)` stub. The loss is silent and permanent. |
| Proposed change | Never default a persisted field to an empty value. Omit `manifest_json` from the write payload when the caller did not supply it, so the stored value is preserved. Apply the same rule to every field in `_do_write` that has a falsy default — a partial write must never be able to erase state it does not own. |
| Why existing architecture cannot solve it | The adapter already distinguishes present from absent keys via `data.get`; it simply chooses a destructive default. This is a one-line semantic correction, not new architecture. |
| Dependencies | C-01. **Blocks C-07** — repairing manifests before this lands guarantees re-corruption. |
| Regression risk | **Low.** Any caller that *intended* to clear a manifest must now do so explicitly. Grep shows no such intent. |
| Verification | PV-12: write a partial state update (e.g. `state` only) to a connector holding a valid manifest; assert `manifest_json` is byte-identical afterwards. |

**C-07 — Repair the corrupted manifests via migration**

| Field | Value |
|---|---|
| File(s) | New migration under `migrations/19.0.1.0.2/`; data in `nexora_connector.manifest_json` |
| Current responsibility | `manifest_json` should hold each connector's capability manifest; `_rebuild_capability_index` reads it. |
| Exact problem | G-03 damage. Live: `context7_mcp` len 2 `{}`; `firecrawl_mcp` len 2 `{}`; `github_mcp` len 16 `{"broken": true}`; `tavily_mcp` len 64 `{"command":"python","args":["-c","import sys; sys.exit(1)"]}`. Only `penpot_mcp` (len 792) is real. Two of the four are **test fixtures** (G-16) that leaked into the live DB. |
| Proposed change | A migration that, for each connector whose `manifest_json` is empty/`{}`/an obvious fixture, reconstructs the manifest from the authoritative source — the connector's own `nexora_mcp_discovered_tool` rows (67 live rows: context7 2, firecrawl 27, github 29, penpot 4, tavily 5). Where no discovered tools exist, leave the field null and let discovery repopulate it rather than fabricating content. **Do not** hand-write manifests. |
| Why existing architecture cannot solve it | Discovered tools already contain exactly the information a manifest needs, and discovery already knows how to obtain it. The repair is a projection of existing data, not new data. |
| Dependencies | **C-06 must land first.** Benefits from C-16 (test isolation) to prevent recurrence. |
| Regression risk | **Medium** — a migration writing connector data. Mitigate: idempotent, only touches rows matching the known-corrupt shapes, records the prior value in the migration log before overwriting. |
| Verification | PV-13: post-migration, every connector with discovered tools has a manifest whose capability set equals its discovered-tool set; a re-run of the migration is a no-op. |

**C-08 — Make the capability index actually populate**

| Field | Value |
|---|---|
| File(s) | `services/connector/runtime/connector_runtime.py:577-582` (`_rebuild_capability_index`), `:229` (`resolve_capability`) |
| Current responsibility | Maintain an in-memory namespace → capability index used by `resolve_capability`. |
| Exact problem | G-04. The rebuild reads **only** `connector.manifest.capabilities`. Because 4/5 manifests are corrupt (G-03), the index is empty; live `nexora_connector_capability` has **0 rows for all 5 connectors**. `resolve_capability` therefore cannot resolve anything. |
| Proposed change | Once C-07 restores manifests, the existing rebuild should populate correctly — verify this before changing the rebuild itself. If it still does not, the rebuild should draw from the same authoritative source chosen in C-11 rather than gaining a second fallback path. |
| Why existing architecture cannot solve it | It can — the rebuild is likely correct code operating on corrupt input. **Fix the input before touching the logic.** This entry exists to prevent a speculative rewrite. |
| Dependencies | C-07. Interacts with C-11 (authoritative capability store). |
| Regression risk | **Low** if it is input-only; re-assess if code changes prove necessary. |
| Verification | PV-14: after C-07, assert `nexora_connector_capability` row counts match discovered-tool counts per connector and `resolve_capability` returns a hit for a known namespace. |

**C-09 — Repair the registry hash gate**

| Field | Value |
|---|---|
| File(s) | `services/capabilities/bootstrap.py:60-108` (`execute_bootstrap`); `ir_config_parameter` key `nexora.mcp_registry_hash` |
| Current responsibility | Idempotently sync `config/mcp_registry.json` into `nexora_capability_registry`, skipping the sync when the file hash is unchanged. |
| Exact problem | G-08. Stored hash `4e8c39b4afe83f9b158fc149a48f404769c3363335e949393c68d4fc87e467c3` ≠ current file hash `BCCDEAB8313D6B946EB629362A0F0E8D3328F6C3E21E66524EEEC7F647E65EFF`. The DB therefore holds an *older* revision of the registry, proven live: the file says `mcp.github` is `enabled=false, lifecycle=planned`, the DB says `enabled=true, lifecycle=production`. Routing decisions are made from stale configuration. |
| Proposed change | Investigate **why** the gate did not re-fire before changing it — a stale hash with drifted content means either the sync ran and failed silently, or `set_param` ran without the sync, or the file changed while the module was not upgraded. The likely structural fault is that the hash is stored *after* a sync whose failure is not checked. Make hash storage conditional on verified sync success, and normalise hash case (stored lowercase vs computed uppercase is itself a comparison hazard worth confirming). |
| Why existing architecture cannot solve it | The gate exists and is the right idea. It lacks a success precondition and possibly a case-normalisation step. |
| Dependencies | C-01. Interacts with C-03 (registry rows determine target type). |
| Regression risk | **Medium** — a corrected gate will re-sync on next upgrade, which will rewrite `nexora_capability_registry` and may deactivate rows (`synchronize_manifests` deactivates missing rows unless `provider == 'nexora'`). The resulting row set must be predicted **before** enabling. |
| Verification | PV-15: with the current file, a forced sync produces a registry whose `enabled`/`lifecycle` per row matches the JSON exactly; the stored hash then equals the computed hash; a second run is a no-op. |

**C-10 — Close the seed/declaration gap**

| Field | Value |
|---|---|
| File(s) | `__manifest__.py` (3 connector XMLs); `data/` connector seed XMLs; `migrations/19.0.1.0.1/pre-migrate.py` |
| Current responsibility | Declare connectors, configs, and credentials as `noupdate="1"` seed data with stable external IDs. |
| Exact problem | G-18. Live `ir_model_data` holds **8** rows: penpot (3), tavily (3), firecrawl (2). There is **no `credential_firecrawl_api_key` xmlid** despite `FIRECRAWL_API_KEY` existing, and **no xmlids at all** for `context7_mcp` or `github_mcp` — both connectors, their configs and their credentials are entirely imperative. A clean install yields **3 of 5** connectors, **2 of 5** credentials, **0** discovered tools. |
| Proposed change | Add declarative seeds for `context7_mcp` and `github_mcp` (connector + config + credential placeholder) and the missing firecrawl credential placeholder, following the existing penpot/tavily XML pattern exactly. Credential **values** must never be seeded — only the credential record with `is_set=false`. Add an adoption migration so existing imperative rows acquire the new external IDs instead of being duplicated. |
| Why existing architecture cannot solve it | The pattern already exists and works (penpot/tavily/firecrawl). This is completion, not invention. `pre-migrate.py` already demonstrates the adoption technique for 6 xmlids. |
| Dependencies | C-01. |
| Regression risk | **Medium** — a botched adoption creates duplicate connectors. Mitigate: adopt by `connector_id` match, assert row counts unchanged after migration. |
| Verification | PV-16: on a clean database, `-i nexora_studio` yields all 5 connectors and 5 credential records (unset); on the live database, the migration leaves row counts unchanged and adds 5–6 `ir_model_data` rows. |

**C-11 — Declare one authoritative capability store**

| Field | Value |
|---|---|
| File(s) | `nexora_mcp_discovered_tool`, `nexora_connector_capability`, `nexora_capability_registry` models + their three writers (`capability_discovery.py`, `connector_runtime._rebuild_capability_index`, `capabilities/repository.synchronize_manifests`) |
| Current responsibility | Three tables independently describe "what capabilities exist". |
| Exact problem | G-25. No reconciliation rule exists. Live state: 67 rows in `discovered_tool`, **0** in `connector_capability`, 17 in `capability_registry` (of which 2 — `gsap_docs`, `mdn_docs` — are enabled and `verified` with **no connector at all**, G-19). Nobody can say which is authoritative, and each is written by a different subsystem. |
| Proposed change | **Decision, then ADR, then minimal code.** Recommended: `nexora_mcp_discovered_tool` is authoritative for *what a connector can actually do* (it is the only one populated from live protocol responses); `nexora_capability_registry` is authoritative for *what the platform is allowed to offer* (policy/enablement); `nexora_connector_capability` becomes a derived index or is dropped. Write the ADR in 44.2; implement the derivation only after the ADR is ratified. |
| Why existing architecture cannot solve it | All three stores already exist and two already work. The missing artefact is a *decision*, which is why this is specified as ADR-first. Building a fourth "unified" store would be exactly the speculative architecture the audit forbids. |
| Dependencies | C-07, C-08 (need real data before judging which store is viable). |
| Regression risk | **High if implemented hastily** — this is the largest consolidation in the platform. Specify in 44.2; stage the implementation behind the ADR. |
| Verification | PV-17: for every enabled capability, assert an execution backing exists; assert `gsap_docs`/`mdn_docs` either gain a connector or are disabled. |

### 17.4 Workstream W3 — Security

**C-12 — Remove the master key from plaintext config**

| Field | Value |
|---|---|
| File(s) | `d:\ODOO\configs\dev.conf`; `services/connector/security/odoo_secrets_provider.py:35-82` (key resolution) |
| Current responsibility | Supply the Fernet master key that encrypts every stored credential. |
| Exact problem | G-06. `nexora_connector_secret_key` sits in plaintext in `dev.conf`. Any filesystem read compromises **all** credentials (5 live encrypted values, including a 548-byte Penpot token and a 204-byte GitHub PAT). No production alternative is documented. |
| Proposed change | Keep the existing resolution order (`ir.config_parameter`-style Odoo config → env `NEXORA_CONNECTOR_SECRET_KEY` fallback) — it is already correct — and change *deployment*: remove the key from `dev.conf`, supply it via environment, document the production mechanism in an ADR, and ensure `dev.conf` can never be committed. **No code change is required**; the resolver already supports the secure path. |
| Why existing architecture cannot solve it | It already does. This is a configuration and documentation defect, not an architectural one — which is precisely why it must not be "fixed" with new code. |
| Dependencies | Must be resolved *before* C-01 stages any config file. |
| Regression risk | **Low, but operationally sharp** — if the env var is absent at boot, every credential decryption fails. Verify the env path works before removing the config line, and make the failure message state which mechanism was missing (see C-14). |
| Verification | PV-18: with the key supplied only via environment, all 5 credentials decrypt; with neither source present, boot fails with an explicit, non-secret-bearing message. |

**C-13 — Migrate `nexora.nvidia.api_key` out of `ir_config_parameter`**

| Field | Value |
|---|---|
| File(s) | `ir_config_parameter` (live row); the consuming AI-provider code |
| Current responsibility | Hold an NVIDIA API key for the AI routing layer. |
| Exact problem | G-07. Stored **plaintext** in `ir_config_parameter`, bypassing the encrypted credential subsystem entirely. It is included verbatim in every database dump and visible to any user with settings access. |
| Proposed change | Move the value into the existing encrypted credential store, read it through the existing resolver, and delete the parameter row in the same migration. Do not build a parallel mechanism for AI-provider keys — reuse `nexora_mcp_credential`/`OdooSecretsProvider`. |
| Why existing architecture cannot solve it | It can and should: Fernet encryption, the resolver, and the composite-key scheme all already exist and are used by 5 credentials. This key was simply never onboarded. |
| Dependencies | C-12 (key resolution must be trustworthy first). |
| Regression risk | **Medium** — breaks AI provider calls if the read path is not updated in the same change. Both sides must land together. |
| Verification | PV-19: the parameter row is absent; the AI provider authenticates successfully; a DB dump grep for the key prefix returns nothing. |

**C-14 — Make credential-resolution failure loud**

| Field | Value |
|---|---|
| File(s) | `services/connector/onboarding/mcp_onboarding_service.py:234-238`; `services/connector/connectors/mcp/transport.py:135` |
| Current responsibility | Resolve a connector's credentials and place them into the MCP configuration. |
| Exact problem | G-12. A bare `except Exception: pass` swallows resolution failure. `auth_secret` stays empty; the generic auth guard at `transport.py:135` requires a non-empty secret, so the transport connects **unauthenticated**. The operator sees a 401/403 or an opaque protocol error and diagnoses a network fault. |
| Proposed change | Remove the bare swallow. A connector configured with a `credential_key` whose resolution fails must **fail closed** with a message naming the connector and the credential key — never the value. Distinguish "no credential configured" (legitimate for the 4 stdio connectors with `auth_location='none'`) from "credential configured but unresolvable" (always an error). |
| Why existing architecture cannot solve it | The distinction is already expressible: `credential_key` is either set or not. The code currently collapses both into silence. |
| Dependencies | None. Pairs naturally with C-15. |
| Regression risk | **Low-medium** — a connector currently limping along unauthenticated would now fail at startup. That is the point, but it must be checked against all 5 live connectors before enforcement. |
| Verification | PV-20: with `PENPOT_API_KEY` made unresolvable, connection fails with an explicit message; log/exception scan confirms no secret value appears. |

**C-15 — Declare `env` as a first-class credential-delivery mode**

| Field | Value |
|---|---|
| File(s) | `services/connector/onboarding/mcp_onboarding_service.py:206-257` (esp. `:218` `resolve_all_for_connector`, `:242` `env_vars.update(resolved_secrets)`); `services/connector/connectors/mcp/transport.py:102-111`; `McpConfiguration` |
| Current responsibility | Deliver credentials to an MCP server. |
| Exact problem | G-21 + G-26 (§5.3). There are **two** delivery mechanisms and only one is modelled. The four stdio connectors all report `auth_location='none'` yet **do** authenticate — via `resolve_all_for_connector` decrypting *every* credential for the connector and injecting *all* of them into the child process environment under their credential names. This is an undeclared authentication path with an implicit naming contract, no validation, and a least-privilege violation. It is compounded by `process_env = os.environ.copy()` (`transport.py:102-111`), so the child also inherits the entire Odoo environment. |
| Proposed change | Make the existing behaviour **declared** rather than replacing it: add `env` as a valid `auth_location` value alongside `header`/`query`/`none`, so a stdio connector's authentication is visible in its configuration and validatable. Narrow injection from "all credentials" to "the credentials this connector declares", and consider restricting the inherited environment to an explicit allowlist. Write the ADR — this is one of the five missing ADRs (§14.5). |
| Why existing architecture cannot solve it | `auth_location` already exists as the declared axis of authentication; env delivery simply never joined it. Adding a third enum value is strictly smaller than any parallel mechanism, and it makes four currently-invisible authentications visible. |
| Dependencies | C-14. |
| Regression risk | **Medium-high** — all four stdio connectors depend on the current wholesale injection. Any narrowing must be validated per connector (`CONTEXT7_API_KEY`, `FIRECRAWL_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `TAVILY_API_KEY`) before the broad path is removed. Stage: declare first, narrow second. |
| Verification | PV-21: each stdio connector's config states `auth_location='env'`; each child process receives exactly its own declared credentials and no others; all four still authenticate. |

### 17.5 Workstream W4 — Lifecycle and runtime reliability

**C-16 — Make `health_status` a measurement, not an assertion**

| Field | Value |
|---|---|
| File(s) | `services/connector/integration/bootstrap.py:205-262` (`_startup_reconciliation`, esp. `:242`); `services/connector/connectors/mcp/health.py` |
| Current responsibility | Reconcile persisted connector state at startup and report health. |
| Exact problem | G-05. Line 242 force-writes `'health_status': 'healthy'` **before any probe runs**. Live proof: `github_mcp` is `healthy` while its Docker container is not running (`docker ps` shows no github-mcp container). The field asserts a fact the system never observed. Compounding it, `McpHealthCheck.check_health` calls `transport.list_tools()` and **swallows all exceptions** (`health.py`, 20 lines), so even a real probe cannot report failure distinctly. |
| Proposed change | Two parts. (a) Remove the force-write; introduce an explicit `unknown` health value for "not yet probed" so the field never lies, and let a probe be the only writer of `healthy`/`unhealthy`. (b) Make `check_health` distinguish *reachable*, *unreachable*, and *error*, rather than collapsing everything into a swallowed exception. Keep it generic — no per-connector probes. |
| Why existing architecture cannot solve it | The health-check component, the field, and the transport call all exist. The defect is that one writer bypasses measurement and the measurer discards its own result. |
| Dependencies | C-01. Should land with C-17 (state persistence) so lifecycle and health agree. |
| Regression risk | **Medium** — UI and `runtime_synchronizer` currently assume `healthy` is populated at startup. `unknown` must be handled by both (`runtime_synchronizer` already mishandles `degraded`, G-38 — fix the state alphabet in the same change, C-17). |
| Verification | PV-22: with the github-mcp container stopped, `github_mcp` reports `unhealthy` or `unknown`, never `healthy`; with Penpot running, Penpot reports `healthy` only after a successful probe. |

**C-17 — Unify the lifecycle-state persistence key and state alphabet**

| Field | Value |
|---|---|
| File(s) | `services/connector/runtime/connector_runtime.py` (`_on_health_change`, `_on_lifecycle_transition:192-223`); `services/connector/registry/persistence/odoo_adapter.py`; `services/connector/integration/runtime_synchronizer.py` |
| Current responsibility | Persist connector state transitions. |
| Exact problem | G-20 + G-38. `_on_health_change` writes `{'state': …}` while `_on_lifecycle_transition` writes `{'lifecycle_state': …}`, and the Odoo adapter recognises **only** `lifecycle_state`. Health-driven state changes are therefore **silently dropped**. Separately, `'degraded'` appears in neither `_RUNNING_STATES` nor `_TERMINAL_STATES` in `runtime_synchronizer.py`, so a degraded connector is invisible to reconciliation. |
| Proposed change | Pick one key — `lifecycle_state`, since the adapter and the majority of writers already use it — and make every writer use it. Then enumerate the complete state alphabet in one place and assert that every state belongs to exactly one of the running/terminal/transitional sets, so an unclassified state cannot be introduced silently again. |
| Why existing architecture cannot solve it | The state machine and the persistence adapter both exist and are individually reasonable; they simply disagree on a dictionary key. No new machinery is needed. |
| Dependencies | C-16. |
| Regression risk | **Low-medium** — state values previously dropped will now persist, which may surface connectors as non-running that the UI currently shows as running. That is the correction, not a regression. |
| Verification | PV-23: trigger a health-driven state change; assert it reaches `nexora_connector`; assert every member of the state alphabet is classified. |

**C-18 — Make `_active_connectors` thread-safe**

| Field | Value |
|---|---|
| File(s) | `services/connector/runtime/dispatcher.py:57` (`self._active_connectors = {}`), `:198-213` (`_get_or_create_connector`) |
| Current responsibility | Cache one live connector instance per `connector_id` across requests. |
| Exact problem | G-13. The dict is **not lock-protected** and `_get_or_create_connector` is a classic check-then-act: two concurrent requests for the same connector both miss, both construct, one wins the dict slot — the loser's transport (and, for stdio, its **child process**) is orphaned with no reference and no shutdown. |
| Proposed change | Guard creation with a lock and re-check under it, exactly as `SessionTransportPool` already does (`pool.py:54-67`, including disconnecting the losing instance). Copy the proven pattern rather than inventing one. |
| Why existing architecture cannot solve it | The correct pattern is already implemented in this codebase, in the sibling pool class. This is literal reuse. |
| Dependencies | None. |
| Regression risk | **Low** — the lock is held only around creation. Must not be held across `connect()`, which can block up to the connect timeout (see C-21). |
| Verification | PV-24: concurrent first-touch requests for one connector produce exactly one instance and zero orphaned subprocesses. |

**C-19 — Stop destroying the connector on every error**

| Field | Value |
|---|---|
| File(s) | `services/connector/runtime/dispatcher.py:215-260` (`_execute_on_connector`) |
| Current responsibility | Execute a request against a live connector and handle failure. |
| Exact problem | G-14. **Any** inner exception evicts the connector from `_active_connectors`, calls `shutdown()`, and re-raises. A transient tool-level error — a bad argument, a 404 from a remote API, a tool returning an error object — therefore tears down the transport, kills the stdio subprocess, and (when session binding is active) destroys every pooled session for that connector. |
| Proposed change | Distinguish **transport-fatal** errors from **request-level** errors and evict only on the former. The distinction already exists in the codebase: `_TRANSPORT_ERROR_CODES = {'TRANSPORT_ERROR','TIMEOUT','NO_EXECUTION_ADAPTER'}` (`connector_runtime.py:283`). Reuse that set as the eviction predicate. |
| Why existing architecture cannot solve it | The classification constant already exists and is already used elsewhere for exactly this kind of decision. The dispatcher simply does not consult it. |
| Dependencies | C-18 (eviction must be lock-consistent with creation). |
| Regression risk | **Medium** — retaining a connector after an error that *was* in fact fatal would produce repeated failures instead of one teardown. Mitigate by keeping the existing eviction as the default for anything not positively classified as request-level. |
| Verification | PV-25: a tool called with invalid arguments returns an error while the connector remains live and the next call succeeds on the same instance; a killed subprocess still triggers eviction. |

**C-20 — Propagate post-handshake transport failures**

| Field | Value |
|---|---|
| File(s) | `services/connector/connectors/mcp/transport.py:172-176` |
| Current responsibility | Surface connection and session errors from the background asyncio loop to the calling thread. |
| Exact problem | G-15. Errors are delivered to the caller only via `ready_future`. Once that future is `done()`, the handler's entire remaining behaviour is `_logger.error(f"Error in MCP connection: {e}")`. Every failure **after** a successful handshake — a dead subprocess, a dropped SSE stream, a server crash — is logged and swallowed. The transport continues to present as connected and subsequent calls fail opaquely. |
| Proposed change | Record the terminal error on the transport and mark it unusable, so the next operation fails immediately with the original cause instead of an unrelated timeout. Do not add reconnection logic in 44.2 — surfacing the failure correctly is the prerequisite, and single-flight recovery already exists at the runtime layer. |
| Why existing architecture cannot solve it | The runtime already has recovery machinery (single-flight, `threading.Timer` debounce, max 3 attempts). It cannot trigger because the transport never reports post-handshake death. Fixing the report activates existing recovery. |
| Dependencies | Interacts with C-19 (this is what produces a genuine transport-fatal signal). |
| Regression risk | **Medium** — failures currently invisible will become visible, which may surface as new errors in previously "working" flows. Those flows were already broken. |
| Verification | PV-26: kill a stdio child mid-session; assert the next call fails with a transport error naming the cause, and that runtime recovery is triggered. |

**C-21 — Honour `timeout_seconds` and add a shutdown hook**

| Field | Value |
|---|---|
| File(s) | `services/connector/connectors/mcp/transport.py:187` (`ready_future.result(timeout=60.0)`), `:210` (`_run_sync` default `60.0`); `services/connector/connectors/mcp/configuration.py`; `services/connector/runtime/dispatcher.py` (`_active_connectors` teardown) |
| Current responsibility | Bound connection and call duration; release resources at worker exit. |
| Exact problem | G-22 + G-23. `timeout_seconds` exists as a DB column (live value `60` on all 5 connectors) but is **never carried into `McpConfiguration`** (§4.2) — the timeout is hardcoded `60.0` in two places, so the column is decorative. Separately there is **no shutdown hook**: nothing tears down `_active_connectors` when an Odoo worker exits, so stdio subprocesses outlive their parent. |
| Proposed change | Carry `timeout_seconds` through the existing config path into both call sites — the plumbing for `working_directory`/`startup_policy` is missing for the same reason (G-46), so the same change decides whether those two are wired or dropped. Register a process-exit teardown that calls `shutdown()` on every entry in `_active_connectors`, reusing the existing cascade (`McpConnector.shutdown()` already cascades to `_pool.shutdown_all()`). |
| Why existing architecture cannot solve it | Both the column and the shutdown cascade already exist; neither is connected. This is wiring, not design. |
| Dependencies | C-18 (teardown must be lock-consistent). |
| Regression risk | **Low-medium** — a per-connector timeout shorter than 60s would change failure timing. All live connectors are set to 60, so live behaviour is unchanged. |
| Verification | PV-27: set one connector to a short timeout and observe it applied; assert no orphaned `npx`/`docker` processes remain after a clean worker shutdown. |

**C-22 — Make discovery non-destructive**

| Field | Value |
|---|---|
| File(s) | `services/connector/discovery/capability_discovery.py:147-181` |
| Current responsibility | Refresh `nexora_mcp_discovered_tool` from a live `tools/list` response. |
| Exact problem | G-17. The refresh is `unlink()` followed by `create()`. Every discovery run churns record IDs (breaking any reference to them), and any failure between the two leaves the connector with **zero** tools. The pattern also cannot distinguish "the server removed a tool" from "discovery failed". |
| Proposed change | Reconcile instead of replace: match on `(connector_id, tool_name)`, update existing rows, create new ones, and deactivate — not delete — those absent from a **successful** response. Skip all mutation entirely when the response is unsuccessful. |
| Why existing architecture cannot solve it | Odoo's ORM already provides the matching primitives, and `synchronize_manifests` (`repository.py:175-223`) already demonstrates the deactivate-rather-delete pattern in this same codebase. |
| Dependencies | C-02 (discovery depends on `tools.list` resolving correctly). |
| Regression risk | **Low-medium** — stale rows will linger as inactive rather than vanishing. That is the intended trade. |
| Verification | PV-28: two consecutive discovery runs leave record IDs stable; a forced failure mid-run leaves the previous 67 rows intact.

### 17.6 Workstream W5 — Test infrastructure

**C-23 — Isolate the test database**

| Field | Value |
|---|---|
| File(s) | Test bootstrap / CI invocation; `tests/` |
| Current responsibility | Run the module's tests. |
| Exact problem | G-16. Tests run against the **development database** and their fixtures have permanently corrupted real records: `{"broken": true}` on `github_mcp` and `{"command":"python","args":["-c","import sys; sys.exit(1)"]}` on `tavily_mcp` are both test artefacts sitting in live `manifest_json` columns. Combined with the manifest-wipe default (C-06), a test run is a data-loss event. |
| Proposed change | Establish a dedicated test database for `--test-enable` runs and make the connector tests operate only on records they create. This is a **prerequisite for C-24** — registering 44 additional test files against the dev database would multiply the damage. |
| Why existing architecture cannot solve it | Odoo's test framework already supports isolated databases and transactional test classes; the project simply does not use them for these tests. |
| Dependencies | **Blocks C-24.** Pairs with C-06 + C-07. |
| Regression risk | **None to production code.** |
| Verification | PV-29: run the currently-registered 8 modules against the test DB; assert the dev DB's `manifest_json` values are unchanged afterwards. |

**C-24 — Triage and register the 44 unregistered test files**

| Field | Value |
|---|---|
| File(s) | `tests/__init__.py` (9 lines, imports 8 modules); 52 files in `tests/` |
| Current responsibility | Declare which test modules Odoo executes. |
| Exact problem | G-11. **44 of 52 test files (85%) never execute.** They are not skipped or reported — they are invisible. The suite projects a coverage level that is 85% fictional, and every P0 in §16 is in the uncovered set. |
| Proposed change | **Triage before registering** (§13.6). Classify each of the 44: (a) still valid → register; (b) written against a since-changed API → repair or mark clearly; (c) requires real credentials or a live remote server → move to an explicitly-marked integration group excluded from the default run; (d) genuinely obsolete → propose deletion with justification. **Do not register all 44 blindly, and do not delete any of them in 44.2** — they are the largest existing asset for Phase 44.3. |
| Why existing architecture cannot solve it | Registration is a one-line-per-module mechanism that already works for 8 modules. The work is triage, not infrastructure. |
| Dependencies | **C-23 must land first.** |
| Regression risk | **None to production code**, but expect a large volume of newly-visible failures. Those failures are pre-existing defects becoming observable. |
| Verification | PV-30: every file in `tests/` is either registered, in the marked integration group, or listed with a documented reason; the default run is green or has an explicit, enumerated failure list. |

**C-25 — Add the invariant tests that would have caught this audit's P0s**

| Field | Value |
|---|---|
| File(s) | `tests/` (new cases inside existing modules where possible) |
| Current responsibility | — |
| Exact problem | §13.3: no registered test covers the router→policy→executor chain, `target_type` derivation, executor-registration completeness, `_build_request` namespace parsing, `SessionTransportPool`, lifecycle persistence keys, manifest preservation, capability-index rebuild, the registry hash gate, or discovery destructiveness. Every single P0 lived in that gap. |
| Proposed change | Add small, high-leverage invariant assertions — not broad suites: executor registration is complete for every reachable target type (would have caught G-01 in one line); `tools.list` parses as a protocol namespace (G-02); a partial write preserves `manifest_json` (G-03); the capability index is non-empty for a connector with discovered tools (G-04); `health_status` is never `healthy` without a probe (G-05); stored registry hash equals computed hash after sync (G-08); every lifecycle state is classified (G-17/G-38). |
| Why existing architecture cannot solve it | Nothing prevents these tests today; they were simply never written. |
| Dependencies | C-23; each test lands with its corresponding fix. |
| Regression risk | **None.** |
| Verification | Each assertion fails against pre-fix code and passes after — this is the acceptance criterion for the fix itself. |

### 17.7 Workstream W6 — Consolidation and hygiene

**C-26 — Eliminate the four parallel entry points**

| Field | Value |
|---|---|
| File(s) | `models/tavily_provider.py:44`, `models/github_provider.py:49`, `models/context7_provider.py:43`; `models/connector/nexora_connector.py:139-166` (`action_test_tool_execution`); `services/connector/runtime/dispatcher.py:276-322` (`initialize_and_verify`) |
| Current responsibility | Each independently reaches an MCP server. |
| Exact problem | G-24. Four routes bypass `UniversalCapabilityRouter`: three near-identical model providers calling `dispatch` directly, a UI action constructing its own `ConnectorExecutionTarget` with hardcoded `'tools.call'`/`'echo'`, and `initialize_and_verify` calling `sdk_connector.execute` directly to dodge the `_build_request` bug. Policy, security, credential injection, and observability differ per route — and the canonical path has **no live evidence of success for any connector**, while these bypasses do work. |
| Proposed change | Route all four through the canonical path **after** W1 makes it functional. The three model providers collapse into one generic mechanism (they differ only in connector id and tool name). `initialize_and_verify`'s bypass is deletable the moment C-02 lands — it exists solely because of G-02. `action_test_tool_execution` should call the same router as production rather than hardcoding a namespace and tool. |
| Why existing architecture cannot solve it | The canonical path exists; it is bypassed because it was broken. Fix W1 first and the bypasses become removable rather than load-bearing. **Order matters absolutely: removing a bypass before the canonical path works would break working functionality.** |
| Dependencies | **C-02, C-03, C-04, C-05 must all land and be verified first.** |
| Regression risk | **High** — these are the only paths with demonstrated success. Migrate one at a time, each with before/after evidence. |
| Verification | PV-31: each of the four flows produces an identical result through the router as it does today via its bypass; then the bypass is removed and the flow re-verified. |

**C-27 — Consolidate duplicated logic**

| Field | Value |
|---|---|
| File(s) | `mcp_onboarding_service.py:294-307` and `:360-373` (verbatim 12-key `user_overrides` dict); `odoo_adapter.py` (background-thread cursor detection ×4); `nexora_connector.action_discover_mcp_capabilities:183-190` (triple-fallback runtime resolution) vs `bootstrap.get_connector_runtime():306-309` vs `ConnectorPlatformBootstrap.get_instance()`; `runtime_synchronizer.py:137` (private `_runtime` access) |
| Current responsibility | Four unrelated duplications (§15.2 #2, #3, #4, #26). |
| Exact problem | The `user_overrides` dict is byte-identical in two places; cursor detection is written four times; there are three ways to obtain the runtime and one caller tries all three in sequence — direct evidence that no reliable accessor exists; and `runtime_synchronizer` reaches into a private attribute across the boundary it is supposed to reconcile. |
| Proposed change | One module constant for `user_overrides`; one private helper for cursor detection; **one** canonical runtime accessor with the triple-fallback deleted; a public accessor replacing the `_runtime` reach-through. |
| Why existing architecture cannot solve it | Pure de-duplication of existing behaviour. No design decisions involved. |
| Dependencies | None. Independent of every other change — safe to do early. |
| Regression risk | **Low.** The triple-fallback removal is the only one needing care: confirm the single accessor works in all three calling contexts (HTTP request, background thread, post-load) before deleting the fallbacks. |
| Verification | PV-32: `action_discover_mcp_capabilities` works via the single accessor from all three contexts; grep confirms one definition each. |

**C-28 — Logging and error-message hygiene**

| Field | Value |
|---|---|
| File(s) | `connector_runtime.py:200,206,210,214,219,222,223` (6 × `print()` + `traceback.print_exc()`); `dispatcher.py:150-196` (5 × `DISPATCHER:` f-string INFO + shadowed module logger); `capability_discovery.py:99-101` and `connection_tester.py:141` (raw-payload INFO); `connection_tester.py:200,225-241` and `nexora_connector.py:196` (full traceback into user-facing message, then persisted); `transport.py:10-35` (`trace_file` writes unredacted wire frames, uncapped, unrotated) |
| Current responsibility | Diagnostics and user-facing error reporting. |
| Exact problem | G-40 through G-44. Raw `print()` bypasses Odoo's logging entirely (no level, no handler, no correlation). The shadowed module logger in `dispatcher._resolve_connector` is an outright bug. Raw payload logging at INFO is both noise and a potential disclosure surface. Full tracebacks are shown to users **and persisted** to the record. `trace_file`, though dormant, is an unredacted plaintext sink for every MCP frame. |
| Proposed change | Replace `print()`/`print_exc()` with the module logger; remove the shadowing; demote raw payloads out of INFO and route them through one redacting helper; log tracebacks and show users a message; require `trace_file` to be explicitly opt-in with redaction and a size bound. |
| Why existing architecture cannot solve it | A module logger already exists in every affected file. This is substitution. |
| Dependencies | None. Safe to do early and independently. |
| Regression risk | **Very low.** |
| Verification | PV-33: grep finds zero `print(` / `traceback.print_exc()` in `services/connector`; a forced failure produces a logged traceback and a clean user message; no decrypted secret appears in any log at any level. |

**C-29 — Remove provably dead code**

| Field | Value |
|---|---|
| File(s) | `services/source_framework/transport/mcp_transport.py` (`DeprecationWarning` at line 6); `sdk/connector_components.py:89` (`TypeError` arity fallback); `connector_executor.py:29-42` (`ImportError` stub shim); `factory/connector_factory.py:47-51` (dead sub-factories); `capabilities/strategy.py` (`FallbackStrategy` empty branch); `capabilities/resolver.py` (9-entry stale `provider_map`); `router.py:48` (`_reviewer` suffix shortcut); `executors/local.py:37` (mock-success branch); `connector_runtime.py:229,584` (undefined `ConnectorCapability` / `ConnectorEvent` annotations); `__manifest__.py` (`httpx2` in `external_dependencies`) |
| Current responsibility | Nothing — each is dead, stale, or actively harmful (§15.3). |
| Exact problem | G-31, G-33, G-37, G-45, G-51 plus §15.3 items 1, 3, 4, 5, 7, 19, 24. Of these, two are **not** merely cosmetic: `LocalToolExecutor`'s mock-success branch (G-10) returns `success=True, result="Executed locally (mock)"` whenever `tool_registry is None` — which is every non-HTTP context, so cron/queue/CLI executions silently "succeed" doing nothing; and the undefined annotations are latent `NameError`s. `CapabilityResolver.provider_map`'s 9 entries (`mcp.eslint`, `mcp.playwright`, `mcp.search`, 6 × `*_reviewer`) match **no** live connector and **no** registry row. |
| Proposed change | Remove each after confirming no importer remains. **The mock-success branch must fail loudly instead of returning success** — that is a behaviour fix, not a deletion, and it is P0. `router.py:48`'s `_reviewer` shortcut is a connector-specific hack in generic code and goes with `provider_map`. The legacy `source_framework` transport must be deleted **before** the arity shim that exists only to accommodate it. Verify `httpx2` against the actual imports (`httpx` is what the code uses) rather than assuming. |
| Why existing architecture cannot solve it | Deletion is the change. |
| Dependencies | The `source_framework` transport must precede the arity shim. The mock-success fix is independent and should be done early (it is a P0). |
| Regression risk | **Low for the deletions; medium for the mock-success fix** — flows that appear to work today will start failing. They were never actually working. |
| Verification | PV-34: module imports and boots cleanly after each removal; a cron/queue execution with no tool registry now fails explicitly instead of reporting success. |

**C-30 — Data cleanup and remaining decisions**

| Field | Value |
|---|---|
| File(s) | `nexora_connector.working_directory` on `penpot_mcp`; live `firecrawl` `startup_command`; `nexora_capability_registry` rows for `gsap_docs`/`mdn_docs`; ADR-0067; the 5 missing ADRs (§14.5) |
| Current responsibility | Residual data and documentation inconsistencies. |
| Exact problem | G-46/§15.3 #13: `penpot_mcp.working_directory` holds `C:/Users/kusha/AppData/Roaming/npm/node_modules/@penpot/mcp/packages/server`, meaningless for an `sse` connector — a leftover from a prior stdio attempt. G-47: `firecrawl` uses `npx` while the others use `npx.cmd`, working only by PATHEXT accident on Windows. G-19: `gsap_docs`/`mdn_docs` are enabled and `verified` with no connector. G-49: ADR-0067 names `McpTransportPool` (actual: `SessionTransportPool`), specifies a TTL "reap" with no background reaper, and is still `Proposed`. G-50: five load-bearing decisions have no ADR. |
| Proposed change | Clear the stale `working_directory` via migration; normalise `firecrawl` to `npx.cmd`; either give `gsap_docs`/`mdn_docs` connectors or disable them in the registry file (the file is authoritative, §12.1); reconcile ADR-0067 to the implementation's names and honest eviction semantics and add a max-size bound; write the five missing ADRs — the credential-delivery contract (C-15) and the namespace contract (C-02) are the two that block code changes and must come first. |
| Why existing architecture cannot solve it | Data and documentation only. |
| Dependencies | The registry-file edit interacts with C-09 (hash gate) — changing the file changes the hash, so it must be done deliberately and the resulting sync predicted. |
| Regression risk | **Low**, except the registry-file edit, which triggers a re-sync (C-09 regression note). |
| Verification | PV-35: `penpot_mcp.working_directory` is empty; every enabled registry capability has an execution backing; ADR-0067 names match the code; each ADR in §14.5 exists. |

### 17.8 Sequencing and dependency order

| Wave | Changes | Rationale |
|---|---|---|
| **0** | C-12 (remove key from config, first) → C-01 (commit) | Never commit a secret. Then eliminate the total-loss risk before touching anything. |
| **1** | C-06, C-28, C-27, C-29 (mock-success part) | Stop ongoing data loss; zero/low-risk hygiene; independent of everything. |
| **2** | C-23 → C-25 (per-fix invariants) | Test isolation must exist before any behavioural change is validated. |
| **3** | C-02 (ADR + parse) → C-03 → C-05 → C-04 | The routing contract, in strict order. Contract, then derivation, then ordering, then completeness enforcement. |
| **4** | C-07, C-08, C-09, C-22 | Data repair, once the wipe is stopped and `tools.list` resolves. |
| **5** | C-16, C-17, C-18, C-19, C-20, C-21 | Runtime reliability. C-16/C-17 together; C-18 before C-19/C-21. |
| **6** | C-14 → C-15, C-13 | Credential correctness, then declaration, then the NVIDIA key. |
| **7** | C-10, C-24, C-30, C-29 (deletions) | Reproducibility, test triage, cleanup. |
| **8** | C-26, C-11 | The two highest-risk consolidations, last, only after the canonical path is proven. |

**Absolute ordering constraints** (violating any of these causes damage):

1. **C-12 before C-01** — committing `dev.conf` would publish the master key.
2. **C-06 before C-07** — repairing manifests before stopping the wipe guarantees re-corruption.
3. **C-23 before C-24** — registering 44 test files against the dev DB would corrupt live records at scale.
4. **C-02 before C-26** — the bypasses are the only working paths; they may not be removed until the canonical path works.
5. **C-03 before C-04** — enforcing executor completeness before target-type derivation is fixed would refuse to boot.
6. **C-18 before C-19 and C-21** — eviction and teardown must be lock-consistent with creation.

### 17.9 What Phase 44.2 must NOT do

| Prohibition | Reason |
|---|---|
| Do not register `RemoteToolExecutor` as it stands | It returns unconditional `success=True`; registering it converts every failure into a silent success — strictly worse than `Executor not found`. |
| Do not modify `SessionTransportPool` beyond a max-size bound | §7.4 verdict: dormant but correct. It is the cleanest component in the subsystem. |
| Do not build a fourth capability store | C-11 is a decision about the three that exist, not an invitation to add another. |
| Do not add `streamable_http` / `websocket` transports | G-35 is P2 with no current consumer. Speculative. |
| Do not implement `SecurityLayer` authorization speculatively | G-27 requires a policy decision (who may call what) that does not exist yet. Either decide it properly or leave the no-op documented as a no-op. |
| Do not delete any test file | §13.6. Triage only. |
| Do not "fix" the `basic` auth scheme's missing base64 | G-34 is latent — no connector uses `basic`. Fix it when something needs it, with a test. |
| Do not add reconnection logic to the transport | C-20 surfaces failures so that *existing* runtime recovery can act. Adding a second recovery mechanism would duplicate it. |
| Do not touch `config/mcp_registry.json` casually | It is authoritative (§12.1) and hash-gated. Every edit triggers a re-sync that can deactivate registry rows. |

---

## 18. Phase 44.3 Certification Specification

Phase 44.3 certifies the platform. It is **not** a second implementation phase. Every gate below is a binary PASS/FAIL with a named observation and a named artefact. No gate may be certified by reading code, by reading a prior report, or by asserting that a change "was made".

### 18.0 Preconditions for entering Phase 44.3

Certification may not begin until all of the following hold. If any fails, 44.3 is aborted and returned to 44.2.

| # | Precondition | How established | If it fails |
|---|---|---|---|
| PC-1 | All Phase 44.2 changes are committed; working tree clean | `git status --porcelain` returns zero entries | Abort — results are not attributable to a known revision |
| PC-2 | An isolated certification database exists, restored from a dump of the live DB | C-23 delivered; DB name recorded in the report | Abort — certification must not write to the dev DB |
| PC-3 | The master encryption key is supplied from the environment only | `dev.conf` contains no `nexora_connector_secret_key` (C-12) | Abort — cannot certify a platform whose key is in a config file |
| PC-4 | A pre-certification snapshot of the 8 evidence queries in §11 is captured | SQL output archived alongside the report | Abort — no baseline to diff against |
| PC-5 | Container state is recorded | `docker ps` output archived | Abort — health results are uninterpretable without it |
| PC-6 | The intended-vs-actual reconciliation ADRs from C-02, C-11, C-15 are `Accepted` | ADR files present with status `Accepted` | Abort — cannot certify against an undecided contract |

### 18.1 Evidence rules binding every gate

| Rule | Statement |
|---|---|
| E-1 | Every PASS requires a captured artefact: SQL output, log excerpt, command exit status, or test-run summary. A narrative claim is not evidence. |
| E-2 | **No decrypted secret value, and no prefix or suffix of one, may appear in any artefact.** Presence/absence, length, and record ID only. |
| E-3 | Negative tests are mandatory where specified. A gate that only demonstrates the success path is FAIL. |
| E-4 | Idempotency is mandatory where specified: run twice, assert the second run is a no-op. |
| E-5 | Any gate that cannot be observed without modifying production state must be run on the certification DB (PC-2), never the dev DB. |
| E-6 | A gate whose observation is inconclusive is recorded **FAIL**, not "partial". There is no partial credit. |

### 18.2 Gate group A — Routing contract correctness

| Gate | Certifies | PASS criteria | FAIL criteria |
|---|---|---|---|
| **CG-01** | Protocol namespaces route correctly (C-02, PV-8) | `tools.list` executed through `UniversalCapabilityRouter` returns a tool list. `penpot_mcp.export_shape` still resolves to the Penpot connector. A no-dot namespace and a two-dot namespace each behave exactly as the ratified ADR states. | Any of the three returns `CONNECTOR_NOT_FOUND`, or behaviour differs from the ADR text. |
| **CG-02** | Live connectors resolve to an executable target type (C-03, PV-9) | For all 5 live connectors, `get_manifests_by_namespace('<connector_id>.<tool>')` yields a `CONNECTOR` candidate. **No** live namespace resolves to `REMOTE`. | Any live namespace resolves to `REMOTE`, or any connector yields no candidate. |
| **CG-03** | Executor coverage is fail-closed (C-04, PV-10) | With `CONNECTOR` deliberately unregistered, runtime construction raises at boot with an explicit message. With the real registry, construction succeeds and every target type present in the live registry has an executor. | Runtime constructs successfully with a missing executor, or boots into a state where `Executor not found` is reachable. |
| **CG-04** | Candidate selection is deterministic and explained (C-05, PV-11) | For a namespace with both a registry row and a live connector, the connector candidate is selected on 10/10 runs, and `CapabilityResult.logs` names the selection reason. | Selection varies across runs, or no reason is recorded. |
| **CG-05** | `Executor not found` is unreachable for live configuration | A scripted sweep of all 67 discovered tools plus the 6 generic namespaces produces zero `Executor not found` results. | One or more produce it. |
| **CG-06** | No silent success remains on the path (C-29) | A negative sweep — invalid tool name, invalid arguments, connector stopped — returns `success=False` with a distinguishable error code in every case. | Any failure scenario returns `success=True`. |

### 18.3 Gate group B — Data integrity

| Gate | Certifies | PASS criteria | FAIL criteria |
|---|---|---|---|
| **CG-07** | Partial writes preserve manifests (C-06, PV-12) | A partial state update to a connector holding a valid manifest leaves `manifest_json` byte-identical. Repeated for all 5 connectors and for a state change, a health change, and an error-count change. | Any write shortens, blanks, or replaces `manifest_json`. |
| **CG-08** | Manifests are repaired and stay repaired (C-07, PV-13) | All 5 connectors hold a manifest whose capability set equals their discovered-tool set. `length(manifest_json) > 100` for all 5. A full boot + health cycle + discovery run leaves them intact. Migration re-run is a no-op. | Any manifest remains `{}`, `{"broken": true}`, or the `sys.exit(1)` fixture; or any re-corrupts after a cycle. |
| **CG-09** | Capability index is populated and usable (C-08, PV-14) | `nexora_connector_capability` row count per connector equals its discovered-tool count (67 total). `resolve_capability` returns a hit for a known namespace on every connector. | Any connector has 0 rows, or `resolve_capability` misses a known namespace. |
| **CG-10** | Registry hash gate is truthful (C-09, PV-15) | Stored `nexora.mcp_registry_hash` equals the freshly computed hash of `config/mcp_registry.json`. Every registry row's `enabled` and lifecycle match the JSON. A second sync is a no-op. Editing the JSON and re-syncing propagates the change. | Hash mismatch, any row contradicting the JSON, or a sync that is not idempotent. |
| **CG-11** | `mcp.github` contradiction is resolved | DB `metadata_json` for `mcp.github` matches the JSON exactly for `enabled` and `lifecycle`. | Any residual contradiction. |
| **CG-12** | Exactly one capability store is authoritative (C-11) | The accepted ADR names one authoritative store; the other two are documented as derived, with the derivation direction implemented and tested. | No ADR, or an implementation contradicting it. |
| **CG-13** | Advertised capabilities have execution backings (C-11, PV-17) | Every `enabled=true` registry capability maps to a live connector, or is `enabled=false`. `gsap_docs` and `mdn_docs` resolved either way. | Any enabled capability with no backing. |

### 18.4 Gate group C — Credential security

| Gate | Certifies | PASS criteria | FAIL criteria |
|---|---|---|---|
| **CG-14** | Master key is not on disk in plaintext (C-12, PV-18) | `dev.conf` and every config file contain no key material. With the key supplied only via environment, all 5 credentials decrypt. With neither source present, boot fails with an explicit message containing no key material. | Key present in any config file, or a silent fallback path exists. |
| **CG-15** | No plaintext secret in `ir_config_parameter` (C-13, PV-19) | `nexora.nvidia.api_key` is absent. A scan of all `ir_config_parameter` rows for high-entropy values and known key prefixes returns zero hits. The AI provider still authenticates. | Any plaintext secret remains, or the provider breaks. |
| **CG-16** | Credential-resolution failure is loud (C-14, PV-20) | With `PENPOT_API_KEY` made unresolvable, the connection fails with an explicit message naming the credential key (not its value). The connector never enters `healthy`. | Silent fallback to an unauthenticated connection, or a misleading network error. |
| **CG-17** | Credential delivery is declared and least-privilege (C-15, PV-21) | Each stdio connector declares `auth_location='env'`. Each child process receives exactly its declared credentials and no others — verified by a manifest of injected variable **names**. All four still authenticate. | Any connector injects a credential it does not declare, or any still reports `auth_location='none'` while authenticating. |
| **CG-18** | No secret reaches any sink (PV-33 subset) | A grep of all logs at DEBUG level, all `last_test_result_json` / `last_error_message` fields, all raised exception texts, and any `trace_file` produced during certification finds zero occurrences of any decrypted value. Pool logs show hash prefixes only. | Any single occurrence. |
| **CG-19** | Secrets are absent from URLs in observable form | For `penpot_mcp` (query-param auth), the token appears only on the wire, never in a logged URL, never in an exception message, never in a DB field. | Any logged or persisted URL carrying the token. |

### 18.5 Gate group D — Lifecycle and runtime reliability

| Gate | Certifies | PASS criteria | FAIL criteria |
|---|---|---|---|
| **CG-20** | Health is measured, never asserted (C-16, PV-22) | With the github-mcp container stopped, `github_mcp` reports `unhealthy` or `unknown` — never `healthy`. With Penpot running, Penpot reports `healthy` only after a successful probe, and the probe is visible in logs with a timestamp. Boot does not write `healthy` to any connector. | Any connector reports `healthy` without a successful probe, or boot force-writes health. |
| **CG-21** | Lifecycle state reaches the database (C-17, PV-23) | A health-driven transition is observable in `nexora_connector.state`. Every member of the state alphabet — including `degraded` — is classified by the synchronizer. Both persistence paths use one key. | Any transition dropped, or `degraded` unclassified. |
| **CG-22** | Connector creation is race-free (C-18, PV-24) | 20 concurrent first-touch requests for one connector produce exactly one instance. Process count before and after differs by exactly the expected number of children. Zero orphans. | More than one instance, or any orphaned child. |
| **CG-23** | Tool errors do not destroy the connector (C-19, PV-25) | A tool called with invalid arguments returns an error; the connector remains live; the next call succeeds **on the same instance** (identity asserted). A killed subprocess still triggers eviction. | Connector torn down on a tool-level error, or a genuinely dead transport retained. |
| **CG-24** | Transport failures propagate (C-20, PV-26) | Killing a stdio child mid-session causes the next call to fail with a transport error naming the cause; runtime recovery is triggered; recovery is attempted at most 3 times, then the connector rests in a terminal state. | Failure only logged, an opaque timeout, or unbounded retries. |
| **CG-25** | Configured timeouts are honoured (C-21, PV-27) | One connector set to a short timeout demonstrably times out at that value ±20%. Default remains 60s. After a clean worker shutdown, zero `npx`/`node`/`docker` children remain. | Timeout ignored, or any surviving child process. |
| **CG-26** | Pool remains dormant or is bounded (C-30) | Either no connector uses `request_context` and no pool is constructed (asserted), or the max-size bound is enforced with eviction and the loser-transport disconnect verified. | An unbounded pool reachable in production configuration. |

### 18.6 Gate group E — Discovery and reproducibility

| Gate | Certifies | PASS criteria | FAIL criteria |
|---|---|---|---|
| **CG-27** | Discovery is non-destructive (C-22, PV-28) | Two consecutive discovery runs leave `nexora_mcp_discovered_tool` IDs stable. A forced mid-run failure leaves the previous 67 rows intact. A genuinely removed tool is deactivated, not silently dropped, and is distinguishable from a failed run. | ID churn, any zero-tool window, or a failure indistinguishable from removal. |
| **CG-28** | Live state is reproducible from the repository (C-10, PV-16) | On a clean database, `-i nexora_studio` yields all 5 connectors and all 5 credential records (unset, `is_set=f`). All 5 connectors and 5 credentials have `ir_model_data` entries. On the certification DB, the migration changes no row counts. | Any connector or credential still undeclared, or install producing a different set. |
| **CG-29** | Configuration has no decorative columns (C-30, PV-35) | `working_directory` is either honoured by the stdio path or empty for all connectors. `startup_policy` is either honoured or removed. `timeout_seconds` is honoured (CG-25). | Any column persisted, documented, and ignored. |
| **CG-30** | Discovery covers the declared generic set | All 6 generic namespaces behave per contract on every connector: supported ones return data, unsupported ones return a clear `CAPABILITY_NOT_FOUND`, never a hang or a crash. | Any namespace producing an unhandled exception or a hang. |

### 18.7 Gate group F — Test infrastructure

| Gate | Certifies | PASS criteria | FAIL criteria |
|---|---|---|---|
| **CG-31** | Tests cannot touch production data (C-23, PV-29) | The full registered suite runs against the certification DB. Afterwards, the dev DB's `manifest_json`, connector count, and discovered-tool count are unchanged (diffed against the PC-4 snapshot). | Any dev-DB row changed by a test run. |
| **CG-32** | Test registration is complete and honest (C-24, PV-30) | Every file in `tests/` is registered, in a marked integration group, or listed with a documented reason. The default run is green, or has an explicitly enumerated and justified failure list. Count reconciles to 52. | Any silently unregistered file, or an unexplained failure. |
| **CG-33** | Each P0 has a regression test (C-25) | For each of G-01…G-11, a named test exists that **fails against the pre-44.2 revision** and passes after. This bidirectional proof is mandatory. | Any P0 without a test, or a test that passes on the old revision. |
| **CG-34** | Invariants are enforced by tests, not by review | Automated tests assert: manifests never blank on partial write; health never `healthy` without a probe; no plaintext secret in `ir_config_parameter`; every enabled capability has a backing; registry hash matches file. | Any invariant enforced only by convention. |

### 18.8 Gate group G — Architectural consolidation

| Gate | Certifies | PASS criteria | FAIL criteria |
|---|---|---|---|
| **CG-35** | One execution path (C-26, PV-31) | Grep finds zero direct `dispatch`/`ConnectorExecutionTarget` construction outside the canonical path. The 3 model providers, `action_test_tool_execution`, and `initialize_and_verify` all route through the router, with results identical to their pre-consolidation behaviour. | Any surviving bypass, or a behavioural regression in a converted flow. |
| **CG-36** | No duplicated infrastructure logic (C-27, PV-32) | Exactly one runtime accessor, one cursor-detection helper, one `user_overrides` construction, one transport implementation. Grep proves one definition each. | Any duplicate remaining. |
| **CG-37** | Logging and error hygiene (C-28, PV-33) | Zero `print(` / `traceback.print_exc()` under `services/connector`. Zero shadowed loggers. No raw payload logged at INFO. No traceback in a user-facing message. Forced failures produce a logged traceback and a clean user message. | Any occurrence. |
| **CG-38** | Dead code removed without behaviour change (C-29, PV-34) | Module imports and boots cleanly. The removed items (`_register_executor_with_ucel` stub, dead sub-factories, `_reviewer` shortcut, stale `provider_map`, legacy transport, arity shim, mock-success branch) are gone, and a cron/queue execution with no tool registry now fails explicitly. | Any removal that changes intended behaviour, or any item retained without justification. |
| **CG-39** | Documentation matches implementation (PV-35) | ADR-0067 is `Accepted`, names `SessionTransportPool`, and describes actual eviction. Every ADR listed in §14.5 exists. `external_dependencies` names `httpx`. This report's §14.3 table is updated to show INTENT = IMPL = LIVE. | Any residual mismatch. |
| **CG-40** | Undefined annotations resolved | `ConnectorCapability` and `ConnectorEvent` are imported or removed; a static check reports zero undefined names in `services/connector`. | Any latent `NameError`. |

### 18.9 Certification arithmetic

| Group | Gates | Blocking |
|---|---|---|
| A — Routing | CG-01 … CG-06 | Yes |
| B — Data integrity | CG-07 … CG-13 | Yes |
| C — Credential security | CG-14 … CG-19 | Yes |
| D — Lifecycle | CG-20 … CG-26 | Yes |
| E — Discovery/reproducibility | CG-27 … CG-30 | Yes |
| F — Test infrastructure | CG-31 … CG-34 | Yes |
| G — Consolidation | CG-35 … CG-40 | No — advisory if W6 is deferred |
| **Total** | **40 gates** | **34 blocking** |

**Overall verdict rule:** the platform is CERTIFIED only if all 34 blocking gates PASS. 33/34 is NOT certified. Group G gates may be recorded as `DEFERRED` if and only if Wave 8 is explicitly deferred and each deferral is listed in the risk register.

### 18.10 Conditions that invalidate a certification result

| # | Invalidating condition |
|---|---|
| I-1 | Any gate certified from code reading rather than observation |
| I-2 | Any gate certified against the dev DB instead of the certification DB |
| I-3 | Any change to implementation code made **during** 44.3 to make a gate pass — that returns the work to 44.2 and voids all gates run before it |
| I-4 | Any artefact containing a secret value — the artefact must be destroyed and the gate re-run |
| I-5 | A working tree that is dirty at the moment a gate is run |
| I-6 | A negative test omitted where §18 marks it mandatory |
| I-7 | Container/service state changing mid-certification without being re-recorded |

### 18.11 Required 44.3 deliverable

A single report, `docs/reports/phase44_3_platform_certification.md`, containing: the PC-1…PC-6 precondition record; a 40-row gate table with PASS/FAIL/DEFERRED, the artefact reference, and the observed value for each; the diff of the §11 evidence queries before and after; the bidirectional CG-33 proof matrix; the residual risk register; and the overall verdict computed by §18.9. Gates must be reported in group order with no reordering to flatter the result.

---

## 19. Risk Register

Two distinct risk classes are recorded separately: **standing risks** that exist right now in the platform as it stands, and **execution risks** created by carrying out Phase 44.2.

Likelihood/Impact: H / M / L. Exposure = the product, expressed as **Critical / High / Medium / Low**.

### 19.1 Standing risks (present today, before any change)

| ID | Risk | Likelihood | Impact | Exposure | Evidence | Current mitigation | Residual after 44.2 |
|---|---|---|---|---|---|---|---|
| R-01 | Seven phases of work are lost to a single careless git command | M | H | **Critical** | 85 working-tree entries incl. `pool.py`, the 43.8 migration, all Phase 37–43 reports | **None** | Eliminated by C-01 |
| R-02 | Filesystem read of `configs/dev.conf` yields the master key and therefore all 5 credentials | M | H | **Critical** | plaintext `nexora_connector_secret_key` | None — the file is the documented mechanism | Eliminated by C-12 |
| R-03 | A DB dump distributes `nexora.nvidia.api_key` in plaintext | H | M | **High** | live `ir_config_parameter` row | None | Eliminated by C-13 |
| R-04 | Silent, permanent manifest loss on any partial connector write | H | H | **Critical** | `odoo_adapter.py:135`; 4/5 manifests already destroyed | None — already occurred | Eliminated by C-06; damage repaired by C-07 |
| R-05 | Operators trust `health_status='healthy'` and it means nothing | H | H | **Critical** | `bootstrap.py:242`; `github_mcp` healthy with a stopped container | None | Eliminated by C-16 |
| R-06 | The canonical router cannot execute the platform's own connectors; only bypasses work | H | H | **Critical** | `router.py:54` + `mcp.penpot` = REMOTE + REMOTE unregistered | 4 bypasses that each reimplement dispatch | Eliminated by C-02/C-03/C-04 |
| R-07 | Cron, queue and CLI executions report success without executing anything | H | H | **Critical** | `local.py:37` mock branch + `generation_runtime.py:54-58` | None | Eliminated by C-29 |
| R-08 | Routing decisions are made from a stale registry revision | H | M | **High** | stored hash ≠ file hash; `mcp.github` contradiction | None | Eliminated by C-09 |
| R-09 | Running the test suite corrupts live connector records | H | H | **Critical** | `{"broken": true}` and `sys.exit(1)` fixtures persisted in production rows | Suite is 85% unregistered, which accidentally limits the blast radius | Eliminated by C-23 |
| R-10 | A regression ships undetected because 44/52 test files never run | H | M | **High** | `tests/__init__.py` | None | Reduced by C-24; not eliminated until coverage is proven |
| R-11 | An unauthenticated MCP connection is silently established and diagnosed as a network fault | M | M | **Medium** | `mcp_onboarding_service.py:234-238` + `transport.py:135` guard | None | Eliminated by C-14 |
| R-12 | A concurrent first-touch race orphans a live subprocess with no owner and no shutdown | M | M | **Medium** | `dispatcher.py:57`, `:198-213` | Lazy startup makes first-touch rare but not absent | Eliminated by C-18 |
| R-13 | A transient tool-level error tears down transport, subprocess and pooled sessions | H | M | **High** | `dispatcher.py:215-260` | Recovery re-creates it, at cost | Eliminated by C-19 |
| R-14 | stdio children outlive the Odoo worker and accumulate | M | M | **Medium** | no shutdown hook | OS reclaims on host restart | Eliminated by C-21 |
| R-15 | A dead subprocess presents as a connected transport that fails opaquely | M | M | **Medium** | `transport.py:172-176` | 60s timeout eventually fires | Eliminated by C-20 |
| R-16 | Each MCP child process inherits the full `os.environ` plus every credential of its connector | H | M | **High** | `transport.py:102-111`; `mcp_onboarding_service.py:242` | Trust in the child package | Reduced by C-15 to declared credentials only |
| R-17 | A discovery failure leaves a connector with zero tools and churned IDs | M | M | **Medium** | `capability_discovery.py:147-181` | Re-running discovery usually restores it | Eliminated by C-22 |
| R-18 | The live database cannot be rebuilt from the repository | H | M | **High** | 2/5 connectors, 3/5 credentials undeclared | Manual reconstruction | Eliminated by C-10 |
| R-19 | A caller is offered `gsap_docs` / `mdn_docs` and gets an unexecutable capability | M | L | **Low** | registry enabled with no connector | None | Eliminated by C-11 |
| R-20 | `SecurityLayer` and `ExecutionScheduler` create a false impression of authorization and concurrency control | M | M | **Medium** | 6-line and 11-line no-ops | None | **Accepted, documented** — not fixed in 44.2 (§17.9) |
| R-21 | Enabling `session_binding='request_context'` exhausts memory/subprocesses via an unbounded pool | L | H | **Medium** | `pool.py` has no max size, no reaper | The feature is dormant | Reduced by the C-30 max-size bound |
| R-22 | `trace_file`, if ever enabled, writes unredacted credentials to an uncapped file | L | H | **Medium** | `transport.py:10-35` | Dormant — no connector sets it | Documented; gated by CG-18 |
| R-23 | An unrecognised `transport_type` fails silently rather than refusing | L | M | **Low** | `transport.py` branches on 2 values | Only 2 values in use | Not addressed in 44.2 — accepted |
| R-24 | A latent `NameError` fires on an untaken branch (`ConnectorCapability`, `ConnectorEvent`) | L | M | **Low** | `connector_runtime.py:229`, `:584` | Branches currently unreached | Eliminated by C-29/CG-40 |

**Standing exposure summary:** 8 Critical, 6 High, 7 Medium, 3 Low.

### 19.2 Execution risks introduced by performing Phase 44.2

| ID | Risk | Likelihood | Impact | Exposure | Trigger | Required control |
|---|---|---|---|---|---|---|
| X-01 | C-01 commits `dev.conf` and publishes the master key into git history permanently | M | H | **Critical** | Committing before C-12 | Absolute ordering constraint #1; explicit `.gitignore`/secret scan before the commit |
| X-02 | C-07 repairs manifests, C-06 is incomplete, and the repair is silently re-wiped | M | H | **High** | Ordering violation | Constraint #2; CG-08 requires manifests to survive a full boot+health+discovery cycle |
| X-03 | C-02 ratifies a namespace contract that breaks the 4 currently-working bypasses before they are converted | M | H | **High** | Removing bypasses too early | Constraint #4; CG-35 requires each converted flow to match its pre-conversion result |
| X-04 | C-04's fail-closed executor check refuses to boot the platform | M | H | **High** | Enforcing completeness before C-03 fixes target-type derivation | Constraint #5; CG-03 tests both directions |
| X-05 | C-03 changes `mcp.penpot` from REMOTE to CONNECTOR and breaks the one connector that demonstrably works end-to-end | M | H | **High** | Target-type change without regression proof | `penpot_mcp.export_shape` with the real shape ID is a named gate in CG-01 |
| X-06 | C-16 turns health into a real measurement and every connector reports unhealthy, appearing to be a regression | H | M | **High** | Truthful health on a platform whose connectors were never actually probed | Expected and correct; CG-20 requires a stopped container to report unhealthy. Do **not** "fix" by restoring the force-write |
| X-07 | C-12 removes the config key and no environment variable is set, so nothing decrypts | M | H | **High** | Incomplete deployment | CG-14 requires both the success path and the explicit-failure path |
| X-08 | C-24 registers 44 test files against the dev DB before C-23 isolates it, corrupting real records at scale | M | H | **Critical** | Ordering violation | Constraint #3; CG-31 diffs the dev DB against the PC-4 snapshot |
| X-09 | C-09 forces a registry re-sync that deactivates rows currently relied upon | M | M | **Medium** | The JSON is older than the DB for some rows | CG-10 requires row-by-row JSON agreement plus idempotency; take a DB snapshot first |
| X-10 | C-26 consolidates entry points and silently changes behaviour for a flow nobody tests | M | M | **Medium** | Bypass removal without a behavioural baseline | CG-35's identical-result requirement; capture the baseline before converting |
| X-11 | C-29 deletes something believed dead that is reached reflectively or by an external caller | L | M | **Low** | Grep-only proof of deadness | CG-38 requires a clean boot plus an explicit-failure demonstration per removal |
| X-12 | Scope creep: 30 change specifications become an open-ended refactor | H | M | **High** | Ambition | §17.9's prohibition table; §18's fixed 40-gate matrix is the definition of done |
| X-13 | A 44.2 change is made during 44.3 to force a gate to pass | M | M | **Medium** | Certification pressure | Invalidating condition I-3 voids all prior gates |
| X-14 | Wave 8 (consolidation) is deferred indefinitely, leaving the P2 *structural causes* of the P0s in place, so the P0s recur | H | M | **High** | Declaring victory after the blocking gates | §16.4's note; each Group G deferral must be listed in the 44.3 risk register |

### 19.3 Risks this audit could not evaluate

| ID | Unknown | Why it could not be resolved | Proposed resolution |
|---|---|---|---|
| U-01 | Whether recovery, health monitoring, and lifecycle transitions actually work in a running worker | Odoo was not running; starting it would force-write `healthy` (PV-5) | Observe on the certification DB during 44.3 |
| U-02 | Whether the `SessionTransportPool` behaves correctly under contention | Dormant; activating it requires a config write (PV-6, PV-7) | Activate on the certification DB only |
| U-03 | Which of the three running Penpot MCP instances actually serves `localhost:9001` | Would require issuing requests | Record during 44.3 (G-48) |
| U-04 | Whether the 44 unregistered test files pass, fail, or are obsolete | Running them writes to the dev DB (PV-1) | C-24 triage on the certification DB |
| U-05 | Whether `mcp.github`'s DB `enabled/lifecycle` was set deliberately or by a stale sync | No audit trail on `nexora_capability_registry` | Decide during C-09; the JSON is authoritative unless stated otherwise |
| U-06 | Whether `httpx2` in `external_dependencies` is a typo or an intentional pin | No corresponding import or requirement found | Confirm during C-30 |
| U-07 | Whether the 5 undeclared/partially-declared records were created by tests, by onboarding, or by hand | Manifest fixtures suggest tests, but `ir_model_data` gaps suggest onboarding | Establish before C-10 so the seeds encode intent, not accident |

---

## 20. Final Recommendation

### 20.1 Verdict

**The platform is architecturally sound and operationally unsafe.**

Both halves of that sentence are load-bearing.

The architecture is genuinely good. Authentication is one generic implementation driven by three orthogonal columns — adding an auth mode is a data change, not a code change (§5.1). The transport layer is a single class handling both live transports with correct sync-over-async bridging. `SessionTransportPool` is the cleanest component in the subsystem and needs no changes (§7.4). ADR-0066 is implemented exactly as written (§14.1). Phase 43.8's Penpot correction was achieved by *using* the generic mechanism rather than adding a special case — which is the strongest available evidence that the design is right. `ComponentConnector` composition, the `ExecutionTargetType` abstraction, and the manifest-driven registry are all correct choices.

What is unsafe is everything around that core:

- The canonical path **cannot execute the platform's own connectors** — `mcp.penpot` resolves to `REMOTE`, and `REMOTE` has no executor (§3.1, G-01). Four separate bypasses exist because of this. The bypasses are not laziness; they are the only working paths. Any assessment that the UCP path is "operational" is contradicted by `router.py:54`.
- **Health status is fabricated.** `bootstrap.py:242` writes `healthy` before probing. `github_mcp` is `healthy` with its container stopped (§9, G-05). Every health-derived claim in every prior report is therefore unfounded.
- **Manifests are being silently destroyed.** 4 of 5 are corrupt, the capability index is entirely empty, and the mechanism — a full-write default of `'{}'` at `odoo_adapter.py:135` — is still live (§9, G-03/G-04).
- **Secrets are exposed** in a plaintext config file and a plaintext DB parameter (G-06, G-07).
- **85% of the test suite never runs**, which is precisely why none of the above was caught (G-11).
- **Seven phases of work are uncommitted**, including the entire ADR-0067 implementation and the 43.8 fix (G-09).

The recurring failure mode is not bad design. It is **silent failure**: mock success in `LocalToolExecutor`, unconditional success in `RemoteToolExecutor`, a swallowed credential-resolution exception, a manifest default of `'{}'`, a force-written `healthy`, a stale hash gate, a no-op `SecurityLayer`, and an ignored `timeout_seconds`. Each individually is small. Together they mean **the platform's self-reported state is not evidence of anything.** That is the single most important finding of this audit, and it is why §18 forbids certifying any gate by reading code or by trusting a prior report.

### 20.2 Recommended course of action

**Proceed to Phase 44.2 as specified in §17 — with C-01 and C-12 first, in that order.**

Do them together and immediately: remove the master key from `dev.conf`, then commit. One commit and one config change eliminate the two Critical standing risks (R-01, R-02) and cost nothing. Until that is done, every other consideration is secondary, because a single careless command destroys the work being audited.

Then execute the waves in §17.8, respecting all six absolute ordering constraints. Do not reorder for convenience — every constraint encodes a way to cause damage.

### 20.3 Three things that must not happen

1. **Do not register `RemoteToolExecutor` to "fix" G-01.** It returns unconditional `success=True`. Registering it converts the loud `Executor not found` into a silent success — strictly worse than the bug. The correct fix is C-03: decide the target type properly.
2. **Do not treat truthful health as a regression.** After C-16, connectors will report unhealthy. That is the fix working. Restoring the force-write to make dashboards green would re-establish the platform's most dangerous defect (X-06).
3. **Do not defer Wave 8 indefinitely.** The P2 items — four parallel entry points, three capability stores, two credential mechanisms, the candidate-ordering hazard, the `pass` executor-registration stub — are the *structural causes* of the P0s. Fixing the P0s while leaving the causes produces point-fixes that re-break (X-14).

### 20.4 Definition of done for the 44.x programme

Phase 44 is complete when the 34 blocking gates of §18 PASS on a clean working tree against an isolated certification database, with an artefact per gate and no secret in any artefact. Not when the code looks right. Not when a report says it works.

The distance between "architecturally sound" and "operationally trustworthy" is exactly those 34 gates.

### 20.5 Compliance statement for Phase 44.1

| Constraint | Status |
|---|---|
| No Python / XML / JS / TS file modified | Confirmed |
| No Odoo record, credential, migration or manifest modified | Confirmed |
| No file deleted | Confirmed |
| No configuration changed | Confirmed |
| No service restarted | Confirmed — Odoo was never started; container state was observed, not altered |
| No destructive command run | Confirmed — all SQL was `SELECT`; all git commands were read-only |
| No state-modifying test run | Confirmed — 7 such tests recorded as PV-1…PV-7 instead (§13.4) |
| No implementation code written | Confirmed — §17 contains specifications only |
| No secret value printed or recorded | Confirmed — credentials referenced by key name and ciphertext length only |
| Prior reports treated as intent, not as ground truth | Confirmed — 3 prior claims corrected (§14.4) |
| Deliverable | This report, 20 sections, at the specified path |
