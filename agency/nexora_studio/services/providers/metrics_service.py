import logging
import threading
from collections import deque
from datetime import datetime
from typing import Dict, List

from .base_provider import (
    ProviderMetricsService,
    ProviderMetricsSnapshot,
    ExecutionPolicy,
    ProviderEventBus,
    ProviderEvent,
    ProviderEventChannel,
    ProviderServiceContainer
)

_logger = logging.getLogger(__name__)

class MetricRecord:
    def __init__(self, latency_ms: float, success: bool, is_fallback: bool, is_retry: bool):
        self.timestamp = datetime.utcnow()
        self.latency_ms = latency_ms
        self.success = success
        self.is_fallback = is_fallback
        self.is_retry = is_retry

class OdooProviderMetricsService(ProviderMetricsService):
    """
    Tracks and aggregates provider metrics over a rolling window.
    Publishes METRICS events at regular intervals.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container
        # Store up to 18000 records per provider (~5 mins @ 60 RPS)
        self._history: Dict[str, deque[MetricRecord]] = {}
        self._cache_hits: Dict[str, int] = {}
        self._cache_misses: Dict[str, int] = {}
        self._selection_counts: Dict[str, int] = {}
        self._lock = threading.Lock()

    @property
    def _event_bus(self) -> ProviderEventBus:
        return self._container.resolve(ProviderEventBus)

    def record_request(self, provider_id: str, latency_ms: float, success: bool, is_fallback: bool, is_retry: bool) -> None:
        record = MetricRecord(latency_ms, success, is_fallback, is_retry)
        
        with self._lock:
            if provider_id not in self._history:
                self._history[provider_id] = deque(maxlen=18000)
            self._history[provider_id].append(record)

    def record_cache_event(self, provider_id: str, hit: bool, level: int) -> None:
        with self._lock:
            if provider_id not in self._cache_hits:
                self._cache_hits[provider_id] = 0
                self._cache_misses[provider_id] = 0
                
            if hit:
                self._cache_hits[provider_id] += 1
            else:
                self._cache_misses[provider_id] += 1

    def record_selection(self, provider_id: str, policy: ExecutionPolicy) -> None:
        with self._lock:
            self._selection_counts[provider_id] = self._selection_counts.get(provider_id, 0) + 1

    def get_snapshot(self, provider_id: str, window_seconds: int = 300) -> ProviderMetricsSnapshot:
        with self._lock:
            history = list(self._history.get(provider_id, []))
            c_hits = self._cache_hits.get(provider_id, 0)
            c_misses = self._cache_misses.get(provider_id, 0)
            selections = self._selection_counts.get(provider_id, 0)
            
        now = datetime.utcnow()
        # Filter records within window
        recent = [r for r in history if (now - r.timestamp).total_seconds() <= window_seconds]
        
        total = len(recent)
        if total == 0:
            return ProviderMetricsSnapshot(
                provider_id=provider_id, window_seconds=window_seconds,
                request_count=0, success_count=0, error_count=0,
                fallback_count=0, retry_count=0,
                avg_latency_ms=0.0, p50_latency_ms=0.0, p95_latency_ms=0.0, p99_latency_ms=0.0,
                cache_hit_count=c_hits, cache_miss_count=c_misses,
                cache_hit_ratio=(c_hits / (c_hits + c_misses)) if (c_hits + c_misses) > 0 else 0.0,
                selection_count=selections,
                total_tokens_consumed=0, total_asset_bytes_consumed=0,
                concurrent_executions=0, utilization_pct=0.0
            )

        successes = sum(1 for r in recent if r.success)
        errors = total - successes
        fallbacks = sum(1 for r in recent if r.is_fallback)
        retries = sum(1 for r in recent if r.is_retry)
        
        latencies = sorted([r.latency_ms for r in recent])
        avg_lat = sum(latencies) / total
        
        def percentile(p):
            idx = int(total * p)
            return latencies[idx] if idx < total else latencies[-1]
            
        c_ratio = (c_hits / (c_hits + c_misses)) if (c_hits + c_misses) > 0 else 0.0

        return ProviderMetricsSnapshot(
            provider_id=provider_id, window_seconds=window_seconds,
            request_count=total, success_count=successes, error_count=errors,
            fallback_count=fallbacks, retry_count=retries,
            avg_latency_ms=avg_lat, 
            p50_latency_ms=percentile(0.50), 
            p95_latency_ms=percentile(0.95), 
            p99_latency_ms=percentile(0.99),
            cache_hit_count=c_hits, cache_miss_count=c_misses, cache_hit_ratio=c_ratio,
            selection_count=selections,
            total_tokens_consumed=0, # Would be updated from cost quota service
            total_asset_bytes_consumed=0,
            concurrent_executions=0, utilization_pct=0.0
        )

    def get_all_snapshots(self, window_seconds: int = 300) -> List[ProviderMetricsSnapshot]:
        with self._lock:
            providers = list(self._history.keys())
        return [self.get_snapshot(p, window_seconds) for p in providers]

    def reset(self, provider_id: str) -> None:
        with self._lock:
            if provider_id in self._history:
                self._history[provider_id].clear()
            self._cache_hits[provider_id] = 0
            self._cache_misses[provider_id] = 0
            self._selection_counts[provider_id] = 0
            
    def publish_snapshots(self) -> None:
        """
        Intended to be called by Odoo cron every 60s.
        """
        snapshots = self.get_all_snapshots(window_seconds=300)
        for snap in snapshots:
            self._event_bus.publish(
                ProviderEvent(
                    event_id=f"metrics_snap_{snap.provider_id}_{datetime.utcnow().timestamp()}",
                    timestamp=datetime.utcnow(),
                    provider_id=snap.provider_id,
                    event_type="METRICS_SNAPSHOT",
                    channel=ProviderEventChannel.METRICS,
                    session_uuid=None,
                    duration_ms=0.0,
                    payload=snap.__dict__
                )
            )
