"""
Connector SDK Base
==================
Part 8 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from .context import ExecutionContext

class BaseConnector(ABC):
    """
    Abstract base class that all real connectors (MCP, GitHub, REST, etc.) must implement.
    The ConnectorDispatcher interacts with this interface.
    """

    @abstractmethod
    def initialize(self, context: ExecutionContext) -> None:
        """
        Called when the connector is first loaded.
        Use this to validate configuration and establish connections.
        """

    @abstractmethod
    def shutdown(self, context: ExecutionContext) -> None:
        """
        Called when the connector is disabled or the platform shuts down.
        Use this to release resources (close HTTP sessions, terminate subprocesses).
        """

    @abstractmethod
    def check_health(self, context: ExecutionContext) -> bool:
        """
        Perform a lightweight health check (e.g. ping the API).
        Returns True if healthy, False otherwise.
        """

    @abstractmethod
    def execute(
        self, 
        capability_namespace: str, 
        parameters: Dict[str, Any], 
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Execute a specific capability provided by this connector.
        
        Args:
            capability_namespace: The fully qualified capability name (e.g., 'search.web').
            parameters: The validated input payload for the capability.
            context: The execution context containing configuration and credentials.
            
        Returns:
            A dictionary matching the capability's output schema.
            
        Raises:
            ConnectorExecutionError if execution fails.
        """
