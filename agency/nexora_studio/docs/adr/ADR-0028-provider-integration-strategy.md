# ADR-0028: Provider Integration Strategy & MCP Transport Foundation

## Status: Accepted

## Date: 2026-07-24

## Context
With the introduction of the Component Source Framework (CSF), we need a rigid protocol governing how external systems (like Penpot and GitHub) communicate with Nexora Studio. Adapters should not be tightly coupled to a specific underlying execution engine like the MCP service, as we may want to support standard REST or GraphQL endpoints in the future.

## Decision
We introduce the **MCP Transport Abstraction Layer** and the **Provider Integration Strategy**.

### 1. Transport Layer Abstraction
All provider adapters MUST communicate through a `BaseTransport` interface, instantiated via a `TransportFactory`. The factory manages the lifecycle and can inject an `MCPTransport`, `MockTransport`, or future `RESTTransport`.

### 2. Provider Lifecycle
- **Registration**: Providers are registered in the `nexora.source_registry` Odoo model.
- **Discovery**: `ProviderManager` dynamically loads them based on their `technical_name` and capabilities.
- **Health**: Providers failing 3 consecutive transport calls are disabled temporarily.

### 3. Capabilities
Providers explicitly declare capabilities (e.g. `DESIGN_TOKENS`, `SEARCH`, `DEPENDENCY_DISCOVERY`). Transport capabilities (e.g., `TOOL_CALL`, `REST`) are evaluated separately by the `TransportFactory`.

### 4. Normalized Output
All outputs must be strictly normalized into `ComponentPackage`, extracting `DesignTokenPackage` (colors, typography, layout) and separating `ComponentPreview` and `ComponentMetadata`.

### 5. Configurable Ranking Profiles
A new `ComponentRankingPipeline` is injected at the end of the `SearchEngine`. It uses configurable profiles (e.g., `default`, `strict_internal`) rather than fixed weights to rank results before presenting to the Builder.

## Consequences
- Providers are now completely transport-agnostic.
- Mock testing is perfectly isolated without requiring a live MCP backend.
- Future REST providers can be added effortlessly.
