import asyncio
import threading
from typing import Optional, Any, Dict
from concurrent.futures import Future

from anyio.abc import ObjectReceiveStream, ObjectSendStream
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

class TraceReceiveStream(ObjectReceiveStream):
    def __init__(self, stream, trace_file):
        self._stream = stream
        self._trace_file = trace_file

    async def receive(self):
        msg = await self._stream.receive()
        with open(self._trace_file, "a") as f:
            f.write(f"<- {msg}\n")
        return msg

    async def aclose(self):
        await self._stream.aclose()

class TraceSendStream(ObjectSendStream):
    def __init__(self, stream, trace_file):
        self._stream = stream
        self._trace_file = trace_file

    async def send(self, msg):
        with open(self._trace_file, "a") as f:
            f.write(f"-> {msg}\n")
        await self._stream.send(msg)

    async def aclose(self):
        await self._stream.aclose()

from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import RuntimeException, TimeoutException
from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
import sys
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
# Must be the same httpx that the MCP SDK validates `auth` against: mcp.client.sse
# type-checks `isinstance(auth, httpx.Auth)`, so aliasing httpx2 here would make
# QueryAuth subclass a foreign base class and be rejected as an invalid auth argument.
import httpx

_logger = get_logger(__name__)

@dataclass
class TransportBinding:
    location: str
    name: str
    value: str

class QueryAuth(httpx.Auth):
    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value

    def auth_flow(self, request: httpx.Request):
        request.url = request.url.copy_merge_params({self.key: self.value})
        yield request

