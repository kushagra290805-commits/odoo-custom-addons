# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

class RuntimeAPI(http.Controller):

    def _check_auth(self):
        if not request.env.user or request.env.user._is_public():
            return False
        if not request.env.user.has_group('agency.group_agency_admin') and not request.env.user.has_group('base.group_system'):
            return False
        return True

    def _error_response(self, status, message):
        return request.make_response(
            json.dumps({'error': message}),
            headers=[('Content-Type', 'application/json')],
            status=status
        )

    def _success_response(self, data, status=200):
        return request.make_response(
            json.dumps({'data': data}),
            headers=[('Content-Type', 'application/json')],
            status=status
        )

    @http.route('/api/v1/runtimes', type='http', auth='user', methods=['GET'], csrf=False)
    def list_runtimes(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        runtimes = request.env['nexora.runtime'].search([])
        data = [{
            'id': r.id,
            'name': r.name,
            'type': r.runtime_type,
            'status': r.status,
            'health': r.health,
            'process_id': r.process_id,
            'endpoint': r.endpoint
        } for r in runtimes]
        return self._success_response(data)

    @http.route('/api/v1/runtimes/<int:id>/status', type='http', auth='user', methods=['GET'], csrf=False)
    def get_runtime_status(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        runtime = request.env['nexora.runtime'].browse(id)
        if not runtime.exists():
            return self._error_response(404, "Runtime not found")
            
        try:
            status = request.env['nexora.runtime_service'].check_health(runtime)
            return self._success_response({
                'id': runtime.id,
                'status': runtime.status,
                'health': runtime.health,
                'details': status
            })
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/runtimes/<int:id>/logs', type='http', auth='user', methods=['GET'], csrf=False)
    def get_runtime_logs(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        runtime = request.env['nexora.runtime'].browse(id)
        if not runtime.exists():
            return self._error_response(404, "Runtime not found")
            
        try:
            # Assuming nexora.runtime_service has a get_logs method or similar
            logs = request.env['nexora.runtime_service'].get_logs(runtime)
            return self._success_response({'logs': logs})
        except AttributeError:
            # If get_logs isn't implemented yet, return empty
            return self._success_response({'logs': []})
        except Exception as e:
            return self._error_response(500, str(e))
