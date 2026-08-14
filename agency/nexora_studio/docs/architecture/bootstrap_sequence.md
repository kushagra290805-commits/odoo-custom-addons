# Connector Platform Bootstrap Sequence

The Universal Connector Platform is strictly instantiated once at application startup. This audit verifies that there are no duplicate initializations and no hidden singleton creation outside of the defined bootstrap sequence.

## Sequence Trace

```mermaid
sequenceDiagram
    participant Odoo as Odoo Environment
    participant Boot as Connector Bootstrap
    participant Persist as OdooConnectorPersistenceAdapter
    participant Reg as ConnectorRegistry
    participant Bus as ConnectorEventBus
    participant Fact as ConnectorFactory
    participant Run as ConnectorRuntime
    participant UCEL as UniversalCapabilityRouter

    Odoo->>Boot: initialize(env)
    activate Boot
    
    Boot->>Persist: instantiate(env)
    
    Boot->>Bus: instantiate()
    
    Boot->>Reg: instantiate(persistence_port)
    
    Boot->>Fact: instantiate(transport_factory, provider_factory)
    
    Boot->>Run: instantiate(registry, bus, factory)
    
    Boot->>UCEL: register_executor(ConnectorExecutionTarget)
    
    deactivate Boot
```

## Audit Findings

1. **Exactly one runtime**: `ConnectorRuntime` is instantiated once in `integration/bootstrap.py`.
2. **Exactly one registry**: `ConnectorRegistry` is created inside the bootstrap sequence and injected.
3. **Exactly one capability index**: Instantiated internal to the Runtime upon boot.
4. **Exactly one event bus**: Instantiated internal to the Runtime.
5. **No duplicate initialization**: Verified across `integration/` modules.
6. **No hidden singletons**: The module-level cache for the runtime is explicitly managed in `bootstrap.py` via a `get_runtime()` accessor, avoiding implicit global singletons scattered across modules.

## Validation Result
✅ **PASSED**.
