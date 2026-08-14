import os
from typing import Dict, Any, List
from .mcp_models import McpServerConfig, McpCapability

class SecurityContext:
    """
    Enforces security sandboxing and capability allow-listing.
    """
    APPROVED_PATHS = [
        "workspace/",
        "generated/",
        "assets/",
        "templates/",
        "scratch/"
    ]
    
    @classmethod
    def validate_capability(cls, config: McpServerConfig, tool_name: str) -> bool:
        """Checks if a discovered tool is allowed by the server's registry filters."""
        if not config.capability_filters:
            # If no filters exist, assume all discovered tools are allowed for this server.
            return True
            
        for f in config.capability_filters:
            if tool_name.startswith(f) or tool_name == f or f == "*":
                return True
        return False
        
    @classmethod
    def validate_filesystem_args(cls, args: Dict[str, Any]) -> None:
        """
        Explicitly block access outside sandbox locations for Filesystem operations.
        Raises SecurityError if violation is detected.
        """
        for k, v in args.items():
            if isinstance(v, str) and ("/" in v or "\\" in v):
                # Simple check for path arguments
                v_normalized = v.replace("\\", "/").strip("/")
                
                # Check for path traversal
                if ".." in v_normalized:
                    raise PermissionError(f"Path traversal detected in argument: {k}={v}")
                    
                # Check if it starts with an approved path
                approved = any(v_normalized.startswith(p.strip("/")) for p in cls.APPROVED_PATHS)
                if not approved:
                    raise PermissionError(f"Path outside sandbox detected: {v}. Allowed: {cls.APPROVED_PATHS}")
