# Phase 26 — Connector Platform Architecture Diagrams
## Universal Connector Platform Foundation

---

## 1. Architecture Overview

```mermaid
graph TD
    BSS["BuilderSessionService\n(sole generation entry point)"]
    GC["GenerationCoordinator"]
    WGP["WebsiteGenerationPipeline\n(17 Engines)"]
    GR["GenerationRuntime\nFROZEN"]
    UCEL["UniversalCapabilityRouter\nFROZEN"]
    EP["EP-004\nConnectorExecutionTarget"]
    CR["ConnectorRuntime\nNEW"]
    REG["ConnectorRegistry\nNEW"]
    CAP["ConnectorCapabilityIndex\nNEW"]
    LM["ConnectorLifecycleManager\nNEW"]
    HM["ConnectorHealthMonitor\nNEW"]
    DISP["ConnectorDispatcher\nNEW"]
    ODOO["Odoo Models\nnexora.connector_*"]
    EXT["External Systems\nFuture Phases"]

    BSS --> GC --> WGP --> GR
    GR --> UCEL
    UCEL --> EP
    EP --> CR
    CR --> REG
    CR --> CAP
    CR --> LM
    CR --> HM
    CR --> DISP
    REG --> ODOO
    DISP --> EXT

    style BSS fill:#2d5a27,color:#fff
    style UCEL fill:#2d5a27,color:#fff
    style GR fill:#2d5a27,color:#fff
    style EP fill:#1a4a7a,color:#fff
    style CR fill:#1a4a7a,color:#fff
    style REG fill:#1a4a7a,color:#fff
    style CAP fill:#1a4a7a,color:#fff
    style LM fill:#1a4a7a,color:#fff
    style HM fill:#1a4a7a,color:#fff
    style DISP fill:#1a4a7a,color:#fff
    style EXT fill:#555,color:#fff
```

**Legend:** Green = Frozen (Generation Platform). Blue = New (Connector Platform).

---

## 2. Connector Lifecycle State Diagram

```mermaid
stateDiagram-v2
    [*] --> REGISTERED : register()
    REGISTERED --> DISCOVERED : resolve_manifest()
    DISCOVERED --> DOWNLOADED : download()
    DISCOVERED --> INSTALLED : already_local()
    DOWNLOADED --> INSTALLED : install()
    INSTALLED --> CONFIGURED : configure()
    CONFIGURED --> AUTHENTICATED : authenticate()
    CONFIGURED --> VALIDATED : no_auth_required()
    AUTHENTICATED --> VALIDATED : validate()
    VALIDATED --> HEALTHY : health_check_pass()
    HEALTHY --> RUNNING : auto
    RUNNING --> PAUSED : operator_pause()
    PAUSED --> RUNNING : operator_resume()
    RUNNING --> FAILED : execution_error()
    RUNNING --> DISABLED : operator_disable()
    RUNNING --> UPDATING : update_triggered()
    UPDATING --> INSTALLED : re_install()
    PAUSED --> DISABLED : operator_disable()
    HEALTHY --> DISABLED : operator_disable()
    FAILED --> DISCOVERED : full_reinstall()
    FAILED --> INSTALLED : reconfigure()
    FAILED --> CONFIGURED : re_auth()
    FAILED --> DISABLED : disable_failed()
    FAILED --> REMOVED : remove_failed()
    DISABLED --> CONFIGURED : re_enable()
    DISABLED --> REMOVED : remove_disabled()
    REMOVED --> [*]
```

---

## 3. Odoo Model Relationship Diagram

