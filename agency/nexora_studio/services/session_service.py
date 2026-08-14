"""
SessionService — manages nexora.auth.session records.

The native Odoo session store is NOT replaced; this service provides a
metadata layer enabling admin visibility and force-logout capability.
See known_limitations.md for notes on session cookie invalidation.
"""
import logging

from odoo import exceptions, fields

from .base_service import BaseService
from .error_codes import AUTHZ_FORBIDDEN, SESSION_NOT_FOUND

_logger = logging.getLogger(__name__)


def _can_view_sessions(user) -> bool:
    return user.has_group("nexora_studio.group_nexora_super_admin") or user.has_group(
        "nexora_studio.group_nexora_admin"
    )


def _session_to_dict(s) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id.id,
        "username": s.user_id.login,
        "ip_address": s.ip_address,
        "browser": s.browser,
        "status": s.status,
        "create_date": s.create_date.isoformat() if s.create_date else None,
        "logout_time": s.logout_time.isoformat() if s.logout_time else None,
    }


class SessionService(BaseService):

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    @classmethod
    def get_sessions(cls, request):
        if not _can_view_sessions(request.env.user):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)
        try:
            sessions = (
                request.env["nexora.auth.session"]
                .sudo()
                .search([], order="create_date desc", limit=100)
            )
            return cls.success_response([_session_to_dict(s) for s in sessions])
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to list nexora.auth.session records")
            return cls.error_response("An unexpected error occurred.", http_code=500)

    # ------------------------------------------------------------------
    # Get one
    # ------------------------------------------------------------------

    @classmethod
    def get_session(cls, request, session_id: int):
        if not _can_view_sessions(request.env.user):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)
        try:
            s = request.env["nexora.auth.session"].sudo().browse(session_id)
            if not s.exists():
                return cls.error_response("Session not found.", http_code=404, error_code=SESSION_NOT_FOUND)
            return cls.success_response(_session_to_dict(s))
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to fetch session %s", session_id)
            return cls.error_response("An unexpected error occurred.", http_code=500)

    # ------------------------------------------------------------------
    # Force logout
    # ------------------------------------------------------------------

    @classmethod
    def force_logout(cls, request, session_id: int):
        """
        Mark a nexora.auth.session as forced_logout.

        The BaseService.validate_session() check will then reject any future
        API request that references this session cookie.
        See known_limitations.md for details on cookie-level invalidation.
        """
        # Only super_admin may force-logout (sessions.manage permission).
        if not request.env.user.has_group("nexora_studio.group_nexora_super_admin"):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)

        try:
            sess = request.env["nexora.auth.session"].sudo().browse(session_id)
            if not sess.exists():
                return cls.error_response(
                    "Session not found.", http_code=404, error_code=SESSION_NOT_FOUND
                )
            sess.write({"status": "forced_logout", "logout_time": fields.Datetime.now()})
        except exceptions.AccessError:
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)
        except Exception:  # noqa: BLE001
            _logger.exception("Unexpected error during force_logout for session %s", session_id)
            return cls.error_response("An unexpected error occurred.", http_code=500)

        try:
            request.env["nexora.audit.log"].sudo().create({
                "user_id": sess.user_id.id,
                "action": "force_logout",
                "ip_address": request.httprequest.remote_addr,
                "session_id": sess.session_id,
                "result": "success",
            })
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to create audit log for force_logout session %s", session_id)

        return cls.success_response()
