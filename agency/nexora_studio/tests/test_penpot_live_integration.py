# -*- coding: utf-8 -*-
import unittest
import os
import sys
import json
import time
from unittest.mock import patch, MagicMock
import urllib.error

# Ensure Odoo and module paths are accessible for standalone test execution
sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from odoo.addons.nexora_studio.services.design.penpot_auth import PATAuthenticator, SessionAuthenticator, get_authenticator
from odoo.addons.nexora_studio.services.design.penpot_client import PenpotAPIClient
from odoo.addons.nexora_studio.services.design.penpot_provider import PenpotDesignProvider


class DummySysParam:
    def __init__(self, params):
        self.params = params
    def sudo(self):
        return self
    def get_param(self, key):
        return self.params.get(key)


class DummyOdooEnv:
    def __init__(self, params):
        self.sysparam = DummySysParam(params)
    def get(self, key):
        if key == 'ir.config_parameter':
            return self.sysparam
        return None
    def __getitem__(self, key):
        if key == 'ir.config_parameter':
            return self.sysparam
        raise KeyError(key)


class TestPenpotLiveIntegration(unittest.TestCase):
    """
    Comprehensive verification suite for Phase 11B Live Penpot Integration.
    Covers unit tests (configuration precedence, retry engine, auth abstraction, schema boundaries)
    and live integration tests against http://localhost:9001.
    """

    def test_01_config_precedence_explicit(self):
        """Tier 1: Explicit provider config overrides all other settings."""
        env = DummyOdooEnv({'nexora.penpot_url': 'http://odoo-sysparam.internal:9001'})
        with patch.dict(os.environ, {'PENPOT_PUBLIC_URI': 'http://env-var.internal:9001'}):
            client = PenpotAPIClient(config={'url': 'http://explicit.internal:9001'}, env=env)
            self.assertEqual(client.base_url, 'http://explicit.internal:9001')

    def test_02_config_precedence_sysparam(self):
        """Tier 2: Odoo sysparam overrides environment variables when no explicit config is given."""
        env = DummyOdooEnv({'nexora.penpot_url': 'http://odoo-sysparam.internal:9001'})
        with patch.dict(os.environ, {'PENPOT_PUBLIC_URI': 'http://env-var.internal:9001'}):
            client = PenpotAPIClient(config={}, env=env)
            self.assertEqual(client.base_url, 'http://odoo-sysparam.internal:9001')

    def test_03_config_precedence_env(self):
        """Tier 3: Environment variable overrides default when no explicit config or sysparam."""
        env = DummyOdooEnv({})
        with patch.dict(os.environ, {'PENPOT_PUBLIC_URI': 'http://env-var.internal:9001'}):
            client = PenpotAPIClient(config={}, env=env)
            self.assertEqual(client.base_url, 'http://env-var.internal:9001')

    def test_04_config_precedence_default(self):
        """Tier 4: Default localhost fallback when nothing else is configured."""
        env = DummyOdooEnv({})
        with patch.dict(os.environ, {}, clear=True):
            if 'PENPOT_PUBLIC_URI' in os.environ:
                del os.environ['PENPOT_PUBLIC_URI']
            if 'PENPOT_URL' in os.environ:
                del os.environ['PENPOT_URL']
            client = PenpotAPIClient(config={}, env=env)
            self.assertEqual(client.base_url, 'http://localhost:9001')

    def test_05_auth_abstraction(self):
        """Verify PATAuthenticator headers and SessionAuthenticator stub behavior."""
        auth = PATAuthenticator("test_token_123")
        headers = auth.get_headers()
        self.assertEqual(headers["Authorization"], "Token test_token_123")
        
        session_auth = SessionAuthenticator("sess_abc")
        self.assertEqual(session_auth.get_headers()["Cookie"], "penpot-session=sess_abc")

    @patch("urllib.request.urlopen")
    def test_06_retry_engine_exponential_backoff(self, mock_urlopen):
        """Verify client automatically retries 5xx transient server errors with backoff."""
        err_503 = urllib.error.HTTPError(
            url="http://localhost:9001/api/rpc/command/get-profile",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=MagicMock(read=lambda: b"Service Temporarily Unavailable")
        )
        
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = MagicMock(read=lambda: b'{"id":"123","fullname":"Test User"}')
        
        mock_urlopen.side_effect = [err_503, err_503, mock_resp]
        
        client = PenpotAPIClient(config={"connect_timeout": 1, "read_timeout": 1})
        start_time = time.time()
        res = client.rpc_call("get-profile", {}, max_retries=3)
        elapsed = time.time() - start_time
        
        self.assertEqual(res.get("id"), "123")
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertGreaterEqual(elapsed, 1.4)

    def test_07_strict_schema_compliance_no_invented_payloads(self):
        """Verify unsupported granular intra-file mutations raise NotImplementedError with documented rationale."""
        provider = PenpotDesignProvider()
        unsupported_methods = [
            ("create_page", ("proj_1", "Page 1")),
            ("create_frame", ("page_1", {})),
            ("create_component", ("page_1", {})),
            ("update_component", ("comp_1", {})),
            ("delete_component", ("comp_1",)),
            ("create_design_tokens", ("proj_1", {})),
            ("apply_theme", ("proj_1", "theme_1")),
            ("import_assets", ("proj_1", [])),
            ("sync_project", ("proj_1",))
        ]
        
        for method_name, args in unsupported_methods:
            method = getattr(provider, method_name)
            with self.assertRaises(NotImplementedError) as ctx:
                method(*args)
            self.assertIn("invented mutation payloads are strictly prohibited", str(ctx.exception))

    def test_08_export_id_resolution(self):
        """Verify export methods correctly parse file_id and object_id from formatted strings or options."""
        with patch.object(PenpotAPIClient, "rpc_call", return_value={"content": "<svg></svg>"}) as mock_rpc:
            provider = PenpotDesignProvider()
            res = provider.export_svg("file_abc:obj_xyz")
            self.assertEqual(res, "<svg></svg>")
            mock_rpc.assert_called_with("export-binfile", {"file-id": "file_abc", "object-id": "obj_xyz", "format": "svg"})
            
            provider.export_png("obj_999", options={"file_id": "file_777"})
            mock_rpc.assert_called_with("export-binfile", {"file-id": "file_777", "object-id": "obj_999", "format": "png"})

    # =========================================================================
    # Live Integration Tests against http://localhost:9001
    # =========================================================================

    def _check_penpot_live(self, client):
        res = client.validate_connection()
        if not res.get("reachable"):
            raise unittest.SkipTest("Live Penpot server at http://localhost:9001 is not running or unreachable.")

    def test_09_live_connection_reachability(self):
        """Live Test: Verify live Penpot server reachability and connection health."""
        client = PenpotAPIClient()
        self._check_penpot_live(client)
        res = client.validate_connection()
        print("\n[LIVE TEST] validate_connection() ->", res)
        self.assertEqual(res.get("status"), "ok")
        self.assertTrue(res.get("reachable"))

    def test_10_live_unauthenticated_rejection(self):
        """Live Test: Verify live server properly rejects unauthenticated requests with HTTP 401."""
        client = PenpotAPIClient()
        self._check_penpot_live(client)
        with self.assertRaises(RuntimeError) as ctx:
            client.rpc_call("get-projects", {"team-id": "00000000-0000-0000-0000-000000000000"}, max_retries=0)
        self.assertIn("401", str(ctx.exception))
        self.assertIn("authentication-required", str(ctx.exception))

    def test_11_live_profile_endpoint(self):
        """Live Test: Verify live get-profile endpoint returns valid profile dictionary."""
        client = PenpotAPIClient()
        self._check_penpot_live(client)
        profile = client.rpc_call("get-profile", {}, max_retries=1)
        print("[LIVE TEST] get-profile ->", profile)
        self.assertIsInstance(profile, dict)
        self.assertIn("id", profile)
        self.assertIn("fullname", profile)


if __name__ == '__main__':
    unittest.main()
