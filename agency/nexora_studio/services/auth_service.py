"""
AuthService — handles all authentication business logic.

Controllers are thin wrappers; all logic lives here.
This service never exposes internal exception details to callers.
"""
import logging
import secrets
import string

from odoo import exceptions, fields

from .base_service import BaseService
from .error_codes import (
    AUTH_ACCOUNT_LOCKED,
    AUTH_INVALID_CREDENTIALS,
    AUTH_PASSWORD_CHANGE_FAILED,
    AUTH_PASSWORD_RESET_FAILED,
    AUTHZ_FORBIDDEN,
    USER_NOT_FOUND,
)
from .permission_service import PermissionService

_logger = logging.getLogger(__name__)

# Alphabet for cryptographically secure temporary passwords.
_PWD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]"
_PWD_MIN_LENGTH = 16


def _generate_secure_password() -> str:
    """
    Generate a cryptographically secure temporary password meeting complexity
    requirements: ≥16 chars, upper, lower, digit, symbol.
    """
    while True:
        pwd = "".join(secrets.choice(_PWD_ALPHABET) for _ in range(_PWD_MIN_LENGTH))
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_digit = any(c.isdigit() for c in pwd)
        has_sym = any(c in string.punctuation for c in pwd)
        if has_upper and has_lower and has_digit and has_sym:
            return pwd


def _build_user_payload(user) -> dict:
    """Build the serializable user dict returned in auth responses."""
    return {
        "id": user.id,
        "username": user.login,
        "display_name": user.name,
        "role": PermissionService.get_primary_role(user),
    }


def _create_audit_log(env, user_id, action: str, result: str, request, session_id=None):
    """Write a nexora.audit.log record; failures are logged but not raised."""
    try:
        vals = {
            "user_id": user_id,
            "action": action,
            "ip_address": request.httprequest.remote_addr,
            "browser": request.httprequest.user_agent.string,
            "result": result,
        }
        if session_id:
            vals["session_id"] = session_id
        env["nexora.audit.log"].sudo().create(vals)
    except Exception:  # noqa: BLE001
        _logger.exception(
            "Failed to create audit log for action=%s user_id=%s", action, user_id
        )


