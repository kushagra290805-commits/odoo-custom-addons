from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from odoo.addons.nexora_studio.services.generation.tools.tool_descriptor import ToolDescriptor
from odoo.addons.nexora_studio.services.generation.tools.tool_result import ToolExecutionResult
from odoo.addons.nexora_studio.services.generation.tools.tool_execution_context import ToolExecutionContext

class BaseTool(ABC):
    """Base class containing actual execution logic for a specific tool."""
    
    @abstractmethod
    def execute(self, payload: Dict[str, Any], context: ToolExecutionContext, scoped_runtime: Any) -> ToolExecutionResult:
        """Executes the tool logic within the runtime boundaries."""
        pass


class ToolProvider(ABC):
    """
    Interface for Tool Providers. 
    Manages a collection of tools and exposes health monitoring.
    """
    
    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass
        
    @abstractmethod
    def initialize(self) -> None:
        """Initialize provider connections (e.g., spin up MCP server connection)."""
        pass
        
    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup resources."""
        pass
        
    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Return provider health status (e.g., {'status': 'healthy', 'latency': 45})."""
        pass
        
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Return overarching capabilities supported by this provider."""
        pass
        
    @abstractmethod
    def tools(self) -> List[ToolDescriptor]:
        """Return metadata descriptors for all tools exposed by this provider."""
        pass
        
    @abstractmethod
    def get_tool(self, tool_id: str) -> Optional[BaseTool]:
        """Resolve a tool ID to its execution class."""
        pass
