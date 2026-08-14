# -*- coding: utf-8 -*-
from odoo import models, api
import logging
import json
import hashlib
from ..models.plugin_descriptor import PluginDescriptor

_logger = logging.getLogger(__name__)

class PluginManifestValidator(models.AbstractModel):
    _name = 'nexora.plugin_manifest_validator'
    _description = 'Enterprise Plugin Manifest Validator'

    @api.model
    def create_descriptor(self, manifest_str):
        try:
            meta = json.loads(manifest_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in manifest: {e}")
            
        required_keys = [
            'capability_code', 'display_name', 'category', 'version', 
            'author', 'provider', 'implementation_model', 'supported_platforms',
            'supports_local', 'supports_remote', 'supports_async',
            'permissions', 'dependencies', 'optional_dependencies',
            'minimum_runtime_version', 'metadata_version'
        ]
        
        missing = [k for k in required_keys if k not in meta]
        if missing:
            raise ValueError(f"Incomplete plugin manifest. Missing: {missing}")
            
        # Semantic Version Validation
        semver_svc = self.env['nexora.semantic_version_service']
        semver_svc.parse_version(meta['version'])
        semver_svc.parse_version(meta['minimum_runtime_version'])
        if meta.get('maximum_runtime_version'):
            semver_svc.parse_version(meta['maximum_runtime_version'])
            
        # Compute Checksum (SHA-256)
        # We sort keys to ensure stable checksum if JSON is formatted differently
        stable_json = json.dumps(meta, sort_keys=True)
        checksum = hashlib.sha256(stable_json.encode('utf-8')).hexdigest()
        
        return PluginDescriptor(
            capability_code=meta['capability_code'],
            version=meta['version'],
            display_name=meta['display_name'],
            category=meta['category'],
            author=meta['author'],
            provider=meta['provider'],
            implementation_model=meta['implementation_model'],
            checksum=checksum,
            supported_platforms=meta.get('supported_platforms', []),
            supports_local=meta.get('supports_local', True),
            supports_remote=meta.get('supports_remote', False),
            supports_async=meta.get('supports_async', False),
            permissions=meta.get('permissions', []),
            dependencies=meta.get('dependencies', []),
            optional_dependencies=meta.get('optional_dependencies', []),
            minimum_runtime_version=meta.get('minimum_runtime_version'),
            maximum_runtime_version=meta.get('maximum_runtime_version'),
            metadata_version=meta.get('metadata_version')
        )
