from odoo import models, api
import os
import hashlib
import json
import logging
from ..runtime.mcp.registry_provider import JsonRegistryProvider
from .repository import CapabilityRepository

_logger = logging.getLogger(__name__)

class RegistryBootstrapService(models.AbstractModel):
    _name = 'nexora.registry_bootstrap_service'
    _description = 'Registry Bootstrap Service'

    @api.model
    def execute_bootstrap(self):
        """
        Idempotent bootstrap of capability registries into the Odoo database.
        """
        _logger.info("Executing Capability Registry Bootstrap...")
        
        registry_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'config', 'mcp_registry.json'
        )
        registry_path = os.path.normpath(registry_path)

        if not os.path.exists(registry_path):
            _logger.warning(f"Registry config not found at {registry_path}")
            return {"status": "skipped", "reason": "file_not_found"}

        # Calculate hash for idempotency checking
        with open(registry_path, 'rb') as f:
            content = f.read()
            current_hash = hashlib.sha256(content).hexdigest()

        # Check hash against a system parameter
        stored_hash = self.env['ir.config_parameter'].sudo().get_param('nexora.mcp_registry_hash')
        if stored_hash == current_hash:
            _logger.info("Registry hash unchanged. Skipping bootstrap synchronization.")
            return {"status": "skipped", "reason": "hash_match"}

        _logger.info(f"Registry hash changed ({stored_hash} -> {current_hash}). Synchronizing...")

        provider = JsonRegistryProvider(registry_path)
        manifests = provider.get_manifests()
        
        # Enforce lifecycle-aware enablement rules
        for manifest in manifests:
            lifecycle = manifest.metadata.get('lifecycle', 'planned')
            if lifecycle in ['verified', 'production']:
                manifest.metadata['enabled'] = True
            elif lifecycle in ['planned', 'deprecated']:
                manifest.metadata['enabled'] = False
            # If experimental, we leave it as configured in JSON
        
        repository = CapabilityRepository(self.env)
        repository.synchronize_manifests(manifests)
        
        # Save new hash
        self.env['ir.config_parameter'].sudo().set_param('nexora.mcp_registry_hash', current_hash)
        
        _logger.info(f"Successfully synchronized {len(manifests)} capabilities.")
        return {"status": "success", "synchronized_count": len(manifests)}
