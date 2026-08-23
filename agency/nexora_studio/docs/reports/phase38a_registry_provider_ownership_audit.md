# Phase 38A — Registry Provider Ownership Audit

**Date:** 2026-08-17
**Objective:** Determine the canonical owner for JsonRegistryProvider and formulate a migration plan to safely delete the final legacy MCP dependency.

## 1. Current Responsibility
JsonRegistryProvider is a JSON configuration parser. It reads config/mcp_registry.json and maps its contents into CapabilityManifest objects representing the abstract definitions of providers and tools available to the system.

## 2. Current Callers
Exactly one caller:
- services/capabilities/bootstrap.py (RegistryBootstrapService.execute_bootstrap)

## 3. Current Data Flow
1. RegistryBootstrapService instantiated during Odoo boot.
2. Calls provider = JsonRegistryProvider('mcp_registry.json').
3. Calls manifests = provider.get_manifests().
4. Passes manifests to CapabilityRepository(self.env).synchronize_manifests(manifests).
5. CapabilityRepository persists these into the 
exora.capability_registry database table.

## 4. Existing Equivalent Implementations
- **JSON Parsing**: None. There is no other component in the codebase that reads mcp_registry.json.
- **Manifest Loading**: CapabilityRepository loads manifests from the database, but does not parse the configuration file.

## 5. Canonical Owner
The canonical owner for reading capability manifests from configuration during boot is services/capabilities/bootstrap.py (RegistryBootstrapService). 
The JsonRegistryProvider is currently located in the legacy runtime (services/runtime/mcp/registry_provider.py) but logically belongs entirely to the services/capabilities bootstrap process.

## 6. Whether Duplication Exists
No functional duplication exists. The ConnectorRegistry and ConnectorCapabilityIndex in the new UCP architecture (services/connector/) handle active runtime connector state and execution routing, which is a fundamentally different concern than bootstrapping the abstract capability definitions into the database.

## 7. Recommended Migration
**Consolidate by Relocation and Simplification:**
1. Extract the get_manifests() parsing logic from JsonRegistryProvider.
2. Move it directly into services/capabilities/bootstrap.py (either as a helper function like _parse_registry_json or a lightweight internal class).
3. Delete the abstract RegistryProvider base class and the dead daemon thread/hot-reloading logic (which is never used by ootstrap.py).
4. Update RegistryBootstrapService.execute_bootstrap to use the localized parser.

## 8. Exact Files That Would Change
- services/capabilities/bootstrap.py (modified to contain the parsing logic)

## 9. Exact Files That Would Eventually Be Deleted
- services/runtime/mcp/registry_provider.py
- The entire services/runtime/mcp/ directory (completing Phase 38 legacy retirement)

## 10. Why The Recommendation Does NOT Create Parallel Architecture
This migration moves an existing responsibility to its rightful existing caller. It introduces no new registries, no new dispatchers, and no new runtimes. It merely centralizes the configuration parsing logic within the service that already orchestrates it, eliminating the structural dependency on the legacy services/runtime/mcp/ directory.

---
**Verdict:** MIGRATION TARGET IDENTIFIED
