"""
Connector Telemetry Interface
=============================
Phase 27.0 — Universal Connector Platform Production Hardening
An abstraction layer for tracking telemetry (counters and histograms).
"""
from abc import ABC, abstractmethod

class ConnectorTelemetryPort(ABC):
    """
    Interface for recording telemetry metrics.
    Concrete implementations can write to memory, Prometheus, Odoo, OpenTelemetry, etc.
    """
    
    @abstractmethod
    def record_counter(self, metric_name: str, value: int = 1, tags: dict = None) -> None:
        """
        Record a generic counter metric (e.g., registration_count, error_count).
        """
        pass

    @abstractmethod
    def record_histogram(self, metric_name: str, value: float, tags: dict = None) -> None:
        """
        Record a histogram or latency metric (e.g., dispatch_latency_ms).
        """
        pass
