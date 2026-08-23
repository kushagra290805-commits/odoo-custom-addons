# -*- coding: utf-8 -*-
"""
Repair corrupted connector manifests and rebuild the derived capability
projection (audit C-07 / C-08 / C-11; ADR-0070 §6).

Live damage (captured pre-closure in
docs/reports/artefacts/PC4_evidence_snapshot_pre_closure_nexora_studio.txt):

    context7_mcp   len   2  {}
    firecrawl_mcp  len   2  {}
    github_mcp     len  16  {"broken": true}
    tavily_mcp     len  64  {"command": "python", "args": ["-c", "import sys; sys.exit(1)"]}
    penpot_mcp     len 792  a registry-policy JSON blob ("namespace": "mcp.penpot", ...)

None of the five persisted values is a valid `ConnectorManifest`:
ConnectorPersistenceService.load_all_connectors() does
``ConnectorManifest(**json.loads(manifest_json))``, which raises TypeError for
unknown keys and falls back to an empty-capability aggregate. The penpot blob,
although "real" JSON, carries registry-policy keys (namespace, provider_id,
lifecycle, ...) that are not manifest fields, so it is corrupt *as a manifest*
even though it was deliberately written by an earlier phase. It is logged in
full before overwrite (audit mitigation: "records the prior value ... before
overwriting") — it contains no credential material.

Repair source: the authoritative protocol store `nexora.mcp_discovered_tool`
(ADR-0070 §5 fixes the one-way derivation direction). The capability list is
the canonical generic MCP namespaces plus each discovered tool name as a
``{connector_id}.{tool_name}`` namespace, exactly as
ConnectorExecutionTarget splits dotted namespaces on the first dot (ADR-0069).
Raw tool names are used verbatim — including names with hyphens or uppercase
(`query-docs`, `AssignCodingAgent`) — because the CAPABILITY_PATTERN gate in
ManifestValidator rejects anything else, and the audit forbids hand-writing
manifests.

Connectors with no discovered tools keep their existing manifest untouched
(nothing is fabricated). The migration is idempotent: rows whose persisted
value already parses into a ConnectorManifest are left byte-identical.

After the manifest repair, the derived projection
(nexora_capability_definition → nexora_connector_capability) is rebuilt from
the same authoritative store so the projection cannot disagree with it
(ADR-0070 §6). The rebuild truncates and repopulates both tables; they hold no
data other than this derivation by design.

The nvidia key removal lives in _remove_nvidia_plaintext_key(): the value is
never read or logged — existence only.
"""
import json
import logging

_logger = logging.getLogger(__name__)

# Canonical generic MCP namespaces (mirrors mcp_onboarding_service._DEFAULT_MCP_CAPABILITIES).
_GENERIC_MCP_CAPABILITIES = [
    'tools.list', 'tools.call', 'resources.list', 'resources.read',
    'prompts.list', 'prompts.get',
]


