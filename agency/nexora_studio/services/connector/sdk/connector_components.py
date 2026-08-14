"""
Connector Components
====================
Phase 27.0 — Universal Connector Platform Production Hardening
Composition helpers for connector authors to minimize boilerplate.
"""
from typing import Dict, Any, Optional

from odoo.addons.nexora_studio.services.connector.sdk.base import BaseConnector
from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext

class ComponentConnector(BaseConnector):
    """
    A concrete implementation of BaseConnector that acts as a structural facade.
    Instead of inheriting behavior, connector authors compose this with their specific
    Transport, Provider, and optionally Health Check implementations.
    """
    def __init__(
        self,
        provider: Any,
        transport: Any,
        health_check: Optional[Any] = None
    ):
        self.provider = provider
        self.transport = transport
        self.health_check = health_check

    def initialize(self, context: ExecutionContext) -> None:
        """
        Initializes the composed provider and transport.
        """
        if hasattr(self.provider, 'initialize'):
            self.provider.initialize(context)
        if hasattr(self.transport, 'connect'):
            try:
                self.transport.connect(context)
            except TypeError:
                self.transport.connect()

    def shutdown(self, context: ExecutionContext) -> None:
        """
        Shuts down the composed provider and transport.
        """
        if hasattr(self.provider, 'shutdown'):
            self.provider.shutdown(context)
        if hasattr(self.transport, 'disconnect'):
            try:
                self.transport.disconnect(context)
            except TypeError:
                self.transport.disconnect()

    def check_health(self, context: ExecutionContext) -> bool:
        """
        Delegates health checking to the injected health_check component,
        falling back to checking if the transport is connected.
        """
        if self.health_check and hasattr(self.health_check, 'check_health'):
            return self.health_check.check_health(context)
        
        if hasattr(self.transport, 'is_connected'):
            return self.transport.is_connected()
            
        return True

    def execute(
        self, 
        capability_namespace: str, 
        parameters: Dict[str, Any], 
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Delegates capability execution to the composed provider.
        """
        if hasattr(self.provider, 'execute'):
            return self.provider.execute(capability_namespace, parameters, context)
            
        # Fallback if provider doesn't have a single execute method
        method_name = f"execute_{capability_namespace.replace('.', '_')}"
        if hasattr(self.provider, method_name):
            method = getattr(self.provider, method_name)
            return method(parameters, context)
            
        from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ProviderException
        raise ProviderException(
            error_code="PROVIDER_NOT_IMPLEMENTED",
            user_safe_message=f"Capability '{capability_namespace}' is not supported.",
            technical_message=f"No execution logic found for '{capability_namespace}' in provider.",
            severity="ERROR"
        )
