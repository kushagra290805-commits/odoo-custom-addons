from odoo import models, api
from odoo.addons.nexora_studio.services.generation.platform.platform_runtime import PlatformRuntime
from odoo.addons.nexora_studio.services.generation.platform.runtime_registry import RuntimeRegistry
from odoo.addons.nexora_studio.services.generation.platform.platform_health import PlatformHealthService
from odoo.addons.nexora_studio.services.runtime.mcp.mcp_runtime_adapter import McpRuntimeAdapter
from odoo.addons.nexora_studio.services.runtime.mcp.registry_provider import JsonRegistryProvider

class NexoraStudioPlatform(models.AbstractModel):
    """
    Thin Odoo service entry point for the PlatformRuntime.
    Contains no business logic; strictly responsible for lifecycle bridging.
    """
    _name = 'nexora_studio.platform'
    _description = 'Nexora Studio Platform Service'
    
    @api.model
    def get_runtime(self) -> PlatformRuntime:
        """
        Returns the global singleton PlatformRuntime instance.
        Bootstraps the runtime if it hasn't been initialized yet.
        """
        if not hasattr(self.env.registry, 'nexora_platform_runtime'):
            self._bootstrap_runtime()
        return self.env.registry.nexora_platform_runtime
        
    @api.model
    def _bootstrap_runtime(self) -> None:
        import os
        registry = RuntimeRegistry()
        health = PlatformHealthService(registry)
        
        # 1. Provide the MCP JSON Configuration Path
        default_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'config', 'mcp_registry.json')
        mcp_registry_path = os.environ.get("NEXORA_MCP_REGISTRY_PATH", os.path.normpath(default_path))
        provider = JsonRegistryProvider(mcp_registry_path)
        
        # 2. Instantiate Adapters and Register
        mcp_adapter = McpRuntimeAdapter(provider)
        registry.register_runtime(mcp_adapter)
        
        # 3. Create the Facade
        runtime = PlatformRuntime(registry, health)
        
        # 4. Initialize Boot Sequence
        if not runtime.initialize():
            import logging
            logging.getLogger(__name__).error("Failed to initialize PlatformRuntime!")
            
        # 5. Store globally in Odoo's registry to persist across requests
        self.env.registry.nexora_platform_runtime = runtime

    @api.model
    def get_health(self) -> dict:
        """Exposes top-level platform health."""
        runtime = self.get_runtime()
        status = runtime.health.get_status()
        
        # Inject Singleton identities for forensics
        try:
            status['singleton_identities'] = {
                'platform_runtime': id(runtime),
                'registry': id(runtime._registry),
                'health_service': id(runtime.health)
            }
        except Exception:
            pass
            
        return status
