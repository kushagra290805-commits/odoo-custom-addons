"""
Base service providing standardized API response envelopes and shared session
validation logic for all Nexora authentication services.
"""
import logging

from odoo import exceptions

from .error_codes import (
    AUTH_ACCOUNT_LOCKED,
    AUTH_SESSION_FORCED_LOGOUT,
    AUTH_UNAUTHORIZED,
)

_logger = logging.getLogger(__name__)


class BaseService:
    """
    Shared utilities for all Nexora backend services.

    All public methods are classmethods or staticmethods so services can be
    used without instantiation (matching the existing calling convention).
    """

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def success_response(data=None, message="Success"):
        """Return a standardized success envelope."""
        response = {"status": "success", "message": message}
        if data is not None:
            response["data"] = data
        return response

    @staticmethod
    def error_response(message, http_code=400, error_code=None):
        """
        Return a standardized error envelope.

        :param message:    Generic, user-safe error description.
        :param http_code:  Numeric HTTP status code (used as a hint for callers).
        :param error_code: Machine-readable code from error_codes.py.
                           React should branch on this value, not on message text.
        """
        response = {
            "status": "error",
            "message": message,
            "code": http_code,
        }
        if error_code:
            response["error_code"] = error_code
        return response

    # ------------------------------------------------------------------
    # Session / security guard
    # ------------------------------------------------------------------

    @staticmethod
    def validate_session(request):
        """
        Validate that the current request carries a live, non-locked,
        non-force-logged-out Nexora session.

        Returns an error_response dict when the session is invalid so the
        controller can return it immediately, or None when everything is fine.
        """
        try:
            user = request.env.user
        except Exception:  # noqa: BLE001  – Odoo env may raise on public users
            return BaseService.error_response(
                "Unauthorized",
                http_code=401,
                error_code=AUTH_UNAUTHORIZED,
            )

        if not user or user._is_public():
            return BaseService.error_response(
                "Unauthorized",
                http_code=401,
                error_code=AUTH_UNAUTHORIZED,
            )

        if user.account_locked:
            # Evict the session so the cookie becomes useless immediately.
            try:
                request.session.logout(keep_db=True)
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "Could not evict session for locked user %s", user.id
                )
            return BaseService.error_response(
                "Account is locked",
                http_code=403,
                error_code=AUTH_ACCOUNT_LOCKED,
            )

        # Check for admin-initiated force-logout via nexora.auth.session metadata.
        try:
            session_tracker = (
                request.env["nexora.auth.session"]
                .sudo()
                .search(
                    [("session_id", "=", request.session.sid)],
                    limit=1,
                )
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Failed to query nexora.auth.session during validate_session"
            )
            session_tracker = None

        if session_tracker and session_tracker.status == "forced_logout":
            try:
                request.session.logout(keep_db=True)
            except Exception:  # noqa: BLE001
                pass
            return BaseService.error_response(
                "Session has been forcibly terminated",
                http_code=401,
                error_code=AUTH_SESSION_FORCED_LOGOUT,
            )

        return None  # Valid — caller continues normally
