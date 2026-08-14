"""
In-Memory Telemetry Recorder
============================
Phase 27.0 — Universal Connector Platform Production Hardening
An in-memory implementation of the telemetry port for local tracking and testing.
"""
from typing import Dict, List
from odoo.addons.nexora_studio.services.connector.sdk.telemetry_port import ConnectorTelemetryPort

class InMemoryTelemetryRecorder(ConnectorTelemetryPort):
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.histograms: Dict[str, List[float]] = {}
        
    def record_counter(self, metric_name: str, value: int = 1, tags: dict = None) -> None:
        if metric_name not in self.counters:
            self.counters[metric_name] = 0
        self.counters[metric_name] += value
        
    def record_histogram(self, metric_name: str, value: float, tags: dict = None) -> None:
        if metric_name not in self.histograms:
            self.histograms[metric_name] = []
        self.histograms[metric_name].append(value)
        
    def get_counter(self, metric_name: str) -> int:
        return self.counters.get(metric_name, 0)
        
    def get_histogram_average(self, metric_name: str) -> float:
        values = self.histograms.get(metric_name, [])
        return sum(values) / len(values) if values else 0.0
