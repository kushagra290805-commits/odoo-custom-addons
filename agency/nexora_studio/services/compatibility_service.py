# -*- coding: utf-8 -*-
from odoo import models, api
from ..models.plugin_descriptor import PluginDescriptor

class CompatibilityService(models.AbstractModel):
    _name = 'nexora.compatibility_service'
    _description = 'Enterprise Plugin Compatibility Layer'

    @api.model
    def validate_plugin_compatibility(self, descriptor: PluginDescriptor):
        semver_svc = self.env['nexora.semantic_version_service']
        
        # Validates minimum and maximum boundaries against the current runtime version
        semver_svc.validate_runtime_bounds(
            descriptor.minimum_runtime_version, 
            descriptor.maximum_runtime_version
        )
                
        platforms = descriptor.supported_platforms
        # Additional platform compatibility checks could be performed here
        return True
