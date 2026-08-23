# Penpot MCP Connectivity Audit

**Date:** 2026-08-19  
**Purpose:** Factual investigation of the existing local Penpot Docker installation's MCP connection model before any configuration changes are made to the `penpot_mcp` connector.

---

## 1. Existing Penpot Docker Installation

Two separate Penpot Docker Compose stacks are running simultaneously on this host:

### Stack A: `compose` (Primary — exposed, with MCP ports)
| Container | Image | Status | Host Ports |
|---|---|---|---|
| `compose-penpot-frontend-1` | `penpotapp/frontend:2.16` | Up | `0.0.0.0:9001→8080` |
| `compose-penpot-mcp-1` | `penpotapp/mcp:2.16` | Up | `0.0.0.0:4401-4402→4401-4402` |
| `compose-penpot-backend-1` | `penpotapp/backend:2.16` | Up | (internal) |
| `compose-penpot-exporter-1` | `penpotapp/exporter:2.16` | Up | (internal) |
| `compose-penpot-postgres-1` | `postgres:15` | Up (healthy) | (internal) |
| `compose-penpot-mailcatch-1` | `sj26/mailcatcher:latest` | Up | `0.0.0.0:1080→1080` |
| `compose-penpot-valkey-1` | `valkey/valkey:8.1` | Up (healthy) | (internal) |

### Stack B: `penpot-local` (Secondary — no MCP ports exposed)
| Container | Image | Status | Host Ports |
|---|---|---|---|
| `penpot-local-penpot-backend-1` | `penpotapp/backend:2.16` | Up | (none) |
| `penpot-local-penpot-exporter-1` | `penpotapp/exporter:2.16` | Up | (none) |
| `penpot-local-penpot-postgres-1` | `postgres:15` | Up (healthy) | (none) |
| `penpot-local-penpot-mcp-1` | `penpotapp/mcp:2.16` | Up | (none, no ports exposed to host) |
| `penpot-local-penpot-valkey-1` | `valkey/valkey:8.1` | Up (healthy) | (none) |

**Active Stack for MCP:** Stack A (`compose`) with Penpot frontend at `http://localhost:9001` and MCP at `http://localhost:4401`.

### Docker Network
- Network name: `compose_penpot`
- Subnet: `172.19.0.0/16`
- The MCP container IP: `172.19.0.5`
- The nginx/frontend IP: `172.19.0.8`

### PENPOT_FLAGS (from docker-compose.yaml)
```
disable-email-verification enable-smtp enable-prepl-server disable-secure-session-cookies enable-mcp
```
Note: `enable-mcp` flag is present, enabling the MCP integration in the Penpot frontend.

---

## 2. Exact Penpot MCP Implementation

- **Image:** `penpotapp/mcp:2.16`  
- **Version:** `2.16.2` (from `/opt/penpot/mcp/version.txt`)  
- **Source:** `https://github.com/penpot/penpot`  
- **Package:** `@penpot/mcp` (NPM, part of the monorepo)
- **License:** MIT (server), MPL-2.0 (Penpot)
- **Runtime:** Node.js v22.21.1

This is the **official Penpot MCP server** shipped directly by the Penpot team as part of the `penpotapp/mcp:2.16` Docker image. It is NOT a community-built wrapper.

---

## 3. MCP Transports Exposed

The server registers **three simultaneous transports**:

| Transport | Type | Host Endpoint | Container Port |
|---|---|---|---|
| Modern Streamable HTTP | Streamable HTTP (MCP 2024-11-05) | `http://localhost:4401/mcp` | 4401 |
| Legacy SSE | SSE (MCP legacy) | `http://localhost:4401/sse` | 4401 |
| WebSocket (PluginBridge) | WebSocket | `ws://localhost:4402` | 4402 |

**Log evidence:**
```
INFO (PenpotMcpServer): Modern Streamable HTTP endpoint: http://0.0.0.0:4401/mcp
INFO (PenpotMcpServer): Legacy SSE endpoint: http://0.0.0.0:4401/sse
INFO (PluginBridge): WebSocket mcpServer started on port 4402
```

### Nginx Proxy Routes (via `mcp-locations.conf`, mounted into `penpot-frontend`)
| Route | Target |
|---|---|
| `/mcp/stream` → `POST http://penpot-mcp:4401/mcp` | Streamable HTTP (buffering off) |
| `/mcp/sse` → `GET http://penpot-mcp:4401/sse` | Legacy SSE (buffering off) |
| `/mcp/ws` → `ws://penpot-mcp:4402` | WebSocket (plugin bridge) |
| `/messages` → `http://penpot-mcp:4401/messages` | SSE post-back messages |

**Therefore, from the host both direct and proxied access are available:**
- Direct Streamable HTTP: `http://localhost:4401/mcp`
- Proxied Streamable HTTP: `http://localhost:9001/mcp/stream`
- Direct SSE: `http://localhost:4401/sse`
- Proxied SSE: `http://localhost:9001/mcp/sse`

---

## 4. MCP Initialization Test — PASS

