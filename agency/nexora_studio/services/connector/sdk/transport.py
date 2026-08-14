"""
Connector SDK: Transport
=========================
Part 2 of Phase 26.2 — Universal Connector Platform Refinement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from .context import ExecutionContext

class BaseTransport(ABC):
    """
    Abstract base class for connector transports (HTTP, gRPC, CLI, Stdio, etc).
    """

    @abstractmethod
    def connect(self, context: ExecutionContext) -> None:
        """Establish the underlying connection."""

    @abstractmethod
    def disconnect(self, context: ExecutionContext) -> None:
        """Tear down the connection."""

    @abstractmethod
    def send_request(self, payload: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Send a request over the transport and wait for a response."""
