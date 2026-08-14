# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

class BuilderSessionAPI(http.Controller):

    def _check_auth(self):
        # We assume standard Odoo session auth is used by the frontend for now
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

    @http.route('/api/v1/sessions', type='http', auth='user', methods=['GET'], csrf=False)
    def list_sessions(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
        
        sessions = request.env['nexora.builder_session'].search([])
        data = [{
            'id': s.id,
            'uuid': s.session_uuid,
            'name': s.name,
            'status': s.status,
            'runtime_state': s.runtime_state,
            'workspace_path': s.target_workspace_path,
        } for s in sessions]
        return self._success_response(data)

    @http.route('/api/v1/sessions', type='http', auth='user', methods=['POST'], csrf=False)
    def create_session(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
        try:
            payload = json.loads(request.httprequest.data)
            config_id = payload.get('builder_configuration_id')
            name = payload.get('name')
            if not config_id or not name:
                return self._error_response(400, "Missing builder_configuration_id or name")
                
            config = request.env['nexora.builder_configuration'].browse(int(config_id))
            if not config.exists():
                return self._error_response(400, "Invalid builder_configuration_id")
            
            session = request.env['nexora.builder_session_service'].create_session({
                'name': name,
                'builder_configuration_id': int(config_id),
            })
            return self._success_response({'uuid': session.session_uuid, 'id': session.id}, status=201)
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/sessions/<string:uuid>/start', type='http', auth='user', methods=['POST'], csrf=False)
    def start_session(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
        
        session = request.env['nexora.builder_session'].search([('session_uuid', '=', uuid)], limit=1)
        if not session:
            return self._error_response(404, "Session not found")
        
        try:
            request.env['nexora.builder_session_service'].start_session(session)
            return self._success_response({'message': 'Session started'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/sessions/<string:uuid>/stop', type='http', auth='user', methods=['POST'], csrf=False)
    def stop_session(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        session = request.env['nexora.builder_session'].search([('session_uuid', '=', uuid)], limit=1)
        if not session:
            return self._error_response(404, "Session not found")
            
        try:
            request.env['nexora.builder_session_service'].stop_session(session)
            return self._success_response({'message': 'Session stopped'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/sessions/<string:uuid>/restart', type='http', auth='user', methods=['POST'], csrf=False)
    def restart_session(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        session = request.env['nexora.builder_session'].search([('session_uuid', '=', uuid)], limit=1)
        if not session:
            return self._error_response(404, "Session not found")
            
        try:
            request.env['nexora.builder_session_service'].restart_session(session)
            return self._success_response({'message': 'Session restarted'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/sessions/<string:uuid>/recover', type='http', auth='user', methods=['POST'], csrf=False)
    def recover_session(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        session = request.env['nexora.builder_session'].search([('session_uuid', '=', uuid)], limit=1)
        if not session:
            return self._error_response(404, "Session not found")
            
        try:
            request.env['nexora.builder_session_service'].recover_session(session)
            return self._success_response({'message': 'Session recovery initiated'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/sessions/<string:uuid>', type='http', auth='user', methods=['DELETE'], csrf=False)
    def destroy_session(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        session = request.env['nexora.builder_session'].search([('session_uuid', '=', uuid)], limit=1)
        if not session:
            return self._error_response(404, "Session not found")
            
        try:
            request.env['nexora.builder_session_service'].destroy_session(session)
            return self._success_response({'message': 'Session destroyed'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/sessions/<string:uuid>/status', type='http', auth='user', methods=['GET'], csrf=False)
    def get_status(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        session = request.env['nexora.builder_session'].search([('session_uuid', '=', uuid)], limit=1)
        if not session:
            return self._error_response(404, "Session not found")
            
        try:
            request.env['nexora.builder_session_service'].get_session_status(session)
            return self._success_response({
                'uuid': session.session_uuid,
                'runtime_state': session.runtime_state,
                'status': session.status,
                'progress_percent': session.progress_percent,
                'current_stage': session.current_stage
            })
        except Exception as e:
            return self._error_response(500, str(e))