**Test command (direct endpoint):**
```
POST http://localhost:4401/mcp
Accept: application/json, text/event-stream
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
  "protocolVersion":"2024-11-05",
  "capabilities":{},
  "clientInfo":{"name":"nexora-audit","version":"1.0"}
}}
```

**Response (HTTP 200 OK):**
```json
{
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {"listChanged": true}},
    "serverInfo": {"name": "penpot", "version": "1.0.0"},
    "instructions": "You have access to Penpot tools..."
  },
  "jsonrpc": "2.0",
  "id": 1
}
```

MCP `Session-ID` returned: `b76ea5af-1d22-4472-8a95-83c1818237ef`

---

## 5. tools/list Result — PASS (4 Tools Discovered)

```json
[
  {"name": "execute_code", "description": "Executes JavaScript code in the Penpot plugin context..."},
  {"name": "high_level_overview", "description": "Returns basic high-level instructions on Penpot..."},
  {"name": "penpot_api_info", "description": "Retrieves Penpot API documentation..."},
  {"name": "export_shape", "description": "Exports a shape from the Penpot design..."}
]
```

**No authentication was required for `initialize` or `tools/list`.** Both calls succeeded without any token, API key, or credential header.

---

## 6. Authentication Model Analysis

The Penpot MCP server operates in **`--multi-user` mode** and implements a **`userToken`-based session binding** architecture:

### A. Penpot Application Authentication
- Standard web login at `http://localhost:9001` with email/password
- Creates a browser session (cookie-based)
- The Penpot Plugin system uses this session internally

### B. Penpot API Authentication
- The Penpot backend API accepts authenticated requests
- Authentication is via the active browser session token (cookie) or a personal API token from Settings

### C. Penpot MCP Authentication — `userToken` (Browser Session Binding)
- The MCP server's `--multi-user` flag enables per-user session isolation
- The WebSocket bridge (`ws://localhost:4402?userToken=<token>`) requires a `userToken` query parameter in multi-user mode
- The `userToken` is **NOT a static API key** — it is a **runtime token issued by the Penpot plugin bridge** when the user opens the Penpot MCP plugin within the browser
- The MCP server registers tools but **actual tool execution requires a live WebSocket connection from a Penpot browser plugin session**

**Critical finding from source code:**
```js
// Line 14421-14422:
if (!sessionContext?.userToken) {
  throw new Error("No userToken found in session context. Multi-user mode requires authentication.");
}
```

Tool execution (`execute_code`, `export_shape`) requires an active Penpot plugin instance connected via WebSocket on port 4402 with the correct `userToken`.

**`initialize` and `tools/list` succeed without auth** — but **tool calls require the plugin session to be active**.

### D. MCP Client Authentication
- The MCP `/mcp` (Streamable HTTP) and `/sse` endpoints accept connections without authentication
- The `userToken` is passed as a query parameter: `http://localhost:4401/mcp?userToken=<TOKEN>`
- Without a `userToken`, the server operates but tool execution fails at runtime (no connected plugin instance found)

**Authentication is NOT a traditional API key authentication — it is a browser-plugin session bridge.**

---

## 7. Can Penpot MCP Work Without API Key / Access Token / OAuth Secret?

| Requirement | Status |
|---|---|
| API Key for `initialize` | NOT required |
| API Key for `tools/list` | NOT required |
| API Key for tool execution | NOT required in the traditional sense |
| Browser session (Penpot plugin open in browser) | **REQUIRED** for tool execution |
| OAuth secret | NOT required |
| `userToken` for HTTP/SSE endpoints | Optional for initialize/list; **required** for tool execution |

**Summary:** The MCP server initializes and lists tools without any credential. However, **actual tool execution requires the Penpot browser plugin to be active and connected to the WebSocket bridge** with a `userToken`. This is a **browser-session-bridged architecture**, not a static API key architecture.

---

## 8. Current UCP Connector Configuration Analysis

### Current Database Record (`penpot_mcp`)

| Field | Value |
|---|---|
| `connector_id` | `penpot_mcp` |
| `name` | `Penpot Design MCP` |
| `state` | `failed` |
| `health_status` | `failed` |
| `error_message` | `Startup reconciliation failed: could not serialize access due to concurrent delete` |
| `enabled` | `False` |
| `registered_at` | `2026-08-10` |

### Server Config (`nexora.mcp_server_config` #33)

| Field | Value |
|---|---|
| `transport_type` | `sse` |
| `command` | `http://localhost:9001/mcp/sse` |
| `authentication_location` | `query` |
| `authentication_name` | `userToken` |
| `authentication_scheme` | `none` |
| `credential_key` | `PENPOT_API_KEY` |
| `startup_policy` | `lazy` |
| `last_test_success` | `True` (tested 2026-08-15) |

### Manifest JSON (stored in DB)

```json
{
  "transport": "sse",
  "endpoint": "http://localhost:9001/mcp/stream",
  "environment_variables": {"PENPOT_API_KEY": "__INJECT_VIA_NEXORA_MCP_CREDENTIAL__"},
  "authentication_requirements": "PENPOT_API_KEY",
  "requires_authentication": false
}
```

