# Architectural Risk Register

This document tracks unresolved architectural risks for the Universal Connector Platform.

| ID | Description | Impact | Likelihood | Mitigation | Blocks Phase 27? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RISK-01** | `ConnectorRuntime` operates exclusively in memory during high-throughput execution. On process restart, the registry is rebuilt from the DB. A database crash during runtime might desync the true `lifecycle_state` from the DB. | Low (only affects persistence, not active execution) | Low | Introduce periodic background sync from Memory -> DB in the `OdooConnectorPersistenceAdapter`. | **NO** |
| **RISK-02** | The `UniversalCapabilityRouter` uses EP-004 to send payloads. If payload shapes change upstream, the Connector Platform might fail to parse them dynamically. | High | Medium | Define rigid JSON Schema validations on `ConnectorExecutionRequest`. | **NO** |
| **RISK-03** | Capability conflicts (two connectors implementing the same namespace) rely on `priority` integer resolution. High priority overrides low priority without complex fallback logic. | Medium | High | Rely on explicit `priority` definition. Future phases may introduce dynamic fallback. | **NO** |
| **RISK-04** | Security of `secret_provider_reference`. SDK does not currently mandate an encrypted vault, only relying on the `BaseConfigurationProvider` implementation. | High | Medium | Phase 27 must implement a proper `OdooVaultAuthenticationProvider` or external HashiCorp Vault provider. | **NO** (SDK abstractions correctly isolate this). |

There are no remaining architectural risks that block Phase 27.
