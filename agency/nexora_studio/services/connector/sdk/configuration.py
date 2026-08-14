"""
Connector SDK: Configuration
=============================
Part 2 of Phase 26.2 — Universal Connector Platform Refinement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from .context import ExecutionContext

class BaseConfigurationProvider(ABC):
    """
    Abstract base class for providing configuration validation and resolution.
    """

    @abstractmethod
    def validate_configuration(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate the raw configuration against the schema.
        Returns a list of error messages, empty if valid.
        """

    @abstractmethod
    def resolve_configuration(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Resolve the final configuration values for execution.
        """
