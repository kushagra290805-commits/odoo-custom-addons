from abc import ABC, abstractmethod
from typing import Dict, Any

class BrowserValidationProvider(ABC):
    """
    Interface only for Browser Validation (Refinement 9).
    Playwright integration is deferred.
    """
    @abstractmethod
    def validate_url(self, url: str) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def check_accessibility(self, url: str) -> Dict[str, Any]:
        pass