class McpTransport:
    """
    Synchronous transport adapter that wraps the official async MCP Python SDK.
    Runs the MCP event loop in a dedicated background thread.
    """
    def __init__(self, config: McpConfiguration, transport_binding: Optional[TransportBinding] = None):
        self.config = config
        self.transport_binding = transport_binding
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[ClientSession] = None
        self._exit_event: Optional[asyncio.Event] = None

        # We need to keep a reference to the context managers so we can exit them
        self._cm_stack = []

    def _run_event_loop(self, ready_future: Future):
        """Runs in the background thread."""
        import sys
        if sys.platform == 'win32':
            # Force SelectorEventLoop to trigger mcp's fallback to subprocess.Popen.
            # ProactorEventLoop in background threads crashes with WinError 87 when spawning Docker.
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)

        self._exit_event = asyncio.Event()
        loop.run_until_complete(self._connect_and_wait(ready_future))
        loop.close()

    async def _connect_and_wait(self, ready_future: Future):
        try:
            if self.config.transport == 'stdio':
                import os
                process_env = os.environ.copy()
                if self.config.env:
                    process_env.update(self.config.env)

                server_params = StdioServerParameters(
                    command=self.config.command,
                    args=self.config.args,
                    env=process_env,
                    # Phase 44.2 (W8): honor the operator-configured working
                    # directory for the stdio MCP server process.
                    cwd=self.config.working_directory
                )

                async with stdio_client(server_params) as (read, write):
                    if self.config.trace_file:
                        read = TraceReceiveStream(read, self.config.trace_file)
                        write = TraceSendStream(write, self.config.trace_file)

                    async with ClientSession(read, write) as session:
                        self._session = session
                        await session.initialize()
                        ready_future.set_result(True)

                        # Keep the context managers open until exit is requested
                        await self._exit_event.wait()

            elif self.config.transport == 'sse':
                from mcp.client.sse import sse_client
                import urllib.parse

                url = self.config.command
                headers = {}
                auth = None

                # Apply generic authentication
                if self.config.auth_location != 'none' and self.config.auth_name and self.config.auth_secret:
                    if self.config.auth_location == 'header':
                        auth_val = self.config.auth_secret
                        if self.config.auth_scheme and self.config.auth_scheme != 'none':
                            scheme = self.config.auth_scheme.capitalize()
                            auth_val = f"{scheme} {auth_val}"
                        headers[self.config.auth_name] = auth_val
                    elif self.config.auth_location == 'query':
                        auth = QueryAuth(self.config.auth_name, self.config.auth_secret)
                        
                # Apply ephemeral transport binding
                if self.transport_binding:
                    if self.transport_binding.location == 'header':
                        headers[self.transport_binding.name] = self.transport_binding.value
                    elif self.transport_binding.location == 'query':
                        parsed = urllib.parse.urlparse(url)
                        query = dict(urllib.parse.parse_qsl(parsed.query))
                        query[self.transport_binding.name] = self.transport_binding.value
                        parsed = parsed._replace(query=urllib.parse.urlencode(query))
                        url = urllib.parse.urlunparse(parsed)

                async with sse_client(url=url, headers=headers if headers else None, auth=auth) as (read, write):
                    if self.config.trace_file:
                        read = TraceReceiveStream(read, self.config.trace_file)
                        write = TraceSendStream(write, self.config.trace_file)

                    async with ClientSession(read, write) as session:
                        self._session = session
                        await session.initialize()
                        ready_future.set_result(True)

                        # Keep the context managers open until exit is requested
                        await self._exit_event.wait()
            else:
                raise ValueError(f"Unsupported transport: {self.config.transport}")


        except Exception as e:
            if not ready_future.done():
                ready_future.set_exception(e)
            else:
                # Phase 44.2 (W14): the connection died AFTER the handshake
                # succeeded. Do not leave a stale session behind — mark the
                # transport disconnected so subsequent calls fail loudly
                # (TRANSPORT_DISCONNECTED) instead of operating on a dead
                # session. is_connected() also checks thread liveness, but
                # clearing the session makes the state truthful explicitly.
                _logger.error(
                    "MCP connection lost after handshake: %s", e,
                    exc_info=True,
                )
                self._session = None

    def connect(self, context: ExecutionContext = None) -> None:
        if self.is_connected():
            return

        ready_future = Future()
        self._thread = threading.Thread(target=self._run_event_loop, args=(ready_future,), daemon=True)
        self._thread.start()

        try:
            # Phase 44.2 (W8): honor the configured timeout for the handshake.
            ready_future.result(timeout=float(self.config.timeout_seconds))
        except Exception as e:
            self.disconnect()
            raise RuntimeException(
                error_code="TRANSPORT_CONNECT_FAILED",
                user_safe_message="Failed to connect to MCP server.",
                technical_message=f"MCP connection failed: {str(e)}"
            )

    def disconnect(self, context: ExecutionContext = None) -> None:
        if self._loop and self._loop.is_running() and self._exit_event:
            self._loop.call_soon_threadsafe(self._exit_event.set)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._session = None
        self._loop = None
        self._thread = None

    def is_connected(self) -> bool:
        return self._session is not None and self._thread is not None and self._thread.is_alive()

    def _run_sync(self, coro, timeout: Optional[float] = None):
        if not self.is_connected():
            raise RuntimeException("TRANSPORT_DISCONNECTED", "MCP Transport is not connected.", "Cannot execute request.")

        # Phase 44.2 (W8): default to the operator-configured request timeout.
        if timeout is None:
            timeout = float(self.config.timeout_seconds)

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            raise TimeoutException(
                error_code="TRANSPORT_TIMEOUT",
                user_safe_message="MCP request timed out.",
                technical_message=f"Request exceeded {timeout} seconds."
            )
        except Exception as e:
            raise RuntimeException(
                error_code="TRANSPORT_ERROR",
                user_safe_message="MCP request failed.",
                technical_message=str(e)
            )

    # =========================================================================
    # MCP Protocol Wrappers
    # =========================================================================

    def list_tools(self) -> Any:
        return self._run_sync(self._session.list_tools())

    def call_tool(self, name: str, arguments: dict, request_context: Optional[dict] = None) -> Any:
        if not self._session:
            raise RuntimeException("TRANSPORT_NOT_CONNECTED", "MCP session is not established.", "self._session is None")
        
        meta = None
        if request_context and self.config.allowed_request_context_fields:
            meta = {}
            for field in self.config.allowed_request_context_fields:
                if field in request_context:
                    meta[field] = request_context[field]
            if not meta:
                meta = None
                
        if meta:
            # Note: SDK session.call_tool kwargs require `meta` as a keyword argument
            return self._run_sync(self._session.call_tool(name, arguments, meta=meta))
        else:
            return self._run_sync(self._session.call_tool(name, arguments))

    def list_resources(self) -> Any:
        return self._run_sync(self._session.list_resources())

    def read_resource(self, uri: str) -> Any:
        return self._run_sync(self._session.read_resource(uri))

    def list_prompts(self) -> Any:
        return self._run_sync(self._session.list_prompts())

    def get_prompt(self, name: str, arguments: dict) -> Any:
        return self._run_sync(self._session.get_prompt(name, arguments))
