# Connector Platform Public API Freeze

The following interfaces represent the frozen public API of the Universal Connector Platform. Future phases may extend these APIs (e.g. by adding optional arguments) but must not break backwards compatibility or remove them without a formal ADR.

## Runtime APIs
- `ConnectorRuntime.__init__(persistence_port)`
- `ConnectorRuntime.boot()`
- `ConnectorRuntime.shutdown()`
- `ConnectorRuntime.dispatch_execution(request: ConnectorExecutionRequest) -> ConnectorExecutionResult`
- `ConnectorRuntime.handle_event(event: ConnectorEvent)`

## Factory APIs
- `ConnectorFactory.create_connector(connector_type: str, config: Dict) -> BaseConnector`
- `ProviderFactory.create_capability_provider(provider_type: str) -> BaseCapabilityProvider`
- `ProviderFactory.create_auth_provider(provider_type: str) -> BaseAuthenticationProvider`
- `TransportFactory.create_transport(transport_type: str, config: Dict) -> BaseTransport`

## SDK APIs (Base Contracts)
- `BaseConnector.initialize(context: ExecutionContext)`
- `BaseConnector.execute(capability_namespace: str, params: Dict, context: ExecutionContext)`
- `BaseTransport.send_request(payload: Dict, context: ExecutionContext)`
- `BaseCapabilityProvider.execute_capability(namespace: str, parameters: Dict, context: ExecutionContext)`
- `BaseAuthenticationProvider.authenticate(context: ExecutionContext)`
- `BaseHealthProvider.check_health(context: ExecutionContext)`
- `BaseConfigurationProvider.resolve_configuration(context: ExecutionContext)`

## Registry APIs
- `ConnectorRegistry.register(connector: Connector)`
- `ConnectorRegistry.get(connector_id: str) -> Optional[Connector]`
- `ConnectorRegistry.list_active() -> List[Connector]`
- `CapabilityIndex.resolve_capabilities(namespace: str) -> List[str]`

## Event Bus APIs
- `ConnectorEventBus.subscribe(subscriber: EventSubscriber)`
- `ConnectorEventBus.publish(event: ConnectorEvent)`

## Persistence Port APIs
- `ConnectorPersistencePort.load_all() -> List[Connector]`
- `ConnectorPersistencePort.save(connector: Connector)`
- `ConnectorPersistencePort.delete(connector_id: str)`
