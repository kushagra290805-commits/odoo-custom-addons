# -*- coding: utf-8 -*-
"""Phase 47.35 — BFF client-route tests (thin-boundary contract).

Follows the Phase 47.31 suite conventions: the BFF app is imported with
the backend on sys.path, the OdooClient singleton is isolated, and the
delegation contract is verified with a mocked OdooClient (the REAL
Odoo-side owner behavior is covered by tests/test_phase47_35_client_api.py
and the standalone E2E scripts/verify_phase47_35.py).

Run with the global python (backend deps):
    python tests/test_phase47_35_bff_client_routes.py
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

BACKEND = r'D:\ODOO\nexora-console\backend'
sys.path.insert(0, BACKEND)

# Isolate the OdooClient singleton BEFORE importing the app modules.
from adapters import odoo_client as odoo_client_mod  # noqa: E402

odoo_client_mod._client_instance = MagicMock()
odoo_client_mod._client_instance.is_connected.return_value = True

import main as bff_main  # noqa: E402
from api.client_routes import CLIENT_ERROR_STATUS  # noqa: E402
from security.auth import create_access_token  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TOKEN = 'nex_cli_unit_test_token_123'


def _client_call_mock(results):
    """Mock OdooClient whose .call(...) returns canned service results."""
    client = MagicMock()
    client.call = MagicMock(side_effect=results)
    return client


class TestClientRoutes(unittest.TestCase):

    def setUp(self):
        self.tc = TestClient(bff_main.app)

    def _with_client(self, mock_client):
        return patch('api.client_routes.get_odoo_client', return_value=mock_client)

    # ── Authentication ────────────────────────────────────────────────

    def test_missing_token_rejected(self):
        r = self.tc.get('/api/v1/client/whoami')
        self.assertEqual(r.status_code, 401)

    def test_invalid_token_maps_to_401(self):
        with self._with_client(_client_call_mock(
                [{'ok': False, 'error_code': 'CLIENT_AUTH_INVALID'}])):
            r = self.tc.get('/api/v1/client/whoami',
                            headers={'Authorization': 'Bearer bogus'})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['detail'], 'CLIENT_AUTH_INVALID')

    def test_expired_token_maps_to_401(self):
        with self._with_client(_client_call_mock(
                [{'ok': False, 'error_code': 'CLIENT_AUTH_EXPIRED'}])):
            r = self.tc.get('/api/v1/client/whoami',
                            headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 401)

    def test_valid_token_passes_through(self):
        payload = {'ok': True, 'project': 'P', 'environment': 'E', 'capabilities': []}
        mock = _client_call_mock([payload])
        with self._with_client(mock):
            r = self.tc.get('/api/v1/client/whoami',
                            headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), payload)
        mock.call.assert_called_once_with(
            'nexora.client_environment_service', 'client_api_whoami',
            [TOKEN], timeout=30.0)

    # ── Console JWT must NOT authenticate client routes ───────────────

    def test_console_jwt_rejected_on_client_routes(self):
        # A VALID console JWT is not a client token: the route delegates
        # it as a client token and the Odoo owner rejects it.
        console_jwt = create_access_token({'sub': 'admin', 'uid': 2, 'role': 'admin'})
        with self._with_client(_client_call_mock(
                [{'ok': False, 'error_code': 'CLIENT_AUTH_INVALID'}])):
            r = self.tc.get('/api/v1/client/whoami',
                            headers={'Authorization': 'Bearer ' + console_jwt})
        self.assertEqual(r.status_code, 401)

    def test_client_token_rejected_on_console_routes(self):
        # A client token is not a console JWT: decode fails -> 401.
        r = self.tc.get('/api/v1/auth/me',
                        headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 401)

    # ── Error contract mapping ────────────────────────────────────────

    def test_error_code_status_mapping(self):
        expected = {
            'CLIENT_AUTH_INVALID': 401,
            'CLIENT_AUTH_EXPIRED': 401,
            'CLIENT_ENV_DELETED': 410,
            'CLIENT_ENV_NOT_READY': 503,
            'CLIENT_CAPABILITY_UNAVAILABLE': 403,
            'CLIENT_DB_UNAVAILABLE': 503,
            'CLIENT_REQUEST_INVALID': 422,
            'CLIENT_BACKEND_ERROR': 502,
        }
        self.assertEqual(CLIENT_ERROR_STATUS, expected)
        for code, status in expected.items():
            with self._with_client(_client_call_mock(
                    [{'ok': False, 'error_code': code}])):
                r = self.tc.get('/api/v1/client/whoami',
                                headers={'Authorization': 'Bearer ' + TOKEN})
                self.assertEqual(r.status_code, status, code)

    def test_transport_failure_sanitized_to_502(self):
        mock = MagicMock()
        mock.call = MagicMock(side_effect=RuntimeError('psycopg2://secret@host leak'))
        with self._with_client(mock):
            r = self.tc.get('/api/v1/client/whoami',
                            headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json()['detail'], 'Client backend unavailable')
        self.assertNotIn('psycopg2', r.text)

    def test_unexpected_result_shape_sanitized(self):
        with self._with_client(_client_call_mock(['not-a-dict'])):
            r = self.tc.get('/api/v1/client/whoami',
                            headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 502)

    # ── Route contracts ───────────────────────────────────────────────

    def test_products_delegation_with_limit(self):
        payload = {'ok': True, 'products': [{'id': 1, 'name': 'W', 'price': 1.0, 'sku': ''}]}
        mock = _client_call_mock([payload])
        with self._with_client(mock):
            r = self.tc.get('/api/v1/client/products?limit=7',
                            headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 200)
        mock.call.assert_called_once_with(
            'nexora.client_environment_service', 'client_api_list_products',
            [TOKEN, 7], timeout=30.0)

    def test_products_limit_bounds_enforced(self):
        for bad in ('0', '-1', '101', 'abc'):
            r = self.tc.get('/api/v1/client/products?limit=' + bad,
                            headers={'Authorization': 'Bearer ' + TOKEN})
            self.assertEqual(r.status_code, 422, bad)

    def test_lead_creation_delegation(self):
        payload = {'ok': True, 'lead_id': 42}
        mock = _client_call_mock([payload])
        body = {'name': 'John', 'email': 'j@x.com', 'phone': '123', 'message': 'hi'}
        with self._with_client(mock):
            r = self.tc.post('/api/v1/client/leads', json=body,
                             headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 200)
        args = mock.call.call_args[0]
        self.assertEqual(args[1], 'client_api_create_lead')
        self.assertEqual(args[2][0], TOKEN)
        # Whitelist: only name/email/phone/message are forwarded.
        self.assertEqual(sorted(args[2][1].keys()), ['email', 'message', 'name', 'phone'])

    def test_lead_payload_validation(self):
        for bad in ({}, {'name': ''}, {'name': 'x' * 500}):
            r = self.tc.post('/api/v1/client/leads', json=bad,
                             headers={'Authorization': 'Bearer ' + TOKEN})
            self.assertEqual(r.status_code, 422, bad)

    def test_lead_extra_fields_never_forwarded(self):
        # Extra/hostile fields are IGNORED (pydantic whitelist): they never
        # reach Odoo — arbitrary model/method/db access is impossible.
        mock = _client_call_mock([{'ok': True, 'lead_id': 1}])
        body = {'name': 'ok', 'evil_field': 1,
                'model': 'res.partner', 'method': 'create',
                'db_name': 'nexora_studio', 'args': ['DROP TABLE']}
        with self._with_client(mock):
            r = self.tc.post('/api/v1/client/leads', json=body,
                             headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 200)
        forwarded = mock.call.call_args[0][2][1]
        self.assertEqual(forwarded, {'name': 'ok', 'email': None,
                                     'phone': None, 'message': None})

    def test_health_route(self):
        with self._with_client(_client_call_mock(
                [{'ok': True, 'environment_status': 'ready',
                  'module_provisioning_state': 'provisioned',
                  'client_db_available': True}])):
            r = self.tc.get('/api/v1/client/health',
                            headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 200)

    # ── No generic passthrough / unknown routes ───────────────────────

    def test_no_generic_execute_route(self):
        # There is deliberately NO generic model/method/SQL passthrough.
        for path in ('/api/v1/client/execute', '/api/v1/client/rpc',
                     '/api/v1/client/odoo', '/api/v1/client/sql',
                     '/api/v1/client/models/res.partner'):
            r = self.tc.post(path, json={'model': 'res.partner', 'method': 'create'},
                             headers={'Authorization': 'Bearer ' + TOKEN})
            self.assertEqual(r.status_code, 404, path)

    def test_unknown_client_route_404(self):
        r = self.tc.get('/api/v1/client/anything-else',
                        headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(r.status_code, 404)

    # ── CORS / boundary posture preserved ─────────────────────────────

    def test_cors_still_safe_no_wildcard_credentials(self):
        cors = next(m for m in bff_main.app.user_middleware
                    if m.cls.__name__ == 'CORSMiddleware')
        origins = cors.kwargs['allow_origins']
        self.assertNotIn('*', origins)
        self.assertTrue(cors.kwargs['allow_credentials'])  # with explicit origins only

    def test_client_routes_are_part_of_single_canonical_app(self):
        # ONE FastAPI app hosts console + client routes.
        paths = {getattr(r, 'path', None) for r in bff_main.app.routes}
        self.assertIn('/api/v1/client/whoami', paths)
        self.assertIn('/api/v1/auth/login', paths)


if __name__ == '__main__':
    unittest.main()
