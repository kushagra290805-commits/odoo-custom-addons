# ADR-0050 — Universal Connector Platform

## 1. Status
**Accepted**

---

## 2. Context

Phase 25.1.5 certified the Nexora Studio runtime as architecturally stable and Connector Platform-ready. It identified a fundamental gap: the Generation Platform (UCEL, Runtime, Planning Layer) is a closed system optimized for deterministic AI-powered website generation. It has no mechanism to safely discover, configure, authenticate, monitor, or lifecycle-manage external integrations.

Previously, providers (GitHub, MCP tools, Firecrawl, etc.) were wired directly into Odoo models and provider registries without a coherent platform contract. This approach cannot scale, mixes provider-specific concerns into the generation runtime, has no unified lifecycle management, no credential isolation, no health monitoring, and cannot accommodate non-MCP connector types.

A Universal Connector Platform is needed as a **separate platform** that sits alongside the Generation Platform, communicates with it through officially defined extension points, and owns all responsibility for external system integration.

---

## 3. Decision

Introduce a Universal Connector Platform as an independent sub-system within Nexora Studio.

The Connector Platform:
- Is architecturally **separate** from the Generation Platform
- Communicates with the UCEL through the `ConnectorExecutionTarget` extension point (EP-004)
- Is the **sole authority** for connector lifecycle, credential management, health monitoring, and capability registration
- Is **never** owned, instantiated, or governed by the Generation Runtime
- Is **never** aware of generation sessions, pipeline stages, or workspace artifacts
- Is instantiated once at platform startup and remains active for the lifetime of the Odoo process

---

## 4. Architectural Separation

```
GENERATION PLATFORM (FROZEN)
────────────────────────────────────────────────────────
  BuilderSessionService → GenerationCoordinator
       → WebsiteGenerationPipeline → [17 Engines]
       → GenerationRuntime (frozen adapters)
       → UniversalCapabilityRouter (UCEL)
                     │
              EP-004 Extension Point
                     │
CONNECTOR PLATFORM (NEW — Phase 26)
────────────────────────────────────────────────────────
  ConnectorRuntime
       → ConnectorRegistry → ConnectorCapabilityIndex
       → ConnectorLifecycleManager
       → ConnectorDispatcher
       → ConnectorHealthMonitor
       → ConnectorDependencyResolver

  Credential Layer (interfaces only — Phase 26)
       → SecretsProvider
       → CredentialResolver
       → ConfigurationProvider
       → AuthenticationProvider

  Odoo Manager (Platform Authority)
       → nexora.connector, nexora.connector_type
       → nexora.connector_health, nexora.connector_event
       → nexora.connector_configuration, nexora.connector_log
       → nexora.connector_marketplace, nexora.connector_repository
       (+ 5 more models)
       │
       ▼
External Systems (future phases)
```

---

## 5. Connector Ownership Boundaries

### Connector Platform OWNS
- Discovery of available connectors
- Connector installation and dependency resolution
- Connector lifecycle state machine
- Connector configuration schema and validation
- Connector credential references and authentication
- Connector health monitoring and degradation handling
- Connector capability namespace registration with UCEL
- Connector event logging and diagnostics
- Connector marketplace and repository management

### Connector Platform DOES NOT OWN
- Generation sessions (owned by `BuilderSessionService`)
- Generation pipeline state (owned by `WebsiteGenerationPipeline`)
- Capability routing decisions (owned by `UniversalCapabilityRouter`)
- Provider ranking for AI models (owned by `CapabilitySelectionEngine`)
- Workspace artifacts (owned by `WorkspaceAdapter`)
- AI prompt engineering (owned by generation engines)

---

## 6. Connector Lifecycle States and Transitions

```
REGISTERED → DISCOVERED → DOWNLOADED → INSTALLED → CONFIGURED
→ AUTHENTICATED → VALIDATED → HEALTHY → RUNNING ↔ PAUSED
                                          │
                               ┌──────────┼──────────┐
                               ▼          ▼           ▼
                           DISABLED    FAILED     UPDATING → INSTALLED
                                          │
                                          ▼
                                       REMOVED
```

**Transition Guards:**
- `INSTALLED → CONFIGURED` — configuration schema must be satisfied
- `CONFIGURED → AUTHENTICATED` — at least one credential reference must resolve
- `AUTHENTICATED → VALIDATED` — health probe must pass
- `VALIDATED → HEALTHY` — zero critical diagnostic failures
- `HEALTHY → RUNNING` — automatic on HEALTHY confirmation
- `RUNNING → PAUSED` — operator-initiated only
- `* → FAILED` — automatic on unhandled error or health failure
- `* → REMOVED` — requires DISABLED or FAILED as precondition

---

## 7. Runtime Communication with UCEL

```
UCEL.execute("search.web", payload, context)
       │
       ▼
 CapabilityResolver.resolve_candidates("search.web")
       │
       ▼
 ExecutionScheduler → ConnectorExecutionTarget.execute(payload)  [EP-004]
       │
       ▼
 ConnectorRuntime.dispatch(ConnectorExecutionRequest)
       │
       ▼
 ConnectorDispatcher → [Connector Instance] → External System
       │
       ▼
 ConnectorExecutionResult → CapabilityResult → UCEL caller
```

