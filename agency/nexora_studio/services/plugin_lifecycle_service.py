# -*- coding: utf-8 -*-
from odoo import models, api
from ..models.runtime_event_constants import RuntimeEvents

class PluginLifecycleService(models.AbstractModel):
    _name = 'nexora.plugin_lifecycle_service'
    _description = 'Enterprise Plugin Lifecycle Service'

    @api.model
    def enable_plugin(self, plugin):
        if plugin.state not in [RuntimeEvents.STATE_INSTALLED, RuntimeEvents.STATE_DISABLED, RuntimeEvents.STATE_DEGRADED]:
            raise ValueError(f"Cannot enable plugin from state: {plugin.state}")
            
        # Integrity check: recalculate checksum or at least assume the file is valid if it matches.
        # Here we just verify it exists if we had a repo binding, but for now we trust the stored checksum.
        # Check dependencies via graph service
        graph_svc = self.env['nexora.dependency_graph_service']
        graph_svc.validate_dependencies_for_enable(plugin)
        
        plugin.state = RuntimeEvents.STATE_ENABLED
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': RuntimeEvents.PLUGIN_ENABLED,
            'message': f"Enabled plugin {plugin.capability_code} v{plugin.version}"
        })
        self.env['nexora.capability_cache_service'].rebuild_cache()

    @api.model
    def disable_plugin(self, plugin):
        if plugin.state not in [RuntimeEvents.STATE_ENABLED, RuntimeEvents.STATE_DEGRADED]:
            raise ValueError(f"Cannot disable plugin from state: {plugin.state}")
            
        plugin.state = RuntimeEvents.STATE_DISABLED
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': RuntimeEvents.PLUGIN_DISABLED,
            'message': f"Disabled plugin {plugin.capability_code} v{plugin.version}"
        })
        self.env['nexora.capability_cache_service'].rebuild_cache()

    @api.model
    def degrade_plugin(self, plugin):
        if plugin.state != RuntimeEvents.STATE_ENABLED:
            raise ValueError(f"Only enabled plugins can be degraded. Current state: {plugin.state}")
        plugin.state = RuntimeEvents.STATE_DEGRADED
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': RuntimeEvents.PLUGIN_DEGRADED,
            'message': f"Plugin {plugin.capability_code} v{plugin.version} degraded"
        })

    @api.model
    def uninstall_plugin(self, plugin):
        if plugin.state == RuntimeEvents.STATE_ENABLED:
            self.disable_plugin(plugin)
            
        code = plugin.capability_code
        version = plugin.version
        plugin.unlink()
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': RuntimeEvents.PLUGIN_REMOVED,
            'message': f"Uninstalled plugin {code} v{version}"
        })
        self.env['nexora.capability_cache_service'].rebuild_cache()

    @api.model
    def upgrade_plugin(self, capability_code, new_descriptor):
        registry = self.env['nexora.capability_registry']
        existing = registry.search([('capability_code', '=', capability_code), ('state', '=', RuntimeEvents.STATE_ENABLED)], limit=1)
        if existing:
            self.disable_plugin(existing)
            
        installer = self.env['nexora.plugin_installer_service']
        new_plugin = installer.install_descriptor(new_descriptor)
        self.enable_plugin(new_plugin)
        return new_plugin

    @api.model
    def downgrade_plugin(self, capability_code, target_version):
        registry = self.env['nexora.capability_registry']
        existing = registry.search([('capability_code', '=', capability_code), ('state', '=', RuntimeEvents.STATE_ENABLED)], limit=1)
        if existing:
            self.disable_plugin(existing)
            
        target_plugin = registry.search([('capability_code', '=', capability_code), ('version', '=', target_version)], limit=1)
        if not target_plugin:
            raise ValueError(f"Target version {target_version} of {capability_code} is not installed. Install it first.")
            
        self.enable_plugin(target_plugin)
        return target_plugin

    @api.model
    def reload_plugin(self, plugin):
        self.disable_plugin(plugin)
        self.enable_plugin(plugin)
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': RuntimeEvents.PLUGIN_RELOADED,
            'message': f"Reloaded plugin {plugin.capability_code} v{plugin.version}"
        })
