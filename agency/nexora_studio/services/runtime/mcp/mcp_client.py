import asyncio
from typing import Dict, Any, List
from .mcp_models import McpServerConfig, McpState
from .transports import McpTransport, StdioTransport, SSETransport

class McpClient:
    """
    Wraps the official mcp ClientSession and handles execution.
    """
    def __init__(self, config: McpServerConfig):
        self.config = config
        self.state = McpState.REGISTERED
        self.transport: McpTransport = self._build_transport()
        self.session = None
        
    def _build_transport(self) -> McpTransport:
        if self.config.transport == "stdio":
            return StdioTransport(
                command=self.config.startup_command,
                args=self.config.startup_args,
                env=self.config.environment_variables,
                cwd=self.config.cwd
            )
        elif self.config.transport == "sse":
            # Assuming startup_command holds the URL for SSE, or it's in env
            url = self.config.environment_variables.get("SERVER_URL", "")
            return SSETransport(url=url)
        raise ValueError(f"Unknown transport: {self.config.transport}")
        
    async def initialize(self) -> None:
        self.state = McpState.INITIALIZING
        from mcp.client.session import ClientSession
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        try:
            await self.transport.connect()
            read, write = self.transport.get_read_write_streams()
            
            self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            self.state = McpState.READY
        except Exception:
            self.state = McpState.FAILED
            raise
            
    async def discover_tools(self) -> List[Dict[str, Any]]:
        if self.state != McpState.READY:
            return []
        res = await self.session.list_tools()
        tools = []
        import hashlib
        for t in res.tools:
            # We'll use hashlib to generate a basic schema hash for versioning diffs
            schema_str = getattr(t, "description", "") + t.name
            schema_hash = hashlib.md5(schema_str.encode('utf-8')).hexdigest()
            tools.append({
                "name": t.name,
                "description": getattr(t, "description", ""),
                "tool_schema_hash": schema_hash
            })
        return tools
        
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        self.state = McpState.BUSY
        try:
            result = await self.session.call_tool(tool_name, args)
            self.state = McpState.READY
            
            # Format SDK output
            content = []
            for item in getattr(result, "content", []):
                if getattr(item, "type", "") == "text":
                    content.append(item.text)
                else:
                    content.append(str(item))
            return {"status": "success", "content": content}
        except Exception:
            self.state = McpState.FAILED
            raise

    async def ping(self) -> bool:
        """Ping the server to check health."""
        if self.state not in (McpState.READY, McpState.BUSY):
            return False
        try:
            # Using list_tools as a lightweight ping since MCP lacks a native ping right now
            await self.session.list_tools()
            return True
        except Exception:
            self.state = McpState.FAILED
            return False
            
    async def reconnect(self) -> None:
        """Attempt to reconnect to the server."""
        self.state = McpState.RECOVERING
        try:
            await self.shutdown()
        except Exception:
            pass
            
        self.transport = self._build_transport()
        await self.initialize()
            
    async def shutdown(self) -> None:
        if hasattr(self, '_exit_stack'):
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
        if self.transport:
            try:
                await self.transport.disconnect()
            except Exception:
                pass
        self.state = McpState.DISABLED
