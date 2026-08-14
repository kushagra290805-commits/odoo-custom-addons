# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

class ProjectAPI(http.Controller):

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

    @http.route('/api/v1/projects', type='http', auth='user', methods=['GET'], csrf=False)
    def list_projects(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        projects = request.env['nexora.project'].search([])
        data = [{
            'id': p.id,
            'name': p.name,
            'status': p.status,
            'client': p.partner_id.name if p.partner_id else None
        } for p in projects]
        return self._success_response(data)

    @http.route('/api/v1/projects', type='http', auth='user', methods=['POST'], csrf=False)
    def create_project(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            name = payload.get('name')
            if not name:
                return self._error_response(400, "Missing project name")
                
            project = request.env['nexora.project'].create({
                'name': name,
                'status': 'draft'
            })
            return self._success_response({'id': project.id}, status=201)
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/projects/<int:id>', type='http', auth='user', methods=['PUT'], csrf=False)
    def update_project(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        project = request.env['nexora.project'].browse(id)
        if not project.exists():
            return self._error_response(404, "Project not found")
            
        try:
            payload = json.loads(request.httprequest.data)
            project.write(payload)
            return self._success_response({'message': 'Project updated'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/projects/<int:id>', type='http', auth='user', methods=['DELETE'], csrf=False)
    def delete_project(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        project = request.env['nexora.project'].browse(id)
        if not project.exists():
            return self._error_response(404, "Project not found")
            
        try:
            project.unlink()
            return self._success_response({'message': 'Project deleted'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/projects/<int:id>/configuration', type='http', auth='user', methods=['GET'], csrf=False)
    def get_project_config(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        project = request.env['nexora.project'].browse(id)
        if not project.exists():
            return self._error_response(404, "Project not found")
            
        # Returning requests and requirements as the configuration context for the project
        requests = request.env['nexora.project_request'].search([('project_id', '=', id)])
        req_data = [{
            'id': r.id,
            'name': r.name,
            'type': r.request_type,
            'status': r.status,
            'requirements': {
                'business_name': r.requirements_id.business_name,
                'industry': r.requirements_id.industry,
                'branding': r.requirements_id.branding_details
            } if r.requirements_id else None
        } for r in requests]
        
        return self._success_response({'requests': req_data})

    @http.route('/api/v1/projects/<int:id>/history', type='http', auth='user', methods=['GET'], csrf=False)
    def get_project_history(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        project = request.env['nexora.project'].browse(id)
        if not project.exists():
            return self._error_response(404, "Project not found")
            
        # Placeholder for AI generation history related to this project's requests
        return self._success_response({'history': []})
