# PHASE 47.34 — FINAL ODOO MODULE PROVISIONING & CAPABILITY MAPPING REPORT

Date: 2026-09-07
Phase: 47.34
Status: COMPLETED (all tests + real-DB E2E green)

## 1. Executive Summary

Phase 47.34 establishes the trusted bridge from the Phase 47.32 Project
Capability Contract to REAL Odoo module installation in the Phase 47.33
isolated client database:

```
Requirement → RequirementEngine → Project Capability Contract
    → deterministic module policy (platform-owned allowlist)
    → approved Module Plan
    → nexora.client_environment_service (canonical owner)
    → isolated Client Odoo DB
    → real module installation (Registry.new install_modules)
    → verified provisioning result
```

A platform-owned capability→module allowlist (`module_policy.py`), a
deterministic versioned Module Plan, a narrowly scoped privileged
installer, idempotent/recoverable provisioning semantics, agency-DB
isolation proofs, and capability-only API payloads were implemented. The
real-DB E2E installed `product`, `contacts`, `sale_management`, `crm`
(plus Odoo-resolved dependencies) into a disposable client DB, verified
agency-DB isolation, idempotency, negative allowlist cases, and
fail-safe/recovery, then dropped the disposable DB.

Module provisioning adds **0 LLM calls** (fully deterministic).

**Operational incident (resolved):** during regression repair, a latent
Phase 47.33 guard bug dropped the development agency DB; it was restored
from the newest backup and the root cause is fixed with regression
coverage (see §29 and ADR-0085).

## 2. Existing Module Installation Audit

| Implementation | Location | Classification | Evidence |
|---|---|---|---|
| `ClientProvisioningAPI.install_modules` | `controllers/client_provisioning_api.py:59` | **STUB + UNSAFE** | accepted arbitrary module names, returned fake success, commented-out service call |
| `ir.module.module.button_immediate_install` | core `base/models/ir_module.py:477` | CANONICAL (Odoo core) | HTTP-oriented; forbidden inside transactional tests (`current_test` guard) |
| `Registry.new(db, update_module=True, install_modules=...)` | core `odoo/orm/registry.py:113`, used by `odoo/service/server.py:1552` (`odoo-bin -i`) | **CANONICAL (chosen primitive)** | dependency-aware, idempotent, headless, in-process registry rebuild |
| `_initialize_db` / `exp_create_database` | core `odoo/service/db.py:67/177` | CANONICAL (owned by 47.33 service) | DB lifecycle, not module install |
| `exp_db_exist` / `list_dbs` | core `odoo/service/db.py:425/434` | CANONICAL (reused) | client-DB existence check |
| `Module.update_list()` | core `ir_module` | CANONICAL (reused) | availability refresh |
| Nexora-side module installer / allowlist / plan | — | **ABSENT** | no wrapping existed; no duplicates created |

No other module-installation implementation exists in `custom-addons`
(grep for `button_install|Registry.new|update_module|ir.module.module`
over custom code found only test files' `Registry.new('nexora_studio')`
registry bootstraps, unrelated to installation).

## 3. Canonical Ownership Decision

- **Module policy owner (new):** `services/design/module_policy.py` —
  platform data + pure deterministic functions. Sibling of
  `capability_policy.py` (which remains the untouched capability
  vocabulary owner).
- **Module provisioning execution owner:** `nexora.client_environment_service`
  (existing 47.33 owner) via `provision_modules` /
  `_install_modules_in_client_db` / `_read_client_module_states`.
  No `ModuleProvisioningOrchestrator`, no second service, no second API.
- **DB lifecycle ownership unchanged:** `status` is never written by the
  module layer; `ClientEnvironmentService` still owns create/drop.

## 4. Capability → Module Policy

`build_module_plan(capabilities)` (module_policy.py):
- unknown capability (not in 47.32 `CAPABILITY_VOCABULARY`) → `ModulePolicyError` (rejected, no plan)
- known + mapped → approved module entries
- known + unmapped → explicit `unresolved_capabilities` with reasons
- deterministic: normalization, dedup, sorted ordering
- plan contains `schema_version`, capabilities, modules
  (`name`, `source_capabilities`, `reason`, `required`, `supported`),
  unresolved list, `supported` flag

