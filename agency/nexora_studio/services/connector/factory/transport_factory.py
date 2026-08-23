"""
Connector Platform: Transport Factory
======================================
Part 3 of Phase 26.2 — Universal Connector Platform Refinement.

DEPRECATED (Phase 44.2, W10/W12, ADR-0068): this factory is dead — it has zero
registration call sites and is never invoked by ConnectorFactory (whose
transport injection is commented out). Concrete connectors (e.g. McpConnector)
construct their own transport directly. The file is retained for backward
compatibility only; do not wire new code through it. Removal is deferred to
Phase 44.3 with dependency proof.
"""
from typing import Dict, Any, Type
from ..sdk.transport import BaseTransport

class TransportFactory:
    """
    Responsible for instantiating the correct transport implementation 
    for a given connector type.

    DEPRECATED — see module docstring. Not used by the canonical MCP path.
    """
    
    def __init__(self) -> None:
        self._registry: Dict[str, Type[BaseTransport]] = {}
        
    def register_transport(self, transport_type: str, transport_cls: Type[BaseTransport]) -> None:
        """Register a transport implementation."""
        self._registry[transport_type] = transport_cls
        
    def create_transport(self, transport_type: str, config: Dict[str, Any]) -> BaseTransport:
        """Instantiate a transport."""
        cls = self._registry.get(transport_type)
        if not cls:
            raise ValueError(f"Unknown transport type: {transport_type}")
        return cls() # In future, config might be passed here.
