# ADR 0069: MCP Namespace Contract (C-02)

## Status
Accepted

Ratified as part of Phase 44.2 closure. Required by Phase 44.1 §18.0 PC-6 and by
the §17.8 absolute ordering constraint **C-02 before C-26** — routing
consolidation (C-26 / Phase 44.2 closure task P11) may not proceed until this
contract is accepted.

## Context

The Universal Connector Platform addresses every executable unit through a
single string: the *capability namespace*. Two structurally different kinds of
string arrive at the same entry point:

1. **MCP protocol methods** — `tools/list`, `tools/call`, `resources/list`,
   `resources/read`, `prompts/list`, `prompts/get`. In the Nexora dialect these
   are written with a dot (`tools.list`) because the namespace field is dotted
   throughout the platform.
2. **Dynamic tool shorthand** — `{connector_id}.{tool_name}`, e.g.
   `penpot_mcp.export_shape`, `tavily_mcp.tavily_search`.

Both are dotted. Nothing in the original design distinguished them.

## Existing problem

Phase 44.1 §17 C-02 (audit finding G-02) recorded that the dispatcher split
*any* dotted namespace on the first `.` and treated the left-hand side as a
connector id. `tools.list` was therefore interpreted as connector `tools`,
method `list`. Because no connector named `tools` exists, every genuine MCP
protocol call was either misrouted or failed with a connector-resolution error,
while a connector whose id happened to collide with a protocol prefix could
silently capture protocol traffic.

The failure was structural, not incidental: the platform had no statement of
which dotted strings are protocol and which are shorthand, so each call site was
free to guess. Connector-specific `if connector_id == …` exceptions were the
natural (and forbidden) way to patch it.

## Decision

A closed, explicit reserved set is the sole arbiter of namespace meaning.

1. **Reserved protocol namespaces are a frozen, closed set of exactly six
   strings**, declared once in the domain layer:

   `tools.list`, `tools.call`, `resources.list`, `resources.read`,
   `prompts.list`, `prompts.get`

2. **Matching is verbatim and happens first.** A namespace is compared for
   equality against the reserved set *before* any `.` splitting is attempted. A
   reserved namespace is passed through to the connector provider untouched; the
   provider translates the Nexora dot form to the MCP wire form.

3. **Only non-reserved dotted namespaces are shorthand.** A namespace that is
   not reserved and contains a `.` is interpreted as
   `{connector_id}.{tool_name}`, split on the **first** dot, so tool names may
   themselves contain dots.

4. **The set is closed to connector influence.** No connector, provider,
   registry entry, manifest, or configuration record may add to, remove from, or
   override the reserved set. There are no connector-specific exceptions to this
   contract. Extending the set requires amending this ADR.

5. **Registry-style namespaces are not protocol namespaces.** Capability
   registry identifiers such as `mcp.penpot.1.0.0` are policy identifiers
   resolved through the capability registry (see ADR-0070); they never enter the
   reserved-set comparison and are never split as connector shorthand.

## Existing canonical abstraction used

No new abstraction is introduced. The contract is expressed entirely through
constructs that already exist:

| Concern | Existing abstraction |
| --- | --- |
| The reserved set | `RESERVED_PROTOCOL_NAMESPACES` — a `frozenset` in [models.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/services/connector/domain/models.py#L71-L78) |
| The predicate | `is_reserved_protocol_namespace(namespace)` in the same module, [models.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/services/connector/domain/models.py#L81-L83) |
| Enforcement point | the existing `ConnectorDispatcher` resolution path |
| Namespace → connector lookup | the existing in-memory `ConnectorCapabilityIndex` |

Placing the set in `services/connector/domain/models.py` is deliberate: the
domain layer is the one module every layer of the canonical chain already
imports, so no new dependency edge is created and no second copy of the set can
drift.

## Rejected alternatives

- **Split on the last dot instead of the first.** Rejected: it does not
  disambiguate anything (`tools.list` still splits), and it breaks tool names
  containing dots.
- **Prefix matching (`startswith("tools.")`).** Rejected: an open-ended prefix
  rule silently captures any future connector whose id begins with a reserved
  word, reintroducing collisions the closed set eliminates.
- **A dedicated `NamespaceKind` enum plus a parser class.** Rejected as
  speculative architecture: the discrimination is one set membership test; a new
  type and parser would add a layer without adding a decision.
- **Per-connector namespace declarations in the manifest.** Rejected: it makes
  protocol semantics connector-configurable, which is exactly the
  connector-specific branching the Phase 44.2 rules forbid.
- **A distinct wire separator (e.g. `tools/list` kept verbatim internally).**
  Rejected: the platform's namespace field, registry files, and persisted rows
  are dotted throughout; changing the internal separator is a broad contract
  break with no correctness gain, since the provider already performs the
  dot→slash translation at the MCP boundary.

## Security and compatibility implications

**Security.** The closed set removes a namespace-confusion attack surface: a
connector cannot register an id that hijacks protocol traffic, because protocol
strings are matched before connector resolution and the set cannot be extended
from data. Conversely, no protocol namespace can be redirected to an attacker
controlled connector by manipulating registry or manifest content.

**Compatibility.** Backward compatible for every valid pre-existing call:

- Non-dotted namespaces — unchanged.
- `{connector_id}.{tool_name}` for non-reserved ids — unchanged.
- The six reserved strings previously *could not work at all*; they now work.
  There is no caller whose working behavior changes.

The only behavior that disappears is the ability to address a connector literally
named `tools`, `resources`, or `prompts` via shorthand. No such connector exists
in the platform (live connector ids: `context7_mcp`, `firecrawl_mcp`,
`github_mcp`, `penpot_mcp`, `tavily_mcp`), so no compatibility shim is required.

## Verification evidence

| Evidence | Source |
| --- | --- |
| Reserved set is a `frozenset` of exactly the six strings | [models.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/services/connector/domain/models.py#L71-L78) |
| Predicate exists and is verbatim equality | [models.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/services/connector/domain/models.py#L81-L83) |
| Set contents asserted exactly (guards silent extension) | `tests/test_phase44_2_hardening.py`, reserved-namespace assertions |
| Every reserved namespace survives dispatch without being split | `tests/test_phase44_2_hardening.py`, per-namespace loop |
| No connector id collides with a reserved prefix | live DB: `select connector_id from nexora_connector` → 5 rows, none of `tools`/`resources`/`prompts` |
| Contract recorded in the hardening report | `docs/reports/phase44_2_mcp_platform_hardening.md`, "Namespace dispatch" row |

Certification gate **CG-04** re-verifies this contract against a live server; it
is not executed by this ADR.

## Consequences

- C-26 / P11 routing consolidation is unblocked: model providers and the source
  adapter can be routed through `UniversalCapabilityRouter` knowing that
  protocol namespaces will not be mangled en route.
- Any future MCP protocol method (e.g. a new `completion.*` method) requires an
  amendment to this ADR and to `RESERVED_PROTOCOL_NAMESPACES` in the same
  change — the set is intentionally the single place to edit.
