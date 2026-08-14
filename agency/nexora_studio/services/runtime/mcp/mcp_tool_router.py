from typing import Dict, Any
from .mcp_runtime_manager import McpRuntimeManager
from .mcp_capability_catalog import McpCapabilityCatalog
from .security_context import SecurityContext

class McpToolRouter:
    """
    Routing layer between ToolCapability and RuntimeManager.
    Handles Tool selection, conflict resolution, fallback, and tool execution.
    """
    def __init__(self, manager: McpRuntimeManager, catalog: McpCapabilityCatalog):
        self.manager = manager
        self.catalog = catalog
        
    async def execute_capability(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Executes a tool by finding the best available capability in the catalog.
        PlatformRuntime should never communicate directly with the Runtime Manager.
        """
        # 1. Selection & Conflict Resolution
        cap = self.catalog.get_preferred_capability(tool_name)
        if not cap:
            raise RuntimeError(f"No available MCP provider for tool: {tool_name}")
            
        # 2. Execution & Fallback loop
        try:
            client = self.manager.clients.get(cap.mcp_id)
            if not client:
                raise ValueError(f"Unknown MCP server: {cap.mcp_id}")
                
            if cap.mcp_id == "filesystem_mcp":
                SecurityContext.validate_filesystem_args(args)
                
            # Log tool call metric
            self.manager.metrics.tool_calls += 1
            
            return await client.call_tool(tool_name, args)
        except Exception as e:
            # Fallback routing logic could be implemented here to try next priority
            # For now, simply raise
            raise RuntimeError(f"Tool {tool_name} failed on {cap.mcp_id}: {str(e)}")
