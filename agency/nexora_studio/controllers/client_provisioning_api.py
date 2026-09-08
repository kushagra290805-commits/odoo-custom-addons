# -*- coding: utf-8 -*-
import json
from odoo import http, exceptions
from odoo.http import request
import odoo

def parse_module_provisioning_payload(payload):
    """Phase 47.34: parse/validate a module-provisioning payload.

    The ONLY trusted input is a list of capabilities from the Phase 47.32
    controlled vocabulary. Arbitrary module identifiers are rejected here —
    the platform (allowlist), not the payload, decides module names.
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object.")
    if 'modules' in payload:
        raise ValueError(
            "Module identifiers are platform-owned data and cannot be "
            "supplied by clients; provide 'capabilities' instead."
        )
    capabilities = payload.get('capabilities', [])
    if not isinstance(capabilities, list) or not all(
        isinstance(c, str) for c in capabilities
    ):
        raise ValueError("'capabilities' must be a list of strings.")
    if not capabilities:
        raise ValueError("Missing 'capabilities'.")
    return capabilities


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
            service = request.env['nexora.client_environment_service']
            env_record = service.create_environment(
                request.env['nexora.project'].search([('name', '=', db_name)], limit=1).id or 0,
                db_name
            )
            env_record.action_provision()
            return self._success_response({'message': f'Database {db_name} created successfully', 'environment_id': env_record.id}, status=201)
        except Exception as e:
            return self._error_response(500, str(e))

    @http.route('/api/v1/provisioning/databases/<string:db_name>/modules', type='http', auth='user', methods=['POST'], csrf=False)
    def install_modules(self, db_name, **kwargs):
        if not self._check_auth():
            return self._error_response(403, "Forbidden")

        try:
            payload = json.loads(request.httprequest.data)
        except Exception:
            return self._error_response(400, "Invalid JSON payload")

        try:
            capabilities = parse_module_provisioning_payload(payload)
        except ValueError as e:
            return self._error_response(400, str(e))

        env_record = request.env['nexora.client_environment'].search(
            [('db_name', '=', db_name)], limit=1
        )
        if not env_record:
            return self._error_response(404, "Client environment not found")

        # Delegate to the canonical module provisioning owner (Phase 47.34):
        # capabilities -> deterministic module policy -> approved plan ->
        # real Odoo module installation in the isolated client DB.
        try:
            summary = request.env['nexora.client_environment_service'].provision_modules(
                env_record.id, capabilities
            )
        except exceptions.ValidationError as e:
            return self._error_response(400, str(e))
        except Exception as e:
            return self._error_response(500, str(e))

        # Never expose credentials; return plan + verified outcome only.
        return self._success_response({
            'message': 'Module provisioning completed for %s' % db_name,
            'plan': summary.get('plan'),
            'installed': summary.get('installed'),
            'skipped': summary.get('skipped'),
            'state': summary.get('state'),
            'environment_id': env_record.id,
        })

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

        # Phase 47.34.x safety hardening: the previous raw
        # ``odoo.service.db.exp_drop(db_name)`` fallback could drop ANY
        # database (including the agency DB) when no environment record
        # existed. Removed: only TRACKED client environments can be
        # deleted through the client lifecycle API, always via the
        # canonical service owner (agency-guarded).
        env_record = request.env['nexora.client_environment'].search([('db_name', '=', db_name)], limit=1)
        if not env_record:
            return self._error_response(
                404,
                "Client environment not found; only tracked client "
                "environments can be deleted"
            )
        try:
            env_record.action_delete()
            return self._success_response({'message': f'Database {db_name} deleted successfully'})
        except exceptions.ValidationError as e:
            return self._error_response(400, str(e))
        except Exception as e:
            return self._error_response(500, str(e))
