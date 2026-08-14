from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class ToolCapability:
    """
    A generic capability abstraction. PlatformRuntime/Orchestrator will 
    decide if this routes to an MCP client, a mock, or a native function.
    """
    name: str
    description: str
    input_schema: Dict[str, Any]
    provider: str # e.g., "mcp:github", "native", "mcp:filesystem"
