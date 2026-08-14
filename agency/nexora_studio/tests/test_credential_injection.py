from odoo.tests.common import TransactionCase, tagged
import os
import json
from unittest.mock import patch, MagicMock

from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import McpTransport
from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration

@tagged('standard', 'at_install')
class TestCredentialInjection(TransactionCase):
    
    def test_transport_injects_credentials_and_preserves_os_environ(self):
        """
        Verify that McpTransport explicitly merges its config.env with os.environ.
        """
        config = McpConfiguration(
            command="docker",
            args=["run", "-i", "--rm", "ghcr.io/github/github-mcp-server"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": "synthetic_test_token_123"}
        )
        
        transport = McpTransport(config)
        
        # We need to mock StdioServerParameters and stdio_client to avoid actually starting anything
        with patch('odoo.addons.nexora_studio.services.connector.connectors.mcp.transport.StdioServerParameters') as mock_params:
            # We mock stdio_client so it doesn't fail when entering context
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = (MagicMock(), MagicMock())
            with patch('odoo.addons.nexora_studio.services.connector.connectors.mcp.transport.stdio_client', return_value=mock_client):
                # Also mock ClientSession
                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.initialize = MagicMock()
                with patch('odoo.addons.nexora_studio.services.connector.connectors.mcp.transport.ClientSession', return_value=mock_session):
                    # We just want to run the _connect_and_wait method once
                    import asyncio
                    from concurrent.futures import Future
                    
                    ready_future = Future()
                    
                    loop = asyncio.new_event_loop()
                    transport._exit_event = asyncio.Event()
                    transport._exit_event.set() # Exit immediately
                    loop.run_until_complete(transport._connect_and_wait(ready_future))
                    loop.close()
                    
                    # Verify StdioServerParameters was called
                    self.assertTrue(mock_params.called, "StdioServerParameters was not called")
                    call_kwargs = mock_params.call_args.kwargs
                    
                    self.assertIn('env', call_kwargs)
                    process_env = call_kwargs['env']
                    
                    # Check our secret is injected
                    self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", process_env)
                    self.assertEqual(process_env["GITHUB_PERSONAL_ACCESS_TOKEN"], "synthetic_test_token_123")
                    
                    # Check OS environment was preserved (e.g. PATH or USERPROFILE)
                    # We can just check that a known os.environ key is present
                    test_key = next(iter(os.environ.keys()))
                    self.assertIn(test_key, process_env)
