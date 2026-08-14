from abc import ABC, abstractmethod
import asyncio
from typing import Dict, Any, Optional

class McpTransport(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        pass
        
    @abstractmethod
    def get_read_write_streams(self) -> tuple:
        pass

from mcp.client.stdio import stdio_client, StdioServerParameters

class StdioTransport(McpTransport):
    """
    Wraps the stdio_client from the official mcp python sdk.
    """
    def __init__(self, command: str, args: list, env: dict, cwd: str = None):
        self.command = command
        self.args = args
        self.env = env
        self.cwd = cwd
        self._ctx = None
        self._read = None
        self._write = None
        
    async def connect(self) -> None:
        import os
        merged_env = os.environ.copy()
        merged_env.update(self.env)
        
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=merged_env,
            cwd=self.cwd
        )
        
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        self._read, self._write = await self._exit_stack.enter_async_context(stdio_client(server_params))
        
    async def disconnect(self) -> None:
        if hasattr(self, '_exit_stack'):
            await self._exit_stack.aclose()
        self._read = None
        self._write = None
        
    def get_read_write_streams(self) -> tuple:
        return (self._read, self._write)

class SSETransport(McpTransport):
    def __init__(self, url: str):
        self.url = url
        self._read = None
        self._write = None
        
    async def connect(self) -> None:
        class MockStream:
            pass
        self._read = MockStream()
        self._write = MockStream()
        
    async def disconnect(self) -> None:
        self._read = None
        self._write = None
        
    def get_read_write_streams(self) -> tuple:
        return (self._read, self._write)
