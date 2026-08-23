# Phase 44.2 — Implementation Decisions (W0)

Input: `phase44_1_mcp_architecture_platform_audit.md` (G-01…G-52, C-01…C-30).
This document records, for every selected change: Finding → Root cause → Existing
abstraction reused → Change → Verification. Rejected/deferred findings are listed
with reasons. No change here creates a parallel MCP architecture; the canonical
chain remains:

```
UniversalCapabilityRouter → ConnectorExecutionTarget → ConnectorRuntime
→ ConnectorDispatcher → McpConnector → McpProvider
→ McpTransport / SessionTransportPool → MCP SDK → real MCP server
```

## Secret provenance checks (W1 preconditions)

| Check | Result |
|---|---|
| `configs/dev.conf` tracked by git? | NO — file lives outside the repo (`D:/ODOO/custom-addons` is the repo root; `configs/` is not under it) |
| Master-key value present in git history? | NO — `git log --all -S <value>` returned zero commits (value never printed here) |
| Repo history remediation required? | NO |
| `nexora.nvidia.api_key` code consumer in repo? | NONE found (grep across `*.py`); it is a DB `ir.config_parameter` only |

## Selected changes

### W1 — Security

**S1. G-06 master key in dev.conf**
- Root cause: plaintext `nexora_connector_secret_key` written into the local dev
  Odoo config file.
- Reused: `odoo_secrets_provider.py` already resolves Odoo-config → env fallback
  (`NEXORA_CONNECTOR_SECRET_KEY`); ADR-0054 already defines this model.
- Change: remove the plaintext line from `configs/dev.conf` (local, untracked);
  document env-only provisioning. No rotation, no history rewrite, no commit.
- Verification: grep of `configs/dev.conf`; `odoo_secrets_provider` unit path
  unchanged.

**S2. G-07 `nexora.nvidia.api_key`**
- Root cause: DB `ir.config_parameter` holding a plaintext provider key; no repo
  code reads it by that key name.
- Change: DEFERRED — BLOCKED — INFRASTRUCTURE. Remediation is a runtime-database
  operation (read/move/delete the parameter) and cannot be proven or performed
  from source alone. Recorded as a Phase 44.3 precondition.

**S3. G-41 traceback persistence (connection_tester.py)**
- Root cause: non-`ConnectorError` failures append `traceback.format_exc()` to
  the user message, which is persisted into `last_test_result_json`.
- Reused: existing `ConnectorError.user_safe_message` pattern.
- Change: user-facing message never includes tracebacks for any exception type;
  full traceback stays in server log only.
- Verification: unit test asserting no traceback text in `error_message`.

**S4. Traceback in UserError (nexora_connector.py `action_discover_mcp_capabilities`)**
- Root cause: `raise UserError(f"...{traceback.format_exc()}")`.
- Change: UserError carries a safe message; traceback logged server-side.
- Verification: code inspection + test.

**S5. G-42 raw MCP payload logging**
- Root cause: `DISCOVERY RESULT RAW: ... data=...` and `TESTER TOOLS RAW: ...
  data=...` at INFO log full payloads (may transit tokens/PII).
- Change: log success/error-code/counts only; never raw `data`.
- Verification: grep for `RAW:` log lines.

**S6. Trace-file exposure (G-43)**
- Root cause: `TraceReceiveStream/TraceSendStream` write unredacted frames when
  `trace_file` is configured.
- Decision: ACCEPT-RISK + guard. `trace_file` is opt-in per-connector config,
  unset by default; no code path sets it implicitly. Documented in ADR-0068
  security model. No redaction engine added (over-engineering for an opt-in
  debug feature).

**S7. Diagnostic traceback logging (onboarding handshake)**
- Decision: internal server-log tracebacks are retained (ops-controlled surface,
  no credential values in exception messages after S8/S9); user-facing surfaces
  are sanitized per S3/S4.

### W2 — G-01 canonical routing

