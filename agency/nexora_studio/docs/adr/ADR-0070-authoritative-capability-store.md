# ADR 0070: Authoritative Capability Store (C-11)

## Status
Accepted

Ratified as part of Phase 44.2 closure. Required by Phase 44.1 §18.0 PC-6.

## Context

The platform holds capability information in three separate persisted tables,
each written by a different subsystem:

| Store | Writer | Live rows |
| --- | --- | --- |
| `nexora_mcp_discovered_tool` | `services/connector/onboarding/capability_discovery.py` | 67 |
| `nexora_capability_registry` | `services/capabilities/repository.py` → `synchronize_manifests` | 17 |
| `nexora_connector_capability` | *nobody* | 0 |

A fourth table, `nexora_capability_definition`, exists as the mandatory
`ondelete='restrict'` target of `nexora_connector_capability.capability_definition_id`
and holds 0 rows.

Separately, the runtime maintains an **in-memory** namespace → connector map,
`ConnectorCapabilityIndex`, rebuilt by
`ConnectorRuntime._rebuild_capability_index()` from
`connector.manifest.capabilities`.

## Existing problem

Phase 44.1 §17 C-11 (finding G-25) recorded that no reconciliation rule existed:
three stores, three writers, no statement of which one is true. Two concrete
defects followed.

1. **The runtime index rebuilt from a corrupt input.** Four of five persisted
   `manifest_json` values are empty or degenerate (`{}`, `{}`, `{"broken": true}`,
   `{"command": "python", "args": [...]}`), so
   `connector.manifest.capabilities` is empty for those connectors and the
   in-memory index cannot resolve their namespaces. Finding G-04 (P0).

