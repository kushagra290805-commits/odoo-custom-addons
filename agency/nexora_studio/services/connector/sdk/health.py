"""
Connector SDK: Health
======================
Part 2 of Phase 26.2 — Universal Connector Platform Refinement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from .context import ExecutionContext

class BaseHealthProvider(ABC):
    """
    Abstract base class for connector health monitoring and diagnostics.
    """

    @abstractmethod
    def check_health(self, context: ExecutionContext) -> Tuple[bool, str, float]:
        """
        Perform a health check on the connector.
        Returns a tuple of (is_healthy, error_detail, latency_ms).
        """

    @abstractmethod
    def get_diagnostics(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Return structured diagnostic information for debugging.
        """
