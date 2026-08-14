# -*- coding: utf-8 -*-
from odoo import models, api
from .cache_backends import CacheBackendFactory
from ..models.runtime_event_constants import RuntimeEvents
import logging

_logger = logging.getLogger(__name__)

class CapabilityCacheService(models.AbstractModel):
    _name = 'nexora.capability_cache_service'
    _description = 'Enterprise Capability Cache Service V2'

    @property
    def _cache(self):
        return CacheBackendFactory.get_backend()

    @api.model
    def rebuild_cache(self):
        _logger.info("Rebuilding Enterprise Capability Cache V2...")
        registry = self.env['nexora.capability_registry'].search([('enabled', '=', True)])
        
        # Validate dependency graph
        graph_svc = self.env['nexora.dependency_graph_service']
        try:
            graph_svc.validate_graph(registry)
        except ValueError as e:
            self.env['nexora.runtime_event'].create({
                'runtime_type': 'system',
                'event_type': RuntimeEvents.VALIDATION_FAILED,
                'message': f"Cache rebuild failed dependency check: {e}"
            })
            raise
            
        sorted_caps = graph_svc.startup_order(registry)
        
        enabled_caps = {}
        for cap in sorted_caps:
            enabled_caps[cap.capability_code] = cap.id
            
        self._cache.set('enabled_capabilities', enabled_caps)
        self._cache.set('sorted_codes', [c.capability_code for c in sorted_caps])
        
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': RuntimeEvents.CACHE_REBUILT,
            'message': f"Capability cache rebuilt with {len(enabled_caps)} enabled capabilities."
        })

    @api.model
    def get_enabled_capability(self, code):
        enabled_caps = self._cache.get('enabled_capabilities')
        if not enabled_caps:
            self.rebuild_cache()
            enabled_caps = self._cache.get('enabled_capabilities')
            
        cap_id = enabled_caps.get(code)
        if cap_id:
            return self.env['nexora.capability_registry'].browse(cap_id)
        return None

    @api.model
    def get_sorted_capabilities(self):
        sorted_codes = self._cache.get('sorted_codes')
        if not sorted_codes:
            self.rebuild_cache()
            sorted_codes = self._cache.get('sorted_codes')
            
        enabled_caps = self._cache.get('enabled_capabilities')
        return [self.env['nexora.capability_registry'].browse(enabled_caps[code]) for code in sorted_codes]

    @api.model
    def invalidate_cache(self):
        self._cache.clear()
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': RuntimeEvents.CACHE_INVALIDATED,
            'message': "Capability cache invalidated."
        })
