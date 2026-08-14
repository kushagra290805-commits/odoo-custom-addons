from typing import Dict, Any, List
from dataclasses import dataclass, field
import json

@dataclass
class DesignToken:
    name: str
    value: str
    token_type: str # 'color', 'spacing', 'radius', 'typography'
    semantic_role: str = ""

class DesignTokens:
    """
    Central repository for all raw and alias design tokens.
    """
    def __init__(self):
        self._tokens: Dict[str, DesignToken] = {}
        
    def register(self, token: DesignToken) -> None:
        self._tokens[token.name] = token
        
    def resolve(self, name: str) -> str:
        """Resolve an alias token down to its raw value."""
        if name not in self._tokens:
            return name
        token = self._tokens[name]
        # Very simple resolution for reference
        if token.value in self._tokens:
            return self.resolve(token.value)
        return token.value
