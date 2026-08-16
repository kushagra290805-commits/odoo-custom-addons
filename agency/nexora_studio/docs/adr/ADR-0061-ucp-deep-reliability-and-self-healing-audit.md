# ADR 0061: UCP Deep Reliability and Self-Healing Audit

## Status
Accepted

## Context
The Universal Connector Platform (UCP) is now capable of integrating dynamic MCP connectors (both via stdio and SSE transports), establishing lifecycles, maintaining capabilities, and reconstructing configurations upon restart (as proven in Phase 35.2).

However, before the platform can safely graduate to autonomous GoSOM execution, we must produce an evidence-backed reliability baseline. We need to definitively answer what breaks the UCP, how it behaves during failures, whether it successfully classifies failures (e.g. transport vs. credential vs. protocol), and exactly what self-healing functionality is missing.

## Decision
We will execute **Phase 35.3: UCP Deep Reliability, Failure-Injection & Self-Healing Audit**.

This phase is **DIAGNOSTIC ONLY**. We will deliberately break the UCP using failure injection, concurrency stress, and restart torture to observe its behavior.
No production codebase changes (remediations) are permitted during this phase to fix defects discovered. All findings will be cataloged in a formal defect inventory matrix with severity classifications to inform the GoSOM Readiness Assessment.

### Architectural Rules
1. **Reuse Existing Infrastructure**: Rely solely on existing runtime, registry, health, dispatcher, onboarding, and transport infrastructure. No parallel runtimes or health systems will be built.
2. **Immutable Production State**: Do not manually force health/lifecycle states through ORM or SQL to make tests pass. Canonical connectors (`github_mcp`, `context7_mcp`, `firecrawl_mcp`, `penpot_mcp`) will be used as read-only regression anchors only.
3. **Disposable Fixtures for Mutation**: All failure injection, concurrency, and stress testing will use disposable connectors with run-scoped IDs (e.g., `test.mcp.reliability.<run_id>`).
4. **Explicit Cleanup**: A fixture ledger will track all created resources (connectors, configs, credentials, PIDs), ensuring cleanup executes through `finally`/`teardown` paths regardless of test success/failure.
5. **Thread Isolation**: Concurrent Odoo workers must NEVER share an Environment or cursor. Each thread will instantiate and close its own cursor/Environment correctly.
6. **Zero Plaintext Credentials**: No credentials will be printed, persisted, captured, compared, or reported in plaintext. Decrypted secrets will not be inspected for testing convenience.

### Ownership Map
The audit will inspect and stress the following components and their defined boundaries:

- **ConnectorPlatformBootstrap**: Controls startup sequences, Odoo sync triggers, and asynchronous background reconciliation (`_startup_reconciliation`).
- **ConnectorRuntime**: Central domain orchestrator managing the `ConnectorRegistry` and `capability index`.
- **ConnectorRegistry**: In-memory store holding authoritative active instances of `Connector` aggregates.
- **ConnectorPersistenceService & Odoo Adapter**: Translates UCP domain models to/from Odoo ORM (`nexora.connector`, etc.).
- **McpOnboardingService**: Manages connector registration, capability discovery, and `McpConfiguration` reconstruction.
- **ConnectorDispatcher & McpTransport**: Instantiates concrete `McpConnector` objects and manages the physical I/O streams (stdio subprocesses, SSE HTTP connections).
- **ConnectorHealth & HealthMonitor**: Domain models and Odoo scheduled actions (`_cron_check_health`) responsible for executing periodic probes and classifying operational status.
- **Credential Resolver & OdooSecretsProvider**: Abstract resolution strategy mapping configurations to persistent secret backends.

## Consequences
- **Positive**: We will obtain a 100% trustworthy, empirical baseline of what UCP can and cannot survive, eliminating assumptions before autonomous GoSOM integration.
- **Positive**: We cleanly separate diagnosis from remediation, preventing scope creep and ensuring that when we do implement self-healing, it solves documented defects.
- **Negative**: Executing and observing these manual/automated failure matrices demands significant diagnostic time and temporary disposable orchestration scripts.
