# -*- coding: utf-8 -*-
import warnings
from typing import Dict, Any, Optional

warnings.warn("Source Framework TransportFactory is deprecated for MCP in Phase 29.", DeprecationWarning)
from .base_transport import BaseTransport
from .mcp_transport import MCPTransport
from .mock_transport import MockTransport

class TransportFactory:
    @staticmethod
    def create_transport(transport_type: str, env: Any, mock_responses: Optional[Dict[str, Any]] = None) -> BaseTransport:
        if transport_type == 'mcp':
            # Assuming env has access to mcp_service
            mcp_runtime = env['nexora.mcp_service'] if env else None
            return MCPTransport(mcp_runtime)
        elif transport_type == 'mock':
            return MockTransport(mock_responses or {})
        else:
            raise ValueError(f"Unknown transport type: {transport_type}")
