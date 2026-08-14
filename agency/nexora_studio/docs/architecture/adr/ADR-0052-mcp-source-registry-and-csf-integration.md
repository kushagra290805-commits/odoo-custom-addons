# ADR-0052: MCP Source Registry & CSF Integration

## Status: ACCEPTED

**Acceptance Rationale:**
Phase 29 consumes Phase 28 ConnectorRuntime exclusively for MCP transport, lifecycle, authentication, capability discovery and execution.
Phase 29 owns source registration, source classification, ranking, normalization and DIP/CSF integration.
Figma MCP remains explicitly deferred until Nexora Studio is successfully hosted. The active Phase 29 MCP set is GitHub, Context7, Tavily, Firecrawl, Penpot, Spline, and Gosom. Figma is the ONLY deferred MCP provider from this active provider family.

## Date: 2026-08-10

## Context

Phase 28 established the `ConnectorRuntime` and MCP Onboarding Platform (ADR-0050, ADR-0051), providing a secure, lifecycle-managed execution environment for MCP tools and resources, isolated from the generation pipeline. 

Simultaneously, Phase 27 established the Design Intelligence Platform (DIP) and Component Source Framework (CSF) (ADR-0027, ADR-0028) to normalize external component and design asset ingestion into a unified `ComponentPackage`.

Phase 29 must bridge these two architectures. We need to integrate our new MCP capabilities as component/knowledge sources for DIP without allowing DIP to manage MCP lifecycles directly, thereby respecting the Phase 28 security and architectural boundaries.

## Decision

### 1. Architectural Boundary and Principles

**Architectural Principle:**
Phase 28 owns connection, transport, authentication, lifecycle, discovery and execution.
Phase 29 owns source registration, normalization, retrieval, ranking and DIP/CSF integration.

- **Phase 28 (`ConnectorRuntime`)** retains exclusive responsibility for:
  - MCP connection establishment and transport (stdio, SSE, etc.)
  - Lifecycle management and health monitoring
  - Security, credentials (`nexora.mcp_credential`), and configuration (`nexora.mcp_server_config`)
  - Capability discovery and storage (`nexora.mcp_discovered_tool`)
  - Execution dispatching (`ConnectorRuntime.dispatch`)

- **Phase 29 (DIP/CSF)** is strictly a **consumer** of the `ConnectorRuntime`.
  - DIP/CSF MUST NOT directly launch MCP subprocesses or manage sessions.
  - All interactions with MCP providers will occur via `ConnectorRuntime.dispatch()`.

### 2. Transport Architecture

Phase 29 is transport-agnostic. MCP transport selection and lifecycle remain exclusively owned by Phase 28 `ConnectorRuntime` and its transport abstraction. DIP/CSF interacts only with the Phase 28 execution interface. We do not assume all MCP providers use stdio (e.g., Penpot uses SSE). Do not duplicate transport handling inside DIP/CSF.

The architecture conceptually is:

```text
DIP
  ↓
CSF Source Provider
  ↓
McpSourceAdapter
  ↓
ConnectorRuntime.dispatch()
  ↓
Phase 28 transport abstraction
  ├── stdio → GitHub / Context7 / Tavily / Firecrawl
  └── SSE → Penpot
```

### 3. The Source Provider Contract

DIP/CSF will consume a normalized `SourceProvider` contract. We introduce `McpSourceAdapter` (extending `BaseAdapter`) which acts as the translation layer.
- **Input**: CSF normalized query (e.g., "Search for a React hero component")
- **Translation**: `McpSourceAdapter` maps this to an MCP tool execution request using `ConnectorCapabilityIndex`.
- **Execution**: The adapter calls `ConnectorRuntime.dispatch(ConnectorExecutionRequest(action=..., payload=...))`.
- **Output**: The adapter normalizes the MCP tool result into a `ComponentPackage` or `KnowledgeDocument`.

### 4. Odoo Model Relationships

- `nexora.connector`: Represents the physical/transport connection to a provider.
- `nexora.mcp_server_config`: The technical parameters to start the connection.
- `nexora.mcp_discovered_tool`: The raw capabilities discovered by the connection.
- `nexora.source_registry`: Will be updated to act as the **logical routing layer** for DIP. It will include a `Many2One` relation to `nexora.connector`. It manages ranking weights, provider categories, and determines which adapter (`adapter_class`) processes the connector's output.
- **Builder Session**: Consumes `DIP` to query for assets. It has no direct knowledge of `nexora.connector` or MCP.

### 5. Source Classification

