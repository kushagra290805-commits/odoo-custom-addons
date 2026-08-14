import asyncio
import threading
import logging
from typing import Dict, Any, List

from odoo.addons.nexora_studio.services.generation.platform.models import Runtime, RuntimeDescriptor, RuntimeType
from .mcp_runtime_manager import McpRuntimeManager
from .mcp_server_registry import McpServerRegistry
from .registry_provider import RegistryProvider
from .mcp_capability_catalog import McpCapabilityCatalog
from .mcp_tool_router import McpToolRouter

_logger = logging.getLogger(__name__)

class McpRuntimeAdapter(Runtime):
    """
    Bridge between synchronous Odoo PlatformRuntime and the asynchronous MCP Runtime Framework.
    Owns the background daemon thread and asyncio EventLoop for persistent MCP IO.
    """
    def __init__(self, provider: RegistryProvider):
        self._provider = provider
        self.registry = McpServerRegistry(provider=self._provider)
        self.catalog = McpCapabilityCatalog()
        self.manager = McpRuntimeManager(registry=self.registry, catalog=self.catalog)
        self.router = McpToolRouter(manager=self.manager, catalog=self.catalog)
        
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._descriptor = RuntimeDescriptor(
            runtime_id="mcp_runtime",
            name="MCP Provider Runtime",
            version="1.0",
            runtime_type=RuntimeType.TOOL,
            dependencies=[], # Add dependencies if necessary
            capabilities=[]
        )

    @property
    def descriptor(self) -> RuntimeDescriptor:
        # Dynamically update capabilities list from catalog
        self._descriptor.capabilities = list(self.catalog._capabilities.keys())
        return self._descriptor

    def initialize(self) -> None:
        """
        Synchronously boots the async manager in a daemon thread.
        """
        _logger.info("Initializing McpRuntimeAdapter...")
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="McpEventLoopThread")
        self._thread.start()
        
        # Block until startup completes
        future = asyncio.run_coroutine_threadsafe(self.manager.startup(), self._loop)
        try:
            future.result(timeout=60.0) # Wait for initial boot
            _logger.info("McpRuntimeAdapter initialized successfully.")
        except Exception as e:
            _logger.error(f"McpRuntimeAdapter initialization failed: {e}")
            raise RuntimeError(f"MCP Bootstrap failed: {e}")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    def shutdown(self) -> None:
        """
        Synchronously gracefully shuts down the async manager.
        """
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.manager.shutdown(), self._loop)
            try:
                future.result(timeout=15.0)
            except Exception as e:
                _logger.warning(f"Error shutting down manager: {e}")
            
            # Stop the loop
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5.0)
            _logger.info("McpRuntimeAdapter shutdown complete.")

    def health_status(self) -> Dict[str, Any]:
        """
        Aggregates health and metrics from the manager.
        """
        return {
            "status": "healthy" if self.manager.metrics.active_sessions > 0 else "degraded",
            "active_sessions": self.manager.metrics.active_sessions,
            "failed_sessions": self.manager.metrics.failed_sessions,
            "reconnect_count": self.manager.metrics.reconnect_count,
            "tool_calls": self.manager.metrics.tool_calls,
            "discovered_tools": self.manager.metrics.discovered_tools
        }
