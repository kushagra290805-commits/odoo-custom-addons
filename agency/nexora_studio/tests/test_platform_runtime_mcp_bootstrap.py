import unittest
import asyncio
from unittest.mock import MagicMock, patch

from odoo.addons.nexora_studio.services.runtime.mcp.mcp_runtime_adapter import McpRuntimeAdapter
from odoo.addons.nexora_studio.services.runtime.mcp.mcp_models import McpServerConfig, StartupPolicy, McpState
from odoo.addons.nexora_studio.services.generation.platform.models import RuntimeStartupPolicy
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

class TestPlatformRuntimeMcpBootstrap(unittest.TestCase):
    def setUp(self):
        self.registry = RuntimeRegistry()
        self.health = PlatformHealthService(self.registry)
        
    @patch('odoo.addons.nexora_studio.services.runtime.mcp.mcp_client.McpClient.initialize')
    @patch('odoo.addons.nexora_studio.services.runtime.mcp.mcp_client.McpClient.discover_tools')
    def test_successful_bootstrap_with_optional(self, mock_discover, mock_init):
        # Mocking async methods
        async def mock_async_init(): return None
        async def mock_async_discover(): return [{"name": "test_tool", "description": "test"}]
        mock_init.side_effect = mock_async_init
        mock_discover.side_effect = mock_async_discover

        provider = MockRegistryProvider({
            "test_mcp": {
                "startup_policy": "optional",
                "transport": "stdio",
                "startup_command": "dummy"
            }
        })
        adapter = McpRuntimeAdapter(provider)
        self.registry.register_runtime(adapter)
        
        runtime = PlatformRuntime(self.registry, self.health)
        
        # Test initialization
        success = runtime.initialize()
        self.assertTrue(success)
        
        capabilities = runtime.list_capabilities()
        self.assertIn("test_tool", capabilities)
        
        # Cleanup
        runtime.shutdown()
        
    @patch('odoo.addons.nexora_studio.services.runtime.mcp.mcp_client.McpClient.initialize')
    def test_failed_bootstrap_with_required(self, mock_init):
        async def mock_async_fail(): raise Exception("Mock connection failed")
        mock_init.side_effect = mock_async_fail

        provider = MockRegistryProvider({
            "test_mcp": {
                "startup_policy": "required",
                "transport": "stdio"
            }
        })
        adapter = McpRuntimeAdapter(provider)
        self.registry.register_runtime(adapter)
        
        runtime = PlatformRuntime(self.registry, self.health)
        
        # Test initialization should fail because policy is REQUIRED and init raised
        with self.assertRaises(RuntimeError):
            # McpRuntimeAdapter throws RuntimeError if boot fails
            runtime.initialize()
