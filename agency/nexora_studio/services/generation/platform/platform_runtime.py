import logging
from typing import List, Callable, Dict, Any
from odoo.addons.nexora_studio.services.generation.platform.runtime_registry import RuntimeRegistry
from odoo.addons.nexora_studio.services.generation.platform.platform_health import PlatformHealthService
from odoo.addons.nexora_studio.services.generation.platform.models import RuntimeLifecycleEvent, Runtime

_logger = logging.getLogger(__name__)

class PlatformRuntime:
    """
    The unified Platform Facade.
    Coordinates initialization, shutdown, and capability discovery.
    """
    def __init__(self, registry: RuntimeRegistry, health_service: PlatformHealthService):
        self._registry = registry
        self.health = health_service
        self._initialized_runtimes: List[str] = []
        # Extension hooks only. Not connected to event buses.
        self._event_hooks: Dict[RuntimeLifecycleEvent, List[Callable[[str], None]]] = {
            e: [] for e in RuntimeLifecycleEvent
        }
        
    def add_event_hook(self, event: RuntimeLifecycleEvent, handler: Callable[[str], None]) -> None:
        self._event_hooks[event].append(handler)
        
    def _emit(self, event: RuntimeLifecycleEvent, runtime_id: str) -> None:
        for handler in self._event_hooks[event]:
            try:
                handler(runtime_id)
            except Exception as e:
                _logger.error(f"Error in Runtime Event Hook: {e}")

    def initialize(self) -> bool:
        """
        Initializes runtimes in deterministic topological order based on dependencies.
        """
        _logger.info("Initializing PlatformRuntime...")
        
        if not self._registry.validate_dependencies():
            _logger.error("Platform initialization failed: Missing dependencies.")
            return False
            
        # 1. Boot runtimes in order based on DAG
        try:
            ordered_ids = self._registry.get_startup_order()
        except ValueError as e:
            _logger.error(f"Platform initialization failed: {e}")
            return False
        from odoo.addons.nexora_studio.services.generation.platform.models import RuntimeStartupPolicy
        
        for runtime_id in ordered_ids:
            descriptor = self._registry.get_descriptor(runtime_id)
            if descriptor and descriptor.startup_policy == RuntimeStartupPolicy.DISABLED:
                _logger.info(f"Skipping disabled runtime: {runtime_id}")
                continue
                
            instance = self._registry.get_instance(runtime_id)
            if instance:
                self._emit(RuntimeLifecycleEvent.INITIALIZING, runtime_id)
                try:
                    instance.initialize()
                    self._emit(RuntimeLifecycleEvent.INITIALIZED, runtime_id)
                    self._initialized_runtimes.append(runtime_id)
                except Exception as e:
                    self._emit(RuntimeLifecycleEvent.FAILED, runtime_id)
                    if descriptor and descriptor.startup_policy == RuntimeStartupPolicy.REQUIRED:
                        _logger.error(f"Failed to initialize REQUIRED runtime {runtime_id}: {e}")
                        return False
                    else:
                        _logger.warning(f"Failed to initialize OPTIONAL runtime {runtime_id}: {e}")
            
        _logger.info("PlatformRuntime initialization complete.")
        return True

    def shutdown(self) -> None:
        """
        Shuts down runtimes in the exact reverse order of initialization.
        """
        _logger.info("Shutting down PlatformRuntime...")
        # Reverse the list of successfully initialized runtimes
        shutdown_order = list(reversed(self._initialized_runtimes))
        
        for runtime_id in shutdown_order:
            instance = self._registry.get_instance(runtime_id)
            if instance:
                self._emit(RuntimeLifecycleEvent.STOPPING, runtime_id)
                try:
                    instance.shutdown()
                    self._emit(RuntimeLifecycleEvent.STOPPED, runtime_id)
                except Exception as e:
                    _logger.error(f"Error shutting down runtime {runtime_id}: {e}")
                    
        self._initialized_runtimes.clear()
        _logger.info("PlatformRuntime shutdown complete.")

    def list_capabilities(self) -> List[str]:
        """
        Exposes a flattened, distinct list of all capabilities across all runtimes.
        """
        capabilities = set()
        for descriptor in self._registry.get_all_descriptors():
            capabilities.update(descriptor.capabilities)
        return sorted(list(capabilities))
        
    def get_runtime(self, runtime_id: str) -> Runtime:
        """
        Exposes underlying runtimes for the Execution Engine if strictly necessary.
        """
        return self._registry.get_instance(runtime_id)
