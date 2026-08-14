# ADR-0017: Enterprise Runtime Hardening

## Status
Accepted

## Context
Phase 11.1 introduced a manifest-driven architecture for the Enterprise Capability Platform. However, some services (like `PluginManager`) accrued multiple responsibilities, versions and cache backends were hardcoded, and the platform relied heavily on raw Python dictionaries for capability representation.

To prepare for Phase 8B and production workloads, the platform needed to adopt a Single Responsibility Principle (SRP), dynamic factory instantiation, strict capability state machines, and cryptographic integrity checks.

## Decision

### 1. Plugin Descriptor & Integrity Verification
We introduced the `PluginDescriptor` data transfer object (DTO). Raw JSON dictionaries are no longer passed between services. `PluginManifestValidator` now parses the manifest, calculates a SHA-256 checksum (to prevent tampering), and emits an immutable `PluginDescriptor`.

### 2. State Machine & Runtime Events Namespace
We abandoned simplistic boolean `enabled` flags in favor of an explicit capability state machine. Valid states are: `DISCOVERED`, `VALIDATED`, `INSTALLED`, `ENABLED`, `DEGRADED`, `DISABLED`, and `REMOVED`. All lifecycle events are standardized under the `RuntimeEvents` namespace.

### 3. Service Refactoring (SRP)
`PluginManager` was refactored into a facade, delegating actual logic to `PluginInstallerService` (for validation, integrity, and installation) and `PluginLifecycleService` (for state transitions).

### 4. Cache & Repository Factories
Instead of hardcoded dependencies, the system now relies on `CacheBackendFactory` (returning `MemoryCacheBackend` or `RedisCacheBackend`) and `PluginRepositoryFactory` (returning `LocalPluginRepository`). This ensures the discovery service does not know about the physical filesystem.

### 5. Semantic & Runtime Versioning
We introduced `RuntimeVersionService` as the definitive source of truth for the platform's version, and `SemanticVersionService` to provide strict boundary validation for `minimum_runtime_version` and `maximum_runtime_version`.

### 6. Builder Health Snapshot
`BuilderHealthService` now yields an immutable `BuilderHealthSnapshot` instead of forcing the UI/dashboard models to lazily compute expensive dependency and cache states on every page load.

## Consequences
- **Positive:** Complete isolation of concerns. Easy to swap in a Redis cache or a remote marketplace repository in the future without touching business logic.
- **Positive:** Cryptographic verification protects against corrupted manifest loads.
- **Negative:** Increased class count and abstraction overhead.
