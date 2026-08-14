"""
Unit tests for AuthService — specifically the secure password generator.

Does not require a running Odoo instance.
Run with: python -m pytest tests/test_auth_service_unit.py -v
"""
import importlib.util
import string
import sys
import types
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Odoo stubs
# ---------------------------------------------------------------------------
for mod in ["odoo", "odoo.exceptions", "odoo.fields"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# ---------------------------------------------------------------------------
# Build a fake "nexora_studio.services" package so relative imports work.
# ---------------------------------------------------------------------------
_SERVICES_PATH = "d:\\ODOO\\custom-addons\\agency\\nexora_studio\\services"


def _load_as_package_member(module_name: str, filename: str, package: types.ModuleType):
    """Load a file as a module belonging to *package*, enabling relative imports."""
    filepath = f"{_SERVICES_PATH}\\{filename}"
    spec = importlib.util.spec_from_file_location(
        f"{package.__name__}.{module_name}",
        filepath,
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    mod.__package__ = package.__name__
    sys.modules[f"{package.__name__}.{module_name}"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    setattr(package, module_name, mod)
    return mod


# Create the fake package
_pkg = types.ModuleType("nexora_studio_services_test")
_pkg.__path__ = [_SERVICES_PATH]
_pkg.__package__ = "nexora_studio_services_test"
sys.modules["nexora_studio_services_test"] = _pkg

_ec = _load_as_package_member("error_codes", "error_codes.py", _pkg)
_ps = _load_as_package_member("permission_service", "permission_service.py", _pkg)
_bs = _load_as_package_member("base_service", "base_service.py", _pkg)
_as_mod = _load_as_package_member("auth_service", "auth_service.py", _pkg)

_generate_secure_password = _as_mod._generate_secure_password


class TestSecurePasswordGeneration(unittest.TestCase):
    def _generate_many(self, n=200):
        return [_generate_secure_password() for _ in range(n)]

    def test_minimum_length(self):
        for pwd in self._generate_many():
            self.assertGreaterEqual(len(pwd), 16, f"Password too short: {pwd}")

    def test_has_uppercase(self):
        for pwd in self._generate_many():
            self.assertTrue(any(c.isupper() for c in pwd), f"No uppercase in: {pwd}")

    def test_has_lowercase(self):
        for pwd in self._generate_many():
            self.assertTrue(any(c.islower() for c in pwd), f"No lowercase in: {pwd}")

    def test_has_digit(self):
        for pwd in self._generate_many():
            self.assertTrue(any(c.isdigit() for c in pwd), f"No digit in: {pwd}")

    def test_has_symbol(self):
        for pwd in self._generate_many():
            self.assertTrue(
                any(c in string.punctuation for c in pwd),
                f"No symbol in: {pwd}",
            )

    def test_never_returns_old_placeholder(self):
        for pwd in self._generate_many():
            self.assertNotEqual(pwd, "temp123!")

    def test_uniqueness_across_200_samples(self):
        passwords = self._generate_many(200)
        self.assertEqual(len(set(passwords)), 200, "Password generator produced duplicates")


if __name__ == "__main__":
    unittest.main()
