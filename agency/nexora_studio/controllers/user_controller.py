from odoo import http
from odoo.http import request
from ..services.base_service import BaseService
from ..services.user_service import UserService

class NexoraUserController(http.Controller):

    @http.route('/api/v1/users/me', type='json', auth='user', methods=['GET', 'POST'], csrf=False, cors='*')
    def get_me(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        return UserService.get_user(request, request.env.uid)

    @http.route('/api/v1/users', type='json', auth='user', methods=['GET', 'POST'], csrf=False, cors='*')
    def manage_users(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        return UserService.get_users(request)
        
    @http.route('/api/v1/users/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_user(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        return UserService.create_user(request, request.jsonrequest)
        
    @http.route('/api/v1/users/<int:user_id>/unlock', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def unlock_user(self, user_id, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        return UserService.unlock_user(request, user_id)
