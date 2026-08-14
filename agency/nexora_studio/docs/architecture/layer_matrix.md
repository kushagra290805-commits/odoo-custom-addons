# Layer Conformance Matrix

The Universal Connector Platform organizes classes strictly into architectural layers. A class belongs to exactly one layer. Mixed responsibilities, misplaced abstractions, and duplicate ownership are prohibited.

| Class / Module | Layer | Responsibility | Status |
| :--- | :--- | :--- | :--- |
| `ConnectorEnvironment`, `ConnectorHealth`, etc | **Domain** | Pure entity definition, state, value objects. | ✅ Conforms |
| `BaseConnector`, `BaseTransport`, etc | **SDK** | Abstract contracts for future connector authors. | ✅ Conforms |
| `ConnectorRuntime` | **Runtime** | Orchestration of all sub-systems (lifecycle, health, execution). | ✅ Conforms |
| `ConnectorDispatcher` | **Runtime** | Dispatches capability execution to target instances. | ✅ Conforms |
| `DependencyResolver` | **Runtime** | Resolves inter-connector dependencies. | ✅ Conforms |
| `ConnectorFactory`, `ProviderFactory` | **Factory** | Instantiates connectors, injects transport and auth. | ✅ Conforms |
| `ConnectorRegistry` | **Registry** | Maintains the active list of connectors. | ✅ Conforms |
| `CapabilityIndex` | **Registry** | Maps capabilities (`search.web`) to `connector_id`. | ✅ Conforms |
| `ConnectorPersistencePort` | **Persistence** | Abstract interface for saving/loading registry state. | ✅ Conforms |
| `OdooConnectorPersistenceAdapter` | **Persistence** | Concrete implementation speaking to Odoo ORM. | ✅ Conforms |
| `ConnectorLifecycleManager` | **Lifecycle** | Transitions connectors across states via FSM. | ✅ Conforms |
| `ConnectorLifecycleStateMachine` | **Lifecycle** | Pure transition graph and guards. | ✅ Conforms |
| `ConnectorEventBus` | **Events** | Asynchronous message propagation across subsystems. | ✅ Conforms |
| `ConnectorExecutionTarget` | **Integration** | Adheres to EP-004 to plug into UCEL. | ✅ Conforms |
| `nexora.connector.*` | **Odoo Models** | Odoo database schema and view records. | ✅ Conforms |

## Validation Result
- **Status**: PASSED.
- **Verification**: No class straddles multiple layers. No abstractions duplicate ownership (e.g., Runtime does not instantiate connectors, Factory does).
