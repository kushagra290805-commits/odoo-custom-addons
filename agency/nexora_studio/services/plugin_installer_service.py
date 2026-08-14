# -*- coding: utf-8 -*-
from odoo import models, api
from ..models.runtime_event_constants import RuntimeEvents
from ..models.plugin_descriptor import PluginDescriptor

class PluginInstallerService(models.AbstractModel):
    _name = 'nexora.plugin_installer_service'
    _description = 'Enterprise Plugin Installer Service'

    @api.model
    def install_descriptor(self, descriptor: PluginDescriptor):
        registry = self.env['nexora.capability_registry'].sudo()
        
        # Compatibility check
        compat_svc = self.env['nexora.compatibility_service']
        compat_svc.validate_plugin_compatibility(descriptor)
        
        existing = registry.search([
            ('capability_code', '=', descriptor.capability_code), 
            ('version', '=', descriptor.version)
        ], limit=1)
        
        if existing:
            raise ValueError(f"Plugin {descriptor.capability_code} v{descriptor.version} is already installed.")
            
        vals = {
            'capability_id': descriptor.capability_id,
            'capability_code': descriptor.capability_code,
            'display_name': descriptor.display_name,
            'category': descriptor.category,
            'version': descriptor.version,
            'author': descriptor.author,
            'provider': descriptor.provider,
            'implementation_model': descriptor.implementation_model,
            'checksum': descriptor.checksum,
            'supported_platforms': ','.join(descriptor.supported_platforms),
            'supports_local': descriptor.supports_local,
            'supports_remote': descriptor.supports_remote,
            'supports_async': descriptor.supports_async,
            'permissions': ','.join(descriptor.permissions),
            'dependencies': ','.join(descriptor.dependencies),
            'optional_dependencies': ','.join(descriptor.optional_dependencies),
            'minimum_runtime_version': descriptor.minimum_runtime_version,
            'maximum_runtime_version': descriptor.maximum_runtime_version,
            'metadata_version': descriptor.metadata_version,
            'state': RuntimeEvents.CAPABILITY_ENABLED
        }
        
        plugin = registry.create(vals)
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': RuntimeEvents.PLUGIN_INSTALLED,
            'message': f"Installed plugin {descriptor.capability_code} v{descriptor.version}"
        })
        return plugin
