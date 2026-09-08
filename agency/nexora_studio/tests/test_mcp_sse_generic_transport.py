# -*- coding: utf-8 -*-
"""Phase 44.2 closure regression tests for the generic MCP SSE transport.

auth_location=query is delivered by appending the resolved credential to the
endpoint URL (SDK 1.x and 2.x/httpx2 compatible) instead of passing a custom
httpx.Auth object. Header/none authentication and the stdio env path must
remain unchanged, and credential values must never leak into error text.
"""
import asyncio
import unittest
import urllib.parse
from concurrent.futures import Future
from unittest.mock import AsyncMock, MagicMock, patch

from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration
from odoo.addons.nexora_studio.services.connector.connectors.mcp import transport as transport_mod
from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import (
    McpTransport,
    TransportBinding,
    _append_query_param,
)


def _sse_config(**overrides):
    kwargs = dict(
        transport='sse',
        command='http://generic-endpoint/mcp/sse',
        args=[],
        env={},
        auth_location='none',
        auth_name='',
        auth_secret='',
        auth_scheme='none',
    )
    kwargs.update(overrides)
    return McpConfiguration(**kwargs)


def _run_sse_handshake(config, binding=None, sse_error=None, capture=None):
    """Run McpTransport._connect_and_wait with mocked sse_client/ClientSession.

    Returns (sse_client_call_kwargs_or_None, ready_future). When ``capture``
    (a dict) is given, the effective httpx/httpx2 logger levels are recorded
    into it at sse_client enter time (handshake moment).
    """
    transport = McpTransport(config, transport_binding=binding)

    async def run():
        transport._exit_event = asyncio.Event()
        transport._exit_event.set()
        ready_future = Future()

        mock_cm = MagicMock()
        if sse_error is not None:
            mock_cm.__aenter__.side_effect = sse_error
        else:
            mock_cm.__aenter__.return_value = (MagicMock(), MagicMock())
        if capture is not None:
            import logging

            async def _capture_levels(*_args, **_kwargs):
                for _name in ('httpx', 'httpx2'):
                    capture[_name] = logging.getLogger(_name).level
                return (MagicMock(), MagicMock())

            mock_cm.__aenter__.side_effect = _capture_levels

        with patch('mcp.client.sse.sse_client', return_value=mock_cm) as mock_sse, \
                patch.object(transport_mod, 'ClientSession') as mock_session_cls:
            session = MagicMock()
            session.initialize = AsyncMock()
            session_cm = MagicMock()
            session_cm.__aenter__.return_value = session
            mock_session_cls.return_value = session_cm

            await transport._connect_and_wait(ready_future)

        call_kwargs = mock_sse.call_args.kwargs if mock_sse.call_args else None
        return call_kwargs, ready_future

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


