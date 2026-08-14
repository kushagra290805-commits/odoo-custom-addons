# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

class AIAPI(http.Controller):

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

    @http.route('/api/v1/ai/providers', type='http', auth='user', methods=['GET'], csrf=False)
    def list_providers(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            adapters = request.env['nexora.ai_provider_manager']._get_adapters()
            data = []
            for name, adapter in adapters.items():
                data.append({
                    'name': name,
                    'available': adapter.is_available() if hasattr(adapter, 'is_available') else False
                })
            return self._success_response(data)
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/ai/generate', type='http', auth='user', methods=['POST'], csrf=False)
    def trigger_generation(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            session_id = payload.get('builder_session_id')
            if not session_id:
                return self._error_response(400, "Missing builder_session_id")
                
            context = {}
            if payload.get('use_test_provider'):
                context['NEXORA_TEST_PROVIDER'] = 'test'
                
            res = request.env['nexora.project_planner_service'].with_context(**context).start_planning(int(session_id), {})
            if res.get('status') == 'error':
                return self._error_response(500, res.get('error'))
            return self._success_response({'message': 'Generation triggered successfully', 'job_uuid': res.get('job_uuid')})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/ai/patch', type='http', auth='user', methods=['POST'], csrf=False)
    def generate_patch(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            instruction = payload.get('instruction')
            file_path = payload.get('file_path')
            
            if not instruction or not file_path:
                return self._error_response(400, "Missing instruction or file_path")
                
            # Assume nexora.patch_engine is the service
            patch = request.env['nexora.patch_engine'].generate_patch(instruction, file_path)
            return self._success_response({'patch': patch})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/ai/estimate-cost', type='http', auth='user', methods=['POST'], csrf=False)
    def estimate_cost(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            task_type = payload.get('task_type', 'simple_task')
            
            cr = request.env['nexora.ai_cost_router']
            adapters = request.env['nexora.ai_provider_manager']._get_adapters()
            selected_adapter = cr.select_provider(task_type, adapters)
            
            return self._success_response({
                'task_type': task_type,
                'recommended_provider': selected_adapter.get_provider_name()
            })
        except Exception as e:
            return self._error_response(500, str(e))
