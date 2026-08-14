# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

class WorkspaceAPI(http.Controller):

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

    @http.route('/api/v1/workspaces/<string:uuid>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_workspace_metadata(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        workspace = request.env['nexora.workspace'].search([('workspace_uuid', '=', uuid)], limit=1)
        if not workspace:
            return self._error_response(404, "Workspace not found")
            
        data = {
            'uuid': workspace.workspace_uuid,
            'name': workspace.name,
            'path': workspace.workspace_path,
            'status': workspace.status,
            'health': workspace.health
        }
        return self._success_response(data)

    @http.route('/api/v1/workspaces/<string:uuid>/tree', type='http', auth='user', methods=['GET'], csrf=False)
    def get_workspace_tree(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        workspace = request.env['nexora.workspace'].search([('workspace_uuid', '=', uuid)], limit=1)
        if not workspace:
            return self._error_response(404, "Workspace not found")
            
        try:
            tree = request.env['nexora.workspace_service'].get_file_tree(workspace)
            return self._success_response({'tree': tree})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/workspaces/<string:uuid>/status', type='http', auth='user', methods=['GET'], csrf=False)
    def get_workspace_status(self, uuid, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        workspace = request.env['nexora.workspace'].search([('workspace_uuid', '=', uuid)], limit=1)
        if not workspace:
            return self._error_response(404, "Workspace not found")
            
        try:
            status = request.env['nexora.workspace_service'].check_health(workspace)
            return self._success_response({
                'uuid': workspace.workspace_uuid,
                'status': workspace.status,
                'health': workspace.health,
                'details': status
            })
        except Exception as e:
            return self._error_response(500, str(e))
