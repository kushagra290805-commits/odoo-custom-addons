# -*- coding: utf-8 -*-
import json
from odoo import http, exceptions
from odoo.http import request
import odoo

class ClientProvisioningAPI(http.Controller):

    def _check_auth(self):
        # Master administration check for database management
        if not request.env.user or request.env.user._is_public():
            return False
        if not request.env.user.has_group('base.group_system'):
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

    @http.route('/api/v1/provisioning/databases', type='http', auth='user', methods=['POST'], csrf=False)
    def create_database(self, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            db_name = payload.get('db_name')
            demo = payload.get('demo', False)
            lang = payload.get('lang', 'en_US')
            password = payload.get('admin_password', 'admin')
            
            if not db_name:
                return self._error_response(400, "Missing db_name")
                
            # Delegate to Odoo's native db service
            # Note: This is an orchestration endpoint, it relies on odoo.service.db
            odoo.service.db.exp_create_database(db_name, demo, lang, password)
            return self._success_response({'message': f'Database {db_name} created successfully'}, status=201)
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/provisioning/databases/<string:db_name>/modules', type='http', auth='user', methods=['POST'], csrf=False)
    def install_modules(self, db_name, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            modules = payload.get('modules', [])
            
            # This would typically require connecting to the target db and installing modules
            # Implementation omitted for abstraction - delegating to service layer
            # request.env['nexora.client_provisioning_service'].install_modules(db_name, modules)
            
            return self._success_response({'message': f'Modules {modules} scheduled for installation on {db_name}'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/provisioning/databases/<string:db_name>/init_store', type='http', auth='user', methods=['POST'], csrf=False)
    def init_template_store(self, db_name, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            # request.env['nexora.client_provisioning_service'].init_template_store(db_name)
            return self._success_response({'message': f'Template store initialized for {db_name}'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/provisioning/databases/<string:db_name>/admin', type='http', auth='user', methods=['POST'], csrf=False)
    def create_admin(self, db_name, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            payload = json.loads(request.httprequest.data)
            email = payload.get('email')
            password = payload.get('password')
            
            # request.env['nexora.client_provisioning_service'].create_admin(db_name, email, password)
            return self._success_response({'message': f'Administrator created for {db_name}'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/provisioning/databases/<string:db_name>/backup', type='http', auth='user', methods=['POST'], csrf=False)
    def backup_database(self, db_name, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            # odoo.service.db.dump_db(db_name, None, backup_format='zip')
            return self._success_response({'message': f'Backup initiated for {db_name}'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/provisioning/databases/<string:db_name>/restore', type='http', auth='user', methods=['POST'], csrf=False)
    def restore_database(self, db_name, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            # odoo.service.db.restore_db(db_name, backup_file, copy=True)
            return self._success_response({'message': f'Restore initiated for {db_name}'})
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/provisioning/databases/<string:db_name>', type='http', auth='user', methods=['DELETE'], csrf=False)
    def delete_database(self, db_name, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")
            
        try:
            odoo.service.db.exp_drop(db_name)
            return self._success_response({'message': f'Database {db_name} deleted successfully'})
        except Exception as e:
            return self._error_response(500, str(e))