## 5. Allowlist

| Capability | Module | Verified in runtime |
|---|---|---|
| products | product | yes |
| customers | contacts | yes |
| contacts | contacts | yes (dedup) |
| orders | sale_management | yes |
| payments | payment | yes |
| inventory | stock | yes |
| leads | crm | yes |
| invoicing | account | yes |
| website_content | website | yes |
| forms | website | yes (Odoo 19 form builder lives in `website`) |

Explicitly unmapped: appointments, bookings, subscriptions, memberships
(no approved implementation in the target Odoo 19 community runtime;
website_form/membership modules absent). All allowlist entries verified
against `community/odoo/addons` presence + manifest deps.

## 6. Module Plan Contract

See §4. Plan persisted on the environment record as JSON
(`module_plan`), execution outcome as `module_provisioning_result`.
Schema version `"1.0"`.

## 7. Odoo Module Availability

Before installation the installer opens the client registry, runs
canonical `ir.module.module.update_list()`, and searches the approved
names. Missing module → whole provisioning fails safely BEFORE any
installation (no partial install from availability failure, no
substitution, no LLM choice). Proven in unit tests and in the E2E
fail-safe scenario (fault-injected unavailable `crm`).

## 8. Dependency Handling

Only approved top-level modules are requested; Odoo's
`Registry.new(install_modules=...)` resolves legitimate dependencies
(loading.py:431–434 `button_install` marks deps). E2E proof: `sale`,
`mail`, `sales_team` (never requested) are `installed` in the client DB.
Dependencies are not user-selectable and cannot bypass the allowlist.

## 9. Installation Owner

`nexora.client_environment_service._install_modules_in_client_db`
(services/client_environment_service.py):
- allowlist re-verification (defense-in-depth) at the trust boundary
- agency-DB guard re-proof
- availability check → transient-state check → partition
  installed/uninstalled → `Registry.new(db_name, update_module=True,
  install_modules=tuple(to_install))` → post-verification read
- never creates/deletes DBs, runs generation, manages AI/Console/frontend
- plain (untranslated) diagnostics: the privileged path must not depend
  on the translation machinery while operating cross-DB

## 10. Idempotency

Retry re-reads actual client-DB module states; installed modules are
skipped; only uninstalled approved modules are installed; results are
post-verified. E2E: repeat provisioning → `installed=[]`, all skipped,
state `provisioned`, no duplicate/broken states.

## 11. Partial Failure / Recovery

On installer exception the service reads actual post-failure module
states and records `failed`/`partial` (+ diagnostic, + flushed for
immediate observability), then re-raises. The client DB is never
dropped/recreated; the DB lifecycle `status` stays `ready`. Retry
reconciles. E2E: fail-safe (unavailable `crm`) → `failed`, DB intact,
retry → `provisioned` with `crm` skipped (already installed).

## 12. Concurrency

Row-level `SELECT ... FOR UPDATE` on `nexora_client_environment`
serializes duplicate provisioning per environment (existing Odoo
transaction mechanism); the duplicate then completes as idempotent no-op.
Cross-process safety: Odoo's own registry/module locks
(`ir_module_module` EXCLUSIVE + `ir_cron` FOR UPDATE inside the loading
critical section). No distributed lock service. Transient
`to install`/`to upgrade`/`to remove` states (interrupted operations)
fail safely with explicit diagnostics; auto-reset deferred.

## 13. Client Environment Integration

`provision_modules` requires: record exists, not deleted, `status ==
'ready'`, `exp_db_exist(db_name)`. Reuses 47.33 lifecycle untouched.
No new connection mechanism, no duplicate credential retrieval.

## 14. Credential Boundary

`OdooSecretsProvider`/Fernet remains the only secret owner (reused for
the client admin password in 47.33). 47.34 adds no new secrets; logs,
errors, and API responses contain no passwords/tokens. The E2E verified
`encrypted_admin_password` is stored encrypted and never printed.

## 15. API Boundary

