# ADR 0058: Penpot Component Source Integration

## Status
Accepted

## Context
As part of Phase 32, we are integrating Penpot as an external Component and Design Source. Historically, Penpot integration was approached via custom providers, adapters, and standalone clients (e.g., `penpot_adapter.py`, `penpot_provider.py`). These legacy paths violated the core architectural mandate that all external intelligence sources must remain strictly optional and isolated from the core orchestration paths. The Nexora core must never depend on the availability of a specific external source provider.

The platform has established a canonical, configuration-driven integration path for external sources via the Phase 31 generic `McpSourceAdapter`.

## Decision

1. **Penpot is an External Plugin:** Penpot will be treated strictly as an optional external plugin. It is not a core dependency.
2. **Chosen Integration Boundary:** We will integrate Penpot via the canonical `Source Framework`. The runtime execution path will be:
   `ComponentDiscoveryEngine -> SearchEngine -> ProviderManager -> SourceRegistry -> McpSourceAdapter -> ConnectorRuntime -> penpot_mcp`.
3. **Reuse of Existing Infrastructure:** The generic `McpSourceAdapter` introduced for GitHub/Shadcn handles semantic intent mapping (`search`, `get`), generic payload configuration, and response normalization. Penpot will utilize this generic adapter through purely declarative JSON configurations in the `SourceRegistry`. No Penpot-specific orchestration (e.g., `PenpotDiscoveryEngine`) will be implemented.
4. **Configuration / Credential Strategy:** Credentials (`PENPOT_CONFIGURATION`) will be injected dynamically at runtime via the established `nexora.mcp_credential` model. The integration must not require credentials during installation or module boot.
5. **Capabilities Required:** The integration will map standard semantic intents (like `search` or `get_component`) to the available `@penpot/mcp` tools, which will be discovered dynamically.
6. **Failure Isolation:** Any failures, unavailability, or missing credentials for `penpot_mcp` will bubble up and be caught gracefully by the `ProviderManager` health monitoring, ensuring unrelated sources (e.g., `react_bits`) and the core platform remain fully functional.

## Consequences

### Positive
* **Decoupling:** Eliminates tight coupling between Nexora core and the Penpot ecosystem.
* **Consistency:** Unifies Penpot integration with other component sources like Shadcn and React Bits.
* **Resiliency:** Core initialization and independent modules are impervious to Penpot downtimes or configuration errors.

### Negative / Explicit Non-Goals
* **Non-Goal:** We will *not* implement bi-directional syncing or deep Penpot workspace management features if they fall outside the standard MCP Component/Source capability contracts.
* **Non-Goal:** We will *not* create bespoke domain models for Penpot nodes if they can be mapped to existing `ComponentPackage` or `DesignTokenPackage` representations.

## Rejection of Bespoke Orchestration
We explicitly reject maintaining or utilizing `PenpotAdapter`, `PenpotProvider`, `PenpotConnector`, or direct API orchestrations. These parallel implementations violate our generic source boundary requirements and will be classified as deprecated/dead code in the ensuing audit.
