# -*- coding: utf-8 -*-
from odoo import models, api
import logging
from .plugin_repository_factory import PluginRepositoryFactory
from ..models.runtime_event_constants import RuntimeEvents

_logger = logging.getLogger(__name__)

class CapabilityDiscoveryService(models.AbstractModel):
    _name = 'nexora.capability_discovery_service'
    _description = 'Enterprise Capability Discovery Service (Manifest-Driven)'

    @api.model
    def execute_discovery(self):
        _logger.info("Executing manifest-driven plugin discovery...")
        
        repo = PluginRepositoryFactory.get_repository()
        manifests = repo.discover_manifests()
        
        installer = self.env['nexora.plugin_installer_service']
        validator = self.env['nexora.plugin_manifest_validator']
        registry = self.env['nexora.capability_registry']
        
        discovered_count = 0
        for manifest_str in manifests:
            try:
                descriptor = validator.create_descriptor(manifest_str)
                existing = registry.search([('capability_code', '=', descriptor.capability_code), ('version', '=', descriptor.version)], limit=1)
                
                if not existing:
                    installer.install_descriptor(descriptor)
                    discovered_count += 1
            except Exception as e:
                _logger.error(f"Failed to process manifest: {str(e)}")
                cap_code = descriptor.capability_code if 'descriptor' in locals() else "unknown"
                self.env['nexora.runtime_event'].create({
                    'runtime_type': 'system',
                    'event_type': RuntimeEvents.CAPABILITY_VALIDATION_FAILED,
                    'message': f"Validation failed for manifest {cap_code}: {e}"
                })
                
        if discovered_count > 0:
            self.env['nexora.capability_cache_service'].rebuild_cache()
            
        return discovered_count
