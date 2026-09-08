# ADR-0085: Odoo Module Provisioning & Capability Mapping

Date: 2026-09-07
Phase: 47.34
Status: Accepted

## Context

Phase 47.32 established the Project Capability Contract
(`RequirementModel.capabilities` + `backend_required`) owned by
`capability_policy.py` and `RequirementEngine`. Phase 47.33 established the
client Odoo database lifecycle owned by `nexora.client_environment_service`
/ `nexora.client_environment` (ADR-0084). The only module-installation
surface was an unsafe stub: `ClientProvisioningAPI.install_modules`
accepted arbitrary module names from payloads and returned fake success.

The target chain for this phase:

```
Requirement → RequirementEngine → Project Capability Contract
    → deterministic Capability Policy → Module Plan
    → ClientEnvironmentService → isolated Client Odoo DB
    → approved Odoo module installation
```

## Decision

1. **Capability → module separation.** Three distinct concepts with strict
   boundaries: PROJECT CAPABILITY ≠ MODULE PLAN ≠ ODOO MODULE EXECUTION.
   The LLM may (indirectly, via the requirement brief) influence only the
   first; the platform deterministically controls the second and third.
   `Project Capability ≠ Odoo Module`, `Module Plan ≠ Module Execution`,
   `Module Provisioning ≠ Database Lifecycle`,
   `Module Provisioning ≠ Frontend Generation`,
   `Module Provisioning ≠ API Gateway`, `Module Provisioning ≠ LLM Authority`.

2. **Allowlist ownership.** A new platform-owned policy,
   `services/design/module_policy.py`, maps Phase 47.32 vocabulary
   capabilities to approved Odoo technical module names. Module identifiers
   are PLATFORM DATA (constants in the policy): they never originate from
   LLM output, user payloads, frontend requests, or arbitrary API payloads.
   The trusted input is `capability="orders"`; the platform decides
   `sale_management`. `nexora.capability_registry` (the MCP/tool registry)
   is NOT repurposed.

3. **Allowlist content** (verified available in the target Odoo 19
   community addons runtime): products→product, customers→contacts,
   contacts→contacts, orders→sale_management, payments→payment,
   inventory→stock, leads→crm, invoicing→account,
   website_content→website, forms→website. Explicitly unmapped (no approved
   implementation in this runtime): appointments, bookings, subscriptions,
   memberships — reported as `unresolved_capabilities`, never silently
   substituted. Unknown capabilities (outside the 47.32 vocabulary) are
   rejected outright.

4. **Module Plan contract.** `build_module_plan(capabilities)` produces a
   deterministic, versioned (`schema_version`), explainable plan: requested
   capabilities (normalized, deduplicated), modules (deduplicated,
   each with `name`, `source_capabilities`, `reason`, `required`,
   `supported`), and `unresolved_capabilities` with explicit reasons.
   Pure Python, zero LLM calls, zero I/O.

5. **Canonical installer ownership.** ONE execution owner:
   `nexora.client_environment_service` (the existing Phase 47.33 control
   plane owner) via `_install_modules_in_client_db`. No new orchestrator,
   no second provisioning service, no second DB lifecycle owner. The model
   `nexora.client_environment` gained a SEPARATE module-provisioning state
   (`module_provisioning_state`: none/provisioning/provisioned/partial/
   failed + `module_plan`/`module_provisioning_result`/
   `module_provisioning_error`) — persistence is required for idempotent
   retry/reconciliation, partial-failure diagnostics, and audit; it is
   deliberately distinct from the DB lifecycle `status`, which module
   provisioning NEVER modifies.

6. **Installation primitive.** `odoo.modules.registry.Registry.new(
   db_name, update_module=True, install_modules=...)` — the same canonical
   primitive `odoo-bin -i` and `odoo.service.server` use
   (odoo/service/server.py:1552). It resolves legitimate dependencies,
   skips already-installed modules, and rebuilds the client registry
   in-process. Availability is verified BEFORE installation via the
   client DB's `ir.module.module` (with canonical `update_list()` refresh):
   an allowlisted-but-unavailable module fails the whole provisioning
   safely with a diagnostic, before anything is installed.

7. **Dependency handling.** The platform controls only the approved
   top-level modules; Odoo's dependency resolution installs required
   dependencies (e.g. sale_management → sale, digest; crm → sales_team,
   mail). Dependencies are not independently user-selectable and cannot
   bypass the allowlist.

8. **Idempotency.** Provisioning is safe to retry: pre-states are read
   from the client DB, installed modules are skipped, only uninstalled
   approved modules are passed to the primitive, and results are
   post-verified from the client DB.

