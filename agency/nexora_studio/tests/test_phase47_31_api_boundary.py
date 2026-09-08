# -*- coding: utf-8 -*-
"""Phase 47.31 (ADR-0082) — canonical headless API boundary tests.

Proves:
  * the BFF is the canonical boundary: Vite proxy targets it; OpenAPI
    serves the full Console contract.
  * the authentication posture: login + health public; every other
    /api/v1 route rejects unauthenticated calls (EXISTING JWT mechanism).
  * /sessions/{id}/events is a thin projection over nexora.runtime_event
    (no producer logic in the API layer).
  * execution/start delegates to the canonical generation owner
    (nexora.builder_session.action_run_generation ->
    BuilderSessionService.run_generation) — the dead
    nexora.execution_engine_service is NOT resurrected.
  * no BFF adapter contains orchestration mechanics.
  * vite proxy / ws targets point at the canonical boundary; no
    committed secrets; no wildcard CORS with credentials.
"""
import os
import re
import sys
import unittest
from unittest.mock import MagicMock, patch

BACKEND = r'D:\ODOO\nexora-console\backend'
CONSOLE = r'D:\ODOO\nexora-console'
ADDON = r'D:\ODOO\custom-addons\agency\nexora_studio'
sys.path.insert(0, BACKEND)

os.environ.setdefault('JWT_SECRET', 'test-secret-4731')
os.environ.setdefault('ODOO_USERNAME', 'test')
os.environ.setdefault('ODOO_PASSWORD', 'test')

# Isolate the OdooClient singleton before importing the app modules.
from adapters import odoo_client as odoo_client_mod  # noqa: E402
odoo_client_mod._client_instance = MagicMock()

import xmlrpc.client  # noqa: E402


class _FakeServerProxy:
    def __init__(self, *a, **k):
        pass

    def authenticate(self, db, login, password, ctx):
        return 2 if (login, password) == ('admin', 'secret') else False


_auth_patch = patch.object(xmlrpc.client, 'ServerProxy', _FakeServerProxy,
                           create=True)

import main as bff_main  # noqa: E402
from api import routes as bff_routes  # noqa: E402
from security.auth import create_access_token  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

FAKE_EVENTS = [
    {'id': 5, 'runtime_type': 'session', 'event_type':
     'generation.completed', 'message': 'Page pattern: saas_product',
     'timestamp': '2026-09-06 12:00:00'},
    {'id': 9, 'runtime_type': 'ai', 'event_type':
     'ai.execution.completed', 'message': 'Execution success',
     'timestamp': '2026-09-06 12:01:00'},
]

_events_calls = []


def _fake_search_read(model, domain, fields=None, limit=200, order=None):
    _events_calls.append({'model': model, 'domain': domain,
                          'fields': fields, 'limit': limit})
    if model == 'nexora.runtime_event':
        return list(FAKE_EVENTS)
    return []


