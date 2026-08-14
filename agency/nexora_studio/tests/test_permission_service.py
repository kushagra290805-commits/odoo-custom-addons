"""
Unit tests for PermissionService.

These tests use mocked res.users objects and do not require a running Odoo instance.
Run with: python -m pytest tests/test_permission_service.py -v
"""
import importlib.util
import sys
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Minimal sys.modules stubs so we can import without a full Odoo environment.
# ---------------------------------------------------------------------------
for mod in ["odoo", "odoo.exceptions", "odoo.fields"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Import the modules under test directly from their file paths — bypasses
# the Odoo package __init__ chain which requires a live Odoo environment.
_SERVICES = "d:\\ODOO\\custom-addons\\agency\\nexora_studio\\services"


def _load(module_name: str, filepath: str):
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_load("nx_error_codes", f"{_SERVICES}\\error_codes.py")
_ps_mod = _load("nx_permission_service", f"{_SERVICES}\\permission_service.py")
PermissionService = _ps_mod.PermissionService
_GROUP_PERMISSION_MAP = _ps_mod._GROUP_PERMISSION_MAP


def _make_user(**groups):
    """Create a mock res.users with has_group behavior driven by *groups* dict."""
    user = MagicMock()
    user.id = 1

    def has_group(xml_id):
        return groups.get(xml_id, False)

    user.has_group.side_effect = has_group
    return user


class TestPermissionServiceRoles(unittest.TestCase):
    def test_super_admin_role(self):
        user = _make_user(**{"nexora_studio.group_nexora_super_admin": True})
        self.assertEqual(PermissionService.get_primary_role(user), "super_admin")

    def test_admin_role(self):
        user = _make_user(**{"nexora_studio.group_nexora_admin": True})
        self.assertEqual(PermissionService.get_primary_role(user), "admin")

    def test_developer_role(self):
        user = _make_user(**{"nexora_studio.group_nexora_developer": True})
        self.assertEqual(PermissionService.get_primary_role(user), "developer")

    def test_viewer_role(self):
        user = _make_user(**{"nexora_studio.group_nexora_viewer": True})
        self.assertEqual(PermissionService.get_primary_role(user), "viewer")

    def test_no_group_returns_none(self):
        user = _make_user()
        self.assertEqual(PermissionService.get_primary_role(user), "none")


class TestPermissionServicePermissions(unittest.TestCase):
    def test_super_admin_has_all_critical_perms(self):
        user = _make_user(**{"nexora_studio.group_nexora_super_admin": True})
        perms = PermissionService.get_permissions(user)
        for p in ["users.manage", "sessions.manage", "audit.read", "console.access"]:
            self.assertIn(p, perms, f"Expected super_admin to have '{p}'")

    def test_developer_cannot_manage_users(self):
        user = _make_user(**{"nexora_studio.group_nexora_developer": True})
        perms = PermissionService.get_permissions(user)
        self.assertNotIn("users.manage", perms)
        self.assertNotIn("sessions.manage", perms)
        self.assertNotIn("audit.read", perms)

    def test_viewer_only_read(self):
        user = _make_user(**{"nexora_studio.group_nexora_viewer": True})
        perms = PermissionService.get_permissions(user)
        self.assertIn("console.access", perms)
        self.assertNotIn("projects.write", perms)

    def test_result_is_deduplicated_and_sorted(self):
        user = _make_user(**{"nexora_studio.group_nexora_super_admin": True})
        perms = PermissionService.get_permissions(user)
        self.assertEqual(perms, sorted(set(perms)))

    def test_has_permission_true(self):
        user = _make_user(**{"nexora_studio.group_nexora_admin": True})
        self.assertTrue(PermissionService.has_permission(user, "audit.read"))

    def test_has_permission_false(self):
        user = _make_user(**{"nexora_studio.group_nexora_developer": True})
        self.assertFalse(PermissionService.has_permission(user, "audit.read"))

    def test_exception_returns_empty_list(self):
        user = MagicMock()
        user.has_group.side_effect = RuntimeError("DB down")
        perms = PermissionService.get_permissions(user)
        self.assertEqual(perms, [])

    def test_developer_denied_audit_in_map(self):
        dev_perms = _GROUP_PERMISSION_MAP.get("nexora_studio.group_nexora_developer", [])
        self.assertNotIn("audit.read", dev_perms)
        self.assertNotIn("sessions.manage", dev_perms)
        self.assertNotIn("users.manage", dev_perms)


if __name__ == "__main__":
    unittest.main()
