import time
from typing import Dict, Optional

class ProviderHealthState:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"

class RuntimeHealthRegistry:
    """
    In-memory registry tracking the real-time health of providers.
    Does not persist to database.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RuntimeHealthRegistry, cls).__new__(cls)
            cls._instance.health_states: Dict[str, dict] = {}
        return cls._instance
        
    def set_health(self, namespace: str, state: str, reason: str = ""):
        self.health_states[namespace] = {
            "state": state,
            "reason": reason,
            "last_updated": time.time()
        }
        
    def get_health(self, namespace: str) -> str:
        """Returns the health state, defaults to HEALTHY if unknown."""
        return self.health_states.get(namespace, {}).get("state", ProviderHealthState.HEALTHY)
        
    def get_full_health_report(self) -> Dict[str, dict]:
        return dict(self.health_states)