class TestMcpSseGenericTransport(unittest.TestCase):

    # ------------------------------------------------------------------
    # URL query-parameter helper
    # ------------------------------------------------------------------

    def test_append_query_param_preserves_existing_and_encodes(self):
        url = _append_query_param(
            'http://host:9001/mcp/sse?foo=bar', 'genericToken', 's3cr&et=va lue')
        parsed = urllib.parse.urlparse(url)
        self.assertEqual(parsed.scheme, 'http')
        self.assertEqual(parsed.netloc, 'host:9001')
        self.assertEqual(parsed.path, '/mcp/sse')
        params = urllib.parse.parse_qsl(parsed.query)
        self.assertIn(('foo', 'bar'), params)
        self.assertIn(('genericToken', 's3cr&et=va lue'), params)
        # Raw special characters must never appear unencoded in the query.
        self.assertNotIn('s3cr&et', url)

    def test_append_query_param_replaces_existing_key(self):
        url = _append_query_param(
            'http://host/mcp/sse?token=stale&keep=1', 'token', 'fresh')
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        self.assertEqual(params['token'], 'fresh')
        self.assertEqual(params['keep'], '1')
        self.assertEqual(url.count('token='), 1)

    def test_append_query_param_on_url_without_query(self):
        url = _append_query_param('http://host/mcp/sse', 'k', 'v')
        self.assertEqual(url, 'http://host/mcp/sse?k=v')

    # ------------------------------------------------------------------
    # SSE handshake: query auth
    # ------------------------------------------------------------------

    def test_query_auth_delivered_via_url_without_auth_object(self):
        config = _sse_config(
            auth_location='query',
            auth_name='genericToken',
            auth_secret='genericSecret',
        )
        call_kwargs, ready_future = _run_sse_handshake(config)

        self.assertTrue(ready_future.done())
        self.assertIsNone(ready_future.exception())
        self.assertIsNotNone(call_kwargs)
        # The credential travels in the URL, correctly encoded.
        params = dict(
            urllib.parse.parse_qsl(urllib.parse.urlparse(call_kwargs['url']).query))
        self.assertEqual(params.get('genericToken'), 'genericSecret')
        # No custom auth object may ever be handed to the MCP SDK: this is
        # what MCP SDK >= 2.0 (httpx2-backed) rejects with TypeError.
        self.assertNotIn('auth', call_kwargs)

    def test_query_auth_wins_over_binding_on_key_collision(self):
        config = _sse_config(
            auth_location='query',
            auth_name='sharedKey',
            auth_secret='authValue',
        )
        binding = TransportBinding(location='query', name='sharedKey', value='bindingValue')
        call_kwargs, ready_future = _run_sse_handshake(config, binding=binding)

        self.assertIsNone(ready_future.exception())
        params = dict(
            urllib.parse.parse_qsl(urllib.parse.urlparse(call_kwargs['url']).query))
        self.assertEqual(params.get('sharedKey'), 'authValue')

    def test_binding_query_applied_without_auth(self):
        config = _sse_config()
        binding = TransportBinding(location='query', name='sessionId', value='abc123')
        call_kwargs, ready_future = _run_sse_handshake(config, binding=binding)

        self.assertIsNone(ready_future.exception())
        params = dict(
            urllib.parse.parse_qsl(urllib.parse.urlparse(call_kwargs['url']).query))
        self.assertEqual(params.get('sessionId'), 'abc123')
        self.assertNotIn('auth', call_kwargs)

    # ------------------------------------------------------------------
    # SSE handshake: header / none auth unchanged
    # ------------------------------------------------------------------

    def test_header_auth_unchanged(self):
        config = _sse_config(
            auth_location='header',
            auth_name='X-Api-Key',
            auth_secret='headerSecret',
            auth_scheme='bearer',
        )
        call_kwargs, ready_future = _run_sse_handshake(config)

        self.assertIsNone(ready_future.exception())
        self.assertEqual(call_kwargs['headers']['X-Api-Key'], 'Bearer headerSecret')
        # URL must stay untouched for header auth.
        self.assertEqual(call_kwargs['url'], 'http://generic-endpoint/mcp/sse')
        self.assertNotIn('auth', call_kwargs)

    def test_header_auth_without_scheme_unchanged(self):
        config = _sse_config(
            auth_location='header',
            auth_name='X-Api-Key',
            auth_secret='plainSecret',
            auth_scheme='none',
        )
        call_kwargs, ready_future = _run_sse_handshake(config)

        self.assertIsNone(ready_future.exception())
        self.assertEqual(call_kwargs['headers']['X-Api-Key'], 'plainSecret')

    def test_no_auth_leaves_url_and_headers_clean(self):
        config = _sse_config()
        call_kwargs, ready_future = _run_sse_handshake(config)

        self.assertIsNone(ready_future.exception())
        self.assertEqual(call_kwargs['url'], 'http://generic-endpoint/mcp/sse')
        self.assertIsNone(call_kwargs['headers'])
        self.assertNotIn('auth', call_kwargs)

    # ------------------------------------------------------------------
    # Credential leak protection
    # ------------------------------------------------------------------

    def test_error_text_redacts_credential_url(self):
        secret = 'leakableSecretValue'
        config = _sse_config(
            auth_location='query',
            auth_name='genericToken',
            auth_secret=secret,
        )
        full_url = _append_query_param(config.command, 'genericToken', secret)
        sse_error = RuntimeError(f'connection to {full_url} refused')

        _, ready_future = _run_sse_handshake(config, sse_error=sse_error)

        exc = ready_future.exception()
        self.assertIsNotNone(exc)
        message = str(exc)
        self.assertNotIn(secret, message)
        self.assertIn(config.command, message)

    def test_query_auth_silences_http_request_loggers_during_handshake(self):
        """httpx (SDK 1.x) / httpx2 (SDK 2.x) log every request line — with
        the full URL and query string — at INFO. While the URL carries the
        credential those loggers must be silenced, and restored afterwards."""
        import logging

        config = _sse_config(
            auth_location='query',
            auth_name='genericToken',
            auth_secret='genericSecret',
        )
        original = {n: logging.getLogger(n).level for n in ('httpx', 'httpx2')}
        capture = {}
        try:
            _, ready_future = _run_sse_handshake(config, capture=capture)
            self.assertIsNone(ready_future.exception())
            self.assertEqual(capture.get('httpx'), logging.WARNING)
            self.assertEqual(capture.get('httpx2'), logging.WARNING)
            # Restored after the connection window.
            for name in ('httpx', 'httpx2'):
                self.assertEqual(logging.getLogger(name).level, original[name])
        finally:
            for name, lvl in original.items():
                logging.getLogger(name).setLevel(lvl)

    def test_header_auth_leaves_http_loggers_untouched(self):
        import logging

        config = _sse_config(
            auth_location='header',
            auth_name='X-Api-Key',
            auth_secret='headerSecret',
        )
        original = {n: logging.getLogger(n).level for n in ('httpx', 'httpx2')}
        capture = {}
        try:
            _, ready_future = _run_sse_handshake(config, capture=capture)
            self.assertIsNone(ready_future.exception())
            # No query param appended -> no logger suppression at all.
            for name in ('httpx', 'httpx2'):
                self.assertEqual(capture.get(name), original[name])
                self.assertEqual(logging.getLogger(name).level, original[name])
        finally:
            for name, lvl in original.items():
                logging.getLogger(name).setLevel(lvl)

    # ------------------------------------------------------------------
    # SDK compatibility / legacy object removal
    # ------------------------------------------------------------------

    def test_installed_sdk_accepts_transport_call_shape(self):
        """Regression for MCP SDK 2.x (httpx2): the exact call shape used by
        McpTransport (headers only, auth=None) must be accepted by whichever
        SDK version is installed."""
        from mcp.shared import _httpx_utils

        client = _httpx_utils.create_mcp_http_client(
            headers={'X-Test': '1'}, auth=None)
        self.assertIsNotNone(client)

    def test_query_auth_object_removed(self):
        self.assertFalse(hasattr(transport_mod, 'QueryAuth'))

    # ------------------------------------------------------------------
    # stdio / env path unchanged
    # ------------------------------------------------------------------

    def test_stdio_still_supported(self):
        config = McpConfiguration(
            transport="stdio",
            command="npx",
            args=["@some/server"],
            env={},
            auth_location="none",
            auth_name="",
            auth_secret="",
            auth_scheme="none"
        )
        transport = McpTransport(config)
        self.assertEqual(transport.config.transport, "stdio")
        self.assertEqual(transport.config.command, "npx")

    def test_stdio_env_auth_location_config_accepted(self):
        """env delivery happens via the stdio process environment; the config
        must keep validating exactly as before."""
        config = McpConfiguration(
            transport="stdio",
            command="docker",
            args=["run", "-i", "--rm", "-e", "SOME_TOKEN", "image"],
            env={"SOME_TOKEN": "__INJECT_VIA_NEXORA_MCP_CREDENTIAL__"},
            auth_location="env",
            auth_name="SOME_TOKEN",
            auth_secret="envSecret",
            auth_scheme="none"
        )
        transport = McpTransport(config)
        self.assertEqual(transport.config.auth_location, "env")
        self.assertEqual(transport.config.env["SOME_TOKEN"], "__INJECT_VIA_NEXORA_MCP_CREDENTIAL__")


if __name__ == '__main__':
    unittest.main()
