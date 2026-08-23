# Phase 43.8 — Penpot API Key Validation Report (Corrected)

> **Correction notice.** An earlier revision of this report concluded that Penpot
> accepted the durable key as an `Authorization: Bearer` header. That conclusion was
> **wrong**. It was inferred from a generic bearer-auth model rather than verified
> against the Penpot MCP server implementation. The authentication boundary has now
> been established from the server source and from live negative controls, and the
> configuration has been corrected. The end result — unattended, browser-free,
> project-bound execution using the Odoo-stored key — still holds, but for a
> different and now-proven reason.

## 1. Configuration Audit

- Records inspected: `nexora.connector` and `nexora.mcp_server_config` for `penpot_mcp` (id=41).
- Original state: `authentication_location='none'`, `session_binding='request_context'`;
  no `nexora.mcp_credential` mapping any API key to Penpot.
- The connector had no declarative seed, so the live rows were hand-edited and at risk
  of drift. A canonical seed and migration now own this configuration.

## 2. Authentication Mechanism — Verified, Not Assumed

The bundled Penpot MCP server (`/opt/penpot/mcp/index.js`, running `--multi-user`) was
read directly:

| Probe | Result |
|---|---|
| Occurrences of `authorization` | **0** |
| Occurrences of `Bearer` | **0** |
| Occurrences of `auth-token` | **0** |
| Token sources actually parsed | `req.query.sessionId`, `req.query.userToken` |

Live negative controls confirmed this on the wire:

| Scenario | `high_level_overview` | `export_shape` |
|---|---|---|
| No credential at all | 29082 bytes | **BLOCKED** — `No userToken found in session context. Multi-user mode requires authentication.` |
| Invalid `Authorization: Bearer <token>` | 29082 bytes (**byte-identical**) | **BLOCKED** — identical message |
| Valid `?userToken=<credential>` | 29135 bytes | **PASS** |

Two findings follow:

1. **Penpot ignores `Authorization` / `Bearer` entirely.** The header path was inert; the
   earlier PASS was produced by the unauthenticated tools, not by header authentication.
2. **The authentication boundary is per-tool, not per-connection.** `initialize`,
   `tools/list`, and `high_level_overview` are unauthenticated. Only project-bound tools
   such as `export_shape` require `userToken`. Any verification that stops at
   `high_level_overview` cannot distinguish authenticated from unauthenticated.

**Verified contract:** the credential must be supplied as the `userToken` **HTTP query
parameter** on the SSE endpoint — `http://localhost:9001/mcp/sse?userToken=<credential>`.

## 3. Corrected Configuration

The canonical seed is now [connector_penpot_data.xml](../../data/connector_penpot_data.xml),
with the live rows brought into line by
[post-migrate.py](../../migrations/19.0.1.0.1/post-migrate.py) (the seed is `noupdate="1"`,
so already-adopted rows are not rewritten by the loader).

| Field | Before (wrong) | After (verified) |
|---|---|---|
| `authentication_location` | `header` | `query` |
| `authentication_name` | `Authorization` | `userToken` |
| `authentication_scheme` | `bearer` | `none` |
| `credential_key` | `PENPOT_API_KEY` | `PENPOT_API_KEY` (unchanged) |
| `session_binding` | `none` | `none` (unchanged) |
| `allowed_request_context_fields_json` | `[]` | `["userToken"]` |

No new architecture was introduced. The existing generic `QueryAuth` mechanism in
[transport.py](../../services/connector/connectors/mcp/transport.py) carries the parameter.
`allowed_request_context_fields_json` is retained only so the generic
`session_binding='request_context'` fallback stays configurable; it is unused on the
API-key path because `request_context` is empty.

The existing encrypted `PENPOT_API_KEY` credential was preserved untouched. No duplicate
connector or credential records were created.

### 3a. Blocking defect found and fixed

Switching to `authentication_location='query'` initially failed at connect time with
`TypeError: Invalid "auth" argument`, surfacing as
`MCP connection failed: unhandled errors in a TaskGroup`.

Root cause: `transport.py` aliased `import httpx2 as httpx`, so `QueryAuth` subclassed
`httpx2.Auth` (httpx2 2.7.0 is installed). But `mcp.client.sse.sse_client` type-checks
`auth` against real `httpx.Auth` 0.28.1, and `httpx2.Auth is httpx.Auth` is `False` —
so every `QueryAuth` instance was rejected.

Fix: `transport.py` now imports the same `httpx` the MCP SDK validates against. This
defect had made **all** query-parameter authentication unusable platform-wide, not just
for Penpot.

## 4. Orphan Credential Cleanup

Two credential rows existed for `penpot_mcp`:

| id | key | populated | verdict |
|---|---|---|---|
| 30 | `PENPOT_API_KEY` | yes | **retained** — actively used |
| 31 | `penpot_api_key` | no | **removed** — proven unreachable |

The lowercase row was not removed for looking redundant; it was proven unusable.
`OdooCredentialResolver.resolve_all_for_connector` performs **exact, case-sensitive**
key matching, so a row keyed `penpot_api_key` can never satisfy
`credential_key='PENPOT_API_KEY'`. No `nexora.mcp_server_config` referenced the lowercase
key. Removal is guarded in the migration, which refuses to delete if the row is populated
or if any server config references it.

## 5. Live Configuration After Upgrade

Module upgraded to `19.0.1.0.1`. Verified without exposing any secret:

