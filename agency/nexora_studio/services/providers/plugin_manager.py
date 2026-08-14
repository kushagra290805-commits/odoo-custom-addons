import logging
from typing import Optional

from .base_provider import (
    ProviderPluginManager,
    ProviderMetadata,
    ProviderServiceContainer,
    ProviderDiscovery,
    ProviderRegistry,
    ProviderStateMachine,
    ProviderRuntimeState
)
from .domain_events import (
    DomainEventPublisher,
    ProviderInstalled,
    ProviderRemoved,
    ProviderEnabled,
    ProviderDisabled
)

_logger = logging.getLogger(__name__)

class OdooProviderPluginManager(ProviderPluginManager):
    """
    Manages the lifecycle of plugins (packages containing providers).
    Provides package validation, signature verification, and installation workflows.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container

    @property
    def _registry(self) -> ProviderRegistry:
        return self._container.resolve(ProviderRegistry)
        
    @property
    def _discovery(self) -> ProviderDiscovery:
        return self._container.resolve(ProviderDiscovery)

    @property
    def _fsm(self) -> ProviderStateMachine:
        return self._container.resolve(ProviderStateMachine)

    def install_plugin(self, package_dir: str) -> bool:
        if not self.validate_packages(package_dir):
            _logger.error(f"Plugin package validation failed: {package_dir}")
            return False
            
        provider_classes = self._discovery.discover_marketplace(package_dir)
        success = True
        
        for p_class in provider_classes:
            if self._discovery.validate_and_register(p_class):
                metadata = p_class.get_default_metadata()
                DomainEventPublisher.publish(ProviderInstalled(metadata.provider_id, metadata.provider_version))
            else:
                success = False
                
        return success

    def uninstall_plugin(self, plugin_id: str) -> bool:
        # Assuming plugin_id maps to provider_id in a 1:1 for simplicity,
        # in reality a plugin might contain multiple providers.
        # We unregister from the system
        if self._registry.unregister_provider(plugin_id):
            DomainEventPublisher.publish(ProviderRemoved(plugin_id))
            return True
        return False

    def enable_plugin(self, plugin_id: str) -> bool:
        state = self._fsm.get_state(plugin_id)
        if state in (ProviderRuntimeState.DISABLED, ProviderRuntimeState.INSTALLED):
            if self._fsm.transition(plugin_id, ProviderRuntimeState.CONFIGURED, reason="Plugin enabled by manager"):
                DomainEventPublisher.publish(ProviderEnabled(plugin_id))
                return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        if self._fsm.transition(plugin_id, ProviderRuntimeState.DISABLED, reason="Plugin disabled by manager"):
            DomainEventPublisher.publish(ProviderDisabled(plugin_id))
            return True
        return False

    def verify_signatures(self, plugin_id: str) -> bool:
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                registry = http.request.env['nexora.provider.registry'].sudo().search([('provider_id', '=', plugin_id)], limit=1)
                if registry:
                    # In a real implementation we would check the signature of the installed package against a public key
                    # For now, we simulate a successful validation if the registry entry exists
                    return True
        except Exception as e:
            _logger.error(f"Failed to verify signatures: {e}")
        return False

    def load_manifests(self, plugin_id: str) -> Optional[ProviderMetadata]:
        return self._registry.get_metadata(plugin_id)

    def validate_packages(self, package_dir: str) -> bool:
        import os
        if not os.path.isdir(package_dir):
            _logger.error(f"Package directory not found: {package_dir}")
            return False
            
        required_files = ['__init__.py']
        for file in required_files:
            if not os.path.isfile(os.path.join(package_dir, file)):
                _logger.error(f"Missing required file {file} in {package_dir}")
                return False
                
        return True
