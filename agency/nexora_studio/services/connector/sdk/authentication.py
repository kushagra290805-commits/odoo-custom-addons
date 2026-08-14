"""
Connector SDK: Authentication
==============================
Part 2 of Phase 26.2 — Universal Connector Platform Refinement.
"""
from abc import ABC, abstractmethod
from .context import ExecutionContext

class BaseAuthenticationProvider(ABC):
    """
    Abstract base class for credential resolution and session management.
    """

    @abstractmethod
    def authenticate(self, context: ExecutionContext) -> bool:
        """
        Perform authentication using the context credentials.
        Returns True if successful.
        """

    @abstractmethod
    def refresh_session(self, context: ExecutionContext) -> bool:
        """
        Refresh an expired session.
        """

    @abstractmethod
    def revoke_session(self, context: ExecutionContext) -> None:
        """
        Revoke the active session.
        """
