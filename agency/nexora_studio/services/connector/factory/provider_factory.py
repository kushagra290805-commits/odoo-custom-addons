"""
Connector Platform: Provider Factory
=====================================
Part 3 of Phase 26.2 — Universal Connector Platform Refinement.
"""
from typing import Dict, Type
from ..sdk.capability import BaseCapabilityProvider
from ..sdk.configuration import BaseConfigurationProvider
from ..sdk.authentication import BaseAuthenticationProvider
from ..sdk.health import BaseHealthProvider

class ProviderFactory:
    """
    Responsible for instantiating the correct provider implementations 
    for capabilities, configuration, authentication, and health.
    """
    
    def __init__(self) -> None:
        self._capability_providers: Dict[str, Type[BaseCapabilityProvider]] = {}
        self._config_providers: Dict[str, Type[BaseConfigurationProvider]] = {}
        self._auth_providers: Dict[str, Type[BaseAuthenticationProvider]] = {}
        self._health_providers: Dict[str, Type[BaseHealthProvider]] = {}

    def register_capability_provider(self, provider_type: str, cls: Type[BaseCapabilityProvider]) -> None:
        self._capability_providers[provider_type] = cls

    def register_config_provider(self, provider_type: str, cls: Type[BaseConfigurationProvider]) -> None:
        self._config_providers[provider_type] = cls

    def register_auth_provider(self, provider_type: str, cls: Type[BaseAuthenticationProvider]) -> None:
        self._auth_providers[provider_type] = cls

    def register_health_provider(self, provider_type: str, cls: Type[BaseHealthProvider]) -> None:
        self._health_providers[provider_type] = cls

    def create_capability_provider(self, provider_type: str) -> BaseCapabilityProvider:
        cls = self._capability_providers.get(provider_type)
        if not cls:
            raise ValueError(f"Unknown capability provider: {provider_type}")
        return cls()

    def create_config_provider(self, provider_type: str) -> BaseConfigurationProvider:
        cls = self._config_providers.get(provider_type)
        if not cls:
            raise ValueError(f"Unknown config provider: {provider_type}")
        return cls()

    def create_auth_provider(self, provider_type: str) -> BaseAuthenticationProvider:
        cls = self._auth_providers.get(provider_type)
        if not cls:
            raise ValueError(f"Unknown auth provider: {provider_type}")
        return cls()

    def create_health_provider(self, provider_type: str) -> BaseHealthProvider:
        cls = self._health_providers.get(provider_type)
        if not cls:
            raise ValueError(f"Unknown health provider: {provider_type}")
        return cls()
