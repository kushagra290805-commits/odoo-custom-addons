# -*- coding: utf-8 -*-
import warnings
from typing import Dict, Any, List
from .base_transport import BaseTransport

warnings.warn("MCPTransport is deprecated and obsolete in Phase 29. Use Phase 28 ConnectorRuntime instead.", DeprecationWarning)

class MCPTransport(BaseTransport):
    def __init__(self, mcp_runtime):
        self.mcp_runtime = mcp_runtime
        
    @property
    def capabilities(self) -> List[str]:
        return ['TOOL_CALL', 'RESOURCE_READ']
        
    def connect(self, config: Dict[str, Any]) -> bool:
        # Pseudo connection logic to MCP runtime
        return True
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if hasattr(self.mcp_runtime, 'env'):
            env = self.mcp_runtime.env
            if env['ir.config_parameter'].sudo().get_param('agency.use_unified_provider_platform', 'False') == 'True':
                from odoo.addons.nexora_studio.services.providers.container import GLOBAL_CONTAINER
                from odoo.addons.nexora_studio.services.providers.base_provider import (
                    ExecutionOrchestrator, ProviderSession, ProviderCategory, ProviderFeatureSet
                )
                if GLOBAL_CONTAINER:
                    orch = GLOBAL_CONTAINER.resolve(ExecutionOrchestrator)
                    session = ProviderSession(
                        session_id="mcp_transport",
                        user_id=env.uid,
                        workspace_path="/tmp",
                        provider=None,
                        auth=None,
                        config={},
                        sandbox=None,
                        quota=None,
                        cost_budget_usd=1.0,
                        metadata={}
                    )
                    payload = {
                        "tool_name": tool_name,
                        "arguments": arguments
                    }
                    features = ProviderFeatureSet(
                        supports_streaming=False,
                        supports_tool_calling=True,
                        supports_vision=False
                    )
                    res = orch.execute(ProviderCategory.MCP, "mcp_tool_call", payload, features, session)
                    if not res.success:
                        raise Exception(f"Unified MCP Error: {res.error}")
                    return res.data

        # Fallback to legacy execution (using proper execute_tool_safely since call_tool didn't exist)
        # Note: runtime is required, we'll pass an empty/mock runtime for the legacy path
        class DummyRuntime:
            builder_session_id = False
        return self.mcp_runtime.execute_tool_safely(DummyRuntime(), tool_name, {}, **arguments)
        
    def get_version(self) -> str:
        return "1.0-mcp"
