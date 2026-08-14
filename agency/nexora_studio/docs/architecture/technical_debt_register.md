# Technical Debt Register

**Workstream H: Technical Debt Register**

## Executive Summary
This register catalogs remaining non-architectural debt inside the Connector Platform. Since Phase 26 strictly focused on architecture and invariants, actual implementation specifics (like full provider integrations) are deferred.

**Status:** 0 Architectural Debt Items Remaining.

---

## 1. Deferred Implementations (Phase 27 Targets)
- **Odoo ORM Syncing:** While `OdooConnectorPersistenceAdapter` stubbing was fixed to avoid crashes (Defect D-002), comprehensive read/write mappings for advanced `manifest_json` fields will require expansion when actual MCP/GitHub manifests are finalized in Phase 27.
- **Security & Secrets:** The `SecretsProvider` and `CredentialResolver` interfaces in `sdk/` are frozen, but concrete implementations bridging to an encrypted vault or Odoo KeyStore are deferred.

## 2. Testing Expansion
- **Coverage Increase:** Overall AAT suite coverage is 56%. Full unit tests targeting every internal error transition inside `ConnectorHealthMonitor` and `ConnectorLifecycleManager` should be authored during CI/CD pipeline implementation.

**Conclusion:** There is zero outstanding architectural debt. The architecture is locked.
