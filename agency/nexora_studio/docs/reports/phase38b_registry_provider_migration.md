# Phase 38B — Registry Provider Migration

**Date:** 2026-08-17
**Objective:** Migrate the final legacy JsonRegistryProvider capability configuration loading logic into the canonical UCP RegistryBootstrapService.

## 1. Before/After Data Flow
**Before:**
RegistryBootstrapService imported JsonRegistryProvider from the legacy services/runtime/mcp/registry_provider.py. It invoked get_manifests() on the provider object to read mcp_registry.json.

**After:**
RegistryBootstrapService now encapsulates the mcp_registry.json parsing internally via the _parse_registry_manifests helper. It creates CapabilityManifest objects natively without reaching into the deprecated legacy runtime boundaries.

## 2. Files Changed
- **Modified:** services/capabilities/bootstrap.py
- **Deleted:** services/runtime/mcp/registry_provider.py

## 3. Behavior Preservation Evidence
The new _parse_registry_manifests function accurately implements the same parsing and object construction logic as the deleted JsonRegistryProvider.get_manifests() and get_raw_config(). The output remains exactly typed as a list of CapabilityManifest objects, with the exact same mapping rules for 	arget_type and metadata defaults. CapabilityRepository.synchronize_manifests consumes this output exactly as before.

## 4. Test Results
The migration test via odoo-bin shell produced the following result:
`python
Result: {'status': 'success', 'synchronized_count': 12}
MIGRATION_TEST_PASS
`
- mcp_registry.json was successfully loaded and parsed.
- Exactly 12 capability manifests were correctly produced and synchronized, identical to the previous behavior.
- Database state remained accurate.

## 5. Remaining Legacy References
A full repository scan for JsonRegistryProvider, RegistryProvider, and services.runtime.mcp confirmed:
- **ZERO** production imports into services/runtime/mcp.
- The only remaining matches in production code are self-contained references *inside* the isolated (and now dead) services/runtime/mcp/ directory. 
- All other matches were found strictly in tests, verification scripts, and documentation.

## 6. Confirmation of No Parallel Architecture
No new registries, dispatchers, catalogs, runtimes, transports, or orchestration layers were created. The logic was successfully localized to its canonical consumer (services/capabilities/bootstrap.py).

## 7. Confirmation of Database State Integrity
No database state was intentionally modified during this transition, apart from the expected idempotency hash update triggered by the successful test synchronization. The actual capability configurations remain unchanged.

## 8. Legacy Retirement Readiness
The final legacy retirement gate is now fully ready. services/runtime/mcp/ is entirely disconnected from production execution and can be safely purged.

---
**Verdict:** PHASE 38B — MIGRATION PASS
