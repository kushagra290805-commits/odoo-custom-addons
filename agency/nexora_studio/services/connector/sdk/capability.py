"""
Connector SDK: Capability
==========================
Part 2 of Phase 26.2 — Universal Connector Platform Refinement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from .context import ExecutionContext

class BaseCapabilityProvider(ABC):
    """
    Abstract base class for capability resolution and execution delegation.
    """

    @abstractmethod
    def list_capabilities(self, context: ExecutionContext) -> List[str]:
        """Return a list of capability namespaces provided."""

    @abstractmethod
    def has_capability(self, namespace: str, context: ExecutionContext) -> bool:
        """Check if a capability is provided."""

    @abstractmethod
    def execute(self, namespace: str, parameters: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Execute a capability.

        Args:
            namespace: The fully qualified capability namespace.
            parameters: Capability execution parameters.
            context: The execution context (auth, correlation IDs, etc.)

        Returns:
            Dict containing the execution result payload.

        Raises:
            ConnectorExecutionError if the capability is unsupported or fails.
        """
        pass
