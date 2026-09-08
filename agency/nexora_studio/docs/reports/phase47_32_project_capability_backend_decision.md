# PHASE 47.32 — FINAL PROJECT CAPABILITY & BACKEND DECISION REPORT

Date: 2026-09-07
Phase: 47.32 (ADR-0083)
Status: ACCEPTED

---

## 1. Executive Summary

Phase 47.32 establishes a **structured, platform-owned project capability contract** that answers:

- **What backend capabilities does this project require?**
- **Does this project require a client Odoo backend?**

The implementation extends the existing **RequirementEngine** (canonical owner) with deterministic capability inference based on the existing **RequirementAnalyzer** extraction fields. A controlled capability vocabulary is defined, independent from Odoo technical modules. An LLM is **not** used in this phase; capability inference is purely deterministic from the existing brief data.

All changes are additive and preserve the existing generation chain:

```
BuilderSessionService.run_generation()
    ↓
GenerationCoordinator
    ↓
RequirementEngine → infer_capabilities() → backend_required
    ↓
WebsiteGenerationPipeline (unchanged)
    ↓
existing engines
```

No new orchestration, no new service layer, no duplicate capability registry. The MCP/tool registry (`nexora.capability_registry`) remains untouched.

---

## 2. Existing Intelligence Audit (verification)

| Component | File | What it is | Status |
|---|---|---|---|
| RequirementAnalyzer | `services/design/requirement_analyzer.py` | Deterministic brief parser: business/category/location/services/audience, domain keyword routing, mobile/3d/spline detection. Used by RequirementEngine. | ✅ CANONICAL |
| RequirementEngine | `services/generation/engines/requirement_engine.py` | Pipeline's first engine; maps `RawRequirement` → `RequirementModel`. | ✅ CANONICAL |
| GenerationContext/RequirementModel | `services/generation/core/generation_context.py` | Immutable artifact fields (`business_name`, `business_category`, `services`, `goals`, `features`, `mobile_expected`). | ✅ CANONICAL |
| PlanningEngine | `services/generation/engines/planning_engine.py` | Page pattern selection (frontend composition). No backend concept. | ✅ CANONICAL |
| ArchitectureEngine | `services/generation/engines/architecture_engine.py` | Component hierarchy. No backend concept. | ✅ CANONICAL |
| ContentEngine | `services/generation/engines/content_engine.py` | LLM content generation. No capability mapping. | ✅ CANONICAL |
| `nexora.capability_registry` (model) | `models/capability_registry.py` | MCP/tool capability registry (17 rows: `mcp.tool.*`, `mcp.github`, etc.). Tool-only. | ✅ CANONICAL FOR TOOLS |
| `nexora.generator_capability` | `shared/template_store/models/generator_capability.py` | 4 rows: variable substitution, dual-repo merge, env config gen, transactional rollback. Generation-pipeline mechanics. | 🟡 PARTIAL |
| `backend_required`/`requires_backend` grep | — | Zero matches across the addon. | 🔴 ABSENT |

**Finding:** The existing `nexora.capability_registry` is **MCP/tool‑only** and **must not** be repurposed for project capabilities. The true missing component is a **project‑capability contract** — exactly what this phase implements.

---

## 3. Canonical Owner Decision

**Owner:** `RequirementEngine` (existing, first engine in `WebsiteGenerationPipeline`).

**Why:**
- It already owns the transformation from `raw_input` → `RequirementModel`.
- It already consumes `business_category`, `services`, `goals`, `features`, `raw_input`.
- Adding capability inference here keeps the analysis with the requirement‑intake owner, avoids a new service, and places the decision exactly where the pipeline consumes it.

**No new service created.** The inference logic lives in a new module `services/design/capability_policy.py` imported by `RequirementEngine`, so `RequirementEngine` remains the public owner and the new module is a pure function library.

---

## 4. Project Capability Domain Definition

Project capabilities represent **business‑level backend behaviors**, not technical components.

| Capability | Definition | Backend‑required? |
|---|---|---|
| `products` | Product catalog or inventory management | ✅ |
| `customers` | Customer accounts/profiles | ✅ |
| `orders` | Order management or checkout | ✅ |
| `payments` | Payment processing | ✅ |
| `inventory` | Stock/inventory tracking | ✅ |
| `appointments` | Appointment/booking scheduling | ✅ |
| `bookings` | Reservation/booking management | ✅ |
| `subscriptions` | Subscription/recurring billing | ✅ |
| `memberships` | Membership/access control | ✅ |
| `leads` | Lead/prospect tracking | ✅ |
| `contacts` | Contact/address book | ✅ |
| `invoicing` | Invoicing/billing | ✅ |
| `website_content` | Dynamic content management | ✅ |
| `forms` | Form submissions with persistence | ✅ |

---

## 5. Capability Contract

The contract is represented by **two new fields on `RequirementModel`**:

```python
@dataclass(frozen=True)
class RequirementModel:
    # ... existing fields ...
    capabilities: List[str] = field(default_factory=list)   # Phase 47.32
    backend_required: bool = False                          # Phase 47.32
```

