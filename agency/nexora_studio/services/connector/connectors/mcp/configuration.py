from typing import List, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class McpConfiguration:
    """
    Configuration for an MCP connection via stdio.
    """
    command: str
    args: List[str] = field(default_factory=list)
    env: Optional[Dict[str, str]] = None
    trace_file: Optional[str] = None
    
    def __post_init__(self):
        # 1. Enforce strict arg tokenization
        if isinstance(self.args, str):
            import shlex
            self.args = shlex.split(self.args)
        elif not isinstance(self.args, list):
            raise ValueError(f"args must be a list of strings, got {type(self.args)}")
            
        for arg in self.args:
            if not isinstance(arg, str):
                raise ValueError(f"All args must be strings. Got {type(arg)} in {self.args}")

        # 2. Prevent path traversal in command
        if ".." in self.command:
            raise ValueError(f"Path traversal detected in command: {self.command}")
            
        # 3. Structural Security
        # We rely on anyio.open_process (shell=False) in McpTransport to guarantee
        # that the command and args are never executed through a shell.
        # Broad character blacklists are avoided to support legitimate MCP tool arguments.
