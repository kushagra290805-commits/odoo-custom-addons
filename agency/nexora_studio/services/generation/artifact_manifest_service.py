# -*- coding: utf-8 -*-
from odoo import models
import json
import os
from datetime import datetime

class ArtifactManifestService(models.AbstractModel):
    _name = 'nexora.artifact_manifest_service'
    _description = 'Artifact Manifest Ledger'

    def create_manifest(self, workspace_path: str, context: dict, hashes: dict) -> dict:
        """
        Creates a JSON manifest representing the generation fingerprint.
        """
        manifest = {
            'generated_at': datetime.utcnow().isoformat(),
            'session_uuid': context.get('builder_session', type('', (), {'session_uuid': 'unknown'})).session_uuid,
            'configuration_uuid': context.get('builder_session', type('', (), {'builder_configuration_id': type('', (), {'configuration_uuid': 'unknown'})})).builder_configuration_id.configuration_uuid,
            'provider': context.get('ai_provider_name', 'none'),
            'file_hashes': hashes,
            'dependencies': context.get('resolved_dependencies', {}),
            'generator_version': '1.0.0'
        }
        
        manifest_path = os.path.join(workspace_path, '.nexora', 'manifest.json')
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
            
        return manifest