class TestCanonicalBoundary(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._auth = _auth_patch
        cls._auth.start()
        cls.token = create_access_token(
            {'sub': 'admin', 'uid': 2, 'role': 'admin'})
        cls.auth = {'Authorization': 'Bearer %s' % cls.token}
        cls.client = TestClient(bff_main.app)

    @classmethod
    def tearDownClass(cls):
        cls._auth.stop()

    def _stub_events_client(self):
        return MagicMock(is_connected=lambda: True,
                          search_read=_fake_search_read,
                          latency_ms=3.0)

    # -- authentication posture ---------------------------------------

    def test_01_login_public_and_issues_jwt(self):
        res = self.client.post('/api/v1/auth/login',
                               json={'username': 'admin',
                                     'password': 'secret'})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['token_type'], 'bearer')
        self.assertIn('access_token', body)

    def test_02_login_rejects_wrong_credentials(self):
        res = self.client.post('/api/v1/auth/login',
                               json={'username': 'admin',
                                     'password': 'wrong'})
        self.assertEqual(res.status_code, 401)

    def test_03_health_public(self):
        res = self.client.get('/api/v1/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['api'], 'ok')

    def test_04_protected_route_requires_jwt(self):
        res = self.client.get('/api/v1/sessions')
        self.assertEqual(res.status_code, 401)
        with patch.object(bff_routes, 'get_odoo_client',
                          self._stub_events_client):
            res2 = self.client.get('/api/v1/sessions',
                                   headers=self.auth)
        self.assertEqual(res2.status_code, 200)

    def test_05_all_non_public_routes_reject_anonymous(self):
        # Behavioral check over the COMPLETE documented contract: every
        # /api/v1 operation except login/health must 401 without a token.
        spec = self.client.get('/api/openapi.json').json()
        checked = 0
        for path, ops in spec['paths'].items():
            if not path.startswith('/api/v1'):
                continue
            for method in ('get', 'post', 'put', 'patch', 'delete'):
                if method not in ops:
                    continue
                if (path, method) == ('/api/v1/auth/login', 'post'):
                    continue
                if (path, method) == ('/api/v1/health', 'get'):
                    continue
                res = getattr(self.client, method if method != 'put'
                              else 'put')(path)
                self.assertEqual(
                    res.status_code, 401,
                    '%s %s must require authentication' % (
                        method.upper(), path))
                checked += 1
        self.assertGreater(checked, 40,
                           'the full Console surface is JWT-protected')

    # -- thin runtime-events projection --------------------------------

    def test_10_events_route_reads_existing_runtime_event_store(self):
        with patch.object(bff_routes, 'get_odoo_client',
                          self._stub_events_client):
            res = self.client.get('/api/v1/sessions/42/events',
                                  headers=self.auth)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual([e['id'] for e in body['events']], [5, 9])
        last = _events_calls[-1]
        self.assertEqual(last['model'], 'nexora.runtime_event')
        self.assertIn(['builder_session_id', '=', 42], last['domain'])
        self.assertIn(['id', '>', 0], last['domain'])
        self.assertIn('id', last['fields'])
        self.assertIn('event_type', last['fields'])

    def test_11_events_route_bounded_and_since_id(self):
        with patch.object(bff_routes, 'get_odoo_client',
                          self._stub_events_client):
            res = self.client.get(
                '/api/v1/sessions/42/events?since_id=5&limit=5000',
                headers=self.auth)
        self.assertEqual(res.status_code, 200)
        last = _events_calls[-1]
        self.assertIn(['id', '>', 5], last['domain'])
        self.assertLessEqual(last['limit'], 500,
                             'limit is bounded server-side')

    # -- execution delegates to the canonical generation owner ----------

    def test_20_execution_start_delegates_to_builder_session(self):
        calls = []
        stub = MagicMock(
            is_connected=lambda: True,
            call=lambda model, method, args, timeout=None:
                calls.append((model, method, args)))
        from adapters.execution_adapter import ExecutionAdapter
        with patch(
            'adapters.execution_adapter.get_odoo_client',
            return_value=stub):
            result = ExecutionAdapter().start_execution(7)
        self.assertEqual(result['status'], 'success')
        model, method, args = calls[0]
        self.assertEqual(model, 'nexora.builder_session')
        self.assertEqual(method, 'action_run_generation')
        self.assertEqual(args, [[7]])

    def test_21_dead_execution_engine_service_not_referenced(self):
        src = open(os.path.join(BACKEND, 'adapters',
                                'execution_adapter.py'),
                   encoding='utf-8').read()
        self.assertNotIn("'nexora.execution_engine_service'",
                         src,
                         'the dead orchestration target must stay dead')

    def test_22_builder_session_model_has_canonical_wrapper(self):
        src = open(os.path.join(ADDON, 'models', 'builder_session.py'),
                   encoding='utf-8').read()
        self.assertIn('def action_run_generation', src)
        block = src.split('def action_run_generation')[1][:600]
        self.assertIn("nexora.builder_session_service", block)
        self.assertIn('run_generation', block)
        self.assertNotIn('execution_engine_service', block)

    # -- adapters stay thin (no orchestration in the API layer) --------

    def test_30_adapters_have_no_orchestration_mechanics(self):
        # Orchestration would show up as imports/calls of pipeline
        # internals, local process execution, or a second generation
        # engine. Docstrings may MENTION the canonical chain they
        # delegate to; strip them before scanning.
        def strip_docs(src):
            src = re.sub(r'""".*?"""', '', src, flags=re.S)
            src = re.sub(r'#.*$', '', src, flags=re.M)
            return src

        forbidden = ('import subprocess', 'subprocess.Popen',
                     'execute_dag', 'def start_execution_thread',
                     'GenerationCoordinator', 'WebsiteGenerationPipeline',
                     'execution_engine_service')
        adapters_dir = os.path.join(BACKEND, 'adapters')
        for name in os.listdir(adapters_dir):
            # odoo_client.py is the JSON-RPC transport (a connection
            # singleton); threading there guards the client instance.
            if (not name.endswith('.py') or name == '__init__.py'
                    or name == 'odoo_client.py'):
                continue
            src = strip_docs(open(os.path.join(adapters_dir, name),
                                  encoding='utf-8').read())
            for token in forbidden:
                self.assertNotIn(
                    token, src,
                    '%s must not contain orchestration (%s)'
                    % (name, token))

    def test_31_single_post_sessions_route_registration(self):
        src = open(os.path.join(BACKEND, 'api', 'routes.py'),
                   encoding='utf-8').read()
        self.assertEqual(src.count('@router.post("/sessions")'), 1,
                         'exactly one (the live, first-registered) '
                         'POST /sessions remains')
        self.assertEqual(src.count('@router.get("/sessions")'), 1)
        self.assertEqual(
            src.count('@public_router.post("/auth/login")'), 1)
        self.assertEqual(src.count('@public_router.get("/health")'), 1)

    # -- console consumption --------------------------------------------

    def test_40_vite_proxy_targets_canonical_bff(self):
        src = open(os.path.join(CONSOLE, 'vite.config.ts'),
                   encoding='utf-8').read()
        self.assertIn("target: 'http://127.0.0.1:8000'", src)
        self.assertIn("target: 'ws://127.0.0.1:8000'", src)
        self.assertNotIn('8069', src)

    def test_41_console_events_feed_matches_route_contract(self):
        hook = open(os.path.join(
            CONSOLE, 'src', 'features', 'workspace', 'hooks',
            'useRuntimeEvents.ts'), encoding='utf-8').read()
        self.assertIn('/sessions/${sessionId}/events', hook)
        self.assertIn('since_id', hook)
        self.assertIn('response.data.events', hook)

    # -- security posture -------------------------------------------------

    def test_50_no_committed_secrets_in_settings(self):
        src = open(os.path.join(BACKEND, 'config', 'settings.py'),
                   encoding='utf-8').read()
        self.assertNotIn('nexora-super-secret-jwt-2026', src)
        self.assertNotIn('Admin@123', src)
        self.assertNotIn('kushagra', src)
        self.assertIn('os.getenv("JWT_SECRET", "")', src)
        self.assertIn('os.getenv("ODOO_USERNAME", "")', src)

    def test_51_cors_no_wildcard_with_credentials(self):
        src = open(os.path.join(BACKEND, 'main.py'),
                   encoding='utf-8').read()
        self.assertNotIn('allow_origins=settings.CORS_ORIGINS + ["*"]',
                         src)
        self.assertIn('allow_origins=settings.CORS_ORIGINS', src)

    def test_52_router_dependency_enforced_on_protected_router(self):
        src = open(os.path.join(BACKEND, 'main.py'),
                   encoding='utf-8').read()
        self.assertIsNotNone(re.search(
            r'include_router\(router.*?dependencies='
            r'\[Depends\(get_current_user\)\]',
            src, re.S))
        self.assertIn('include_router(public_router', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
