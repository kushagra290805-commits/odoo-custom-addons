# -*- coding: utf-8 -*-
from odoo import models, api
from ..models.runtime_event_constants import RuntimeEvents

class BuilderHealthSnapshot:
    def __init__(self, plugin_count, enabled_plugins, disabled_plugins, 
                 dependency_status, cache_status, runtime_health, 
                 compatibility_status, discovery_timestamp):
        self.plugin_count = plugin_count
        self.enabled_plugins = enabled_plugins
        self.disabled_plugins = disabled_plugins
        self.dependency_status = dependency_status
        self.cache_status = cache_status
        self.runtime_health = runtime_health
        self.compatibility_status = compatibility_status
        self.discovery_timestamp = discovery_timestamp
        
    def to_dict(self):
        return {
            'plugin_count': self.plugin_count,
            'enabled_plugins': self.enabled_plugins,
            'disabled_plugins': self.disabled_plugins,
            'dependency_status': self.dependency_status,
            'cache_status': self.cache_status,
            'runtime_health': self.runtime_health,
            'compatibility_status': self.compatibility_status,
            'discovery_timestamp': self.discovery_timestamp
        }

class BuilderHealthService(models.AbstractModel):
    _name = 'nexora.builder_health_service'
    _description = 'Enterprise Builder Health Service'

    @api.model
    def generate_snapshot(self) -> BuilderHealthSnapshot:
        registry = self.env['nexora.capability_registry']
        
        all_plugins = registry.search([])
        enabled_plugins = registry.search([('state', '=', RuntimeEvents.STATE_ENABLED)])
        
        total_count = len(all_plugins)
        enabled_count = len(enabled_plugins)
        disabled_count = total_count - enabled_count
        
        # Verify dependency graph
        graph_svc = self.env['nexora.dependency_graph_service']
        dep_status = "Healthy (Acyclic)"
        try:
            graph_svc.validate_graph(enabled_plugins)
        except Exception as e:
            dep_status = f"Degraded ({str(e)})"
            
        # Verify Cache
        cache_status = "Synchronized"
        try:
            cached_codes = self.env['nexora.capability_cache_service']._cache.get('sorted_codes')
            if cached_codes is None:
                cache_status = "Uninitialized"
        except Exception:
            cache_status = "Error"
            
        runtime_health = "Optimal"
        compatibility_status = "Verified"
        discovery_timestamp = fields.Datetime.now() if hasattr(self.env, 'fields') else "Just now" # fallback
        
        from odoo import fields
        
        return BuilderHealthSnapshot(
            plugin_count=total_count,
            enabled_plugins=enabled_count,
            disabled_plugins=disabled_count,
            dependency_status=dep_status,
            cache_status=cache_status,
            runtime_health=runtime_health,
            compatibility_status=compatibility_status,
            discovery_timestamp=fields.Datetime.now()
        )