def _load_persisted_manifest(raw):
    """Return the parsed dict if raw is a structurally valid ConnectorManifest JSON, else None."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    # A real manifest always declares these three required identity fields.
    if not all(isinstance(data.get(k), str) and data[k] for k in
               ('connector_id', 'display_name', 'connector_type_id')):
        return None
    return data


def _repair_manifests(env):
    """Rebuild manifest_json from discovered tools where the stored value is not a valid manifest."""
    Connector = env['nexora.connector']
    DiscoveredTool = env['nexora.mcp_discovered_tool']

    repaired = 0
    skipped_valid = 0
    kept_empty = 0

    for record in Connector.search([]):
        connector_id = record.connector_id
        current = _load_persisted_manifest(record.manifest_json)
        if current is not None:
            skipped_valid += 1
            continue

        tools = DiscoveredTool.search_read(
            [('connector_id', '=', record.id)],
            fields=['tool_name'],
        )
        if not tools:
            # No discovered tools: leave the field alone and let live discovery
            # repopulate it (ADR-0070 §6 — never fabricate content).
            kept_empty += 1
            continue

        prior = record.manifest_json or ''
        capabilities = list(_GENERIC_MCP_CAPABILITIES) + [
            f"{connector_id}.{t['tool_name']}" for t in tools
        ]
        manifest = {
            'connector_id': connector_id,
            'display_name': record.name or connector_id,
            'connector_type_id': (
                record.connector_type_id.type_code if record.connector_type_id else 'mcp'
            ),
            'sdk_version': '1.0.0',
            'version': record.version or '1.0.0',
            'capabilities': capabilities,
            'transports': ['stdio', 'sse'],
        }
        _logger.info(
            "Repairing corrupt manifest for '%s' (len=%d); prior value: %s",
            connector_id, len(prior), prior,
        )
        record.write({'manifest_json': json.dumps(manifest)})
        repaired += 1

    _logger.info(
        "Manifest repair complete: %d repaired, %d already valid, %d left empty (no discovered tools).",
        repaired, skipped_valid, kept_empty,
    )


def _rebuild_capability_projection(env):
    """Rebuild nexora_capability_definition + nexora_connector_capability from discovered tools."""
    Definition = env['nexora.capability_definition']
    Projection = env['nexora.connector_capability']
    DiscoveredTool = env['nexora.mcp_discovered_tool']

    total_tools = DiscoveredTool.search_count([])
    existing_defs = Definition.search_count([])
    existing_proj = Projection.search_count([])
    if existing_defs == 0 and existing_proj == 0 and total_tools == 0:
        _logger.info("Capability projection: nothing to rebuild.")
        return

    _logger.info(
        "Rebuilding capability projection from %d discovered tools "
        "(dropping %d definitions, %d projection rows).",
        total_tools, existing_defs, existing_proj,
    )

    # Both tables are pure derivations of nexora_mcp_discovered_tool
    # (ADR-0070 §3/§5): they may be truncated and rebuilt without loss.
    Projection.search([]).unlink()
    # Definitions last: projection rows reference them with ondelete='restrict'.
    Definition.search([]).unlink()

    defs_by_namespace = {}
    for tool in DiscoveredTool.search([], order='tool_name'):
        namespace = f"{tool.connector_id.connector_id}.{tool.tool_name}"
        definition = defs_by_namespace.get(namespace)
        if definition is None:
            definition = Definition.create({
                'namespace': namespace,
                'version': '1.0.0',
                'description': tool.description or '',
                'input_schema': tool.input_schema_json or '{}',
                'output_schema': '{}',
                'is_read_only': True,
                'requires_authentication': False,
            })
            defs_by_namespace[namespace] = definition
        Projection.create({
            'connector_id': tool.connector_id.id,
            'capability_definition_id': definition.id,
        })

    _logger.info(
        "Capability projection rebuilt: %d definitions, %d projection rows.",
        len(defs_by_namespace), total_tools,
    )


def _remove_nvidia_plaintext_key(env):
    """Remove the plaintext `nexora.nvidia.api_key` ir.config_parameter row (C-13).

    Existence-only verification: the value itself is never read, written,
    or logged.
    """
    Param = env['ir.config_parameter'].sudo()
    matched = Param.search([('key', '=', 'nexora.nvidia.api_key')])
    if matched:
        matched.unlink()
        _logger.info("Removed plaintext ir.config_parameter key 'nexora.nvidia.api_key'.")
    else:
        _logger.info("ir.config_parameter key 'nexora.nvidia.api_key' already absent.")


def _declare_stdio_credential_delivery(env):
    """Declare credential delivery for stdio connectors (ADR-0071 R1/R2).

    A stdio connector that owns a set credential must not record
    authentication_location='none'. This declares the credential's env
    variable in env_vars_json with the reserved injection placeholder and
    flips authentication_location to 'env'.

    Declared-only injection then delivers exactly that key (least privilege).
    Today each connector owns exactly one credential, so the delivered
    environment is byte-equivalent to the previous wholesale fallback while
    becoming truthful and auditable.

    Credential VALUES are never read or logged here — keys only.
    """
    Config = env['nexora.mcp_server_config']
    Credential = env['nexora.mcp_credential']
    _PLACEHOLDER = '__INJECT_VIA_NEXORA_MCP_CREDENTIAL__'

    for cred in Credential.search([('is_set', '=', True)]):
        connector = cred.connector_id
        if not connector:
            continue
        config = Config.search([('connector_id', '=', connector.id)], limit=1)
        if not config:
            continue
        if config.transport_type != 'stdio':
            continue
        if not cred.credential_key:
            continue

        try:
            env_vars = json.loads(config.env_vars_json or '{}')
            if not isinstance(env_vars, dict):
                env_vars = {}
        except (ValueError, TypeError):
            env_vars = {}

        changed = {}
        if env_vars.get(cred.credential_key) != _PLACEHOLDER:
            # Declare only this connector's own credential key; never touch
            # unrelated entries already present.
            env_vars[cred.credential_key] = _PLACEHOLDER
            changed['env_vars_json'] = json.dumps(env_vars)
        if config.authentication_location != 'env':
            changed['authentication_location'] = 'env'
        if changed:
            config.write(changed)
            _logger.info(
                "Declared 'env' credential delivery ('%s') for stdio connector '%s'.",
                cred.credential_key, connector.connector_id,
            )


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _repair_manifests(env)
    _rebuild_capability_projection(env)
    _remove_nvidia_plaintext_key(env)
    _declare_stdio_credential_delivery(env)