2. **`nexora_connector_capability` was mistaken for the runtime index.** The
   audit expected the 0-row count to explain G-04. Inspection during this closure
   pass establishes that it does not: `ConnectorCapabilityIndex` is a pure
   in-process `Dict[str, List[str]]` guarded by an `RLock`
   ([capability_index.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/services/connector/registry/capability_index.py#L27-L30)),
   and **no code path writes `nexora_connector_capability` at all**. The table is
   an unpopulated relational projection, not the resolution mechanism. Its
   emptiness is therefore a *reporting/observability* defect, not the cause of
   G-04; the cause is the corrupt `manifest_json` input.

Distinguishing these two things is the substance of this ADR: fixing the input
fixes routing, and populating the projection fixes visibility. They are not the
same fix.

## Decision

Three stores, three distinct and non-overlapping authorities. No fourth store.

### 1. `nexora_mcp_discovered_tool` — authoritative for protocol truth

What a connector *can actually do*. It is the only store populated from live MCP
`tools/list` responses, so it is the sole source of record for the existence,
name, description and input schema of a tool. Nothing else may assert that a tool
exists.

### 2. `nexora_capability_registry` — authoritative for platform policy

What the platform *is allowed to offer*: enablement, priority, provider,
lifecycle/verification state, `supports_local` / `supports_remote`, and
`implementation_model` (which drives `ExecutionTargetType` derivation in
[repository.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/services/capabilities/repository.py#L11-L23)).
It never asserts that a tool exists; a registry entry may be enabled for a
capability whose connector is absent, and that is a reconciliation defect to be
resolved against the registry file, not evidence of a tool.

### 3. `nexora_connector_capability` — derived index, never a source

A read-only relational projection of (1) joined to the connectors that own it,
maintained for reporting, views and SQL-level evidence queries. It is
**derived**: it may be truncated and rebuilt at any time without loss. It is
never read to make a routing decision and never written by a caller as a way of
declaring a capability.

Consequently `nexora_capability_definition` is likewise derived: a definition row
exists because a discovered tool requires one to satisfy the
`ondelete='restrict'` foreign key, keyed on its `unique(namespace, version)`
constraint.

### 4. `ConnectorCapabilityIndex` remains the sole routing authority

Namespace → connector resolution stays in memory, rebuilt from the connector
manifest. This is unchanged and deliberate: routing must not incur a DB query per
dispatch. The manifest is therefore the *input contract* to routing, which makes
manifest integrity a routing correctness requirement.

### 5. Derivation direction is fixed and one-way

```
live MCP server
  → tools/list
    → nexora_mcp_discovered_tool          (protocol truth, authoritative)
      → connector manifest capabilities   (routing input)
        → ConnectorCapabilityIndex         (in-memory routing authority)
      → nexora_capability_definition       (derived, FK target)
        → nexora_connector_capability      (derived projection)

nexora_capability_registry                 (policy, independent authority)
  → CapabilityManifest.target_type         (execution target derivation)
```

Nothing flows backwards. A derived store may never write to an authoritative
one. In particular, repairing a manifest reads discovered tools; it never
synthesises tools from a manifest.

### 6. Repair obligations that follow

- Manifests are repaired **from discovered tools**, the authoritative store.
  Where a connector has no discovered tools, the manifest capability list is left
  empty for discovery to populate; content is never fabricated. (Phase 44.2
  closure P3, audit C-07.)
- The derived projection is rebuilt from the same authoritative store in the same
  migration, after the manifest repair, so the projection and the manifest cannot
  disagree. (Audit C-08: "fix the input before touching the logic.")
- Rebuild is idempotent and must never replace a valid manifest with an empty or
  degenerate one.

## Existing canonical abstraction used

No new abstraction. Each authority is an existing model with an existing writer:

| Concern | Existing abstraction |
| --- | --- |
| Protocol truth | `nexora.mcp_discovered_tool` + `McpCapabilityDiscoveryService` |
| Policy | `nexora.capability_registry` + `CapabilityRepository.synchronize_manifests` |
| Derived projection | `nexora.connector_capability` / `nexora.capability_definition` models (already declared, already ACL'd in `security/ir.model.access.csv`) |
| Routing | `ConnectorCapabilityIndex` + `ConnectorRuntime._rebuild_capability_index()` |
| Repair vehicle | the existing `migrations/<version>/post-migrate.py` mechanism, following the pattern already established by `migrations/19.0.1.0.1/` |

## Rejected alternatives

- **Build a unified capability store.** Rejected explicitly by the audit: "a
  fourth 'unified' store would be exactly the speculative architecture the audit
  forbids." The three stores answer three genuinely different questions;
  merging them would force policy and protocol truth into one row and destroy the
  ability to enable a capability independently of its live discovery state.
- **Drop `nexora_connector_capability` and `nexora_capability_definition`.**
  Considered seriously, since nothing reads them for routing. Rejected because
  both models are already declared, already exposed in
  `views/connector_views.xml`, already ACL'd, and are the only SQL-queryable
  join between a connector and its capabilities — which the §11 evidence queries
  and CG-09 rely on. Dropping them would be a destructive schema change with no
  correctness benefit, and the Phase 44.2 rules forbid deletion without
  dependency proof of safety.
- **Make `nexora_connector_capability` the routing authority (a DB query per
  dispatch).** Rejected: it converts an O(1) in-memory lookup into a per-request
  query, and it requires an Odoo `env` on the dispatch path, which the runtime
  deliberately does not have.
- **Populate the manifest by hand.** Rejected by C-07 ("Do not hand-write
  manifests") — hand-written manifests are indistinguishable from protocol truth
  once persisted, which would permanently corrupt the authority chain.
- **Treat `nexora_capability_registry` as authoritative for tool existence.**
  Rejected: it is seeded from `config/mcp_registry.json`, a policy file, and its
  live state already contains two enabled entries (`mcp.gsap_docs`,
  `mcp.mdn_docs`) with no connector at all — proof that it can assert
  capabilities that do not exist.

## Security and compatibility implications

**Security.** A one-way derivation direction removes a privilege-escalation
shape: because derived stores can never write back, a user with write access to
the projection (admin views) cannot cause a tool to appear routable. Routing can
only gain a capability from a live protocol response or from explicit policy.
Discovered-tool rows carry names, descriptions and input schemas only — never
credential material — so populating the projection introduces no new secret
surface.

**Compatibility.** Additive and backward compatible:

- Routing behavior is unchanged in mechanism; it changes only in *outcome*, and
  only for connectors whose manifests were corrupt (they become routable).
- `nexora_capability_registry` semantics are unchanged.
- Populating `nexora_connector_capability` and `nexora_capability_definition`
  moves them from 0 rows to N rows. Nothing reads them today, so no existing
  reader can be broken; the `unique(connector_id, capability_definition_id)` and
  `unique(namespace, version)` constraints make the rebuild safely idempotent.
- No table is dropped and no column is removed, so no downgrade path is needed.

## Verification evidence

| Evidence | Source |
| --- | --- |
| `ConnectorCapabilityIndex` is in-memory only (`Dict` + `RLock`, no `env`) | [capability_index.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/services/connector/registry/capability_index.py#L27-L30) |
| No writer exists for `nexora_connector_capability` | repository-wide search for `connector_capability`: only model definition, view, ACL, an audit script read, and docs — no `create`/`write` |
| Index rebuild reads only `connector.manifest.capabilities` | [connector_runtime.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/services/connector/runtime/connector_runtime.py#L589-L594) |
| Four of five persisted manifests are corrupt | `nexora_cert`: `{}`, `{}`, `{"broken": true}`, `{"command": …}`; only `penpot_mcp` is well-formed |
| Discovered tools are populated and per-connector | `nexora_cert`: 67 rows — context7 2, firecrawl 27, github 29, penpot 4, tavily 5 |
| `nexora_capability_definition` is the mandatory FK target | [nexora_connector_capability.py](file:///d:/ODOO/custom-addons/agency/nexora_studio/models/connector/nexora_connector_capability.py#L8) `ondelete='restrict'`, `required=True` |
| Registry can assert capabilities with no connector | `nexora_cert`: `mcp.gsap_docs.1.0.0`, `mcp.mdn_docs.1.0.0` enabled with no connector row |
| Pre-closure baseline captured before any repair | `docs/reports/artefacts/PC4_evidence_snapshot_pre_closure_nexora_studio.txt` |

Certification gate **CG-09** re-verifies that per-connector projection counts
equal discovered-tool counts and that `resolve_capability` returns a hit for a
known namespace. It is not executed by this ADR.

## Consequences

- The Phase 44.2 closure manifest-repair migration has an unambiguous source of
  truth to repair *from*, and an unambiguous obligation to rebuild the projection
  *after* the repair.
- Any future capability surface must declare which of the three authorities it
  belongs to; "a new capability table" is not an available option.
- `nexora_capability_definition` rows are derived artefacts. They must not be
  hand-authored in seed data, or the derivation would no longer be one-way.
