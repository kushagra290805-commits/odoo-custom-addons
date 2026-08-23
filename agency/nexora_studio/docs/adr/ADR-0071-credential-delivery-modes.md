# ADR 0071: Credential Delivery Modes (C-15)

## Status
Accepted

Ratified as part of Phase 44.2 closure. Required by Phase 44.1 §18.0 PC-6.

## Context

An MCP connector authenticates to its server in exactly one of two physically
different ways, decided by transport:

| Transport | Physical delivery | Where the code lives |
| --- | --- | --- |
| `sse` | HTTP header or URL query parameter on the SSE handshake | `services/connector/connectors/mcp/transport.py:137-145` |
| `stdio` | Environment variable in the child process | `services/connector/onboarding/mcp_onboarding_service.py:267-298` → `transport.py:102-104` |

The platform already has one declared axis for this: the
`authentication_location` field on `nexora.mcp_server_config`, carried into the
runtime as `McpConfiguration.auth_location`. Its enum values were
`none | header | query`.

Live configuration state before this ADR (`nexora_cert`):

| Connector | Transport | `authentication_location` | Credential present |
| --- | --- | --- | --- |
| `penpot_mcp` | `sse` | `query` | `PENPOT_API_KEY`, `is_set=t` |
| `context7_mcp` | `stdio` | `none` | `CONTEXT7_API_KEY`, `is_set=t` |
| `firecrawl_mcp` | `stdio` | `none` | `FIRECRAWL_API_KEY`, `is_set=t` |
| `github_mcp` | `stdio` | `none` | `GITHUB_PERSONAL_ACCESS_TOKEN`, `is_set=t` |
| `tavily_mcp` | `stdio` | `none` | `TAVILY_API_KEY`, `is_set=t` |

## Existing problem

Phase 44.1 §17 C-15 (finding G-21) recorded two defects, both consequences of
the same omission — **environment delivery was never a value on the declared
axis**.

1. **Four authentications are invisible.** All four stdio connectors record
   `authentication_location = 'none'` and yet all four authenticate. The field
   that exists precisely to state "how does this connector authenticate" says
   "it does not". Nothing can validate, audit, or report the real answer, and
   §11 evidence queries reading `authentication_location` return a false
   negative for 4 of 5 connectors.

2. **Delivery was over-broad.** `_build_mcp_configuration` called
   `resolve_all_for_connector(connector_id)` and then
   `env_vars.update(resolved_secrets)`, injecting *every* credential the
   connector owns into the child environment regardless of what the server
   needs. Each connector currently owns exactly one credential, so the present
   blast radius is zero — but the design violates least privilege by
   construction.

A third, related defect (G-12) was that an unresolvable credential silently
yielded `''` and the transport then connected unauthenticated, which surfaced
as a misdiagnosed network fault. That was fixed in Phase 44.2 W9; this ADR
records the rule it now implements so the behaviour is contractual rather than
incidental.

## Decision

`auth_location` is the **single declared axis of credential delivery** for MCP
connectors. It takes exactly four values.

1. **`none`** — the connector does not authenticate. No credential is
   resolved for delivery, and none is injected. Legitimate only for servers
   that genuinely require no credential.

2. **`header`** — `sse` only. The credential is sent as the HTTP header named
   by `authentication_name`, optionally prefixed by `authentication_scheme`.

3. **`query`** — `sse` only. The credential is sent as the URL query
   parameter named by `authentication_name`, via the existing generic
   `QueryAuth`.

4. **`env`** — `stdio` only. The credential is delivered as an environment
   variable of the child MCP server process. The variable name is the
   credential key itself, declared in `env_vars_json` with the reserved
   placeholder value `__INJECT_VIA_NEXORA_MCP_CREDENTIAL__`.

Four rules govern the axis.

**R1 — Declaration is mandatory and truthful.** A connector that authenticates
must not record `auth_location = 'none'`. Each stdio connector that
authenticates records `auth_location = 'env'`.

**R2 — Declared-only injection.** When at least one `env_vars_json` key
carries the injection placeholder, **only** those keys receive resolved
credentials. Undeclared credentials owned by the connector are not injected.
Wholesale injection remains only as the fallback for a connector that declares
nothing, so that no currently-working stdio connector is broken by the
contract's introduction; narrowing takes effect per connector as declarations
are seeded. This is the audit's staging rule: *declare first, narrow second.*

**R3 — Fail closed.** Any credential that is *declared* and cannot be resolved
is a configuration error. `ConnectorConfigurationError(CREDENTIAL_UNRESOLVED)`
is raised, naming the connector and the credential **key**. Unauthenticated
connection as a fallback is forbidden. This applies identically to
`header`/`query` (`credential_key` set but unresolvable) and to `env`
(placeholder declared but unresolvable).

**R4 — Values never leave the delivery path.** A credential value is decrypted
inside `_build_mcp_configuration`, placed in `McpConfiguration`, and consumed
by `McpTransport`. It is never persisted, never returned in a health/test
payload, and never logged. Diagnostics report credential **names** only. This
extends the existing rule that the master key lives solely in
`NEXORA_CONNECTOR_SECRET_KEY` (PC-3).

`env` is deliberately *not* applicable to `sse`, and `header`/`query` are
deliberately *not* applicable to `stdio`: the two transports have no shared
delivery surface. The enum is a single axis, not a matrix, because a connector
has exactly one transport.

