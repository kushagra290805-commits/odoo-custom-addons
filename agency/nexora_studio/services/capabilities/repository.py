from typing import List, Optional
from .models import CapabilityManifest, ExecutionTargetType

class CapabilityRepository:
    def __init__(self, env=None):
        self.env = env
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
                # Determine target type
                if r.supports_remote:
                    target_type = ExecutionTargetType.REMOTE
                elif r.supports_local:
                    target_type = ExecutionTargetType.LOCAL
                else:
                    target_type = ExecutionTargetType.REMOTE
                
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
            self._cache[namespace] = manifests
            return manifests
            
        return []
        
    def get_all_manifests(self) -> List[CapabilityManifest]:
        if not self.env:
            return []
        records = self.env['nexora.capability_registry'].sudo().search([])
        manifests = []
        for r in records:
            if r.supports_remote:
                target_type = ExecutionTargetType.REMOTE
            elif r.supports_local:
                target_type = ExecutionTargetType.LOCAL
            else:
                target_type = ExecutionTargetType.REMOTE
            
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
                'implementation_model': manifest.metadata.get('implementation_model', ''),
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