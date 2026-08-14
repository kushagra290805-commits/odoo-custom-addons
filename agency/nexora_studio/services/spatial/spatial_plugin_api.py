from typing import Dict, Any, List
from odoo.addons.nexora_studio.services.spatial.spatial_event_bus import SpatialEventBus

class SpatialPluginAPI:
    """
    Exposes safe extension hooks for third-party tools to interact 
    with the Spatial Backend without touching core models directly.
    """
    def __init__(self, event_bus: SpatialEventBus):
        self.event_bus = event_bus
        self._plugins: Dict[str, Any] = {}
        
    def register_plugin(self, plugin_id: str, plugin_instance: Any) -> None:
        """
        Registers a plugin and executes its initialization hook.
        """
        self._plugins[plugin_id] = plugin_instance
        if hasattr(plugin_instance, "on_register"):
            plugin_instance.on_register(self)
            
    def get_plugin(self, plugin_id: str) -> Any:
        return self._plugins.get(plugin_id)