- Root cause: `capabilities/bootstrap.py:33` derives
  `target_type = LOCAL if transport=='stdio' else REMOTE`, conflating transport
  with execution target; no REMOTE executor is registered, so SSE capabilities
  fail as "Executor not found"; stdio ones route to `LocalToolExecutor` which
  mock-succeeds when `tool_registry` is None (G-10).
- Reused: `ExecutionTargetType.CONNECTOR`, `ConnectorExecutionTarget`,
  `get_connector_runtime()`; router already fails closed on missing executor.
- Change: registry-backed MCP capabilities are derived as `CONNECTOR` (both
  `bootstrap._parse_registry_manifests` and `repository` manifest derivation).
  `RemoteToolExecutor` is deliberately NOT registered (per 44.1 §17.9).
  `LocalToolExecutor` mock-success branch becomes a loud failure.
- Verification: unit tests — manifest target types; routing test proving
  `CONNECTOR` resolution; failure-propagation test (no executor → failure, never
  mock success).

### W3 — G-02 namespace contract

- Root cause: `connector_executor.py:122-134` splits ANY dotted namespace into
  `connector.tool`, corrupting reserved protocol namespaces.
- Reused: `McpProvider` already implements the six protocol namespaces.
- Change: canonical contract — reserved set
  `{tools.list, tools.call, resources.list, resources.read, prompts.list,
  prompts.get}` is matched FIRST and passed through untouched; only non-reserved
  dotted namespaces are treated as `{connector_id}.{tool_name}` shorthand. No
  connector-specific exceptions.
- Verification: regression tests for all six reserved namespaces + arbitrary
  discovered tool namespace.

### W4 — G-03/G-04/G-08 registry consistency

- G-03 Root cause: `odoo_adapter._do_write` full-write path defaults
  `manifest_json` to `'{}'`, wiping populated manifests on any full save.
  - Reused: existing partial-write path semantics.
  - Change: full write preserves existing `manifest_json` unless the caller
    explicitly provides one; partial write also accepts `state`→`lifecycle_state`
    normalization.
  - Verification: unit test — full write without manifest does not clobber.
- G-08 Root cause: registry hash stored even when sync semantics are stale.
  - Change: hash is computed from the actual file bytes and only advanced after
    a successful, idempotent sync; sync no longer deactivates rows based on a
    stale in-memory set.
  - Verification: double-run sync idempotency test; hash-drift test.
- G-04 Root cause: `_rebuild_capability_index` only reads capabilities from
  connectors currently running in-process → empty index after restart.
  - Reused: persisted manifests (`CapabilityRepository`).
  - Change: index rebuilt from persisted manifests of enabled connectors, not
    from live runtime objects only.
  - Verification: index non-empty after simulated restart (unit).

### W5 — G-05 truthful health + G-20/G-38

- Root cause: three force-write surfaces set `health_status='healthy'` without a
  probe: `integration/bootstrap._startup_reconciliation`,
  `nexora_connector.action_enable`; `_cron_check_health` searches state
  `'degraded'` which is not a lifecycle state.
- Reused: `ConnectorHealthMonitor` thresholds + `probe_health` + cron.
- Change: registration/enable may set lifecycle `running` but health stays
  `unknown` until a real probe succeeds; cron domain fixed to valid lifecycle
  states; `degraded` exists only as `health_status`. Persistence key
  standardized to `lifecycle_state` (adapter contract) — G-20.
  `CapabilityRepository` health filter reconciled: manifests visible when
  lifecycle is active and health is not `failed` (`unknown` allowed), so
  truthful health does not hide capabilities.
- Verification: unit tests — enable ≠ healthy; probe success ⇒ healthy;
  probe failure ⇒ degraded/failed per monitor thresholds.

### W6 — context contract

- Corrected premise (verified in code): both context types ALREADY carry
  `request_context` — `ExecutionContext` (sdk/context.py:24) and
  `ConnectorRuntimeContext` (domain/models.py:427). The 44.1 premise that the
  SDK context lacked the field was inaccurate.
