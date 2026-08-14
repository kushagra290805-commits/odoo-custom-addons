"""
Connector Platform: Connector Factory
======================================
Part 3 of Phase 26.2 — Universal Connector Platform Refinement.
"""
from typing import Dict, Any, Type
from ..sdk.base import BaseConnector
from .transport_factory import TransportFactory
from .provider_factory import ProviderFactory

class ConnectorFactory:
    """
    Centralized factory for creating BaseConnector instances.
    Injects dependencies (transport, capabilities, config, auth, health).
    """

    def __init__(
        self,
        transport_factory: TransportFactory,
        provider_factory: ProviderFactory
    ) -> None:
        self.transport_factory = transport_factory
        self.provider_factory = provider_factory
        self._connector_registry: Dict[str, Type[BaseConnector]] = {}

    def register_connector_type(self, connector_type: str, cls: Type[BaseConnector]) -> None:
        """Register a base connector implementation for a specific type."""
        self._connector_registry[connector_type] = cls

    def create_connector(self, connector_type: str, config: Dict[str, Any]) -> BaseConnector:
        """
        Instantiate a connector and wire its dependencies.
        In future phases, this will resolve the specific provider types from the manifest
        and inject them into the connector.
        """
        cls = self._connector_registry.get(connector_type)
        if not cls:
            raise ValueError(f"Unknown connector type: {connector_type}")

        # Instantiate
        try:
            connector = cls(config)
        except TypeError:
            # Fallback for connectors that don't accept config (e.g. Phase 27.0 LocalCliConnector)
            connector = cls()

        # In a real implementation, the connector might accept injected providers via properties
        # or constructor. For now, we return the instantiated BaseConnector subclass.
        # e.g.:
        # connector.transport = self.transport_factory.create_transport(...)
        # connector.auth_provider = self.provider_factory.create_auth_provider(...)
        
        return connector
