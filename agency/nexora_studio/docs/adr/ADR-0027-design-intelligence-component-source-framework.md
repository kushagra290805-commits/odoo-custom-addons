# ADR-0027: Design Intelligence Platform & Component Source Framework

## Status: Proposed

## Date: 2026-07-24

## Context

As Nexora Studio evolves, the need for diverse and high-quality UI components has grown beyond what a static, internal Template Store can provide. Modern web development relies heavily on external component libraries (e.g., Shadcn, Magic UI, Aceternity), design assets (Penpot), and remote repositories (GitHub).

Currently, Nexora's architecture tightly couples component discovery and retrieval with the Builder Sessions and the internal Template Store. This monolithic approach hinders scalability, makes integrating third-party component sources difficult, and restricts the Builder to a limited set of internal assets.

To provide a richer, more dynamic design intelligence layer, we need a flexible framework capable of querying, normalizing, and provisioning components from any external or internal source transparently.

## Decision

We will implement the **Design Intelligence Platform (DIP)** with the **Component Source Framework (CSF)** as a provider-based, plugin-oriented architecture. This subsystem will remain completely decoupled from Builder Sessions, Template Store, and AI Orchestration, integrating with them only through well-defined service interfaces.

### 1. Provider Adapters
We will use a one-adapter-per-provider structure under `services/source_framework/adapters/`. Future providers (e.g., `shadcn_adapter.py`, `magic_ui_adapter.py`) can be plugged in without modifying existing core code.
- `base_adapter.py`
- `penpot_adapter.py`
- `github_adapter.py`
- `internal_adapter.py`

### 2. ComponentPackage Domain Model
To prevent adapters from returning provider-specific structures, we introduce the `ComponentPackage` domain model. This unified object encapsulates:
- Metadata
- Preview
- Dependencies
- Installation guide
- License
- Provenance
- Compatibility
- Provider information

### 3. Provider Capability System
Providers will explicitly advertise their supported capabilities (e.g., `SEARCH`, `PREVIEW`, `DOWNLOAD`, `DEPENDENCY_DISCOVERY`, `INSTALLATION_GUIDE`, `LICENSE_INFORMATION`). The `ProviderManager` will route requests based on these advertised capabilities rather than assuming universal support.

### 4. Provider Health Monitor
A dedicated `ProviderHealthMonitor` service will track provider health status, latency, rate-limit awareness, recovery detection, and enforce a retry/backoff strategy. The `ProviderManager` will skip unhealthy providers automatically.

### 5. Quality Scoring
The `QualityScorer` will evaluate components using heuristics including: repository popularity, maintenance recency, release activity, documentation quality, automated test availability, TypeScript support, accessibility, bundle size, performance, responsiveness, AI confidence, and license compatibility.

### 6. Dependency Resolution
The `DependencyResolver` will support recursive dependency graphs, peer dependencies, version conflicts, and package/framework compatibility, designed with future ecosystems (Shadcn, R3F/Drei) in mind.

### 7. Compatibility Checker
The `CompatibilityChecker` will validate components against the Builder Session context (React/Next.js versions, CSS strategy, TypeScript version, runtime constraints) and return structured compatibility reports.

### 8. Provenance Tracking
Every imported component will retain strict provenance metadata: provider, repository, commit SHA, release version, license, import timestamp, and import source.

### 9. Component Index
The `ComponentIndex` will only persist meaningful interactions (imported, installed, previewed, or AI-selected components) rather than every search result. The cache will also store provider version, indexing timestamp, cache version, and commit SHA.

### 10. Semantic Search Readiness
The `ComponentIndex` will be architected to reserve extension points for embeddings, semantic tags, AI-generated summaries, and vector search integration, avoiding future schema redesigns.

### 11. Plugin Architecture
Provider registration is entirely registry-driven. Adding a new provider requires only:
1. Creating the adapter.
2. Registering the provider.
3. Enabling the provider.
No modifications will be required to `SearchEngine`, `ProviderManager`, or `RecommendationEngine`.

## Consequences

*   **Positive**: A robust, future-proof plugin architecture for UI component sourcing.
*   **Positive**: High fault-tolerance via the Provider Health Monitor.
*   **Positive**: Highly decoupled services ensure isolated failure domains.
*   **Negative**: Initial engineering complexity is high due to comprehensive scoring, resolution, and compatibility layers.
