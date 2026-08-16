# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock

import httpx
from odoo.tests.common import TransactionCase
from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration
from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import McpTransport, QueryAuth

class TestMcpSseGenericTransport(unittest.TestCase):

    def test_query_auth_contract(self):
        """
        Verify that generic query authentication correctly applies the configured
        key-value pair to the request URL, independent of Penpot specifics.
        """
        auth = QueryAuth(key="testToken", value="secret123")

        request = httpx.Request("GET", "http://localhost/mcp/sse")

        flow_generator = auth.auth_flow(request)
        modified_request = next(flow_generator)

        self.assertIn("testToken=secret123", str(modified_request.url))
        self.assertNotIn("userToken", str(modified_request.url))
        self.assertNotIn("penpot", str(modified_request.url).lower())

    @patch('mcp.client.sse.sse_client')
    def test_sse_endpoint_authentication_persistence(self, mock_sse_client):
        """
        Verify that when transport is initialized with SSE, the query authentication
        is correctly passed down to the MCP SDK's sse_client without any
        hardcoded provider details.
        """
        config = McpConfiguration(
            transport="sse",
            command="http://generic-endpoint/mcp/sse",
            auth_location="query",
            auth_name="genericToken",
            auth_secret="genericSecret",
            args=[],
            env={},
            auth_scheme="none"
        )
        transport = McpTransport(config)

        # Test basic connection config logic
        import asyncio
        loop = asyncio.new_event_loop()

        async def run_transport():
            # We mock exit_event so it returns immediately
            transport._exit_event = asyncio.Event()
            transport._exit_event.set()

            from concurrent.futures import Future
            ready_future = Future()

            # Use a mock async context manager for sse_client
            mock_cm = MagicMock()
            mock_cm.__aenter__.return_value = (MagicMock(), MagicMock())
            mock_sse_client.return_value = mock_cm

            with patch('odoo.addons.nexora_studio.services.connector.connectors.mcp.transport.ClientSession') as mock_client_session:
                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__.return_value = MagicMock()
                mock_client_session.return_value = mock_session_cm

                await transport._connect_and_wait(ready_future)

            # Verify the call to sse_client
            mock_sse_client.assert_called_once()
            call_kwargs = mock_sse_client.call_args.kwargs

            self.assertEqual(call_kwargs['url'], "http://generic-endpoint/mcp/sse")
            self.assertIsNotNone(call_kwargs['auth'])
            self.assertEqual(call_kwargs['auth'].key, "genericToken")
            self.assertEqual(call_kwargs['auth'].value, "genericSecret")

        loop.run_until_complete(run_transport())
        loop.close()

    def test_stdio_still_supported(self):
        """
        Verify that stdio transport is still valid and has not been broken
        by the introduction of SSE.
        """
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
