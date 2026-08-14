from typing import Type, TypeVar, Dict, Optional
from .base_provider import ProviderServiceContainer, ServiceRegistration, ServiceLifetime

T = TypeVar('T')

class OdooProviderServiceContainer(ProviderServiceContainer):
    """
    Dependency Injection Composition Root for the Unified Provider Platform.
    Registers services and manages their lifecycles (Singleton, Scoped, Transient).
    """
    
    def __init__(self, parent: Optional['OdooProviderServiceContainer'] = None):
        self._registrations: Dict[Type, ServiceRegistration] = {}
        self._singletons: Dict[Type, object] = {}
        self._scoped: Dict[Type, object] = {}
        self._provider_classes: Dict[str, Type] = {}
        self._provider_metadata: Dict[str, 'ProviderMetadata'] = {}
        self._parent = parent
        
        # If this is a child container, copy parent's registrations and singletons
        if parent:
            self._registrations = dict(parent._registrations)
            self._singletons = parent._singletons
            self._provider_classes = parent._provider_classes
            self._provider_metadata = parent._provider_metadata
    
    def register(self, registration: ServiceRegistration) -> None:
        """Register a service in the container."""
        self._registrations[registration.service_type] = registration
        
    def register_provider_class(self, provider_id: str, provider_class: Type, metadata: 'ProviderMetadata') -> None:
        """Register a specific AI provider implementation class."""
        self._provider_classes[provider_id] = provider_class
        self._provider_metadata[provider_id] = metadata
        
    def get_provider_class(self, provider_id: str) -> Optional[Type]:
        return self._provider_classes.get(provider_id)
        
    def get_provider_metadata(self, provider_id: str) -> Optional['ProviderMetadata']:
        return self._provider_metadata.get(provider_id)
        
    def list_providers(self, active_only: bool = True) -> list:
        # Note: Active state checking would normally happen in Odoo model or FSM
        return list(self._provider_metadata.values())

    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance by its type."""
        if service_type not in self._registrations:
            raise ValueError(f"Service {service_type.__name__} is not registered in the container.")
            
        registration = self._registrations[service_type]
        
        if registration.lifetime == ServiceLifetime.SINGLETON:
            if service_type not in self._singletons:
                self._singletons[service_type] = self._instantiate(registration)
            return self._singletons[service_type]
            
        elif registration.lifetime == ServiceLifetime.SCOPED:
            if service_type not in self._scoped:
                self._scoped[service_type] = self._instantiate(registration)
            return self._scoped[service_type]
            
        elif registration.lifetime == ServiceLifetime.TRANSIENT:
            return self._instantiate(registration)
            
        raise ValueError(f"Unknown service lifetime: {registration.lifetime}")

    def _instantiate(self, registration: ServiceRegistration) -> object:
        """Create a new instance of the registered service using recursive resolution."""
        if registration.factory:
            return registration.factory(self)
            
        import inspect
        impl_type = registration.implementation_type
        if not hasattr(impl_type, '__init__'):
            return impl_type()
            
        sig = inspect.signature(impl_type.__init__)
        kwargs = {}
        for name, param in sig.parameters.items():
            if name == 'self':
                continue
            # If the parameter is the container itself, inject it
            if param.annotation is ProviderServiceContainer or param.annotation == 'ProviderServiceContainer':
                kwargs[name] = self
            elif param.annotation != inspect.Parameter.empty:
                # Try to resolve the dependency by its type annotation
                try:
                    kwargs[name] = self.resolve(param.annotation)
                except ValueError:
                    # If it has a default, use it
                    if param.default != inspect.Parameter.empty:
                        pass # default will be used
                    else:
                        raise ValueError(f"Cannot resolve dependency {name}: {param.annotation} for {impl_type.__name__}")
            else:
                if param.default == inspect.Parameter.empty:
                    raise ValueError(f"Cannot resolve untyped dependency {name} for {impl_type.__name__}")
                    
        return impl_type(**kwargs)
        
    def create_scope(self) -> 'ProviderServiceContainer':
        """Create a new request-scoped child container."""
        return OdooProviderServiceContainer(parent=self)
        
    def build(self) -> None:
        """
        Validate all registrations and eagerly construct singletons.
        Raises ValueError if dependencies cannot be resolved or circular dependencies exist.
        """
        for service_type, registration in self._registrations.items():
            if registration.lifetime == ServiceLifetime.SINGLETON:
                self.resolve(service_type)

GLOBAL_CONTAINER: Optional[OdooProviderServiceContainer] = None

def bootstrap_container(env=None) -> OdooProviderServiceContainer:
    """Bootstraps the DI container, registering all Odoo services."""
    global GLOBAL_CONTAINER
    if GLOBAL_CONTAINER is not None:
        return GLOBAL_CONTAINER
        
    container = OdooProviderServiceContainer()
    
    from .lock_service import OdooLockService
    from .event_bus import OdooProviderEventBus
    from .state_machine import OdooProviderStateMachine
    from .dependency_graph import OdooProviderDependencyGraph
    from .compat_service import OdooCompatibilityService
    from .discovery_service import OdooProviderDiscovery
    from .registry_service import OdooProviderRegistry, OdooProviderFactory
    from .health_service import OdooProviderHealthService
    from .telemetry_service import OdooProviderTelemetryService
    from .metrics_service import OdooProviderMetricsService
    from .capability_cache import OdooCapabilityCache
    from .cache_service import OdooProviderCache
    from .cost_quota_service import OdooUnifiedCostQuotaService
    from .capability_resolver import OdooCapabilityResolver
    from .migration_service import OdooProviderMigrationService
    from .execution_orchestrator import OdooExecutionOrchestrator
    from .transaction_manager import OdooProviderTransactionManager
    from .plugin_manager import OdooProviderPluginManager
    from .base_provider import (
        LockService, ProviderEventBus, ProviderStateMachine, ProviderDependencyGraph,
        ProviderCompatibilityService, ProviderDiscovery, ProviderRegistry, ProviderFactory,
        ProviderHealthService, ProviderTelemetryService, ProviderMetricsService,
        CapabilityCache, ProviderCache, UnifiedCostQuotaService, CapabilityResolver,
        ProviderMigrationService, ExecutionOrchestrator, ProviderTransactionManager,
        ProviderPluginManager
    )
    
    container.register(ServiceRegistration(LockService, OdooLockService, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderEventBus, OdooProviderEventBus, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderStateMachine, OdooProviderStateMachine, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderDependencyGraph, OdooProviderDependencyGraph, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderCompatibilityService, OdooCompatibilityService, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderDiscovery, OdooProviderDiscovery, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderRegistry, OdooProviderRegistry, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderFactory, OdooProviderFactory, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderHealthService, OdooProviderHealthService, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderTelemetryService, OdooProviderTelemetryService, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderMetricsService, OdooProviderMetricsService, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(CapabilityCache, OdooCapabilityCache, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderCache, OdooProviderCache, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(UnifiedCostQuotaService, OdooUnifiedCostQuotaService, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(CapabilityResolver, OdooCapabilityResolver, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderMigrationService, OdooProviderMigrationService, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderTransactionManager, OdooProviderTransactionManager, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ProviderPluginManager, OdooProviderPluginManager, ServiceLifetime.SINGLETON))
    container.register(ServiceRegistration(ExecutionOrchestrator, OdooExecutionOrchestrator, ServiceLifetime.SINGLETON))
    
    # Store env context in the container for services that need DB access during bootstrap
    # Not natively supported by raw DI, but we can register it as an instance
    if env is not None:
        from typing import Any
        container.register(ServiceRegistration(type(env), lambda c: env, ServiceLifetime.SINGLETON))
        
    container.build()
    GLOBAL_CONTAINER = container
    return container
