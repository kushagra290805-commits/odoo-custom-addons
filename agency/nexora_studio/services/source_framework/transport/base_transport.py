# -*- coding: utf-8 -*-
# LEGACY / NON-CANONICAL (Phase 44.2, W12, ADR-0068):
# Source-framework transport layer. Imported only by legacy
# source_framework/adapters/*; unreachable from the canonical connector
# runtime path. Do not wire new MCP work through it. Deletion deferred to
# Phase 44.3 with dependency proof.
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
