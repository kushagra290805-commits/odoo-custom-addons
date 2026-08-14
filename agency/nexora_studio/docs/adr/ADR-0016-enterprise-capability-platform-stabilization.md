# ADR-0016: Enterprise Capability Platform Stabilization

## Status
Accepted

## Context
Phase 11 introduced the Enterprise Capability Platform to decouple runtime features (like tools, preview engines) from hardcoded implementations. However, relying on Python model inspection for discovery is error-prone, insecure for third-party extensions, and violates clean separation of concerns. Additionally, the cache implementation was tightly coupled to Odoo models and lacked a thread-safe, distributed-ready backend. To scale Nexora Studio across distributed workers and an open plugin ecosystem, the platform requires rigorous stabilization.

## Decision
1. **Manifest-Based Discovery**: We will replace Python reflection (self.env.registry.items()) with a plugin.json manifest requirement. The CapabilityDiscoveryService will become manifest-driven, scanning the filesystem for plugin.json descriptors. Python classes will only execute logic, not govern their own registration.
2. **Plugin Manifest Validation**: A dedicated PluginManifestValidator service will enforce JSON schema compliance, Semantic Versioning rules, and dependency constraints.
3. **Plugin Package Manager**: A central PluginManager will orchestrate the lifecycle of plugins (install, upgrade, downgrade, enable, disable), acting as the single entry point.
4. **Abstract Capability Cache**: We will refactor CapabilityCacheService to abstract the backend (MemoryCacheBackend today, RedisCacheBackend tomorrow) for worker-safe operation.
5. **Dependency Graph V2**: A formal DependencyGraphService will enforce startup order and detect cycles.
6. **Metadata Versioning**: A MetadataVersionService will handle schema migrations (e.g., from v1.0 to v2.0) to preserve backward compatibility.
7. **Plugin Compatibility Layer**: A CompatibilityService will gate plugins based on minimum/maximum runtime versions.
8. **Expanded Runtime Events**: Granular events (plugin.installed, dependency.cycle_detected, etc.) will provide full traceability.

## Consequences
- **Positive**: Complete decoupling of discovery from Odoo model loading. 
- **Positive**: Strict verification of third-party plugins before they can execute.
- **Positive**: Worker-safe caching paves the way for distributed Generation Jobs.
- **Negative**: Increased complexity in plugin authoring, as authors must maintain both Python logic and plugin.json manifests. All existing capabilities (ilesystem, git, 	erminal, etc.) must be migrated to the manifest format.
