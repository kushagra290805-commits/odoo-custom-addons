from typing import Set, Type
from odoo.addons.nexora_studio.services.generation.core.runtime_exceptions import RuntimeCapabilityError

class RuntimeScopeRegistry:
    """Registry mapping Engine classes to their allowed Runtime capabilities."""
    
    def __init__(self):
        self._registry = {}
        
    def register(self, engine_class: Type, capabilities: Set[str]):
        self._registry[engine_class.__name__] = capabilities
        
    def get_scope(self, engine_class: Type) -> Set[str]:
        return self._registry.get(engine_class.__name__, set())
        
    def resolve_scope_name(self, engine_name: str) -> str:
        """Helper to derive a scope name for metadata (e.g. 'Requirement Scope')."""
        return f"{engine_name.replace('Engine', '')} Scope"


class ScopedRuntimeProxy:
    """
    A capability view of the GenerationRuntime.
    Intercepts attribute access and validates against the allowed scope.
    """
    def __init__(self, runtime: 'GenerationRuntime', allowed_capabilities: Set[str]):
        self._runtime = runtime
        self._allowed_capabilities = allowed_capabilities
        
    def __getattr__(self, name: str):
        # Allow overriding on the proxy itself
        if name in self.__dict__:
            return self.__dict__[name]
            
        if name in self._allowed_capabilities:
            return getattr(self._runtime, name)
            
        raise RuntimeCapabilityError(
            f"Engine attempted to access unauthorized capability '{name}'. "
            f"Allowed capabilities for this scope: {self._allowed_capabilities}"
        )
