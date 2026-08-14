"""
PermissionService — single source of truth for resolving frontend permissions
from Odoo Security Groups.

All backend services that need to return or check permissions must use this
service exclusively.  No controller or service may hardcode permission lists.

PERMISSION REFERENCE TABLE
===========================

Permission string        Consumed by                             Description
------------------------  ----------------------------------------  -----------------------------------------------
console.access            ProtectedRoute guard                    User may open the React developer console
projects.read             ProjectsPage, useProjectsQuery          Read own/assigned projects
projects.write            ProjectEditor, ProjectActions           Create and modify projects
projects.manage           ProjectsAdmin, ProjectActions (admin)   Delete and manage all projects
templates.read            TemplateStore browser                   Browse available templates
templates.manage          TemplateAdmin                           Create / update / delete templates
runtimes.manage           RuntimePanel                           Start, stop, restart runtime environments
users.manage              UsersPage (admin view)                  CRUD on developer/viewer accounts
users.manage_developers   UsersPage (admin view, scoped)          Admin-scoped developer account CRUD
users.reset_password      UserActions → Reset Password button     Trigger password reset on behalf of a user
users.reset_developer_password  UserActions (admin-scoped)        Admin-scoped password reset for developers
users.enable              UserActions → Enable button             Re-activate a disabled account
users.disable             UserActions → Disable button            Deactivate an account
sessions.view             SessionsPage                            List tracked sessions
sessions.manage           SessionsPage → Force Logout button      Force-logout any session (Super Admin only)
audit.read                AuditPage                               Read audit log entries
odoo.backend.access       (informational, not enforced in React)  Full Odoo backend access
odoo.backend.access_limited (informational)                       Limited Odoo backend access
"""
import logging

_logger = logging.getLogger(__name__)

# Static mapping from Odoo group XML IDs to application permission strings.
# Every entry in a list MUST appear in the reference table above.
_GROUP_PERMISSION_MAP: dict[str, list[str]] = {
    "nexora_studio.group_nexora_super_admin": [
        "console.access",
        "projects.read",
        "projects.write",
        "projects.manage",
        "templates.read",
        "templates.manage",
        "runtimes.manage",
        "users.manage",
        "users.reset_password",
        "users.enable",
        "users.disable",
        "sessions.view",
        "sessions.manage",
        "audit.read",
        "odoo.backend.access",
    ],
    "nexora_studio.group_nexora_admin": [
        "console.access",
        "projects.read",
        "projects.write",
        "projects.manage",
        "templates.read",
        "templates.manage",
        "runtimes.manage",
        "users.manage_developers",
        "users.reset_developer_password",
        "users.enable",
        "users.disable",
        "sessions.view",
        "audit.read",
        "odoo.backend.access_limited",
    ],
    "nexora_studio.group_nexora_developer": [
        "console.access",
        "projects.read",
        "projects.write",
        "templates.read",
    ],
    "nexora_studio.group_nexora_viewer": [
        "console.access",
        "projects.read",
        "templates.read",
    ],
}

_ROLE_MAP: dict[str, str] = {
    "nexora_studio.group_nexora_super_admin": "super_admin",
    "nexora_studio.group_nexora_admin": "admin",
    "nexora_studio.group_nexora_developer": "developer",
    "nexora_studio.group_nexora_viewer": "viewer",
}


class PermissionService:
    """
    Resolves Odoo Security Group membership into a deduplicated list of
    application-level permission strings.

    All other services must call ``PermissionService.get_permissions(user)``
    instead of reading Security Groups directly.
    """

    @staticmethod
    def get_permissions(user) -> list[str]:
        """
        Return the deduplicated set of permission strings for *user*.

        :param user: ``res.users`` record (may be sudo'd or not — only
                     ``has_group`` is called, which is always allowed).
        :returns:    Sorted list of unique permission strings.
        """
        permissions: set[str] = set()
        try:
            for group_xml_id, perms in _GROUP_PERMISSION_MAP.items():
                if user.has_group(group_xml_id):
                    permissions.update(perms)
        except Exception:  # noqa: BLE001
            _logger.exception(
                "PermissionService.get_permissions failed for user %s",
                getattr(user, "id", "unknown"),
            )
        return sorted(permissions)

    @staticmethod
    def get_primary_role(user) -> str:
        """
        Return the single highest-privilege role label for *user*.

        Roles are evaluated in descending privilege order so the first match
        wins.  Returns ``"none"`` when the user has no Nexora group.
        """
        try:
            for group_xml_id, role in _ROLE_MAP.items():
                if user.has_group(group_xml_id):
                    return role
        except Exception:  # noqa: BLE001
            _logger.exception(
                "PermissionService.get_primary_role failed for user %s",
                getattr(user, "id", "unknown"),
            )
        return "none"

    @staticmethod
    def has_permission(user, permission: str) -> bool:
        """
        Convenience method for services that need to check a single permission.
        """
        return permission in PermissionService.get_permissions(user)
