from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from odoo.addons.nexora_studio.services.generation.knowledge.models import KnowledgeDescriptor, KnowledgeChunk, KnowledgeQuery
from odoo.addons.nexora_studio.services.generation.knowledge.enums import ProviderType

class KnowledgeProvider(ABC):
    """
    Interface for Knowledge Providers.
    Follows exact same lifecycle pattern as Phase 18.6 ToolProvider.
    """
    
    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass
        
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        pass

    @abstractmethod
    def initialize(self) -> None:
        pass
        
    @abstractmethod
    def shutdown(self) -> None:
        pass
        
    @abstractmethod
    def health(self) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def capabilities(self) -> List[str]:
        pass
        
    @abstractmethod
    def metadata(self) -> List[KnowledgeDescriptor]:
        """Return descriptors for all available knowledge chunks from this provider."""
        pass
        
    @abstractmethod
    def fetch(self, query: KnowledgeQuery) -> List[KnowledgeChunk]:
        """Retrieve actual content chunks based on a structured query."""
        pass

class InternalTemplateStoreProvider(KnowledgeProvider):
    """Concrete provider for Odoo's internal template store."""
    
    @property
    def provider_id(self) -> str:
        return "odoo_internal_templates"
        
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.INTERNAL_TEMPLATE

    def initialize(self) -> None:
        pass
        
    def shutdown(self) -> None:
        pass
        
    def health(self) -> Dict[str, Any]:
        return {"status": "healthy"}
        
    def capabilities(self) -> List[str]:
        return ["templates", "components"]
        
    def metadata(self) -> List[KnowledgeDescriptor]:
        return []
        
    def fetch(self, query: KnowledgeQuery) -> List[KnowledgeChunk]:
        return []

# Scaffolded future providers
class FigmaProvider(KnowledgeProvider):
    @property
    def provider_id(self) -> str: return "figma_integration"
    @property
    def provider_type(self) -> ProviderType: return ProviderType.FIGMA
    def initialize(self) -> None: pass
    def shutdown(self) -> None: pass
    def health(self) -> Dict[str, Any]: return {"status": "unimplemented"}
    def capabilities(self) -> List[str]: return []
    def metadata(self) -> List[KnowledgeDescriptor]: return []
    def fetch(self, query: KnowledgeQuery) -> List[KnowledgeChunk]: return []

class GitHubProvider(KnowledgeProvider):
    @property
    def provider_id(self) -> str: return "github_integration"
    @property
    def provider_type(self) -> ProviderType: return ProviderType.GITHUB
    def initialize(self) -> None: pass
    def shutdown(self) -> None: pass
    def health(self) -> Dict[str, Any]: return {"status": "unimplemented"}
    def capabilities(self) -> List[str]: return []
    def metadata(self) -> List[KnowledgeDescriptor]: return []
    def fetch(self, query: KnowledgeQuery) -> List[KnowledgeChunk]: return []

class PenpotProvider(KnowledgeProvider):
    @property
    def provider_id(self) -> str: return "penpot_integration"
    @property
    def provider_type(self) -> ProviderType: return ProviderType.PENPOT
    def initialize(self) -> None: pass
    def shutdown(self) -> None: pass
    def health(self) -> Dict[str, Any]: return {"status": "unimplemented"}
    def capabilities(self) -> List[str]: return []
    def metadata(self) -> List[KnowledgeDescriptor]: return []
    def fetch(self, query: KnowledgeQuery) -> List[KnowledgeChunk]: return []

class MCPProvider(KnowledgeProvider):
    @property
    def provider_id(self) -> str: return "mcp_generic"
    @property
    def provider_type(self) -> ProviderType: return ProviderType.MCP
    def initialize(self) -> None: pass
    def shutdown(self) -> None: pass
    def health(self) -> Dict[str, Any]: return {"status": "unimplemented"}
    def capabilities(self) -> List[str]: return []
    def metadata(self) -> List[KnowledgeDescriptor]: return []
    def fetch(self, query: KnowledgeQuery) -> List[KnowledgeChunk]: return []

class LocalDocumentationProvider(KnowledgeProvider):
    @property
    def provider_id(self) -> str: return "local_docs"
    @property
    def provider_type(self) -> ProviderType: return ProviderType.LOCAL_DOCUMENTATION
    def initialize(self) -> None: pass
    def shutdown(self) -> None: pass
    def health(self) -> Dict[str, Any]: return {"status": "unimplemented"}
    def capabilities(self) -> List[str]: return []
    def metadata(self) -> List[KnowledgeDescriptor]: return []
    def fetch(self, query: KnowledgeQuery) -> List[KnowledgeChunk]: return []