Sources are classified to determine their adapter boundary and retrieval strategy.

**ACTIVE PHASE 29 MCP PROVIDERS:**
| Source | Classification | Adapter Boundary |
|---|---|---|
| **GitHub MCP** | Repository Source | `McpSourceAdapter` (delegates to ConnectorRuntime) |
| **Context7 MCP** | Documentation/Knowledge Source | `McpSourceAdapter` |
| **Tavily MCP** | Web Research Source | `McpSourceAdapter` |
| **Firecrawl MCP** | Web Extraction Source | `McpSourceAdapter` |
| **Penpot MCP** | Design Source | `McpSourceAdapter` |
| **Spline** | Design Source | `McpSourceAdapter` |
| **Gosom** | Internal Source | `McpSourceAdapter` |

**DEFERRED MCP PROVIDERS:**
| Source | Classification | Reason |
|---|---|---|
| **Figma MCP** | Design Source | Deferred until hosted deployment. Local/device constraints make it unsuitable for the current local integration. |

**PACKAGE / COMPONENT SOURCES:**
| Source | Classification | Adapter Boundary |
|---|---|---|
| **shadcn** | Package/Component Source | `ComponentLibraryAdapter` |
| **Magic UI** | Package/Component Source | `ComponentLibraryAdapter` |
| **Aceternity** | Package/Component Source | `ComponentLibraryAdapter` |
| **React Bits** | Package/Component Source | `ComponentLibraryAdapter` |
| **21st.dev** | Package/Component Source | `ComponentLibraryAdapter` |
| **R3F/Drei** | Package/Component Source | `ComponentLibraryAdapter` |
| **Nexora Template Store** | Internal Source | `InternalAdapter` |
| **GitHub repositories** | Repository Source | `GitRepositoryAdapter` |

**DOCUMENTATION SOURCES:**
| Source | Classification | Adapter Boundary |
|---|---|---|
| **Three.js docs** | Documentation Source | `DocumentationAdapter` |
| **React Three Fiber docs** | Documentation Source | `DocumentationAdapter` |
| **Drei docs** | Documentation Source | `DocumentationAdapter` |
| **GSAP docs** | Documentation Source | `DocumentationAdapter` |
| **MDN docs** | Documentation Source | `DocumentationAdapter` |

### 6. MCP Provider Verification Definition

A provider is **VERIFIED** only after the current Phase 28 `ConnectorRuntime` has successfully:
1. initialized the actual provider,
2. established the actual MCP transport,
3. completed MCP initialization,
4. discovered capabilities,
5. and successfully executed at least one representative capability.

Repository existence or package availability must NOT be considered verification. All active Phase 29 MCP candidates (GitHub, Context7, Tavily, Firecrawl, Penpot, Spline, Gosom) currently remain **UNVERIFIED**.

### 7. Deferred Integration: Figma MCP

Nexora Studio will NOT integrate Figma MCP during the current local development/Phase 29 work. 
- **Current Design Provider**: Penpot MCP is the deliberately selected active design MCP for the current architecture.
- **Figma Future Boundary**: Figma MCP integration will happen in a later hosted phase after the production hosting environment is operational. No Phase 29 connector or source record should be created for Figma.
- **Existing Groundwork**: Existing Figma provider/adaptor work from ADR-0028 should remain as architectural groundwork. It must not be deleted or treated as obsolete, but marked as future hosted integration groundwork.

### 8. Architectural Gaps & Contradictions

- **Contradiction (ADR-0028)**: ADR-0028 proposed an `MCPTransport` inside the `source_framework`. This contradicts ADR-0050/0051 which centralized all MCP transport in `ConnectorRuntime`. 
  - **Resolution**: `source_framework/transport/mcp_transport.py` will be deprecated. The CSF `McpSourceAdapter` will directly invoke `ConnectorRuntime.dispatch()`, delegating transport entirely to Phase 28.
- **Gap**: `nexora.source_registry` currently contains a `config_json` field that historically stored credentials. 
  - **Resolution**: This field will be strictly sanitized. Credentials must be migrated to `nexora.mcp_credential` linked via a `nexora.connector` record.

## Consequences

- **Positive**: Strict decoupling. DIP focuses purely on AI-driven retrieval and normalization; ConnectorRuntime focuses purely on secure protocol execution.
- **Positive**: Zero credential leakage into the Design Intelligence Platform.
- **Negative**: Adds a layer of indirection (DIP -> CSF Adapter -> ConnectorRuntime) requiring careful error translation mapping.
