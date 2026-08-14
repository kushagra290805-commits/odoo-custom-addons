from .repository import CapabilityRepository
from .lifecycle import CapabilityLifecycleManager

class CapabilityDiscoveryEngine:
    def __init__(self, lifecycle_manager: CapabilityLifecycleManager):
        self.lifecycle_manager = lifecycle_manager
        
    def discover_local(self):
        pass
        
    def discover_remote(self, endpoint: str):
        pass