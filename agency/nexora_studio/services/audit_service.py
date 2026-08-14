"""
AuditService — provides read access to nexora.audit.log.

Only Admin and Super Admin may query audit logs.
"""
import logging

from .base_service import BaseService
from .error_codes import AUTHZ_FORBIDDEN

_logger = logging.getLogger(__name__)


def _can_read_audit(user) -> bool:
    return user.has_group("nexora_studio.group_nexora_super_admin") or user.has_group(
        "nexora_studio.group_nexora_admin"
    )


def _log_to_dict(log) -> dict:
    return {
        "id": log.id,
        "user_id": log.user_id.id if log.user_id else None,
        "username": log.user_id.login if log.user_id else None,
        "action": log.action,
        "ip_address": log.ip_address,
        "result": log.result,
        "session_id": log.session_id or None,
        "create_date": log.create_date.isoformat() if log.create_date else None,
    }


class AuditService(BaseService):

    @classmethod
    def get_logs(cls, request, limit: int = 50, offset: int = 0):
        if not _can_read_audit(request.env.user):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)

        # Clamp pagination to safe bounds.
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        try:
            logs = (
                request.env["nexora.audit.log"]
                .sudo()
                .search([], order="create_date desc", limit=limit, offset=offset)
            )
            total = request.env["nexora.audit.log"].sudo().search_count([])
            return cls.success_response({
                "logs": [_log_to_dict(log) for log in logs],
                "total": total,
                "limit": limit,
                "offset": offset,
            })
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to fetch audit logs")
            return cls.error_response("An unexpected error occurred.", http_code=500)
