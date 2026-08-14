# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseTransport(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        pass
        
    @abstractmethod
    def connect(self, config: Dict[str, Any]) -> bool:
        pass
        
    @abstractmethod
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        pass
        
    @abstractmethod
    def get_version(self) -> str:
        pass
