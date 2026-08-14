# Universal Connector Platform Dependency Graph

## Component Dependencies

The Connector Platform strictly enforces the following dependency rules:

1. **Domain (`services/connector/domain`)**
   - Imports: Python standard library only.
   - Prohibitions: No Odoo, no SDK, no Runtime, no Factory.

2. **SDK (`services/connector/sdk`)**
   - Imports: `domain`
   - Prohibitions: No Odoo, no Runtime, no Factory, no external dependencies.

3. **Runtime (`services/connector/runtime`)**
   - Imports: `domain`, `sdk`, `events`, `lifecycle`, `factory`, `registry`
   - Prohibitions: No Odoo (enforced by Hexagonal Architecture via Persistence Port). No Generation Platform coupling.

4. **Factory (`services/connector/factory`)**
   - Imports: `domain`, `sdk`
   - Prohibitions: No Generation Platform coupling, no Odoo.

5. **Registry (`services/connector/registry`)**
   - Imports: `domain`, `persistence.port`
   - Prohibitions: No Odoo models directly.

6. **Persistence (`services/connector/registry/persistence`)**
   - Adapters (`OdooConnectorPersistenceAdapter`): Imports Odoo Environment and ORM.
   - Ports/Services: No Odoo imports.

7. **Integration (`services/connector/integration`)**
   - Imports: `GenerationRuntime`, `UniversalCapabilityRouter` (only at defined EP-004 boundary).
   - Prohibitions: Generational logic leaking into Connector Runtime.

### Dependency Graph

```mermaid
graph TD
    subgraph Odoo [Odoo ORM Boundary]
        OM[nexora.connector.*]
    end

    subgraph Connector Platform
        DOM[Domain]
        SDK[SDK]
        EVT[Events]
        LIFE[Lifecycle]
        FACT[Factory]
        REG[Registry]
        PORT[Persistence Port]
        ADAPT[Persistence Adapter]
        RUN[Runtime]
        INT[Integration Bridge]
    end

    subgraph Generation Platform (Frozen)
        UCEL[UniversalCapabilityRouter]
        GEN[GenerationRuntime]
    end

    SDK --> DOM
    EVT --> DOM
    LIFE --> DOM
    LIFE --> EVT
    FACT --> SDK
    FACT --> DOM
    PORT --> DOM
    REG --> DOM
    REG --> PORT
    ADAPT --> PORT
    ADAPT --> OM
    RUN --> REG
    RUN --> LIFE
    RUN --> EVT
    RUN --> FACT
    RUN --> DOM
    INT --> RUN
    INT --> UCEL
```

## Validation Result
- **Status**: PASSED.
- **Verification**: No circular dependencies exist. Odoo imports are strictly confined to `OdooConnectorPersistenceAdapter`. Factory holds pure logic without leaking Generation runtime concerns.