The existing stubbed route `POST /api/v1/provisioning/databases/<db>/modules`
is now real and capability-driven:
- payload must be `{"capabilities": [...]}`; any `modules` key is
  rejected with an explicit message (module identifiers are
  platform-owned)
- delegates to `nexora.client_environment_service.provision_modules`
- returns plan + verified outcome only (no credentials)
No new API; FastAPI BFF (`nexora-console/backend`) remains the sole
Console headless boundary (no BFF consumer requires module provisioning
yet — no BFF change).

## 16. Generation Boundary

The frozen chain is untouched (no generation file modified — git status
evidence): `BuilderSessionService.run_generation() →
GenerationCoordinator → GenerationRuntime → WebsiteGenerationPipeline`.
Module provisioning is a sibling backend workflow, not wired into the
pipeline; no engine gained DB/module/credential responsibility.

## 17. Security Boundary

```
untrusted requirement/LLM output
    → Project Capability Contract (47.32)
    → deterministic capability validation
    → platform-owned allowlist (module_policy.py)
    → approved Module Plan
    → privileged installer (allowlist re-check + agency guard)
    → Client Odoo DB
```
- arbitrary module names rejected at controller (payload parser),
  policy (unknown capability), AND installer (allowlist re-check) —
  proven in unit tests + E2E (`some_arbitrary_module`,
  `base`, LLM-style `sale_management`-as-capability all rejected)
- agency DB cannot be selected as provisioning/deletion target
  (`_is_agency_database` normalizes Odoo 19's list-valued
  `config['db_name']` and always includes runtime `cr.dbname`)
- no credential leakage; no user/LLM override of the allowlist

## 18. ADR-0085

Created: `docs/adr/ADR-0085-odoo-module-provisioning-capability-mapping.md`
(all 17 required topics incl. the explicit separation statements and the
incident note).

## 19. Files Changed

| File | Change | Why |
|---|---|---|
| `services/design/module_policy.py` | NEW | platform-owned allowlist + deterministic plan (no existing owner — unavoidable new policy data) |
| `services/client_environment_service.py` | MODIFIED | provisioning owner methods; robust `_is_agency_database`; failure-state flushes (Odoo 19 defers writes) |
| `models/client_environment.py` | MODIFIED | separate module-provisioning state fields + `action_provision_modules` |
| `controllers/client_provisioning_api.py` | MODIFIED | unsafe stub → real capability-driven route + `parse_module_provisioning_payload` |
| `tests/test_phase47_34_module_provisioning.py` | NEW | 39 focused tests |
| `tests/test_phase47_33_client_lifecycle.py` | MODIFIED | test repairs (real agency guard exercise; manual try/except for state observation) |
| `tests/test_phase47_5_pipeline_behavior.py` | MODIFIED | stale pre-47.32 assertion aligned to canonical capability contract |
| `tests/__init__.py` | MODIFIED | registered 47_33 + 47_34 test modules (required for odoo-bin discovery) |
| `scripts/verify_phase47_34.py` | NEW | real-DB E2E |
| `docs/adr/ADR-0085-...md` | NEW | ADR |
| `docs/reports/phase47_34_odoo_module_provisioning.md` | NEW | this report |

## 20. Tests

- **47.34 unit/integration (TransactionCase, post_install):** 39 tests —
  policy determinism, allowlist security, plan contract, availability,
  installation, idempotency, partial recovery, agency isolation, payload
  security. All PASS.
- **47.33 regression:** 8 lifecycle tests (repaired) — all PASS.
- **Combined odoo-bin run:** `0 failed, 0 error(s) of 47 tests`.
- **47.31 regression (standalone):** 17 tests OK.
- **47.32 regression (standalone):** 20 tests OK.
- **Generation regression (standalone):** 38 tests OK
  (`test_phase47_5_pipeline_behavior`, `test_phase47_7_artifact_consumers`).

## 21. Real DB + Module E2E

`scripts/verify_phase47_34.py` (venv python, dev.conf, agency DB
`nexora_studio`), all checks PASS (exit 0):
- disposable client DB `nexora_e2e4734_135445` created via REAL
  `exp_create_database` (environment `ready`, credential encrypted)