The UCEL does not know whether it is talking to a `LocalToolExecutor`, `RemoteToolExecutor`, or `ConnectorExecutionTarget`. This is a transparent, additive extension.

---

## 8. Extension Philosophy

1. **New connector types** — register a `ConnectorTypeDescriptor` in the `ConnectorTypeRegistry`. No existing code changes.
2. **New capabilities per connector** — add capability manifests to `nexora.connector_capability`. Index updates automatically.
3. **New credential types** — define a new `ConnectorCredentialReference.credential_type` value and implement a new `AuthenticationProvider`. No interface changes to `SecretsProvider`.
4. **New lifecycle states** — can be inserted between existing states; existing state names and exit transitions are immutable.

---

## 9. Forward Compatibility Guarantees

1. **Additive only.** New connector types never require modifying `ConnectorRuntime`, `ConnectorRegistry`, or `ConnectorLifecycleManager`.
2. **Namespace stability.** Once a capability namespace is registered, it is never removed or renamed. Deprecated namespaces are aliased.
3. **Contract preservation.** `ConnectorExecutionRequest` and `ConnectorExecutionResult` schemas are append-only.
4. **Credential isolation.** The `SecretsProvider` interface is the only credential access path. No connector may read credentials through any other mechanism.
5. **Platform boundary.** The Connector Platform never imports from `services/generation/`. The Generation Platform imports from the Connector Platform only through `services/connector/integration/`.

---

## 10. Consequences

**Positive:**
- Unified lifecycle for all connector types (MCP, REST, GraphQL, CLI, Docker, etc.)
- Credential isolation at interface boundary
- Independent health monitoring per connector
- Full auditability via event and diagnostic models
- Marketplace management for future connector discovery
- Zero coupling to Generation Platform internals
- Forward-compatible by design

**Negative:**
- ~38 new files in Phase 26 (architecture only)
- Connector implementations require type-specific adapters (future phases)
- Bootstrap timing must be coordinated with Odoo database readiness

---

## 11. ADR Relationships

| ADR | Relationship |
|-----|-------------|
| ADR-0029 | UCEL — ConnectorPlatform communicates through EP-004 |
| ADR-0042 | Generation Architecture Constitution — preserved intact |
| ADR-0044 | Canonical Provider Execution Contract — ConnectorExecutionResult follows same semantics |
| ADR-0047 | Capability Selection Engine — unchanged |
| Phase 25.1.5 PRE-001 | SecretsProvider interface defined in Part 8 |
| Phase 25.1.5 PRE-002 | CapabilityResolver hardcode addressed via ConnectorRegistry bootstrap |

---

## 12. Acceptance Criteria

- All Phase 26 files created and Odoo-loadable
- `ConnectorRuntime` boots without error
- `ConnectorLifecycleStateMachine` enforces all transition guards
- `SecretsProvider`, `CredentialResolver`, `ConfigurationProvider`, `AuthenticationProvider` defined as ABCs
- `ConnectorExecutionTarget` registered in UCEL executor dict
- No provider-specific code in `services/connector/`

---

## 13. Refinements (Phase 26.1)

The architecture was refined in Phase 26.1 to implement:
- **Generic Source Architecture**: Replaced Marketplace/Repository with generic `Source` and `Catalog` abstractions.
- **Manifest / Release Separation**: Replaced `ConnectorVersion` with an immutable `ConnectorManifest` and multiple `ConnectorRelease` records, distinguishing published artifacts from deployed instances (`ConnectorInstallation`).
- **Persistence Adapter Pattern**: Introduced `ConnectorPersistencePort`, isolating the `ConnectorRuntime` from Odoo ORM (`OdooConnectorPersistenceAdapter`).
- **Capability Decoupling**: Separated `CapabilityDefinition` (canonical namespace and schema) from `ConnectorCapabilityImplementation` (connector-specific priority and configuration).
- **Expanded Configuration**: Upgraded `ConnectorConfiguration` to a full document model supporting schema, defaults, user overrides, and secret references.
- **Structured Telemetry**: Expanded `ConnectorHealth` to include structured telemetry (availability, latency, quota/rate-limit status, and drift detection).
- **Typed Event Bus**: Introduced a synchronous `ConnectorEventBus` to decouple components like `LifecycleManager` and `HealthMonitor`.
- **Connector SDK Foundation**: Created a formal SDK (`BaseConnector`, `ExecutionContext`, `Exceptions`) for future connector authors to build against.

---

## 14. Final Architecture Freeze (Phase 26.2)

The architecture was permanently frozen in Phase 26.2 after introducing the following final refinements:
- **Connector Environment**: Introduced `ConnectorEnvironment` to explicitly model the execution destination (local, docker, vps, etc) and its constraints (CPU, memory, OS, network access), ensuring the platform supports multiple installations of the same connector safely.
- **Factory Isolation**: Extracted all dependency injection, provider selection, and transport wiring into a dedicated `ConnectorFactory` layer. The `ConnectorRuntime` is now strictly limited to lifecycle orchestration.
- **Complete SDK**: Finalized the provider SDK by introducing abstract base classes for all capability, transport, configuration, authentication, and health resolution patterns.
- **Future Extensibility Audit**: Certified that the platform architecture can seamlessly accommodate MCP, GitHub, REST, Docker, CLI, and AI models without any core runtime or registry modifications.
