from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.platform.runtime_registry import RuntimeRegistry

class PlatformHealthService:
    """
    Aggregates health across the entire execution platform.
    """
    def __init__(self, registry: RuntimeRegistry):
        self._registry = registry
        
    def system_status(self) -> Dict[str, Any]:
        """
        Gathers diagnostic data from all registered runtimes.
        Assumes runtimes implement a `health_status()` method.
        """
        runtimes_health = {}
        all_online = True
        
        for descriptor in self._registry.get_all_descriptors():
            instance = self._registry.get_instance(descriptor.runtime_id)
            
            # Default fallback if the runtime doesn't expose health_status
            runtime_info = {"status": "online"}
            
            if hasattr(instance, "health_status") and callable(instance.health_status):
                try:
                    runtime_info = instance.health_status()
                    if runtime_info.get("status") != "online":
                        all_online = False
                except Exception as e:
                    runtime_info = {"status": "error", "error_message": str(e)}
                    all_online = False
                    
            runtimes_health[descriptor.runtime_id] = runtime_info
            
        return {
            "platform_status": "online" if all_online else "degraded",
            "registered_runtimes_count": len(self._registry.get_all_descriptors()),
            "runtimes": runtimes_health
        }