9. **Partial provisioning / recovery.** Failures never drop or recreate
   the client DB and never modify the DB lifecycle state. On failure the
   service reads actual post-failure module states and records
   `failed`/`partial` with diagnostics; retry reconciles (skips installed,
   installs remaining). No automatic rollback of successful installations.
   Interrupted Odoo operations (transient `to install`/`to upgrade`/
   `to remove` states) fail safely with an explicit diagnostic; automatic
   state reset is deferred.

10. **Concurrency.** Duplicate provisioning for the same environment is
    serialized by a row-level `SELECT ... FOR UPDATE` on
    `nexora_client_environment` (existing Odoo transaction mechanism); the
    blocked duplicate then completes as an idempotent no-op. Cross-process
    safety relies on Odoo's own registry/module locks. No distributed lock
    service.

11. **Security boundary.**
    `untrusted requirement/LLM output → Project Capability Contract →
    deterministic capability validation → platform-owned allowlist →
    approved Module Plan → privileged installer → Client Odoo DB`.
    Defense-in-depth: the installer re-verifies every module name against
    the allowlist and re-proves `agency DB ≠ client DB` (robust
    `_is_agency_database`: Odoo 19 `config['db_name']` may be a LIST, so
    the guard normalizes config values AND always includes the runtime
    `cr.dbname`). Credentials remain owned by
    `OdooSecretsProvider`/Fernet; no passwords/tokens in logs, errors, or
    API responses.

12. **ClientEnvironment relationship.** Provisioning requires: environment
    exists, not deleted, `status == 'ready'`, client DB exists
    (`odoo.service.db.exp_db_exist`). No new database connection mechanism,
    no duplicate credential retrieval.

13. **RequirementModel relationship.** `RequirementEngine` → capabilities
    (47.32, unchanged) → `provision_modules(env_id, capabilities)`. The
    capability policy remains canonical; module planning is a sibling
    deterministic policy, not an LLM call.

14. **API boundary.** The existing (previously stubbed/unsafe)
    `POST /api/v1/provisioning/databases/<db>/modules` route is now real
    and capability-driven: it accepts ONLY `capabilities`, rejects
    `modules` payloads outright, and delegates to the canonical service.
    No new API, no BFF change (no existing BFF consumer requires module
    provisioning; the FastAPI BFF remains the sole Console boundary).

15. **GenerationCoordinator relationship.** None in this phase. The frozen
    chain `BuilderSessionService.run_generation() → GenerationCoordinator
    → GenerationRuntime → WebsiteGenerationPipeline` is untouched; module
    provisioning is a sibling backend workflow, triggerable only through
    the explicit control-plane surface.

## Incident note (2026-09-07)

During this phase's regression repair, a latent Phase 47.33 bug caused the
agency DB to be dropped in the development environment: `_delete` compared
`db_name == odoo.tools.config['db_name']`, which is a LIST in Odoo 19, so
the guard never matched and `exp_drop` executed. The DB was restored from
the newest available backup (2026-08-23, pre-keyreset) and upgraded to
current code. The guard is now robust (see §11) and covered by a real
regression test. Data written between Aug 23 and Sep 7 was lost; connector
API keys encrypted with the pre-reset Fernet key must be re-entered.

**Hardening amendment (Phase 47.34.x):** the post-incident audit found a
second unguarded hole — the provisioning controller's DELETE route had a
raw `exp_drop` fallback for untracked database names (removed). The
canonical guard `_is_agency_database` is now FAIL-CLOSED (ambiguous
database identity — list/None/empty/non-string input, or malformed
`db_name` configuration — raises and blocks the operation), client-DB
naming collisions with the agency DB are rejected at creation, a model
constraint prevents re-pointing an environment at the agency DB, and
`_provision` re-checks the guard as the last line of defense.

## Non-goals (Phase 47.34)

- Client API / authentication (47.35)
- Frontend ↔ client backend binding (47.36)
- Full-stack validation (47.37)
- Console provisioning UI (47.38)
- Automatic module-state reset tooling
- Module upgrade/uninstall flows
- BFF route exposure (no consumer requires it yet)

## Consequences

- One canonical module provisioning owner; no duplicate orchestration.
- Deterministic, explainable, versioned module plans with zero LLM calls.
- Arbitrary module names cannot reach the Odoo installation primitive.
- Agency DB can never be a provisioning or deletion target.
- Provisioning is idempotent, observable, and recoverable.
- Generation pipeline, BFF, capability registry, and DB lifecycle owners
  are unchanged.

## Future

- 47.35: client API on top of the verified client Odoo DB.
- 47.36: frontend binding.
- Optional: interrupted-operation state reset; module upgrade flows.
