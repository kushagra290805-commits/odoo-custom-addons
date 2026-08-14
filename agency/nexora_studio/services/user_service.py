"""
UserService — manages Nexora user accounts via Odoo res.users.

Controllers are thin wrappers; all logic lives here.
"""
import logging
import secrets
import string

from odoo import exceptions

from .base_service import BaseService
from .error_codes import (
    AUTHZ_FORBIDDEN,
    USER_CREATE_FAILED,
    USER_NOT_FOUND,
)

_logger = logging.getLogger(__name__)

_PWD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
_PWD_MIN_LENGTH = 16


def _generate_secure_password() -> str:
    """Return a cryptographically secure temporary password (≥16 chars)."""
    while True:
        pwd = "".join(secrets.choice(_PWD_ALPHABET) for _ in range(_PWD_MIN_LENGTH))
        if (
            any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in string.punctuation for c in pwd)
        ):
            return pwd


def _can_manage_users(user) -> bool:
    return user.has_group("nexora_studio.group_nexora_super_admin") or user.has_group(
        "nexora_studio.group_nexora_admin"
    )


def _user_to_dict(u) -> dict:
    return {
        "id": u.id,
        "username": u.login,
        "display_name": u.name,
        "active": u.active,
        "account_locked": u.account_locked,
        "must_change_password": u.must_change_password,
        "is_nexora_user": u.is_nexora_user,
    }


def _create_audit_log(env, user_id, action: str, result: str, request):
    try:
        env["nexora.audit.log"].sudo().create({
            "user_id": user_id,
            "action": action,
            "ip_address": request.httprequest.remote_addr,
            "result": result,
        })
    except Exception:  # noqa: BLE001
        _logger.exception(
            "Failed to create audit log for action=%s user_id=%s", action, user_id
        )


class UserService(BaseService):

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    @classmethod
    def get_users(cls, request):
        if not _can_manage_users(request.env.user):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)
        try:
            users = request.env["res.users"].sudo().search([("is_nexora_user", "=", True)])
            return cls.success_response([_user_to_dict(u) for u in users])
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to fetch Nexora users")
            return cls.error_response("An unexpected error occurred.", http_code=500)

    # ------------------------------------------------------------------
    # Get one
    # ------------------------------------------------------------------

    @classmethod
    def get_user(cls, request, user_id: int):
        if not _can_manage_users(request.env.user):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)
        try:
            u = request.env["res.users"].sudo().browse(user_id)
            if not u.exists() or not u.is_nexora_user:
                return cls.error_response("User not found.", http_code=404, error_code=USER_NOT_FOUND)
            return cls.success_response(_user_to_dict(u))
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to fetch user %s", user_id)
            return cls.error_response("An unexpected error occurred.", http_code=500)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @classmethod
    def create_user(cls, request, vals: dict):
        if not _can_manage_users(request.env.user):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)

        vals = dict(vals)  # defensive copy
        vals["is_nexora_user"] = True
        vals["must_change_password"] = True

        # Generate a secure temporary password and return it to the admin.
        temp_password = _generate_secure_password()
        vals["password"] = temp_password

        try:
            new_user = request.env["res.users"].sudo().create(vals)
        except exceptions.ValidationError as exc:
            _logger.info("Validation error creating user: %s", exc)
            return cls.error_response(
                "Invalid user data. Check required fields.",
                http_code=400,
                error_code=USER_CREATE_FAILED,
            )
        except Exception:  # noqa: BLE001
            _logger.exception("Unexpected error creating Nexora user")
            return cls.error_response("An unexpected error occurred.", http_code=500)

        _create_audit_log(request.env, new_user.id, "user_create", "success", request)

        return cls.success_response(
            {
                "id": new_user.id,
                "temporary_password": temp_password,
                "must_change_password": True,
            },
            message="User created. Temporary password is shown once; relay it securely.",
        )

    # ------------------------------------------------------------------
    # Unlock
    # ------------------------------------------------------------------

    @classmethod
    def unlock_user(cls, request, user_id: int):
        if not _can_manage_users(request.env.user):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)
        try:
            u = request.env["res.users"].sudo().browse(user_id)
            if not u.exists() or not u.is_nexora_user:
                return cls.error_response("User not found.", http_code=404, error_code=USER_NOT_FOUND)
            u.write({"account_locked": False, "failed_login_count": 0})
        except exceptions.AccessError:
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)
        except Exception:  # noqa: BLE001
            _logger.exception("Unexpected error unlocking user %s", user_id)
            return cls.error_response("An unexpected error occurred.", http_code=500)

        _create_audit_log(request.env, user_id, "account_unlock", "success", request)
        return cls.success_response()

    # ------------------------------------------------------------------
    # Enable / Disable
    # ------------------------------------------------------------------

    @classmethod
    def set_user_active(cls, request, user_id: int, *, active: bool):
        if not _can_manage_users(request.env.user):
            return cls.error_response("Forbidden", http_code=403, error_code=AUTHZ_FORBIDDEN)
        try:
            u = request.env["res.users"].sudo().browse(user_id)
            if not u.exists() or not u.is_nexora_user:
                return cls.error_response("User not found.", http_code=404, error_code=USER_NOT_FOUND)
            u.with_context(active_test=False).write({"active": active})
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Unexpected error %s user %s",
                "enabling" if active else "disabling",
                user_id,
            )
            return cls.error_response("An unexpected error occurred.", http_code=500)

        action = "user_enable" if active else "user_disable"
        _create_audit_log(request.env, user_id, action, "success", request)
        return cls.success_response()
