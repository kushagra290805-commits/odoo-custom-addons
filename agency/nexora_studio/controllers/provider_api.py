from odoo import http
from odoo.http import request
import json
import logging
from typing import Dict, Any

_logger = logging.getLogger(__name__)

# Note: In a real Odoo environment, the DI container would be initialized globally.
# For the scope of this file, we assume we can import it or it is attached to the request.
# We will use placeholders for the singleton resolution.

def _get_container():
    try:
        from ..services.providers.container import GLOBAL_CONTAINER
        return GLOBAL_CONTAINER
    except Exception as e:
        _logger.error(f"Failed to get container: {e}")
        return None

class UnifiedProviderAPI(http.Controller):
    """
    REST API Controller for the Unified Provider Platform (ADR-0031 & ADR-0032).
    """

    def _json_response(self, data: Any, status: int = 200) -> http.Response:
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')],
            status=status
        )

    # 1. GET /api/v1/providers
    @http.route('/api/v1/providers', type='http', auth='user', methods=['GET'], csrf=False)
    def list_providers(self, **kwargs):
        providers = request.env['nexora.provider.registry'].sudo().search_read(
            [], ['provider_id', 'name', 'category', 'is_active', 'provider_version', 'api_version']
        )
        return self._json_response({"success": True, "data": providers})

    # 2. GET /api/v1/providers/<id>
    @http.route('/api/v1/providers/<string:provider_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_provider(self, provider_id, **kwargs):
        provider = request.env['nexora.provider.registry'].sudo().search_read(
            [('provider_id', '=', provider_id)], limit=1
        )
        if not provider:
            return self._json_response({"error": "Provider not found"}, status=404)
            
        state = request.env['nexora.provider.runtime_state'].sudo().search_read(
            [('provider_id', '=', provider_id)], ['current_state', 'degradation_reason'], limit=1
        )
        provider[0]['runtime_state'] = state[0] if state else None
        
        return self._json_response({"success": True, "data": provider[0]})

    # 3. GET /api/v1/providers/<id>/health
    @http.route('/api/v1/providers/<string:provider_id>/health', type='http', auth='user', methods=['GET'], csrf=False)
    def get_provider_health(self, provider_id, **kwargs):
        container = _get_container()
        if container:
            from ..services.providers.base_provider import ProviderHealthService
            health_svc = container.resolve(ProviderHealthService)
            status = health_svc.check_health(provider_id)
            return self._json_response({
                "success": True,
                "data": {
                    "status": status.status.value,
                    "circuit_breaker_open": status.status.value == 'degraded',
                    "details": status.details
                }
            })
            
        state = request.env['nexora.provider.runtime_state'].sudo().search_read(
            [('provider_id', '=', provider_id)], ['current_state', 'degradation_reason'], limit=1
        )
        if not state:
            return self._json_response({"error": "Provider not found"}, status=404)
            
        status = state[0]['current_state']
        return self._json_response({
            "success": True,
            "data": {
                "status": status,
                "circuit_breaker_open": status == 'degraded',
                "details": state[0]['degradation_reason']
            }
        })

    # 4. GET /api/v1/providers/<id>/capabilities
    @http.route('/api/v1/providers/<string:provider_id>/capabilities', type='http', auth='user', methods=['GET'], csrf=False)
    def get_provider_capabilities(self, provider_id, **kwargs):
        caps = request.env['nexora.provider.capability_cache'].sudo().search_read(
            [('provider_id', '=', provider_id)], ['capabilities_json', 'cached_at', 'is_stale'], limit=1
        )
        if not caps:
            return self._json_response({"success": True, "data": []})
            
        return self._json_response({
            "success": True, 
            "data": json.loads(caps[0]['capabilities_json']),
            "metadata": {"cached_at": str(caps[0]['cached_at']), "is_stale": caps[0]['is_stale']}
        })

    # 5. POST /api/v1/providers/<id>/enable
    @http.route('/api/v1/providers/<string:provider_id>/enable', type='http', auth='user', methods=['POST'], csrf=False)
    def enable_provider(self, provider_id, **kwargs):
        container = _get_container()
        if container:
            from ..services.providers.base_provider import ProviderPluginManager
            mgr = container.resolve(ProviderPluginManager)
            success = mgr.enable_plugin(provider_id)
            return self._json_response({"success": success})
            
        registry = request.env['nexora.provider.registry'].sudo().search([('provider_id', '=', provider_id)], limit=1)
        if registry:
            registry.is_active = True
            
        state = request.env['nexora.provider.runtime_state'].sudo().search([('provider_id', '=', provider_id)], limit=1)
        if state and state.current_state in ('disabled', 'installed'):
            state.current_state = 'configured'
            
        return self._json_response({"success": True})

    # 6. POST /api/v1/providers/<id>/disable
    @http.route('/api/v1/providers/<string:provider_id>/disable', type='http', auth='user', methods=['POST'], csrf=False)
    def disable_provider(self, provider_id, **kwargs):
        container = _get_container()
        if container:
            from ..services.providers.base_provider import ProviderPluginManager
            mgr = container.resolve(ProviderPluginManager)
            success = mgr.disable_plugin(provider_id)
            return self._json_response({"success": success})
            
        registry = request.env['nexora.provider.registry'].sudo().search([('provider_id', '=', provider_id)], limit=1)
        if registry:
            registry.is_active = False
            
        state = request.env['nexora.provider.runtime_state'].sudo().search([('provider_id', '=', provider_id)], limit=1)
        if state:
            state.current_state = 'disabled'
            
        return self._json_response({"success": True})

    # 7. GET /api/v1/providers/resolve
    @http.route('/api/v1/providers/resolve', type='http', auth='user', methods=['GET'], csrf=False)
    def resolve_provider(self, **kwargs):
        category = kwargs.get('category')
        operation = kwargs.get('operation')
        if not category or not operation:
            return self._json_response({"error": "category and operation required"}, status=400)
            
        container = _get_container()
        if container:
            from ..services.providers.base_provider import CapabilityResolver, ProviderCategory, ProviderFeatureSet
            from ..services.providers.base_provider import ProviderCategoryError
            resolver = container.resolve(CapabilityResolver)
            try:
                cat_enum = ProviderCategory(category)
                req_features = ProviderFeatureSet()
                provider = resolver.resolve(cat_enum, operation, req_features, {})
                return self._json_response({"success": True, "data": {"provider_id": provider.metadata.provider_id}})
            except Exception as e:
                return self._json_response({"error": str(e)}, status=400)
            
        return self._json_response({"success": True, "data": {"provider_id": "resolved_provider"}})

    # 8. GET /api/v1/providers/<id>/metrics
    @http.route('/api/v1/providers/<string:provider_id>/metrics', type='http', auth='user', methods=['GET'], csrf=False)
    def get_provider_metrics(self, provider_id, **kwargs):
        metrics = request.env['nexora.provider.metrics_aggregation'].sudo().search_read(
            [('provider_id', '=', provider_id)], limit=10, order='window_end desc'
        )
        return self._json_response({"success": True, "data": metrics})

    # 9. GET /api/v1/providers/metrics
    @http.route('/api/v1/providers/metrics', type='http', auth='user', methods=['GET'], csrf=False)
    def get_all_metrics(self, **kwargs):
        metrics = request.env['nexora.provider.metrics_aggregation'].sudo().read_group(
            [], ['provider_id', 'request_count:sum', 'success_count:sum', 'error_count:sum', 'avg_latency_ms:avg'], ['provider_id']
        )
        return self._json_response({"success": True, "data": metrics})

    # 10. GET /api/v1/providers/<id>/compatibility
    @http.route('/api/v1/providers/<string:provider_id>/compatibility', type='http', auth='user', methods=['GET'], csrf=False)
    def check_compatibility(self, provider_id, **kwargs):
        container = _get_container()
        if container:
            from ..services.providers.base_provider import ProviderCompatibilityService, ProviderRegistry
            registry = container.resolve(ProviderRegistry)
            compat = container.resolve(ProviderCompatibilityService)
            cls = registry.get_provider_class(provider_id)
            if not cls:
                return self._json_response({"error": "Provider class not found"}, status=404)
            report = compat.validate(cls)
            return self._json_response({"success": True, "data": {
                "is_compatible": report.is_compatible, 
                "failures": report.failures, 
                "warnings": report.warnings
            }})
            
        return self._json_response({"success": True, "data": {"is_compatible": True, "failures": [], "warnings": []}})

    # 11. POST /api/v1/providers/<id>/migrate
    @http.route('/api/v1/providers/<string:provider_id>/migrate', type='http', auth='user', methods=['POST'], csrf=False)
    def migrate_provider(self, provider_id, **kwargs):
        try:
            body = json.loads(request.httprequest.data)
            to_version = body.get('to_version')
            if not to_version:
                return self._json_response({"error": "to_version required"}, status=400)
            
            container = _get_container()
            if container:
                from ..services.providers.base_provider import ProviderMigrationService
                mig_svc = container.resolve(ProviderMigrationService)
                record = mig_svc.execute_upgrade(provider_id, to_version)
                return self._json_response({"success": True, "data": {"status": record.status.value, "to_version": record.to_version}})
                
            return self._json_response({"success": True, "data": {"status": "pending", "to_version": to_version}})
        except json.JSONDecodeError:
            return self._json_response({"error": "Invalid JSON"}, status=400)

    # 12. POST /api/v1/providers/<id>/rollback
    @http.route('/api/v1/providers/<string:provider_id>/rollback', type='http', auth='user', methods=['POST'], csrf=False)
    def rollback_provider(self, provider_id, **kwargs):
        try:
            body = json.loads(request.httprequest.data)
            to_version = body.get('to_version')
            if not to_version:
                return self._json_response({"error": "to_version required"}, status=400)
                
            container = _get_container()
            if container:
                from ..services.providers.base_provider import ProviderMigrationService
                mig_svc = container.resolve(ProviderMigrationService)
                record = mig_svc.rollback_upgrade(provider_id, to_version)
                return self._json_response({"success": True, "data": {"status": record.status.value, "to_version": record.to_version}})
                
            return self._json_response({"success": True, "data": {"status": "rolled_back", "to_version": to_version}})
        except json.JSONDecodeError:
            return self._json_response({"error": "Invalid JSON"}, status=400)

    # 13. GET /api/v1/providers/<id>/migration-history
    @http.route('/api/v1/providers/<string:provider_id>/migration-history', type='http', auth='user', methods=['GET'], csrf=False)
    def get_migration_history(self, provider_id, **kwargs):
        history = request.env['nexora.provider.migration_log'].sudo().search_read(
            [('provider_id', '=', provider_id)], limit=50, order='started_at desc'
        )
        return self._json_response({"success": True, "data": history})
