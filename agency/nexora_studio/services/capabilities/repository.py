from typing import List, Optional
from .models import CapabilityManifest, ExecutionTargetType
from odoo.addons.nexora_studio.services.connector.domain.models import is_reserved_protocol_namespace

# Phase 44.2 (W5 / ADR-0068): lifecycle states in which a connector's
# discovered capabilities remain routable. Health is a separate axis:
# 'unknown' (not yet probed) must NOT hide capabilities; only 'failed' does.
_ACTIVE_LIFECYCLE_STATES = {'running', 'healthy', 'paused'}


def _derive_target_type(record) -> ExecutionTargetType:
    """Single authoritative target-type derivation for registry records.

    Phase 44.2 (W2 / ADR-0068): connector-backed capabilities (MCP registry
    entries) resolve to CONNECTOR. Transport kind is not a target-type concern.
    Phase 44.2 closure (C-03 / C-04): LOCAL is preferred over REMOTE for rows
    supporting both. REMOTE has deliberately NO registered executor
    (RemoteToolExecutor returns unconditional success — audit §17.9), so a
    remote-only row resolves to REMOTE and the boot-time completeness check
    refuses to start rather than failing per request with "Executor not found".
    """
    if record.implementation_model == 'connector':
        return ExecutionTargetType.CONNECTOR
    if record.supports_local:
        return ExecutionTargetType.LOCAL
    return ExecutionTargetType.REMOTE


def _connector_is_routable(connector) -> bool:
    """Truthful health-aware filter (W5): active lifecycle + not failed."""
    return connector.state in _ACTIVE_LIFECYCLE_STATES and connector.health_status != 'failed'


