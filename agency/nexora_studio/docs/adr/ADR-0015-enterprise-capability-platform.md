# ADR-0015: Enterprise Capability Platform

## Status
Accepted

## Context
Phase 8A.1 introduced a Dynamic Capability Registry, successfully decoupling tool resolution from Python model names. However, the discovery process still relied on _register_hook() making ORM writes upon module upgrade. As the platform prepares for a diverse ecosystem (MCP, IDEs, external AI agents, Cloud Providers, Kubernetes runners), the registry must mature into an Enterprise Capability Platform. 

## Decision
We will separate concerns by extracting caching, discovery, and lifecycle management from the capability_registry model into dedicated enterprise services.

### Architecture Constraints
1. **No ORM Writes in Boot Hooks**: _register_hook() must solely expose metadata dictionaries (without writing to the DB).
2. **Capability Discovery Service**: A dedicated service (capability_discovery_service) runs as an idempotent synchronization job, comparing available Python/plugin metadata against the DB to register, update, or deprecate capabilities.
3. **Capability Cache Service**: To prevent O(N) database queries per runtime launch, the capability_cache_service will map the dependency graph, cache valid capabilities, and provide O(1) in-memory resolution.
4. **Lifecycle Manager**: capability_lifecycle_service orchestrates install, upgrade, downgrade, disable, and enable actions, emitting appropriate untime_events.
5. **Standardized Metadata**: Every capability must expose an expanded payload including dependencies, versions, author, category, and async support. Missing metadata will result in discovery rejection.
6. **Plugin Framework**: Plugins will exist in a dedicated file structure and self-register via discovery, ensuring core runtime code never imports plugin code directly.

## Consequences
- **Positive**: Sub-millisecond runtime capability resolution due to the capability_cache_service.
- **Positive**: Boot loops are safer without recursive DB updates in _register_hook().
- **Positive**: Dependency graphs allow capabilities to start/stop in proper order (e.g., github requires git_runtime).
- **Negative**: Increased complexity in discovery and caching logic.
