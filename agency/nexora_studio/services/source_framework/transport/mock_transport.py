# -*- coding: utf-8 -*-
# LEGACY / NON-CANONICAL (Phase 44.2, W12, ADR-0068):
# Source-framework transport layer. Imported only by legacy
# source_framework/adapters/*; unreachable from the canonical connector
# runtime path. Do not wire new MCP work through it. Deletion deferred to
# Phase 44.3 with dependency proof.
from typing import Dict, Any, List
from .base_transport import BaseTransport

class MockTransport(BaseTransport):
    def __init__(self, mock_responses: Dict[str, Any]):
        self.mock_responses = mock_responses
        
    @property
    def capabilities(self) -> List[str]:
        return ['TOOL_CALL', 'MOCK']
        
    def connect(self, config: Dict[str, Any]) -> bool:
        return True
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if tool_name in self.mock_responses:
            return self.mock_responses[tool_name](arguments)
        raise Exception(f"Tool {tool_name} not mocked")
        
    def get_version(self) -> str:
        return "1.0-mock"