- Verified chain (no code change required):
  `connector_executor._build_request` builds `ConnectorRuntimeContext(
  request_context=payload.get("request_context", {}))` →
  `dispatcher._execute_on_connector` passes `request.context` directly to
  `sdk_connector.execute(context=...)` → `McpProvider` reads it via
  `getattr(context, 'request_context', {})` (duck typing works for both types)
  → `transport.call_tool(..., request_context=...)` intersects with
  `allowed_request_context_fields` into `meta`.
- Decision: keep duck typing; no third context type; no new field.
  `ConnectorRuntimeContext` remains the canonical runtime context for the
  connector subsystem; `ExecutionContext` is the SDK-level equivalent.
- Reused: ADR-0066 allowlist (`allowed_request_context_fields`) already gates
  what crosses the MCP boundary into `meta`; no hardcoding of `userToken`.
- Verification: static chain inspection (this phase) + propagation unit test
  (request_context → dispatcher → provider → transport.call_tool meta
  intersection) in the W13 regression suite.

### W7 — SessionTransportPool

- Per 44.1 §17.9 the only sanctioned pool change is a size bound.
- Change: add max-size bound with locked eviction of the oldest/expired entry on
  overflow (reusing the existing lock re-check pattern). TTL, sha256 keys,
  isolation, shutdown already implemented — verified against ADR-0067.
- ADR-0067 status updated Proposed → Implemented (W15).
- Verification: pool unit tests (isolation, eviction on overflow, cleanup).

### W8 — configuration correctness

- `timeout_seconds`: USED-DECLARED → wired. Model field already exists
  (`nexora.mcp_server_config.timeout_seconds`, default 60). Change: carried
  through onboarding `user_overrides` → `McpConfiguration.timeout_seconds` →
  `McpConnector` → `McpTransport.connect()` ready-wait and `_run_sync` default,
  replacing hardcoded 60.0. One precedence model: configured value, else 60.
- `startup_policy`: LEGACY/implicit — `eager` equals the existing
  `initialize_and_verify` at registration; `lazy` equals dispatcher on-demand
  creation. No code change; classified and documented.
- `working_directory`: IGNORED → wired for stdio as `StdioServerParameters`
  cwd when provided (small, real correctness fix); otherwise classified unused.

### W9 — credential minimization

- G-12 Root cause: onboarding silently substitutes `''` when a required
  credential fails to resolve.
  - Change: fail closed — `auth_location != 'none'` + unresolved credential ⇒
    `ConnectorConfigurationError`; no silent empty secret.
- G-21 Root cause: `env_vars.update(resolved_secrets)` injects every resolved
  credential into every stdio server environment.
  - Change: declared-only injection via `__INJECT_VIA_NEXORA_MCP_CREDENTIAL__`
    placeholder values in `env_vars_json`. When at least one declaration
    exists, ONLY declared keys are injected (declared-but-unresolvable fails
    closed). When no declaration exists — the current state of all 5 seeded
    connectors (`env_vars_json='{}'`; the placeholders live only in
    `config/mcp_registry.json`, which onboarding does not read) — the legacy
    wholesale injection is preserved as a backward-compat fallback. This
    follows the audit's own staging ("declare first, narrow second",
    regression risk Medium-high): narrowing activates per connector as
    declarations are added, without breaking the 4 live stdio connectors.
- G-52 Root cause: `CredentialResolver.validate()` suffix-scan matches keys of
  other connectors → false positives.
  - Change: exact composite-key match (`<connector_id>:<credential_key>`).
- No credential caching introduced; plaintext stays request/runtime scoped.
- Verification: unit tests for fail-closed, declared-only injection, exact-key
  validation.

### W10/W12 — legacy & factory consolidation (classify, deprecate, no mass delete)

- `TransportFactory` / `ProviderFactory`: DEAD (zero registration call sites,
  proven by grep). Change: remove their instantiation from `ConnectorRuntime`
  ctor (unused usage), add module deprecation notices. Files kept (no deletion).
  `ConnectorFactory` remains the single live construction path (Option B-lite).
- `services/source_framework/transport/*`: LEGACY — imported only by legacy
  `source_framework/adapters/*`, unreachable from the canonical router. Change:
  deprecation notice; no production wiring. Deletion deferred to 44.3 with
  dependency proof.
