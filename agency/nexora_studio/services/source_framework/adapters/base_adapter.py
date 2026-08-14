# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..domain_models import ComponentPackage
from ..transport.base_transport import BaseTransport

class BaseProviderAdapter(ABC):
    
    def __init__(self, transport: Optional[BaseTransport] = None, config: Optional[Dict[str, Any]] = None):
        self.transport = transport
        self.config = config or {}
        
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Return list of supported capabilities (e.g. SEARCH, PREVIEW, DOWNLOAD, DESIGN_TOKENS)"""
        pass
        
    @abstractmethod
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        pass
        
    @abstractmethod
    def get_component(self, component_id: str) -> ComponentPackage:
        pass
        
    @abstractmethod
    def get_metadata(self, component_id: str) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def get_preview(self, component_id: str) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def get_dependencies(self, component_id: str) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def get_license(self, component_id: str) -> str:
        pass
        
    @abstractmethod
    def get_installation_guide(self, component_id: str) -> str:
        pass