| Field | Value | Expected | |
|---|---|---|---|
| connector | `penpot_mcp` | `penpot_mcp` | OK |
| state | `running` | `running` | OK |
| health | `healthy` | `healthy` | OK |
| `authentication_location` | `query` | `query` | OK |
| `authentication_name` | `userToken` | `userToken` | OK |
| `authentication_scheme` | `none` | `none` | OK |
| `credential_key` | `PENPOT_API_KEY` | `PENPOT_API_KEY` | OK |
| credential populated | `True` | populated | OK |
| `session_binding` | `none` | `none` | OK |

`last_error` is empty. The connector had been left in a stale `failed` state written
before the httpx fix; it was cleared through the canonical `action_enable()` operator
action — which re-runs the full registration pipeline (config validation, credential
resolution, MCP handshake) and persists `running` only on success — not by a manual
database write.

## 6. Unattended Execution — Real Project-Bound Operation

Executed through the canonical production path with **no browser, no plugin, no manual
session token, and `request_context={}`**:

```
UniversalCapabilityRouter
  -> ConnectorExecutionTarget      (ConnectorExecutionTarget(runtime=wired))
  -> ConnectorRuntime
  -> ConnectorDispatcher
  -> McpConnector                  (pool=None, session_binding=none -> global transport)
  -> McpProvider
  -> McpTransport                  (QueryAuth -> ?userToken=<credential>)
  -> Penpot MCP
```

| Operation | Result |
|---|---|
| connector health | **PASS** — `ConnectorHealthStatus.HEALTHY` via `runtime.probe_health()` |
| `tools/list` | **PASS** — `['execute_code', 'export_shape', 'high_level_overview', 'penpot_api_info']` |
| `high_level_overview` | **PASS** — 29135 bytes |
| `export_shape` | **PASS** — 244 bytes, shape `11755e51-bf0d-80bc-8008-618097a49912` |

The shape ID is a real, pre-existing shape in the live Penpot workspace, previously
verified in this phase. It was not fabricated and was not obtained from a browser
session during this run.

`tools.list` was dispatched at `ConnectorRuntime.dispatch()` rather than through
`ConnectorExecutionTarget`. This is not a bypass: `ConnectorExecutionTarget._build_request`
splits any dotted namespace into `{connector_id}.{tool_name}`, so the reserved MCP
namespace `tools.list` cannot be expressed at that layer by design. The remaining
layers of the path are identical, and both project-bound tool calls went through the
full `ConnectorExecutionTarget` entry point.

## 7. Credential Behaviour

| Claim | Evidence |
|---|---|
| Read by the canonical credential mechanism | `OdooCredentialResolver.resolve_all_for_connector` via `McpOnboardingService._build_mcp_configuration`; resolved `auth_secret` length 343 |
| Becomes the `userToken` query parameter | `QueryAuth.auth_flow` output inspected: wire query params `['userToken']`, value matches the vault value |
| Penpot receives it at transport initialization | `QueryAuth` is passed to `sse_client` at connect; SSE handshake succeeds and project-bound calls authenticate |
| No `Authorization` header sent | `Authorization` absent from the outgoing request headers |
| Project-bound execution succeeds | `export_shape` returned a non-error 244-byte result |
| No token in `request_context` | `request_context={}` passed explicitly on every call |
| Not persisted outside encrypted storage | 0 rows in `nexora_mcp_server_config` (`command` / `args_json` / `env_vars_json`) contain it; 0 rows hold it as plaintext in `nexora_mcp_credential` |
| Not present in logs / reports / errors | Not echoed in tool output; `connector.error_message` empty; only length is ever printed |

A negative control isolates authentication as the sole variable: the same UCP path with
`auth_location='none'` is **BLOCKED**, while `auth_location='query'` **PASSES**.

## 8. SessionTransportPool Integrity (Phase 43.6 Preserved)

`SessionTransportPool` is **not** dead code and has not been removed or disabled. It is
configuration-gated in `McpConnector.__init__` and remains reachable:

| `session_binding` | Pool instantiated | Transport used |
|---|---|---|
| `none` | `False` | global transport |
| `request_context` | `True` | `SessionTransportPool` |

Both branches were exercised live. The pool implementation and module are intact.

Penpot uses the simpler global transport because the durable key is itself sufficient
per request. The pool remains the correct mechanism for services that genuinely require
request- or session-bound credentials.

## 9. Final Classification

**PASS — PENPOT_API_KEY_UNATTENDED_PROJECT_EXECUTION**

A real project-bound operation (`export_shape` on an existing shape) succeeded through
the canonical UCP path using only the durable, encrypted, Odoo-stored `PENPOT_API_KEY`,
with no browser session, no plugin, and an empty `request_context`.

## 10. Conclusion

The durable Odoo-stored Penpot key fully replaces the browser-session requirement for
unattended project orchestration — but via the `userToken` **query parameter**, not a
Bearer header. The corrected configuration is now declaratively seeded and
migration-enforced, so the live boundary matches the verified server contract rather than
an assumption.

Two corrections to the previous report's claims:

- The Bearer-header configuration never authenticated anything. It appeared to work only
  because the tools exercised were unauthenticated.
- `SessionTransportPool` is not "entirely unnecessary". It is unnecessary *for the Penpot
  API-key path*, and remains live, gated, generic infrastructure for session-bound
  services.
