from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class GenerationMetrics:
    """
    Lightweight service capturing generation telemetry.
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider: str = ""
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    retry_count: int = 0
    cache_hit: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
class MetricsCollector:
    def __init__(self):
        self._metrics = []
        
    def record(self, metric: GenerationMetrics):
        self._metrics.append(metric)
        
    def get_summary(self) -> dict:
        total_cost = sum(m.cost_usd for m in self._metrics)
        total_latency = sum(m.latency_ms for m in self._metrics)
        return {
            "total_calls": len(self._metrics),
            "total_cost": total_cost,
            "total_latency_ms": total_latency
        }