- capabilities `[products, customers, contacts, orders, leads,
  subscriptions]` → approved plan `[contacts, crm, product,
  sale_management]` + explicit unresolved `subscriptions`
- REAL installation via `Registry.new(..., install_modules=...)`
- client DB verified: all 4 approved modules `installed`; dependencies
  `sale`, `mail`, `sales_team` `installed` (never requested)
- `module_provisioning_state = provisioned`, DB lifecycle `ready`
- agency DB module-state snapshot identical before/after

## 22. Negative Allowlist E2E

- `provision_modules(env, ['totally_unknown_feature'])` → rejected;
  provisioning state preserved (`provisioned`), no installation
- `_install_modules_in_client_db(db, ['some_arbitrary_module'])` →
  rejected by the allowlist; Odoo primitive never invoked
- fault-injected unavailable `crm` (allowlisted but hidden from the
  client runtime list) → provisioning FAILED safely BEFORE any
  installation; diagnostic recorded; client DB intact; DB lifecycle
  `ready`

## 23. Idempotency Evidence

Repeat of the same plan: `installed=[]`,
`skipped=['contacts','crm','product','sale_management']`, state stays
`provisioned`, client-DB states all `installed`, no duplicates. Recovery
after the fail-safe: retry → `provisioned`, `crm`+`sale_management`
skipped (already installed).

## 24. Agency DB Isolation Evidence

- explicit proof `client=nexora_e2e4734_135445 ≠ agency=['nexora_studio']`
- agency `ir_module_module` snapshot (name→state) IDENTICAL
  before/after the whole E2E (changed=[])
- no `to install/to upgrade/to remove` leftovers in agency
- per-module agency states unchanged (e.g. `product` stayed
  `uninstalled`, `crm` stayed `installed` — as it was in baseline)
- disposable client DB dropped at the end via REAL `exp_drop`;
  agency control-plane consistent

## 25. Chain-Integrity Proof

Generation chain untouched (git status: no generation file modified).
RequirementEngine still produces the 47.32 capability contract
(verified by generation regression tests asserting
`capabilities=['website_content']`, `backend_required=True`).
47.34 extends the chain deterministically AFTER the capability contract;
capability_policy.py and RequirementEngine are unmodified.

## 26. Duplicate-Orchestration Proof

- ONE module installation owner (`_install_modules_in_client_db`)
- ONE installation primitive (`Registry.new install_modules` — same as
  `odoo-bin -i`)
- ONE lifecycle owner (unchanged 47.33 service)
- ONE policy owner (`module_policy.py`)
- no new orchestrator/coordinator/API/gateway/secret store/MCP registry;
  `nexora.capability_registry` untouched

## 27. LLM Call Count

Before: 1 content-generation LLM call per real generation E2E
(unchanged). After: identical. **Module provisioning adds 0 LLM calls**
(pure deterministic policy; E2E log contains no AI activity).

## 28. Dead/Legacy Implementation Classification

| Implementation | Status |
|---|---|
| `install_modules` controller stub | WAS STUB+UNSAFE → now CANONICAL capability-driven route |
| `nexora.client_provisioning_service` (comment-only reference) | MISSING/DEAD → superseded by `nexora.client_environment_service` |
| remaining controller stubs (`init_store`, `create_admin`, `backup`, `restore`) | STUB (deferred, documented) |
| 47.33 `_delete` agency guard | LATENT BUG (list-vs-string config compare) → FIXED + regression-covered |

## 29. Remaining Gaps / Incident Record

**INCIDENT (resolved):** during 47.34 regression repair, the repaired
47.33 test exercised the real agency-deletion guard for the first time.
The guard compared `db_name == odoo.tools.config['db_name']`, which is a
LIST in Odoo 19 — the comparison never matched — so `exp_drop` dropped
the development agency DB `nexora_studio`. Recovery: server stopped;
DB restored from newest backup
(`backups/phase44_3_prekeyreset_20260823_221750/nexora_studio.dump`,
pg_restore, exit 0); schema upgraded to current code via `-u
nexora_studio` (68 modules, provider/MCP data intact); dev server
restarted (port 8069). Root cause fixed (`_is_agency_database`) with
regression coverage. **Residual impact:** agency data written between
2026-08-23 and 2026-09-07 was lost (test-run artifacts mostly);
connector API keys encrypted with the pre-reset Fernet key must be
re-entered (startup log shows unresolved `CONTEXT7/FIRECRAWL/GITHUB/
PENPOT/TAVILY` secrets — restoration effect, not a 47.34 defect).

