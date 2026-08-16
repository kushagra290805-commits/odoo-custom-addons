# ADR-0063: Architecture Governance and Anti-Parallelism Rule

**Date**: 2026-08-16
**Status**: Accepted
**Context**: Nexora Studio Universal Connector Platform (UCP)

## Context
During the expansion of the Universal Connector Platform (Phase 35), an architecture audit revealed the persistence of a "legacy" MCP execution runtime (`services/runtime/mcp/`) running completely in parallel with the newly established canonical UCP runtime (`services/connector/`). 
This dual-runtime architecture caused duplicated ownership (two registries, two catalogs, two dispatchers, overlapping background threads) and obscured execution paths, violating the core tenets of the UCP. 

Parallel architectures create immense technical debt, unpredictable failure domains, and unmaintainable sprawl. We must establish a strict governance rule to prevent the introduction of new parallel orchestrators and enforce maximum reuse of the canonical architecture.

## Decision
We establish a permanent **Hard Architecture Rule** governing all future additions to the Nexora Studio ecosystem. 

Before implementing a new component or abstraction, developers and autonomous agents MUST search the repository for the existing owner and all existing consumers. **A new component is explicitly PROHIBITED when an existing canonical component can satisfy the requirement through extension or integration.**

### 1. Mandatory Pre-Implementation Sequence
Every implementation of a new system, connector, or provider MUST follow this sequence:
1. **Inspect** the existing architecture.
2. **Identify** the canonical owner for the responsibility being changed.
3. **Trace** actual callers and runtime usage.
4. **Search** for duplicate/parallel implementations.
5. **Determine** whether the requested capability already exists.
6. **Reuse/extend** the existing canonical implementation if it exists.
7. **Consolidate** or remove duplicate logic where appropriate.
8. **Only create a new abstraction** if the audit proves that no suitable canonical owner exists.
9. **Document** the architectural decision in an ADR before implementation.
10. **Implement**.
11. **Verify** real runtime behavior and ownership.
12. **Verify** that no parallel execution path was introduced.

### 2. Canonical Architecture Ownership Matrix
The following components are the strictly enforced, permanent canonical owners of their respective domains. No parallel component may be created that overlaps with these responsibilities.

| Domain | Canonical Owner |
| :--- | :--- |
| **Connector Registration** | `ConnectorRegistry` (via `ConnectorRegistrationPipeline`) |
| **Connector Runtime** | `ConnectorRuntime` (No "UniversalManager", no "McpManager") |
| **Lifecycle** | `ConnectorLifecycleManager` |
| **Health** | `ConnectorHealthMonitor` |
| **Events** | `ConnectorEventBus` |
| **Recovery** | `ConnectorRuntime` (Canonical single-flight recovery path) |
| **Initialization** | `ConnectorDispatcher.initialize_and_verify()` |
| **Transport** | Existing canonical transport abstraction (`McpTransport`, `LocalCliTransport`) |
| **Capability Registry** | `ConnectorCapabilityIndex` |
| **Capability Execution** | `ConnectorDispatcher` (Canonical execution path) |
| **Generation Engine** | Existing Generation Engine (`execution_orchestrator.py` etc.) but MUST delegate tool execution to UCP |
| **GoSOM (System of Models)** | Interface/translation layer only. No new connector runtime architecture. |

### 3. Deletion Before Replacement Rule
When replacing an architectural component:
1. The new canonical component must be established.
2. All consumers must be migrated.
3. The legacy component must be proven unreachable.
4. The legacy component MUST be deleted.
Ghost threads, orphaned registries, and unreachable orchestrators must not be left in the codebase.

### 4. ADR Requirement for Future Architecture
For every future major architectural phase, an ADR MUST be created or updated *before* implementation begins. The ADR must explicitly define the existing owner, why it is sufficient/insufficient, the reuse strategy, affected consumers, migration strategy, deletion strategy, and verification plan.

## Consequences
- **Positive:** A highly cohesive, predictable, and resilient architecture where all capabilities route through hardened, globally visible choke points (e.g., `ConnectorDispatcher`, `ConnectorEventBus`).
- **Negative:** Slightly higher upfront friction when introducing new capabilities, as developers must thoroughly audit and integrate with existing abstractions rather than greenfielding parallel structures.
