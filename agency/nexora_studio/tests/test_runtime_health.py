import unittest
import asyncio
from unittest.mock import MagicMock, patch

from odoo.addons.nexora_studio.services.runtime.mcp.mcp_runtime_adapter import McpRuntimeAdapter
from odoo.addons.nexora_studio.services.runtime.mcp.mcp_models import McpServerConfig, StartupPolicy, McpState
from odoo.addons.nexora_studio.services.generation.platform.platform_runtime import PlatformRuntime
from odoo.addons.nexora_studio.services.generation.platform.runtime_registry import RuntimeRegistry
from odoo.addons.nexora_studio.services.generation.platform.platform_health import PlatformHealthService

class MockRegistryProvider:
    def __init__(self, raw_config):
        self.raw_config = raw_config
        self.callbacks = []
    def get_raw_config(self):
        return self.raw_config
    def subscribe(self, cb):
        self.callbacks.append(cb)

class TestRuntimeHealth(unittest.TestCase):
    def setUp(self):
        self.registry = RuntimeRegistry()
        self.health = PlatformHealthService(self.registry)

    @patch('odoo.addons.nexora_studio.services.runtime.mcp.mcp_client.McpClient.ping')
    @patch('odoo.addons.nexora_studio.services.runtime.mcp.mcp_client.McpClient.reconnect')
    @patch('odoo.addons.nexora_studio.services.runtime.mcp.mcp_client.McpClient.initialize')
    @patch('odoo.addons.nexora_studio.services.runtime.mcp.mcp_client.McpClient.discover_tools')
    def test_health_monitor_recovery(self, mock_discover, mock_init, mock_reconnect, mock_ping):
        async def mock_async_init(): return None
        async def mock_async_discover(): return [{"name": "test_tool", "description": "test"}]
        
        # Ping fails first time, succeeds second time
        async def mock_async_ping(): 
            if mock_ping.call_count == 1:
                return False
            return True
            
        async def mock_async_reconnect(): return None

        mock_init.side_effect = mock_async_init
        mock_discover.side_effect = mock_async_discover
        mock_ping.side_effect = mock_async_ping
        mock_reconnect.side_effect = mock_async_reconnect

        provider = MockRegistryProvider({
            "test_mcp": {
                "startup_policy": "optional",
                "transport": "stdio"
            }
        })
        adapter = McpRuntimeAdapter(provider)
        self.registry.register_runtime(adapter)
        runtime = PlatformRuntime(self.registry, self.health)
        
        # Initialize
        runtime.initialize()
        
        # Wait a moment for background task to ping and recover
        import time
        time.sleep(0.5)
        
        # Check health status
        status = adapter.health_status()
        self.assertIn("active_sessions", status)
        
        runtime.shutdown()
