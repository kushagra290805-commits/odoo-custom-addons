from odoo import http
from odoo.http import request
from ..services.base_service import BaseService
from ..services.audit_service import AuditService

class NexoraAuditController(http.Controller):
    @http.route('/api/v1/audit', type='json', auth='user', methods=['GET', 'POST'], csrf=False, cors='*')
    def get_logs(self, **kwargs):
        valid = BaseService.validate_session(request)
        if valid: return valid
        data = request.jsonrequest or {}
        limit = data.get('limit', 50)
        offset = data.get('offset', 0)
        return AuditService.get_logs(request, limit=limit, offset=offset)
