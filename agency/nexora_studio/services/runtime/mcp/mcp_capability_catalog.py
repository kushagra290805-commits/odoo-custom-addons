from typing import Dict, List, Optional
from .mcp_models import McpCapability, McpState

class McpCapabilityCatalog:
    """
    Maintains metadata for every dynamically discovered tool across all connected MCPs.
    PlatformRuntime queries this catalog before invoking tools.
    """
    def __init__(self):
        # Maps tool_name -> list of capabilities (potentially multiple MCPs expose same tool)
        self._capabilities: Dict[str, List[McpCapability]] = {}
        
    def register_capability(self, capability: McpCapability) -> None:
        if capability.tool_name not in self._capabilities:
            self._capabilities[capability.tool_name] = []
        self._capabilities[capability.tool_name].append(capability)
        
        # Sort by priority (higher priority first)
        self._capabilities[capability.tool_name].sort(key=lambda x: x.priority, reverse=True)
        
    def get_capabilities(self, tool_name: str) -> List[McpCapability]:
        """Returns all capabilities matching the tool name, sorted by priority."""
        return self._capabilities.get(tool_name, [])
        
    def get_preferred_capability(self, tool_name: str) -> Optional[McpCapability]:
        """Returns the highest priority available capability for a tool."""
        caps = self.get_capabilities(tool_name)
        for cap in caps:
            if cap.runtime_status in (McpState.READY, McpState.REGISTERED):
                return cap
        return None
        
    def update_status(self, mcp_id: str, new_status: McpState) -> None:
        """Updates the status of all capabilities belonging to a specific MCP."""
        for tool_list in self._capabilities.values():
            for cap in tool_list:
                if cap.mcp_id == mcp_id:
                    cap.runtime_status = new_status