class CapabilityRepository:
    def __init__(self, env=None):
        self.env = env
        self._cache = {}

    def get_all_registry_records(self):
        """Raw nexora.capability_registry records for boot-time invariants
        (executor completeness, C-04). Empty when no env is bound."""
        if not self.env:
            return []
        return self.env['nexora.capability_registry'].sudo().search([])

    def invalidate_cache(self):
        """Phase 44.2 (W4 / G-29): allow callers to drop stale manifest cache."""
        self._cache = {}
        
    def get_manifests_by_namespace(self, namespace: str) -> List[CapabilityManifest]:
        if namespace in self._cache:
            return self._cache[namespace]
            
        if self.env:
            # Query Phase 22 canonical plugin registry
            records = self.env['nexora.capability_registry'].sudo().search(
                [('capability_code', '=', namespace)],
                order='priority desc, version desc'
            )
            manifests = []
            for r in records:
                # Determine target type (Phase 44.2: single derivation)
                target_type = _derive_target_type(r)
                
                import json
                
                metadata = {}
                if hasattr(r, 'metadata_json') and r.metadata_json:
                    try:
                        metadata = json.loads(r.metadata_json)
                    except:
                        pass
                
                # Ensure core fields exist
                metadata['provider'] = r.provider
                metadata['implementation_model'] = r.implementation_model
                metadata['category'] = r.category
                
                manifest = CapabilityManifest(
                    namespace=r.capability_id,
                    display_name=r.display_name,
                    target_type=target_type,
                    version=r.version,
                    aliases=[],
                    input_schema={},
                    output_schema={},
                    metadata=metadata
                )
                manifests.append(manifest)

            # Dynamic MCP Capability lookup
            # Phase 44.2 (W3): reserved protocol namespaces are never the
            # "{connector_id}.{tool_name}" shorthand.
            # Phase 44.2 closure (C-05 / PV-11): the live connector-derived
            # candidate is collected FIRST so insertion order agrees with the
            # policy rule "prefer a live connector-backed candidate over a
            # registry-derived one".
            connector_manifests = []
            if '.' in namespace and not is_reserved_protocol_namespace(namespace):
                connector_id, tool_name = namespace.split('.', 1)
                mcp_records = self.env['nexora.mcp_discovered_tool'].sudo().search([
                    ('connector_id.connector_id', '=', connector_id),
                    ('tool_name', '=', tool_name)
                ])
                for mcp_record in mcp_records:
                    connector = mcp_record.connector_id
                    # Health-aware filtering (W5: truthful, unknown allowed)
                    if not _connector_is_routable(connector):
                        continue

                    import json
                    input_schema = {}
                    if mcp_record.input_schema_json:
                        try:
                            input_schema = json.loads(mcp_record.input_schema_json)
                        except:
                            pass

                    manifest = CapabilityManifest(
                        namespace=namespace,
                        display_name=mcp_record.description or tool_name,
                        target_type=ExecutionTargetType.CONNECTOR,
                        version="1.0",
                        input_schema=input_schema,
                        metadata={
                            'provider': 'mcp',
                            'connector_id': connector_id,
                            'category': 'mcp_tool',
                            'implementation_model': 'connector',
                            'description': mcp_record.description or tool_name,
                            'source': 'live_connector',
                        }
                    )
                    connector_manifests.append(manifest)

            # Live connector candidates win the ordering; registry-derived
            # candidates remain as fallback.
            manifests = connector_manifests + manifests
            
            self._cache[namespace] = manifests
            return manifests
            
        return []
        
    def get_all_manifests(self) -> List[CapabilityManifest]:
        if not self.env:
            return []
        records = self.env['nexora.capability_registry'].sudo().search([])
        manifests = []
        for r in records:
            target_type = _derive_target_type(r)
            
            import json
            metadata = {}
            if hasattr(r, 'metadata_json') and r.metadata_json:
                try:
                    metadata = json.loads(r.metadata_json)
                except:
                    pass
            metadata['provider'] = r.provider
            metadata['implementation_model'] = r.implementation_model
            metadata['category'] = r.category
            
            manifest = CapabilityManifest(
                namespace=r.capability_code,
                display_name=r.display_name,
                target_type=target_type,
                version=r.version,
                aliases=[],
                input_schema={},
                output_schema={},
                metadata=metadata
            )
            manifests.append(manifest)
            self._cache[r.capability_code] = [manifest]
            
        mcp_records = self.env['nexora.mcp_discovered_tool'].sudo().search([])
        for mcp_record in mcp_records:
            connector = mcp_record.connector_id
            if not _connector_is_routable(connector):
                continue
                
            import json
            input_schema = {}
            if mcp_record.input_schema_json:
                try:
                    input_schema = json.loads(mcp_record.input_schema_json)
                except:
                    pass
                    
            namespace = f"{connector.connector_id}.{mcp_record.tool_name}"
            manifest = CapabilityManifest(
                namespace=namespace,
                display_name=mcp_record.description or mcp_record.tool_name,
                target_type=ExecutionTargetType.CONNECTOR,
                version="1.0",
                input_schema=input_schema,
                metadata={
                    'provider': 'mcp',
                    'connector_id': connector.connector_id,
                    'category': 'mcp_tool',
                    'implementation_model': 'connector',
                    'description': mcp_record.description or mcp_record.tool_name
                }
            )
            manifests.append(manifest)
            if namespace not in self._cache:
                self._cache[namespace] = []
            self._cache[namespace].append(manifest)
            
        return manifests
        
    def register_manifest(self, manifest: CapabilityManifest):
        if manifest.namespace not in self._cache:
            self._cache[manifest.namespace] = []
        self._cache[manifest.namespace].append(manifest)
        
    def synchronize_manifests(self, manifests: List[CapabilityManifest]):
        """
        Synchronizes manifests into the nexora.capability_registry database.
        Called exclusively by RegistryBootstrapService.
        """
        if not self.env:
            return

        registry = self.env['nexora.capability_registry'].sudo()
        existing_records = registry.search([])
        
        existing_map = {r.capability_code: r for r in existing_records}
        
        # Keep track of active namespaces to mark missing as inactive
        active_namespaces = set()

        import json

        for manifest in manifests:
            active_namespaces.add(manifest.namespace)
            enabled = manifest.metadata.get('enabled', False)
            
            vals = {
                'capability_id': f"{manifest.namespace}.{manifest.version}",
                'capability_code': manifest.namespace,
                'display_name': manifest.display_name,
                'version': manifest.version,
                'provider': manifest.metadata.get('provider', 'nexora'),
                'category': manifest.metadata.get('category', 'tool'),
                # Phase 44.2 (W2): connector-backed capabilities must read back
                # as CONNECTOR; implementation_model is the derivation key.
                'implementation_model': (
                    'connector'
                    if manifest.target_type == ExecutionTargetType.CONNECTOR
                    else manifest.metadata.get('implementation_model', '')
                ),
                'supports_local': manifest.target_type == ExecutionTargetType.LOCAL,
                'supports_remote': manifest.target_type == ExecutionTargetType.REMOTE,
                'enabled': enabled,
                'checksum': 'bootstrap_hash',
                'state': 'capability.enabled' if enabled else 'capability.disabled',
                'metadata_json': json.dumps(manifest.metadata)
            }
            
            if manifest.namespace in existing_map:
                # Update existing record
                existing_map[manifest.namespace].write(vals)
            else:
                # Create new record
                registry.create(vals)
                
        # Mark removed as inactive
        for record in existing_records:
            if record.capability_code not in active_namespaces and record.provider != 'nexora':
                record.write({'enabled': False, 'state': 'capability.disabled'})