- Top-level `services/mcp_*.py` (legacy Odoo-model MCP services): LEGACY —
  consumed by `services/providers/adapters/mcp_bridge_adapter.py` (legacy AI
  provider platform), not by the connector runtime. Change: documented as
  non-canonical; removal DEFERRED (removing imports risks legacy provider
  platform regression; out of 44.2 scope).
- `connector_executor` ImportError fallback shim: removed (fail loud).
- Dead `hasattr(ExecutionTargetType, 'CONNECTOR')` block in
  `integration/bootstrap.py`: removed.
- `print()`/`traceback.print_exc()` in `connector_runtime` lifecycle handler →
  module logger.

### W11 — discovery persistence

- Root cause: `unlink()` + `create()` churns IDs and a failed discovery wipes
  previously discovered capabilities (false implication of unavailability).
- Consumers: `CapabilityRepository` searches by `(connector_id, tool_name)` — no
  stable-ID dependency, but deterministic upsert is cheap and removes churn.
- Change: upsert keyed on `(connector_id, tool_name, discovery_source)`;
  discovery failure skips persistence entirely (existing records retained) and
  surfaces a warning.
- Verification: unit tests — upsert idempotency; failure preserves records.

### W13 — test infrastructure (G-11)

- Root cause: `tests/__init__.py` registers 8 of ~50+ modules; two registered
  modules import nonexistent `services.runtime.mcp.*`.
- Change: register the unregistered modules that are importable against the
  current tree; mark modules importing `services.runtime.mcp` as broken/dead
  (not registered, documented); add one focused regression suite
  (`test_phase44_2_hardening.py`) covering: namespace contract, target-type
  derivation, fail-closed credentials, pool bound, truthful health, manifest
  preservation. Classification: UNIT (new suite) / INTEGRATION (existing
  registered Odoo tests) / LIVE MCP + PRODUCTION CERTIFICATION → 44.3.
- Verification: `python -m compileall` + Odoo test run of registered modules.

### W14 — silent failure removal

- `transport.py` post-handshake error swallow: mark transport disconnected so
  subsequent calls fail fast with `TRANSPORT_NOT_CONNECTED` (real failure)
  instead of hanging/silent loss.
- Onboarding allowed-fields JSON `except: pass` → logged warning + empty list.
- No reconnection logic added (44.1 §17.9).

## Rejected / deferred findings

| Finding | Decision | Reason |
|---|---|---|
| G-09 (7 phases uncommitted) | DEFERRED | Explicit instruction: do not commit |
| G-07 remediation | BLOCKED — INFRASTRUCTURE | DB-side parameter; no repo code consumer; needs live DB |
| G-35 new transports (streamable_http/websocket) | REJECTED | 44.1 §17.9 prohibition |
| G-34 `basic` auth scheme | REJECTED | 44.1 §17.9 prohibition |
| Speculative SecurityLayer | REJECTED | 44.1 §17.9 prohibition |
| Fourth capability store | REJECTED | 44.1 §17.9 prohibition |
| Reconnection/backoff logic | REJECTED | 44.1 §17.9 prohibition |
| Registering `RemoteToolExecutor` | REJECTED | 44.1 §17.9; fail-closed routing preferred |
| Renaming `SessionTransportPool` | REJECTED | Instruction: keep actual class name |
| Mass deletion of legacy dirs | DEFERRED to 44.3 | Requires dependency proof; no speculative deletion |
| `mcp_registry.json` removal | REJECTED | Production bootstrap consumes it (44.1 established) |
| Git history rewrite | NOT REQUIRED | Proven: key value never in history |
| Remaining G-2x/G-4x cosmetic items | DEFERRED | Cleanup-only; not correctness/security blockers |

## Ordering honored

C-12 (security sinks) before C-01 (routing); C-06 (registry) before C-07
(capability index); C-03 (manifest preservation) before C-04 (sync); C-18
(dispatcher lock reuse of pool pattern) before C-19 (eviction predicate);
C-23 before C-24. ADR-0068 written before implementation.
