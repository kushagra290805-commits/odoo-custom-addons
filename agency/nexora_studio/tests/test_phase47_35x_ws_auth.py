# -*- coding: utf-8 -*-
"""Phase 47.35.x (F1 remediation) — WebSocket authentication/isolation tests.

Proves the /ws/events hub is an authenticated agency-Console channel:

  * unauthenticated / timeout / malformed -> closed before any event
  * client API token (nex_cli_*) -> closed (wrong credential class)
  * invalid/expired Console JWT -> closed
  * valid Console JWT -> CONNECTION_ESTABLISHED + ping/pong works
  * only authenticated sockets are registered for broadcasts (no
    cross-tenant/unauthenticated event leakage)
  * the canonical JWT decoder is the ONLY validator (no second auth system)

The OdooClient singleton is mocked (transport-level concerns are covered
by the Phase 47.35 route suites and the 47.35.x real E2E).

Run with the global python (backend deps):
    python tests/test_phase47_35x_ws_auth.py
"""
import os
import sys
import unittest
import unittest.mock
from unittest.mock import MagicMock

BACKEND = r'D:\ODOO\nexora-console\backend'
sys.path.insert(0, BACKEND)

os.environ.setdefault('JWT_SECRET', 'ws-auth-test-secret-4735x-0123456789AB')
os.environ.setdefault('ODOO_USERNAME', 'test')
os.environ.setdefault('ODOO_PASSWORD', 'test')

# Isolate the OdooClient singleton BEFORE importing the app modules.
from adapters import odoo_client as odoo_client_mod  # noqa: E402

odoo_client_mod._client_instance = MagicMock()
odoo_client_mod._client_instance.is_connected.return_value = True

import main as bff_main  # noqa: E402  (one canonical app)
from api import ws as bff_ws  # noqa: E402
from security.auth import create_access_token  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

VALID_TOKEN = create_access_token({'sub': 'console-user', 'uid': 2,
                                   'role': 'admin'})
CLIENT_API_TOKEN = 'nex_cli_ws_isolation_probe_000000000000'


def _expect_closed(ws):
    """Assert the hub fails closed.

    TestClient surfaces the server close as a {'type': 'websocket.close'}
    message on the first receive and raises WebSocketDisconnect on the
    next; accept either form but REQUIRE the 4401 close code.
    """
    try:
        msg = ws.receive()
    except WebSocketDisconnect as exc:
        assert exc.code == 4401, exc.code
        return exc.code
    assert msg.get('type') == 'websocket.close', msg
    assert msg.get('code') == 4401, msg
    return msg.get('code')


class TestWebSocketAuthentication(unittest.TestCase):

    def setUp(self):
        self.tc = TestClient(bff_main.app)
        # Keep the auth window short for the timeout tests.
        self._patch = unittest.mock.patch.object(bff_ws, 'AUTH_TIMEOUT_SECONDS', 0.5)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def _connect(self):
        return self.tc.websocket_connect('/ws/events')

    # ── Authentication (negative matrix) ─────────────────────────────

    def test_unauthenticated_socket_closed_without_events(self):
        # No AUTH sent at all: the auth window times out (patched to 0.5s)
        # and the socket is closed without ANY event payload.
        with self._connect() as ws:
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)

    def test_malformed_json_closed(self):
        with self._connect() as ws:
            ws.send_text('not json')
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)

    def test_non_auth_first_message_closed(self):
        with self._connect() as ws:
            ws.send_json({'type': 'SUBSCRIBE_SESSIONS'})
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)

    def test_client_api_token_rejected(self):
        # Client credential class must NOT authenticate the agency stream.
        with self._connect() as ws:
            ws.send_json({'type': 'AUTH', 'token': CLIENT_API_TOKEN})
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)

    def test_invalid_jwt_rejected(self):
        with self._connect() as ws:
            ws.send_json({'type': 'AUTH', 'token': 'bogus.jwt.value'})
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)

    def test_expired_jwt_rejected(self):
        from datetime import timedelta
        expired = create_access_token({'sub': 'x'},
                                      expires_delta=timedelta(seconds=-3600))
        with self._connect() as ws:
            ws.send_json({'type': 'AUTH', 'token': expired})
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)

    def test_auth_without_token_rejected(self):
        with self._connect() as ws:
            ws.send_json({'type': 'AUTH'})
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)

    # ── Authentication (positive) ────────────────────────────────────

    def test_valid_console_jwt_accepted(self):
        with self._connect() as ws:
            ws.send_json({'type': 'AUTH', 'token': VALID_TOKEN})
            hello = ws.receive_json()
            self.assertEqual(hello['type'], 'CONNECTION_ESTABLISHED')
            # Realtime behavior remains functional after authentication.
            ws.send_json({'type': 'ping'})
            pong = ws.receive_json()
            self.assertEqual(pong['type'], 'pong')

    def test_canonical_decoder_is_the_only_validator(self):
        # No second auth system: ws.py uses security.auth.decode_token.
        import inspect
        src = inspect.getsource(bff_ws)
        self.assertIn('from security.auth import decode_token', src)
        self.assertNotIn('jwt.decode', src)

    # ── Authorization / isolation ─────────────────────────────────────

    def test_only_authenticated_sockets_receive_broadcasts(self):
        manager = bff_ws.get_manager()
        # A registered (authenticated) fake socket receives the broadcast;
        # an UNREGISTERED raw socket (never authenticated) structurally
        # cannot — broadcast() iterates only active_connections.
        received = []

        class FakeSock:
            async def send_json(self, message):
                received.append(message)

        registered = FakeSock()
        manager.register(registered)
        self.addCleanup(manager.disconnect, registered)
        import asyncio
        asyncio.run(manager.broadcast({'type': 'SYSTEM_HEALTH', 'payload': {}}))
        self.assertEqual(received, [{'type': 'SYSTEM_HEALTH', 'payload': {}}])
        # Isolation proof: an unregistered socket receives nothing even
        # after an identical broadcast.
        outsider = FakeSock()
        self.assertNotIn(outsider, manager.active_connections)
        received.clear()
        asyncio.run(manager.broadcast({'type': 'SESSIONS_UPDATE', 'payload': {}}))
        self.assertEqual(received, [{'type': 'SESSIONS_UPDATE', 'payload': {}}])
        self.assertEqual(len(received), 1)

    def test_unauthenticated_socket_never_registered(self):
        with self._connect() as ws:
            ws.send_json({'type': 'AUTH', 'token': CLIENT_API_TOKEN})
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)
        manager = bff_ws.get_manager()
        self.assertEqual(len(manager.active_connections), 0)

    def test_authenticated_socket_registered_and_cleaned_up(self):
        manager = bff_ws.get_manager()
        with self._connect() as ws:
            ws.send_json({'type': 'AUTH', 'token': VALID_TOKEN})
            ws.receive()  # CONNECTION_ESTABLISHED
            self.assertEqual(len(manager.active_connections), 1)
        # Context exit closes the socket -> disconnect handler removes it.
        self.assertEqual(len(manager.active_connections), 0)

    def test_close_code_is_4401_unauthorized(self):
        with self._connect() as ws:
            ws.send_json({'type': 'AUTH', 'token': 'wrong-class-token'})
            code = _expect_closed(ws)
            self.assertEqual(code, 4401)

    # ── Regression: the route is still mounted in the ONE app ─────────

    def test_ws_route_part_of_single_canonical_app(self):
        paths = {getattr(r, 'path', None) for r in bff_main.app.routes}
        self.assertIn('/ws/events', paths)
        self.assertIn('/api/v1/client/whoami', paths)


if __name__ == '__main__':
    unittest.main()
