# -*- coding: utf-8 -*-
from typing import Dict, Any

class ProviderHealthMonitor:
    def __init__(self):
        self.health_status: Dict[str, Dict[str, Any]] = {}
        
    def track_latency(self, provider_id: str, latency_ms: float):
        if provider_id not in self.health_status:
            self.health_status[provider_id] = {"latency_history": [], "failures": 0, "status": "HEALTHY"}
        self.health_status[provider_id]["latency_history"].append(latency_ms)
        
    def record_failure(self, provider_id: str):
        if provider_id not in self.health_status:
            self.health_status[provider_id] = {"latency_history": [], "failures": 0, "status": "HEALTHY"}
        self.health_status[provider_id]["failures"] += 1
        if self.health_status[provider_id]["failures"] > 3:
            self.health_status[provider_id]["status"] = "UNHEALTHY"
            
    def check_health(self, provider_id: str) -> bool:
        if provider_id not in self.health_status:
            return True
        return self.health_status[provider_id]["status"] == "HEALTHY"
