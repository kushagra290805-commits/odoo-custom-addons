from odoo import http
from odoo.http import request
from ..services.base_service import BaseService
from ..services.auth_service import AuthService

class NexoraAuthController(http.Controller):

    @http.route('/api/v1/auth/login', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def login(self, **kwargs):
        data = kwargs
        login = data.get('username')
        password = data.get('password')
        return AuthService.login(request, login, password)

    @http.route('/api/v1/auth/logout', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def logout(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        return AuthService.logout(request)

    @http.route('/api/v1/auth/session', type='json', auth='user', methods=['GET', 'POST'], csrf=False, cors='*')
    def check_session(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        return AuthService.get_session(request)

    @http.route('/api/v1/auth/change-password', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def change_password(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        data = kwargs
        return AuthService.change_password(request, data.get('old_password'), data.get('new_password'))

    @http.route('/api/v1/auth/reset-password', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def reset_password(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        data = kwargs
        return AuthService.reset_password(request, data.get('user_id'), data.get('new_password'))

