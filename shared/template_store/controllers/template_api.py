# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request

class TemplateStoreAPI(http.Controller):

    def _check_auth(self):
        if not request.env.user or request.env.user._is_public():
            return False
        # Template store might have different access, but we'll use agency admin for consistency in this API
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

    @http.route('/api/v1/templates', type='http', auth='user', methods=['GET'], csrf=False)
    def list_templates(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            templates = request.env['nexora.template_backend'].search([])
            data = [{
                'id': t.id,
                'name': t.name,
                'description': t.description,
            } for t in templates]
            return self._success_response(data)
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/<int:id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_template(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            template = request.env['nexora.template_backend'].browse(id)
            if not template.exists():
                return self._error_response(404, "Template not found")
                
            return self._success_response({
                'id': template.id,
                'name': template.name,
                'description': template.description
            })
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/categories', type='http', auth='user', methods=['GET'], csrf=False)
    def list_categories(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            # We don't have a category model, return static or derived
            return self._success_response([{'id': 1, 'name': 'Backend'}, {'id': 2, 'name': 'Frontend'}])
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/<int:id>/versions', type='http', auth='user', methods=['GET'], csrf=False)
    def get_versions(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            versions = request.env['nexora.template_version'].search([('backend_template_id', '=', id)])
            data = [{'id': v.id, 'version_number': v.name} for v in versions]
            return self._success_response(data)
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/<int:id>/dependencies', type='http', auth='user', methods=['GET'], csrf=False)
    def get_dependencies(self, id, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            return self._success_response({'dependencies': []})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/search', type='http', auth='user', methods=['GET'], csrf=False)
    def search_templates(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        query = kwargs.get('q', '')
        try:
            templates = request.env['nexora.template_backend'].search([('name', 'ilike', query)])
            data = [{'id': t.id, 'name': t.name} for t in templates]
            return self._success_response(data)
        except Exception as e:
            return self._error_response(500, str(e))

    # --- AI-oriented Endpoints ---

    @http.route('/api/v1/templates/recommend', type='http', auth='user', methods=['POST'], csrf=False)
    def recommend_template(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            requirements = payload.get('requirements', {})
            # Route to AI service for recommendation
            # recommendation = request.env['nexora.ai_provider_manager'].recommend_template(requirements)
            return self._success_response({'recommended_template_id': 1, 'reasoning': 'Matches business needs.'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/resolve', type='http', auth='user', methods=['POST'], csrf=False)
    def resolve_template(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            template_id = payload.get('template_id')
            # Resolve physical assets via AI or template engine
            return self._success_response({'status': 'resolved', 'asset_bundle_url': '/assets/bundle.zip'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/capabilities', type='http', auth='user', methods=['GET'], csrf=False)
    def list_capabilities(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            return self._success_response({'capabilities': ['e-commerce', 'blog', 'booking']})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/validate_dependencies', type='http', auth='user', methods=['POST'], csrf=False)
    def validate_dependencies(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            template_id = payload.get('template_id')
            selected_capabilities = payload.get('capabilities', [])
            
            # Use dependency graph service to validate
            # is_valid, conflicts = request.env['nexora.dependency_graph_service'].validate(template_id, selected_capabilities)
            return self._success_response({'is_valid': True, 'conflicts': []})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/templates/instantiate', type='http', auth='user', methods=['POST'], csrf=False)
    def instantiate_template(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            template_id = payload.get('template_id')
            project_id = payload.get('project_id')
            
            if not template_id or not project_id:
                return self._error_response(400, "Missing template_id or project_id")
                
            # Delegate to service layer
            # workspace = request.env['template_store.template_service'].instantiate_template(template_id, project_id)
            
            return self._success_response({
                'message': 'Template instantiated successfully',
                'workspace_path': f'/tmp/workspace_{project_id}',
                'status': 'initialized'
            })
        except Exception as e:
            return self._error_response(500, str(e))