**Safety hardening follow-up (Phase 47.34.x, 2026-09-07):** a dedicated
hardening pass closed the remaining holes found in the post-incident
audit: (1) the `DELETE /api/v1/provisioning/databases/<db_name>`
controller route had an UNGUARDED raw `exp_drop` fallback when no
environment record existed (same incident class — removed; only tracked
client environments are deletable, always via the guarded service);
(2) `_is_agency_database` is now FAIL-CLOSED — non-string/None/empty/
list database identities raise and block the operation, and malformed
`db_name` configuration (non-string entries, unexpected types) blocks
every destructive operation; (3) `create_environment` rejects sanitized
client names that collide with the agency DB (e.g. identifier "studio"
→ `nexora_studio`); (4) a model constraint blocks re-pointing a client
environment's `db_name` at the agency DB; (5) `_provision` re-checks the
agency guard as the last line of defense. Coverage:
`tests/test_phase47_34x_safety_hardening.py` (24 tests) + updated
47.33/47.34 agency tests; 71/71 TransactionCase tests green; real
runtime verification via `scripts/verify_phase47_34x_safety.py`
(16/16 checks: live fail-closed behavior, naming-collision rejection,
real disposable-DB create/delete, agency snapshot unchanged).

**Post-restore follow-up (2026-09-07, blank `/odoo` screen):** Odoo 19's
`exp_drop` also deletes the database filestore
(`odoo/service/db.py:250-252` — `shutil.rmtree(filestore)`), so the
incident destroyed the agency filestore along with the DB. After the
DB-only restore, all 150 stored `ir_attachment` records referenced
missing files; the generated web-client asset bundles 500'd and left
`/odoo` blank. Remediation: canonical asset regeneration (deleted the 20
stale `/web/assets/%` bundle attachments; Odoo rebuilt them from source —
verified HTTP 200 with full content). Residual impact: ~130
non-regenerable binary attachments (pre-Aug-23 images/exports) remain
referenced-but-missing — accepted data loss from the incident; no
credential values involved.

Other gaps: interrupted-operation state reset (deferred); module
upgrade/uninstall flows (deferred); BFF exposure (no consumer yet).

## 30. Explicitly Deferred Work

- 47.35: client API + authentication on the verified client Odoo DB
- 47.36: frontend ↔ client backend binding
- 47.37: full-stack validation
- 47.38: Console provisioning UI
- automatic transient-module-state reset tooling
- module upgrade/uninstall provisioning

## 31. Architecture Invariant Confirmation

- Phase 47.32 capability contract canonical & reused ✅
- no MCP capability registry reuse ✅
- no arbitrary capability accepted (unknown → rejected) ✅
- canonical allowlist, deterministic mapping, platform-owned module IDs ✅
- unsupported mappings explicit (unresolved + reasons) ✅
- no LLM module authority (0 LLM calls) ✅
- real approved modules installed into isolated client DB ✅
- agency DB never targeted (proven in code, tests, E2E) ✅
- Odoo dependency handling correct (deps installed, not selectable) ✅
- repeated provisioning idempotent ✅
- partial failure recoverable ✅
- unavailable modules fail safely ✅
- ClientEnvironmentService remains DB lifecycle owner ✅
- ONE module installation owner, no duplicate orchestrator/API ✅
- FastAPI BFF remains canonical headless boundary ✅
- no credential leakage; no allowlist override ✅
- client DB isolation preserved ✅
- no client API / frontend binding / Console UI ✅
- no new provider/model/connector/Graphify changes ✅
- focused tests + regressions + real E2E + negative + idempotency +
  agency-integrity evidence all green ✅
- no manual DB edits; no generated-workspace patches ✅

---

*End of Phase 47.34 report.*