class AuthService(BaseService):

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    @classmethod
    def login(cls, request, login: str, password: str):
        if not login or not password:
            return cls.error_response(
                "Username and password are required.",
                http_code=400,
                error_code=AUTH_INVALID_CREDENTIALS,
            )

        db = request.env.cr.dbname

        try:
            auth_info = request.session.authenticate(request.env, {'type': 'password', 'login': login, 'password': password})
            uid = auth_info['uid']
        except exceptions.AccessDenied:
            # Expected failure path — wrong credentials.
            cls._handle_failed_login(request, login)
            return cls.error_response(
                "Invalid credentials.",
                http_code=401,
                error_code=AUTH_INVALID_CREDENTIALS,
            )
        except Exception:  # noqa: BLE001 — unexpected DB / session error
            _logger.exception("Unexpected error during session.authenticate for login=%s", login)
            return cls.error_response(
                "An unexpected error occurred. Please try again.",
                http_code=500,
            )

        if not uid:
            cls._handle_failed_login(request, login)
            return cls.error_response(
                "Invalid credentials.",
                http_code=401,
                error_code=AUTH_INVALID_CREDENTIALS,
            )

        # Reload user in the now-authenticated environment.
        user = request.env["res.users"].browse(uid)

        if user.account_locked:
            request.session.logout(keep_db=True)
            return cls.error_response(
                "Account is locked. Contact an administrator.",
                http_code=403,
                error_code=AUTH_ACCOUNT_LOCKED,
            )

        # Reset failure counter and record last login.  Use sudo only for
        # writing Nexora extension fields — the user record itself is owned by
        # the user so this is safe.
        user.sudo().write({
            "nexora_last_login": fields.Datetime.now(),
            "failed_login_count": 0,
        })

        _create_audit_log(
            request.env, uid, "login", "success", request, session_id=request.session.sid
        )

        try:
            request.env["nexora.auth.session"].sudo().create({
                "user_id": uid,
                "session_id": request.session.sid,
                "ip_address": request.httprequest.remote_addr,
                "browser": request.httprequest.user_agent.string,
                "status": "active",
            })
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to create nexora.auth.session for user %s", uid)

        return cls.success_response({
            "authenticated": True,
            "user": _build_user_payload(user),
            "permissions": PermissionService.get_permissions(user),
            "must_change_password": user.must_change_password,
        })

    @classmethod
    def _handle_failed_login(cls, request, login: str):
        """Increment failure counter and lock account after threshold."""
        try:
            user = (
                request.env["res.users"]
                .sudo()
                .search([("login", "=", login)], limit=1)
            )
            if not user:
                return
            new_count = user.failed_login_count + 1
            vals = {"failed_login_count": new_count}
            if new_count >= 5:
                vals["account_locked"] = True
                _logger.warning(
                    "Nexora: account locked after 5 failed attempts — user %s (id=%s)",
                    login,
                    user.id,
                )
            user.write(vals)
            _create_audit_log(
                request.env, user.id, "failed_login", "failure", request
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Failed to process failed_login counter for login=%s", login
            )

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    @classmethod
    def logout(cls, request):
        session_id = request.session.sid
        uid = request.env.uid
        try:
            request.session.logout(keep_db=True)
        except Exception:  # noqa: BLE001
            _logger.exception("Error during session.logout for user %s", uid)

        _create_audit_log(
            request.env, uid, "logout", "success", request, session_id=session_id
        )

        try:
            tracker = (
                request.env["nexora.auth.session"]
                .sudo()
                .search([("session_id", "=", session_id)], limit=1)
            )
            if tracker:
                tracker.write({"status": "logged_out", "logout_time": fields.Datetime.now()})
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Failed to update nexora.auth.session on logout for session %s", session_id
            )

        return cls.success_response()

    # ------------------------------------------------------------------
    # Session check
    # ------------------------------------------------------------------

    @classmethod
    def get_session(cls, request):
        user = request.env.user
        return cls.success_response({
            "authenticated": True,
            "user": _build_user_payload(user),
            "permissions": PermissionService.get_permissions(user),
            "must_change_password": user.must_change_password,
        })

    # ------------------------------------------------------------------
    # Change password (own password)
    # ------------------------------------------------------------------

    @classmethod
    def change_password(cls, request, old_pwd: str, new_pwd: str):
        if not old_pwd or not new_pwd:
            return cls.error_response(
                "Both current and new passwords are required.",
                http_code=400,
                error_code=AUTH_PASSWORD_CHANGE_FAILED,
            )
        try:
            # Odoo's change_password validates the old password internally.
            request.env["res.users"].change_password(old_pwd, new_pwd)
        except exceptions.AccessDenied:
            return cls.error_response(
                "Current password is incorrect.",
                http_code=400,
                error_code=AUTH_PASSWORD_CHANGE_FAILED,
            )
        except exceptions.UserError as exc:
            _logger.info(
                "Password change rejected by Odoo policy for user %s: %s",
                request.env.uid,
                exc,
            )
            return cls.error_response(
                "Password does not meet requirements.",
                http_code=400,
                error_code=AUTH_PASSWORD_CHANGE_FAILED,
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Unexpected error during change_password for user %s", request.env.uid
            )
            return cls.error_response(
                "An unexpected error occurred. Please try again.",
                http_code=500,
            )

        try:
            request.env.user.sudo().write({"must_change_password": False})
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Failed to clear must_change_password for user %s", request.env.uid
            )

        _create_audit_log(
            request.env, request.env.uid, "password_change", "success", request
        )
        return cls.success_response()

    # ------------------------------------------------------------------
    # Password reset (admin action on behalf of another user)
    # ------------------------------------------------------------------

    @classmethod
    def reset_password(cls, request, user_id: int, new_password: str | None = None):
        """
        Reset a user's password.  Only super_admin and admin may call this.

        If *new_password* is not supplied, a cryptographically secure temporary
        password is generated and returned **once** in the response data.
        The administrator is responsible for delivering it securely to the user.
        """
        caller = request.env.user
        is_super_admin = caller.has_group("nexora_studio.group_nexora_super_admin")
        is_admin = caller.has_group("nexora_studio.group_nexora_admin")
        if not (is_super_admin or is_admin):
            return cls.error_response(
                "You do not have permission to reset passwords.",
                http_code=403,
                error_code=AUTHZ_FORBIDDEN,
            )

        if not user_id:
            return cls.error_response(
                "user_id is required.",
                http_code=400,
            )

        try:
            target_user = request.env["res.users"].sudo().browse(user_id)
            if not target_user.exists() or not target_user.is_nexora_user:
                return cls.error_response(
                    "User not found.",
                    http_code=404,
                    error_code=USER_NOT_FOUND,
                )
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to load target user %s for password reset", user_id)
            return cls.error_response("An unexpected error occurred.", http_code=500)

        generated = False
        if not new_password:
            new_password = _generate_secure_password()
            generated = True

        try:
            # Use Odoo's _change_password (low-level) which bypasses the current
            # user check — only callable with sudo(), which we have.
            target_user._change_password(new_password)
        except exceptions.UserError as exc:
            _logger.info(
                "Password reset rejected by Odoo policy for user %s: %s",
                user_id,
                exc,
            )
            return cls.error_response(
                "New password does not meet the password policy.",
                http_code=400,
                error_code=AUTH_PASSWORD_RESET_FAILED,
            )
        except Exception:  # noqa: BLE001
            _logger.exception("Unexpected error resetting password for user %s", user_id)
            return cls.error_response("An unexpected error occurred.", http_code=500)

        try:
            target_user.sudo().write({
                "must_change_password": True,
                "failed_login_count": 0,
                "account_locked": False,
            })
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Failed to update post-reset flags for user %s", user_id
            )

        _create_audit_log(
            request.env,
            target_user.id,
            "password_reset",
            "success",
            request,
        )

        response_data: dict = {"user_id": user_id}
        if generated:
            # Return the temporary password once so the admin can relay it.
            response_data["temporary_password"] = new_password
            response_data["must_change_password"] = True

        return cls.success_response(
            response_data,
            message="Password reset successfully. User must change password on next login.",
        )
