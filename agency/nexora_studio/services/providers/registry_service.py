import logging
from typing import Dict, List, Optional, Type

from .base_provider import (
    ProviderRegistry,
    ProviderFactory,
    BaseProvider,
    ProviderMetadata,
    ProviderCategory,
    ProviderConfiguration,
    ProviderAuthentication,
    ProviderStateMachine,
    ProviderRuntimeState
)
from .container import ProviderServiceContainer

_logger = logging.getLogger(__name__)

class OdooProviderRegistry(ProviderRegistry):
    """
    [DEPRECATED] Registry for managing provider metadata and classes.
    Class registration has been migrated to the OdooProviderServiceContainer.
    This class now acts as a thin wrapper for backward compatibility and DB synchronization.
    Will be fully removed in a future cleanup phase.
    """

    def __init__(self, container: ProviderServiceContainer):
        _logger.warning("DEPRECATED: OdooProviderRegistry is deprecated. Class registration is now handled by ProviderServiceContainer.")
        self._container = container

    @property
    def _state_machine(self) -> ProviderStateMachine:
        return self._container.resolve(ProviderStateMachine)

    def register_provider(self, provider_class: Type[BaseProvider]) -> None:
        """
        [DEPRECATED] Delegate registration to the canonical container.
        """
        metadata: ProviderMetadata
        if hasattr(provider_class, 'get_default_metadata'):
            metadata = provider_class.get_default_metadata()
        else:
            raise ValueError(f"Provider {provider_class.__name__} missing get_default_metadata()")

        provider_id = metadata.provider_id
        
        # Delegate class and metadata storage to the canonical DI container
        if hasattr(self._container, 'register_provider_class'):
            self._container.register_provider_class(provider_id, provider_class, metadata)
            
        _logger.info(f"Delegated provider {provider_id} registration to Container.")

    def get_metadata(self, provider_id: str) -> Optional[ProviderMetadata]:
        if hasattr(self._container, 'get_provider_metadata'):
            return self._container.get_provider_metadata(provider_id)
        return None

    def list_providers(self, category: Optional[ProviderCategory] = None, active_only: bool = True) -> List[ProviderMetadata]:
        """
        [DEPRECATED] Delegate listing to the canonical container.
        """
        results = []
        if hasattr(self._container, 'list_providers'):
            all_providers = self._container.list_providers(active_only=False)
        else:
            all_providers = []
            
        for metadata in all_providers:
            if category and metadata.category != category:
                continue
                
            if active_only:
                # Need to check FSM state
                state = self._state_machine.get_state(metadata.provider_id)
                if state in (ProviderRuntimeState.DISABLED, ProviderRuntimeState.ARCHIVED):
                    continue
                    
            results.append(metadata)
            
        return results

    def unregister_provider(self, provider_id: str) -> bool:
        """
        [DEPRECATED] Removes a provider from the registry.
        """
        _logger.warning("unregister_provider is deprecated and no longer supported on the wrapper.")
        return False

    def get_provider_class(self, provider_id: str) -> Optional[Type[BaseProvider]]:
        """
        [DEPRECATED] Delegate to container.
        """
        if hasattr(self._container, 'get_provider_class'):
            return self._container.get_provider_class(provider_id)
        return None


class OdooProviderFactory(ProviderFactory):
    """
    Focused solely on instantiation (ADR-0031). 
    Selection is delegated to CapabilityResolver.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container

    @property
    def _registry(self) -> OdooProviderRegistry:
        # We need the OdooProviderRegistry specifically to get the class
        return self._container.resolve(ProviderRegistry)

    def create_provider(self, provider_id: str, config: ProviderConfiguration, auth: ProviderAuthentication) -> BaseProvider:
        """
        Instantiate a provider by its ID.
        Initializes and authenticates the provider instance.
        """
        provider_class = self._registry.get_provider_class(provider_id)
        if not provider_class:
            raise ValueError(f"Cannot create provider: {provider_id} is not registered.")
            
        metadata = self._registry.get_metadata(provider_id)
        
        # Instantiate the provider class
        provider = provider_class(metadata=metadata)
        
        # Run initialization and authentication lifecycle steps
        provider.initialize(config)
        
        if not provider.authenticate(auth):
            from .base_provider import ProviderAuthenticationError
            raise ProviderAuthenticationError(f"Authentication failed for provider {provider_id}", provider_id)
            
        return provider

    def resolve_provider_for_capability(self, category, operation_type, capability_version, context) -> BaseProvider:
        """
        Backward-compatible thin delegation to CapabilityResolver.
        """
        from .base_provider import CapabilityResolver, ProviderFeatureSet
        resolver = self._container.resolve(CapabilityResolver)
        
        # We construct a generic feature set since we don't have detailed features here
        features = ProviderFeatureSet()
        
        # This will resolve and then we assume the orchestrator will create the provider
        # But this method in the old architecture returned an instantiated provider.
        # Actually, capability resolver returns the BaseProvider instance, so we just delegate.
        return resolver.resolve(category, operation_type, features, context)