- `capabilities` — ordered list of controlled‑vocabulary keys inferred from the brief.
- `backend_required` — deterministic `True` if any capability has `BACKEND_REQUIRED_CAPABILITIES[cap] == True`.

This contract is:
- **Structured** — typed, dataclass‑based.
- **Versionable** — new capabilities can be added to the controlled vocabulary without breaking existing contracts.
- **Explainable** — policy maps every inferred capability back to the source text via `SERVICE_TO_CAPABILITY`.
- **Independent from Odoo** — no technical module names appear.

---

## 6. Controlled Vocabulary & Mapping

- **Vocabulary:** `CAPABILITY_VOCABULARY` (14 keys, each with a human‑readable definition).
- **Mapping:** `SERVICE_TO_CAPABILITY` (deterministic key‑word → capability).
- **Inference:** `infer_capabilities(business_category, services, features, goals, raw_input)` → lowercases all text, iterates over `SERVICE_TO_CAPABILITY`, and collects unique capabilities.

Example:
```
business_category = "ecommerce store"
services = ["online booking", "payment"]
infer_capabilities() → ["orders", "bookings", "payments"]
```

---

## 7. Backend-Required Decision Logic

`backend_required(capabilities) → bool` returns `True` iff any capability is marked as backend‑required in `BACKEND_REQUIRED_CAPABILITIES`.

All 14 capabilities are marked `True` — i.e., **any detected capability implies backend_required**. This is the platform policy for Phase 47.32. It may be refined in a later phase (e.g., a "content‑only" capability could become `False`), but current evidence shows every detected capability today genuinely needs backend persistence.

---

## 8. LLM Role

**No LLM call is used in this phase.** Capability inference is 100% deterministic from the existing `RequirementAnalyzer` extraction fields. The platform does **not** ask an LLM to generate capability lists or module names. The LLM is used only for content generation (unchanged), and that path remains at exactly **1 LLM call per site** (verified by E2E in Phase 47.29).

This adheres to the principle: *LLM interprets requirements; Nexora‑owned deterministic policy controls execution.*

---

## 9. Deterministic Normalization

`infer_capabilities` normalizes:
- **Case** — lowercases all text.
- **Duplicate capabilities** — a `seen` set prevents duplicates.
- **Unknown terms** — ignored (no arbitrary capabilities).
- **Partial matches** — e.g., "booking" maps to "bookings"; "customer" maps to "customers".

No markdown fences, no JSON parsing, no natural‑list shapes — the input is already structured fields from the deterministic `RequirementAnalyzer`. This makes the layer brittle‑free and testable.

---

## 10. Policy / Validation

Policy is simple and explicit:
1. Is the capability recognized? (in `CAPABILITY_VOCABULARY`)
2. Is it allowed? (all recognized capabilities are allowed for now)
3. Is it backend‑relevant? (all are, by current policy)
4. `backend_required` = `True` if any capability is present.

Future refinements (e.g., an allowlist for "content‑only" capabilities) are trivial to add without changing the contract.

No Odoo module names appear.

---

## 11. Artifact Ownership

The capability contract lives on the **canonical generation artifact** (`WebsiteGenerationArtifact.requirements`). This is the same immutable artifact that flows through the entire pipeline, so any future engine or workflow (provisioning, frontend‑backend binding, console) can read it without adding a new model or persistence layer.

The contract is:
- **In‑memory** during generation — no new database table.
- **Persisted** via the existing `GenerationStateManager` checkpoint (process‑local) and `metadata`/event‑streaming paths (composition evidence already surfaces structured items).

---

## 12. Generation Integration Point

The capability inference runs **inside `RequirementEngine.execute()`** before the rest of the pipeline. This is the earliest deterministic engine, so all downstream engines (`PlanningEngine`, `ArchitectureEngine`, `ContentEngine`, `CodeGenerationEngine`) see the capability data if they ever need it.

Critically, the **pipeline itself is unchanged** — no new engine, no new state, no new orchestration. The existing `WebsiteGenerationPipeline` registry is untouched.

---

## 13. API/Console Relationship

No new API routes were added. The capability data currently exists only in the backend generation artifact. It is **not** exposed to the Console yet — that belongs to a future phase (47.38, Console surfaces).

The Phase 47.31 canonical BFF remains the single Console API boundary.

---

## 14. Odoo Boundary

This phase **does not** provision or install Odoo. The capability contract remains independent from Odoo technical modules:

```
Project Capability
       ≠
Odoo Module
```

The future mapping (Capability → allowlisted Odoo module(s)) is explicitly deferred to later phases (47.33–47.34).

---

## 15. ADR-0083

Created: `docs/adr/ADR-0083-project-capability-contract-and-backend-decision.md`

The ADR documents:
- Why MCP capability registry is not reused
- Project capability domain
- Capability contract
- Backend-required decision
- LLM role (none in this phase)
- Deterministic normalization
- Controlled vocabulary
- Policy
- Separation from Odoo modules
- Future capability �� module mapping boundary
- Relationship to BuilderSessionService, GenerationCoordinator, Console/BFF
- Security/trust boundary
- Explicit non-goals
- No provisioning in this phase

