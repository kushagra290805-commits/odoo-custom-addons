from odoo import http
from odoo.http import request
from ..services.base_service import BaseService
from ..services.session_service import SessionService

class NexoraSessionController(http.Controller):
    @http.route('/api/v1/sessions', type='json', auth='user', methods=['GET', 'POST'], csrf=False, cors='*')
    def get_sessions(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        return SessionService.get_sessions(request)
        
    @http.route('/api/v1/sessions/<int:session_id>/force-logout', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def force_logout(self, session_id, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        return SessionService.force_logout(request, session_id)
