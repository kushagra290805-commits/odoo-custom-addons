from abc import ABC, abstractmethod
from typing import Dict, Any

class ProviderInterface(ABC):
    """
    Abstract Base Class for all external integrations.
    Ensures safe lifecycle management and stateless execution.
    """
    @abstractmethod
    def initialize(self) -> None:
        """Called upon registry load or first invocation."""
        pass
        
    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Returns the health status and latency of the provider."""
        pass
        
    @abstractmethod
    def shutdown(self) -> None:
        """Called during platform teardown to release resources."""
        pass
        
    @abstractmethod
    def execute(self, request: 'ProviderExecutionRequest') -> 'ProviderExecutionResult':
        """
        Canonical execution boundary (ADR-0044).
        During migration, fallback signatures may be invoked via *args, **kwargs.
        """
        raise NotImplementedError("Providers must implement the canonical execute(request) method")