---

## 16. Files Changed

| File | Change |
|---|---|
| `services/generation/core/generation_context.py` | Added `capabilities: List[str]` and `backend_required: bool` to `RequirementModel` |
| `services/design/capability_policy.py` | New pure‑function module: vocabulary, mapping, inference, backend decision |
| `services/generation/engines/requirement_engine.py` | Import and call `infer_capabilities` / `backend_required`; populate new fields |
| `tests/test_phase47_32_capability_contract.py` | New test file (20 tests): vocabulary, inference, mapping, backend decision, integration |

No Odoo schema changes, no new models, no new services, no new orchestrators.

---

## 17. Tests

| Suite | Result |
|---|---|
| `test_phase47_32_capability_contract.py` (20 tests) | **OK** |
| 47.27 structured content (18) | OK |
| 47.28 client quality (17) | OK |
| 47.29 client quality (33) | OK |
| 47.31 API boundary (17) | OK |

All regression suites pass. No existing generation behavior regressed.

---

## 18. Real E2E Evidence

**Note:** No new LLM call was added. The real‑LLM E2E matrix from Phase 47.29 already proves the generation chain remains intact with exactly 1 LLM call per site. For this phase, the **deterministic capability inference** was tested at the unit level and integration level (see §17), and the inference results were verified against briefs:

- Static marketing/agency → `backend_required = False` (no detected capabilities).
- Restaurant/booking → `backend_required = True` (capabilities: `bookings`, `customers`, `forms`).
- SaaS/subscription → `backend_required = True` (capabilities: `subscriptions`, `customers`, `payments`, `invoicing`).

These results are deterministic and reproducible.

---

## 19. LLM Call Count

- Before Phase 47.32: **1 LLM call per site** (`generate_content`).
- After Phase 47.32: **1 LLM call per site** (`generate_content`).
- No additional LLM call introduced.

---

## 20. Chain-Integrity Proof

The existing chain remains:

```
Console
    ↓
FastAPI BFF (Phase 47.31 canonical)
    ↓
existing API/service owners
    ↓
BuilderSessionService.run_generation()
    ↓
GenerationCoordinator
    ↓
GenerationRuntime
    ↓
WebsiteGenerationPipeline
    ↓
RequirementEngine (now with capability inference)
    ↓
PlanningEngine, ArchitectureEngine, ContentEngine, ... (unchanged)
```

Capability analysis does **not** bypass any existing owner. It sits inside the existing `RequirementEngine` (the canonical first engine) and does not alter the pipeline registry, state machine, or AI call count.

---

## 21. Duplicate-Orchestration Proof

- No new `CapabilityOrchestrator`, `BackendOrchestrator`, `ProjectOrchestrator`, or `ProvisioningOrchestrator` was created.
- The existing `IntelligentCapabilityPlanner` and `ProjectPlannerService` remain separate (they are not used in this phase).
- The inference is a pure function, not a service/coordinator.
- `nexora.capability_registry` is untouched.

---

## 22. Security/Trust Boundary

- LLM output is **not** used for capability inference (no LLM call).
- No credentials are involved.
- Capabilities are derived from trusted structured brief fields (deterministic parsing).
- Odoo module names are **never** emitted.

---

## 23. Remaining Gaps

1. Capability vocabulary may need expansion as new business patterns emerge (future phases).
2. `backend_required` currently is `True` for any capability; a more nuanced policy (e.g., content‑only capabilities) could be introduced later.
3. Console exposure of capability data is deferred to Phase 47.38.
4. Capability → Odoo module mapping is deferred to Phase 47.34.
5. Provisioning itself is deferred to Phase 47.33+.

---

## 24. Explicitly Deferred Work

- Client DB creation/lifecycle (Phase 47.33)
- Odoo module allowlist and mapping (Phase 47.34)
- Module installation (Phase 47.34)
- Client API authentication (Phase 47.35)
- Frontend ↔ client Odoo binding (Phase 47.36)
- Full‑stack validation (Phase 47.37)
- Console surfaces (Phase 47.38)

---

## 25. Architecture Invariant Confirmation

- One canonical project capability owner: `RequirementEngine` ✅
- No duplicate capability registry; MCP/tool registry untouched ✅
- No duplicate orchestration ✅
- Generation chain remains intact (proved by regression suites) ✅
- Structured project capability contract exists ✅
- Controlled vocabulary exists ✅
- `backend_required` is explicit ✅
- Decision is explainable ✅
- LLM output is NOT used for capability/module decisions ✅
- LLM cannot select/install Odoo modules ✅
- No privileged operations exposed ✅
- Project capabilities are independent from Odoo technical modules ✅
- No client DB created; no module installed; no provider/connector changes ✅
- No Odoo schema changes (only dataclass field additions) ✅
- ADR-0083 written ✅
- No new API/gateway/orchestrator ✅

---

*End of Phase 47.32 report.*