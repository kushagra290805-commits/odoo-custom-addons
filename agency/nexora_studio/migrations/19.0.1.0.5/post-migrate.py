# -*- coding: utf-8 -*-
"""Phase 47.8A: correct the stale mcp.penpot classification so GenerationRuntime boots.

Root cause (trace):
- _parse_registry_manifests (bootstrap.py:37) ALREADY classifies ALL registry-backed
  MCP entries as ExecutionTargetType.CONNECTOR (Phase 44.2 W2 / ADR-0068).
- synchronize_manifests writes implementation_model='connector' when
  target_type == CONNECTOR.
- _derive_target_type derives CONNECTOR when implementation_model == 'connector'.
- BUT the stored mcp_registry.json hash 4e8c39b4 != current file hash c1d72a04,
  so bootstrap hasn't re-synced since pre-44.2.
- DB row (id=11) is a STALE projection from the pre-44.2 parser:
  implementation_model='nexora.provider.penpot_mcp', supports_local=False,
  supports_remote=True -> REMOTE -> GenerationRuntime construction refuses to boot.

Fix: minimal, idempotent correction of ONLY the mcp.penpot row's three
classification columns. Leave enabled/state/provider/category/metadata_json
untouched. Scope guard: ONLY capability_code = 'mcp.penpot'.
"""

def migrate(cr, version):
    cr.execute(
        """
        UPDATE nexora_capability_registry
        SET implementation_model = 'connector',
            supports_local = false,
            supports_remote = false
        WHERE capability_code = 'mcp.penpot'
          AND (implementation_model != 'connector'
               OR supports_local
               OR supports_remote)
        """
    )
    updated = cr.rowcount
    if updated:
        print(f"Phase 47.8A: corrected mcp.penpot classification ({updated} row)")
    else:
        print("Phase 47.8A: mcp.penpot already correctly classified (idempotent)")