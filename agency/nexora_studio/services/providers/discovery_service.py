import logging
from typing import List, Type

from .base_provider import (
    ProviderDiscovery,
    BaseProvider,
    ProviderCompatibilityService,
    ProviderRegistry
)
from .container import ProviderServiceContainer

_logger = logging.getLogger(__name__)

class OdooProviderDiscovery(ProviderDiscovery):
    """
    Discovers providers from multiple sources and delegates validation 
    to the ProviderCompatibilityService before registering them.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container
        # Note: We don't cache references to singleton services here, 
        # we resolve them on demand to avoid initialization order cycles 
        # if they depend back on something else, though typically it's fine.

    @property
    def _compat_service(self) -> ProviderCompatibilityService:
        return self._container.resolve(ProviderCompatibilityService)
        
    @property
    def _registry(self) -> ProviderRegistry:
        return self._container.resolve(ProviderRegistry)

    def discover_builtin(self) -> List[Type[BaseProvider]]:
        """
        Discovers built-in providers shipped with Nexora Studio.
        """
        from odoo.addons.nexora_studio.services.providers.component.internal_template_adapter import InternalTemplateProvider
        from odoo.addons.nexora_studio.services.providers.component.shadcn_adapter import ShadcnComponentProvider
        from odoo.addons.nexora_studio.services.providers.component.magic_ui_adapter import MagicUIComponentProvider
        from odoo.addons.nexora_studio.services.providers.component.aceternity_adapter import AceternityComponentProvider
        from odoo.addons.nexora_studio.services.providers.component.react_bits_adapter import ReactBitsComponentProvider
        from odoo.addons.nexora_studio.services.providers.component.twentyfirst_dev_adapter import TwentyFirstDevComponentProvider
        
        return [
            InternalTemplateProvider,
            ShadcnComponentProvider,
            MagicUIComponentProvider,
            AceternityComponentProvider,
            ReactBitsComponentProvider,
            TwentyFirstDevComponentProvider
        ]

    def discover_community(self) -> List[Type[BaseProvider]]:
        """
        Discovers community providers installed in the Python environment.
        """
        # Might use importlib.metadata.entry_points
        return []

    def discover_marketplace(self, package_dir: str) -> List[Type[BaseProvider]]:
        """
        Discovers marketplace providers downloaded to a specific directory.
        """
        # Scan package_dir for manifests, load modules dynamically
        return []

    def validate_and_register(self, provider_class: Type[BaseProvider]) -> bool:
        """
        Validates the provider class and registers it if compatible.
        """
        report = self._compat_service.validate(provider_class)
        
        if report.is_compatible:
            # Route registration through the canonical DI container
            metadata = provider_class.get_default_metadata()
            if hasattr(self._container, 'register_provider_class'):
                self._container.register_provider_class(metadata.provider_id, provider_class, metadata)
                
                # We still notify the legacy OdooProviderRegistry to sync with the Odoo DB
                # This will be cleaned up in Phase 19G.2 when we migrate DB sync entirely
                self._registry.register_provider(provider_class)
            else:
                self._registry.register_provider(provider_class)
                
            _logger.info(f"Successfully validated and registered provider: {report.provider_id}")
            return True
        else:
            _logger.error(
                f"Failed to register provider {report.provider_id} due to compatibility issues: {report.failures}"
            )
            return False