## Existing canonical abstraction used

No new component is introduced. Every element already exists.

| Concern | Existing abstraction | Location |
| --- | --- | --- |
| Declared delivery mode | `authentication_location` Selection | `models/connector/nexora_mcp_server_config.py:63-67` |
| Runtime carrier | `McpConfiguration.auth_location` | `services/connector/connectors/mcp/configuration.py:23` |
| Decryption | `OdooCredentialResolver.resolve_all_for_connector` | `services/connector/credentials/odoo_credential_resolver.py:125` |
| Assembly / fail-closed point | `McpOnboardingService._build_mcp_configuration` | `services/connector/onboarding/mcp_onboarding_service.py:206` |
| `sse` delivery | `headers` dict / `QueryAuth` | `services/connector/connectors/mcp/transport.py:137-145` |
| `stdio` delivery | `process_env.update(self.config.env)` | `services/connector/connectors/mcp/transport.py:102-104` |
| Credential storage | `nexora.mcp_credential` (Fernet, composite key) | `models/connector/nexora_mcp_credential.py` |

The `env` mode is a third enum value plus a validation constraint. It adds no
branch that names a connector: the placeholder mechanism is generic and is read
from configuration, satisfying the standing prohibition on connector-specific
credential branches.

## Rejected alternatives

1. **Leave `stdio` credential injection undeclared.** Rejected: it makes the
   `authentication_location` field lie for 4 of 5 connectors and leaves the
   §11 evidence query structurally unable to report the truth. The audit
   classified this as architecturally undeclared behaviour (G-21), not as an
   acceptable convention.

2. **A separate `credential_delivery_mode` field.** Rejected: it would create
   a second axis describing the same thing, guaranteeing divergence between
   `authentication_location = 'none'` and
   `credential_delivery_mode = 'env'`. Adding a value to the existing enum is
   strictly smaller.

3. **A per-connector credential adapter class.** Rejected: it is the
   connector-specific branch the architecture forbids, and delivery differs by
   *transport*, not by connector.

4. **Immediate hard narrowing (drop wholesale injection outright).** Rejected
   for this closure pass: with no connector yet carrying a declaration, an
   unconditional switch would instantly de-authenticate all four working stdio
   connectors. R2's fallback plus seeded declarations reach the same end state
   without a functional regression window.

5. **An explicit environment allowlist for the whole child process.** Deferred,
   not rejected on merit: `process_env = os.environ.copy()` still passes the
   Odoo worker's full environment to the child. That is a distinct hardening
   item with its own blast radius and is out of scope for C-15, which governs
   *credential* delivery.

## Security and compatibility implications

**Security.**
- Four previously-undeclared authentications become declared and auditable.
- Least privilege becomes expressible and enforced wherever declared: a
  connector's child process receives only the credentials it declares.
- Fail-closed removes the silent-unauthenticated-connection path, which
  previously converted an authorization fault into a misleading transport
  fault.
- No secret value is added to any log, artefact, health payload, or DB column
  by this decision. Diagnostics carry credential names only.
- `query` delivery retains its inherent structural exposure (the token is part
  of the URL). That risk is unchanged by this ADR and is recorded in the audit
  risk table; declaring the mode does not worsen it.

**Compatibility.**
- `none`, `header`, and `query` behave exactly as before. No existing record
  changes meaning.
- Adding an enum value is additive; existing stored values remain valid.
- A connector with no injection declaration keeps its current wholesale
  injection behaviour, so no live connector regresses.
- `env` is only meaningful for `stdio`; validation rejects nonsensical
  combinations at write time rather than at connect time.

## Verification evidence

| Claim | Evidence |
| --- | --- |
| Two physical delivery paths exist | `transport.py:137-145` (sse) vs `transport.py:102-104` fed by `mcp_onboarding_service.py:298` (stdio) |
| The declared axis had only three values | `nexora_mcp_server_config.py:63-67` |
| Four connectors authenticate while declaring `none` | live `nexora_mcp_server_config` + `nexora_mcp_credential.is_set=t` for `context7_mcp`, `firecrawl_mcp`, `github_mcp`, `tavily_mcp` |
| Injection was wholesale | `resolve_all_for_connector(connector_id)` at `mcp_onboarding_service.py:218`; `env_vars.update(resolved_secrets)` at `:298` |
| Fail-closed is implemented for header/query | `mcp_onboarding_service.py:231-245` (`CREDENTIAL_UNRESOLVED`) |
| Fail-closed is implemented for declared env | `mcp_onboarding_service.py:279-295` (`CREDENTIAL_UNRESOLVED`) |
| Master key is env-only | `configs/dev.conf` contains no key; `NEXORA_CONNECTOR_SECRET_KEY` only (PC-3) |
| Only one credential per connector today | live `nexora_mcp_credential`: 5 rows, 5 distinct connectors |

## Consequences

- `authentication_location` gains `env`; a constraint enforces
  transport/mode coherence.
- Seed data for stdio connectors declares its credential env variable with the
  reserved placeholder, making delivery visible in configuration.
- §11 evidence queries reading `authentication_location` now report the real
  delivery mode for all five connectors, which is what CG-17 asserts.
- The residual `os.environ.copy()` breadth is recorded as a separate future
  hardening item and is explicitly **not** claimed as closed by C-15.
