import os
from typing import Dict, Any, List

class LocalCliConfiguration:
    """Provides validated configuration for the Local CLI Connector."""
    
    def __init__(self, raw_config: Dict[str, Any]):
        self.working_directory: str = raw_config.get("working_directory", os.getcwd())
        if self.working_directory and not os.path.isdir(self.working_directory):
            raise ValueError(f"Invalid working directory: {self.working_directory}")
            
        self.allowed_executables: List[str] = raw_config.get("allowed_executables", [])
        self.default_timeout_seconds: float = float(raw_config.get("default_timeout_seconds", 60.0))
        if self.default_timeout_seconds < 0:
            raise ValueError("Timeout cannot be negative")
            
        self.max_output_size_bytes: int = int(raw_config.get("max_output_size_bytes", 1048576))
        self.shell: bool = bool(raw_config.get("shell", True))
        self.environment_variables: Dict[str, str] = raw_config.get("environment_variables", {})
        
    def is_executable_allowed(self, executable: str) -> bool:
        if not self.allowed_executables:
            return True
        return executable in self.allowed_executables