### Discovered Tools (Already Populated)
The connector already has 4 discovered tools in the database:
- `execute_code`
- `export_shape`
- `high_level_overview`
- `penpot_api_info`

### Why the Connector is `state=failed, health=failed`

The error message is:
```
Startup reconciliation failed: could not serialize access due to concurrent delete
```

This is **NOT a connection or authentication failure**. This is a **database transaction serialization error** during the startup bootstrap reconciliation phase. The connector failed due to a race condition with a concurrent delete operation (likely from the Phase 42 test fixture cleanup), not because the MCP endpoint is unreachable or incorrectly configured.

**Evidence:** The `last_test_success = True` (tested 2026-08-15) and `last_test_result_json` shows:
```json
{"success": true, "latency_ms": 937.0, "tool_count": 4, "resource_count": 0, "prompt_count": 0, "error_message": ""}
```

The connector was working correctly when last tested.

---

## 9. Transport Compatibility Analysis

| Aspect | Current Config | Actual MCP Server | Compatible? |
|---|---|---|---|
| Transport type (config) | `sse` | SSE + Streamable HTTP | Partial |
| Transport type (manifest) | `sse` (endpoint points to `/mcp/stream`) | Streamable HTTP at `/mcp` | **Mismatch** |
| SSE endpoint | `http://localhost:9001/mcp/sse` | `http://localhost:4401/sse` or `http://localhost:9001/mcp/sse` | **PASS** |
| Streamable HTTP endpoint | `http://localhost:9001/mcp/stream` | `http://localhost:4401/mcp` or `http://localhost:9001/mcp/stream` | **PASS** |
| Auth requirement | `PENPOT_API_KEY` (credential) | No static API key; `userToken` via query param | **Mismatch** |
| MCP initialized | ✗ (connector failed) | ✓ (HTTP 200 confirmed) | — |

**Key finding:** The endpoint is reachable and MCP initialization succeeds. The configured SSE endpoint (`http://localhost:9001/mcp/sse`) is valid. The configured Streamable HTTP endpoint (`http://localhost:9001/mcp/stream`) is also valid. Both are proxied through nginx into the MCP container.

---

## 10. Exact Configuration Changes Required

### Issue 1: Database Serialization Error (Primary Failure Cause)
The `failed` state is caused by a startup reconciliation transaction error — a PostgreSQL concurrent delete race condition during system startup, NOT a connection failure.  
**Fix:** Re-enable and re-bootstrap the connector to clear the stale error state.

### Issue 2: Transport Inconsistency
The manifest says `transport: "sse"` but the endpoint `http://localhost:9001/mcp/stream` is the **Streamable HTTP** endpoint. These should be consistent.  
**Fix:** Update `transport_type` to `streamable_http` and endpoint to `http://localhost:4401/mcp` for direct access, OR keep `http://localhost:9001/mcp/stream` with `streamable_http` transport.

### Issue 3: `userToken` Authentication Complexity
The server config sets `credential_key = PENPOT_API_KEY` and `authentication_scheme = none`. In multi-user mode, the actual tool execution requires a `userToken` from an active browser plugin session — not a static API key.  
**For initial integration:** Since `initialize` and `tools/list` succeed without authentication, the connector can be onboarded for capability discovery without a `userToken`. Tool execution via the plugin bridge requires a live browser session.

### Issue 4: Connector Not Enabled
`enabled = False` — the connector needs to be enabled after fixing the transport classification.

---

## 11. Summary: Can Penpot Be Onboarded Without Any Key?

| Capability | Without Key | With Key/Token |
|---|---|---|
| MCP `initialize` | **YES** | YES |
| MCP `tools/list` | **YES** | YES |
| Capability discovery | **YES** | YES |
| Tool execution (non-browser) | NO | NO (browser session required) |
| Tool execution (with plugin) | N/A | YES (with active browser plugin) |

**Conclusion:** Penpot can be onboarded into the UCP for capability discovery without any API key or static token. The MCP server initializes and exposes tools without credentials. Tool execution itself requires the Penpot browser plugin to be active and connected.

---

## 12. Final Verdict

```
REQUIRES_CONFIGURATION
```

The MCP server is installed, running, and accessible. The `initialize` and `tools/list` calls succeed without any key. The current `penpot_mcp` connector record failed due to a **database transaction serialization error during startup**, NOT due to a connection or authentication failure. The last known test was a PASS. The connector is misconfigured (transport label mismatch, stale error state) but the underlying MCP server is fully operational.

**The connector does NOT need a new API key to be onboarded for capability discovery.** It requires:
1. Clearing the stale `failed` state
2. Correcting the transport classification from `sse` to `streamable_http`
3. Re-enabling the connector
4. Choosing the correct endpoint (`http://localhost:4401/mcp` direct, or `http://localhost:9001/mcp/stream` proxied)

For tool execution beyond `tools/list`, a browser plugin session with `userToken` will be required — but this is a runtime flow requirement, not an MCP client configuration requirement.