```mermaid
erDiagram
    nexora_connector_type {
        char type_code PK
        char display_name
        selection lifecycle_policy
        boolean supports_health_check
        boolean requires_session
    }
    nexora_connector {
        char connector_id PK
        m2o connector_type_id FK
        char version
        selection state
        selection health_status
        boolean enabled
    }
    nexora_connector_capability {
        int id PK
        m2o connector_id FK
        char capability_namespace
        char display_name
        char version
    }
    nexora_connector_version {
        int id PK
        m2o connector_id FK
        char version_string
        boolean is_current
        char checksum
    }
    nexora_connector_installation {
        int id PK
        m2o connector_id FK
        selection state
        char installation_path
        datetime installed_at
    }
    nexora_connector_configuration {
        int id PK
        m2o connector_id FK
        char config_key
        boolean is_secret
        boolean is_required
    }
    nexora_connector_dependency {
        int id PK
        m2o connector_id FK
        m2o depends_on_connector_id FK
        selection dependency_type
        char version_constraint
    }
    nexora_connector_health {
        int id PK
        m2o connector_id FK
        selection status
        datetime last_checked
        float latency_ms
    }
    nexora_connector_event {
        int id PK
        m2o connector_id FK
        char event_type
        selection severity
        datetime occurred_at
    }
    nexora_connector_marketplace {
        int id PK
        m2o connector_type_id FK
        char name
        char publisher
        boolean verified
    }
    nexora_connector_repository {
        int id PK
        char name
        char url
        boolean enabled
    }

    nexora_connector_type ||--o{ nexora_connector : "typed_as"
    nexora_connector ||--o{ nexora_connector_capability : "provides"
    nexora_connector ||--o{ nexora_connector_version : "versioned_by"
    nexora_connector ||--o| nexora_connector_installation : "installed_via"
    nexora_connector ||--o{ nexora_connector_configuration : "configured_by"
    nexora_connector ||--o{ nexora_connector_dependency : "depends_on"
    nexora_connector ||--o{ nexora_connector_health : "monitored_by"
    nexora_connector ||--o{ nexora_connector_event : "emits"
    nexora_connector_type ||--o{ nexora_connector_marketplace : "listed_in"
```

---

## 4. UCEL → Connector Runtime Interaction Diagram

```mermaid
sequenceDiagram
    participant Eng as Generation Engine
    participant GR as GenerationRuntime
    participant UCEL as UniversalCapabilityRouter
    participant ET as ConnectorExecutionTarget
    participant CR as ConnectorRuntime
    participant REG as ConnectorRegistry
    participant IDX as CapabilityIndex
    participant DISP as ConnectorDispatcher
    participant CONN as Connector Instance

    Eng->>GR: runtime.tools.execute("search.web", payload)
    GR->>UCEL: execute("search.web", payload, context)
    UCEL->>UCEL: resolve_candidates("search.web")
    UCEL->>ET: execute(payload_dict)
    ET->>ET: build_request(payload_dict)
    ET->>CR: dispatch(ConnectorExecutionRequest)
    CR->>IDX: get_primary("search.web")
    IDX-->>CR: connector_id = "com.nexora.tavily"
    CR->>REG: get("com.nexora.tavily")
    REG-->>CR: Connector(state=RUNNING)
    CR->>DISP: dispatch(request, connector)
    DISP->>CONN: execute_on_connector(request)
    CONN-->>DISP: ConnectorExecutionResult(SUCCESS)
    DISP-->>CR: result
    CR-->>ET: ConnectorExecutionResult
    ET->>ET: build_capability_result(result)
    ET-->>UCEL: CapabilityResult(success=True)
    UCEL-->>GR: CapabilityResult
    GR-->>Eng: result_data
```

---

## 5. Connector Platform Ownership Matrix

| Responsibility | Owner | Must NOT Be In |
|---------------|-------|---------------|
| Connector discovery | `ConnectorRegistry` | `GenerationRuntime` |
| Connector lifecycle state | `ConnectorLifecycleManager` | `GenerationRuntime` |
| Capability namespace routing | `UniversalCapabilityRouter` (UCEL) | `ConnectorRuntime` |
| Credential storage | `SecretsProvider` (CP Phase 1) | Generation engines |
| Credential resolution | `CredentialResolver` | UCEL, GenerationRuntime |
| Health monitoring | `ConnectorHealthMonitor` | Generation engines |
| Dependency resolution | `ConnectorDependencyResolver` | UCEL |
| Execution dispatch | `ConnectorDispatcher` | `GenerationRuntime` |
| Connector manifest authority | `nexora.connector` (Odoo) | Services layer |
| UCEL routing decisions | `CapabilitySelectionEngine` | `ConnectorRuntime` |
| Generation session | `BuilderSessionService` | Connector Platform |
| Workspace artifacts | `WorkspaceAdapter` | Connector Platform |
| AI model selection | `OdooCapabilityResolver` | `ConnectorRuntime` |

