import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Any, Callable
from .mcp_models import McpState, McpCapability, StartupPolicy, McpLifecycleEvent, McpMetrics
from .mcp_server_registry import McpServerRegistry
from .mcp_capability_catalog import McpCapabilityCatalog
from .mcp_client import McpClient
from .security_context import SecurityContext

logger = logging.getLogger(__name__)

class McpRuntimeManager:
    """
    Manages MCP lifecycle, client creation, active background health monitoring,
    and capability catalog orchestration.
    Does NOT handle tool execution.
    """
    def __init__(self, registry: McpServerRegistry, catalog: McpCapabilityCatalog):
        self.registry = registry
        self.catalog = catalog
        self.clients: Dict[str, McpClient] = {}
        self.metrics = McpMetrics()
        self._health_task: Optional[asyncio.Task] = None
        self._event_hooks: List[Callable[[McpLifecycleEvent, str], None]] = []
        self._running = False
        
    def add_event_hook(self, handler: Callable[[McpLifecycleEvent, str], None]) -> None:
        self._event_hooks.append(handler)
        
    def _emit(self, event: McpLifecycleEvent, mcp_id: str) -> None:
        for handler in self._event_hooks:
            try:
                handler(event, mcp_id)
            except Exception as e:
                logger.error(f"Error in MCP Event Hook: {e}")

    async def startup(self) -> None:
        """Load registry -> Instantiate -> Connect -> Discover -> Catalog"""
        start_time = time.time()
        self.registry.load()
        self._running = True
        
        for config in self.registry.get_enabled_servers():
            if config.startup_policy == StartupPolicy.DISABLED:
                continue
                
            client = McpClient(config)
            self.clients[config.id] = client
            
            try:
                await self._boot_client(client)
                self.metrics.active_sessions += 1
            except Exception as e:
                logger.error(f"Failed to start MCP {config.id}: {e}")
                self.metrics.total_errors += 1
                self.catalog.update_status(config.id, McpState.FAILED)
                self._emit(McpLifecycleEvent.MCP_FAILED, config.id)
                
                if config.startup_policy == StartupPolicy.REQUIRED:
                    raise RuntimeError(f"Required MCP {config.id} failed to start: {e}")
                    
        self.metrics.startup_time = time.time() - start_time
        
        # Start background health monitor
        self._health_task = asyncio.create_task(self._health_monitor_loop())
        
    async def _boot_client(self, client: McpClient) -> None:
        config = client.config
        await client.initialize()
        self._emit(McpLifecycleEvent.MCP_CONNECTED, config.id)
        
        tools = await client.discover_tools()
        self._emit(McpLifecycleEvent.MCP_DISCOVERED, config.id)
        
        for tool in tools:
            tool_name = tool.get("name", "")
            if SecurityContext.validate_capability(config, tool_name):
                cap = McpCapability(
                    mcp_id=config.id,
                    tool_name=tool_name,
                    description=tool.get("description", ""),
                    transport=config.transport,
                    runtime_status=McpState.READY,
                    tool_schema_hash=tool.get("tool_schema_hash", ""),
                    discovery_timestamp=time.time()
                )
                self.catalog.register_capability(cap)
                self.metrics.discovered_tools += 1
                
        self._emit(McpLifecycleEvent.MCP_READY, config.id)

    async def shutdown(self) -> None:
        """Graceful shutdown of all clients."""
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
                
        for client in self.clients.values():
            await client.shutdown()
            self._emit(McpLifecycleEvent.MCP_DISCONNECTED, client.config.id)
            
    async def _health_monitor_loop(self) -> None:
        while self._running:
            await asyncio.sleep(10.0) # Configurable heartbeat interval
            
            for mcp_id, client in self.clients.items():
                if client.state in (McpState.READY, McpState.BUSY):
                    is_healthy = await client.ping()
                    if not is_healthy:
                        logger.warning(f"MCP {mcp_id} failed ping. Marking for recovery.")
                        self._emit(McpLifecycleEvent.MCP_DISCONNECTED, mcp_id)
                        
                if client.state in (McpState.FAILED, McpState.RECOVERING):
                    # Exponential backoff jitter logic
                    self._emit(McpLifecycleEvent.MCP_RECOVERING, mcp_id)
                    jitter = random.uniform(0.5, 2.0)
                    await asyncio.sleep(jitter)
                    
                    try:
                        self.metrics.reconnect_count += 1
                        await client.reconnect()
                        # On successful reconnect, re-discover tools to refresh catalog
                        await self._boot_client(client)
                        logger.info(f"Successfully recovered MCP {mcp_id}")
                    except Exception as e:
                        logger.error(f"Recovery failed for MCP {mcp_id}: {e}")
                        self.metrics.total_errors += 1
                        self._emit(McpLifecycleEvent.MCP_FAILED, mcp_id)