---

## 6. Connector Dependency Graph

```mermaid
graph BT
    domain["domain/models.py\nPure Python Types"]
    connector_types["domain/connector_types.py\nType Descriptors"]
    type_registry["domain/type_registry.py\nType Registry"]
    cred_interfaces["credentials/interfaces.py\nABC Interfaces"]
    cap_index["registry/capability_index.py\nO(1) Lookup"]
    conn_registry["registry/connector_registry.py\nConnector Store"]
    states["lifecycle/states.py\nState Enum"]
    transitions["lifecycle/transitions.py\nState Machine"]
    lifecycle_mgr["lifecycle/lifecycle_manager.py\nTransition Orchestrator"]
    health_mon["runtime/health_monitor.py\nHealth Checker"]
    dep_resolver["runtime/dependency_resolver.py\nDep Graph"]
    dispatcher["runtime/dispatcher.py\nExecution Router"]
    conn_runtime["runtime/connector_runtime.py\nCentral Orchestrator"]
    executor["integration/connector_executor.py\nUCEL Bridge"]
    bridge["integration/runtime_bridge.py\nRuntime Bridge"]
    bootstrap["integration/bootstrap.py\nStartup Orchestrator"]
    odoo_models["models/connector/*\nOdoo Persistence"]

    connector_types --> domain
    type_registry --> connector_types
    cred_interfaces --> domain
    cap_index --> domain
    conn_registry --> domain
    states --> domain
    transitions --> states
    lifecycle_mgr --> transitions
    health_mon --> domain
    dep_resolver --> domain
    dispatcher --> conn_registry
    dispatcher --> cap_index
    conn_runtime --> conn_registry
    conn_runtime --> cap_index
    conn_runtime --> lifecycle_mgr
    conn_runtime --> health_mon
    conn_runtime --> dep_resolver
    conn_runtime --> dispatcher
    executor --> conn_runtime
    bridge --> conn_runtime
    bootstrap --> conn_runtime
    bootstrap --> executor
    bootstrap --> bridge
    conn_registry --> odoo_models
```

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|------|---------|-----------|
| Connector execution adapter not yet implemented | P2 | Dispatcher returns `NO_EXECUTION_ADAPTER` failure — non-blocking until CP Phase 2 |
| MCP transport layer is a stub | P1 | Connector dispatch for MCP type returns failure until PRE-004 resolved |
| SecretsProvider not yet implemented | P1 | `NullConfigurationAdapter` ensures non-null `runtime.configuration` — safe no-op |
| Bootstrap timing before DB ready | P2 | `startup()` gracefully handles None env; sync deferred |
| Odoo module load order | P2 | `connector` package loaded last in `models/__init__.py` |
| ConnectorTypeRegistry concurrent writes at startup | P3 | Protected by RLock; only builtins written at startup |
| UCEL `ExecutionTargetType.CONNECTOR` not yet defined | P2 | Bootstrap logs warning and skips registration — non-fatal |

---

## 8. Migration Timeline

```
Phase 26 (NOW)    → Architecture + Foundation (no connectors)
Phase 27 (CP-1)   → SecretsProvider + Resolver hardcode fix + Bootstrap hardening
Phase 28 (CP-2)   → GitHub + Git connectors + MCP transport + ADR-0044 migration
Phase 29 (CP-3)   → REST connectors (Gosom, Firecrawl, Tavily, Penpot, Spline, Context7)
Phase 30 (CP-4)   → Docker + CLI + Figma + Deployment connectors
Phase 31 (CP-GA)  → Legacy provider deprecation + Final migration
```
