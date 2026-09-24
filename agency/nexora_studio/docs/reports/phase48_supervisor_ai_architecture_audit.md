# Phase 48 — Supervisor AI / Luna Architecture Audit

## 1. Executive Summary
This audit evaluated the existing Nexora Studio architecture to determine the optimal insertion point for a future Supervisor AI role. The Supervisor will analyze requirements, instruct GPT-5.6 Luna, evaluate generated evidence, and request bounded improvements. The architecture strictly avoids duplicate orchestration layers, reusing existing generation pipelines, AI runtime bindings, and validation evidence.

## 2. Current Executable Generation Architecture
- **Session Lifecycle**: `BuilderSessionService` manages the top-level state machine (`draft` -> `preparing` -> `generating` -> etc.).
- **Execution Coordinator**: `GenerationCoordinator` owns context initialization, state checkpointing, and event publishing.
- **Generation Pipeline**: `WebsiteGenerationPipeline` executes the frozen deterministic chain (Requirement -> Design -> Content -> Asset -> Code -> Validation).
- **Runtime Environment**: `GenerationRuntime` provides the workspace and AI abstractions to the pipeline.

## 3. Current AI Runtime Architecture
- **Adapter**: `AIRuntimeAdapter` (injected via `GenerationRuntime`) is the primary interface for generation engines.
- **Provider Registry & Routing**: `ProviderManager` routes requests, applies `ProviderExecutionPolicy`, and tracks metrics.
- **Model Selection**: `CostRouter` resolves the canonical model (`openai/gpt-5.6-luna`) based on registry capabilities.

## 4. Existing Evidence/Validation Architecture
- **Validation Engine**: `ValidationEngine` currently collects build evidence (linting/compilation) and attaches visual fingerprints.
- **Event Timeline**: `BuilderSessionService._composition_summary` surfaces a deterministic composition manifest from `metadata`.
- **Evidence Contract**: The existing `GenerationContext.metadata` (including `composition_manifest`, `validation_issues_count`, `build_acceptance`) acts as the unified evidence contract for post-generation evaluation.

## 5. Existing Reviewer/Planner/Supervisor-like Mechanisms
- `AIReviewFramework` (`core/ai_review_framework.py`): Deprecated legacy wrapper for self-reflection and bug fixing. Active but obsolete.
- `ReviewerAgent` (`agents/roles/reviewer_agent.py`): QA agent inside an alternative multi-agent orchestrator path.
- `SupervisorEngine` (`orchestration/failure_recovery.py`): Error recovery loop for individual agents.
- `ConfidenceEvaluator` (`tools/visual_verification.py`): Visual assessment.
These are largely duplicated or deprecated paths that should NOT be integrated into the canonical pipeline.

## 6. Candidate Insertion Points
- **A. BuilderSessionService**: Too high-level. Manages overall DB state, git lifecycle, and workspaces.
- **B. GenerationCoordinator**: Owns the generation context, event bus, and pipeline invocation.
- **C. WebsiteGenerationPipeline**: Too low-level. Represents a single linear execution of the generation engines.
- **D. ValidationEngine**: Evaluates build evidence, but lacks authority to orchestrate a pipeline retry.

## 7. Recommended Insertion Point and Why
**GenerationCoordinator.start_generation** is the correct insertion point.
It already encapsulates the call to `self.pipeline.run(context, runtime)`. A bounded loop (capped at 3-5 iterations) can be wrapped around the pipeline execution. After the pipeline returns a `completed_context`, the coordinator invokes the Supervisor AI role. The Supervisor analyzes `context.metadata` (evidence) against `requirements`. If improvements are needed, it updates `context.artifact.requirements` (or instructions) and triggers the next loop iteration. This preserves the canonical pipeline completely.

## 8. Supervisor ↔ Luna Responsibility Boundary
- **Supervisor AI**: High-reasoning evaluation. Produces structured execution instructions, defines bounds, and assesses evidence.
- **GPT-5.6 Luna**: Execution model. Receives bounded instructions through the existing `AIRuntimeAdapter` and implements code via the standard `WebsiteGenerationPipeline`.

## 9. Initial-Generation Lifecycle
1. `BuilderSessionService.run_generation()` invokes `GenerationCoordinator.start_generation()`.
2. Supervisor (inside Coordinator) evaluates requirements and formulates initial instruction.
3. Coordinator executes `WebsiteGenerationPipeline` using Luna.
4. Pipeline produces artifact and metadata (evidence).
5. Supervisor evaluates evidence.
6. If inadequate, and attempt < max, Supervisor refines instruction; Coordinator loops back to step 3.
7. If adequate or attempt == max, Coordinator returns completed context.

## 10. Manual-Improvement Lifecycle
1. New `BuilderSessionService.run_manual_improvement()` is invoked via API.
2. Supervisor evaluates user request against current workspace state.
3. If invalid/risky, rejects gracefully without execution.
4. If valid, generates a single structured instruction.
5. Coordinator runs `WebsiteGenerationPipeline` exactly once (`max_attempts=1`).
6. Results are returned to the user; no automatic subsequent looping.

## 11. Attempt-Cap Ownership
Enforced deterministically by `GenerationCoordinator`. The Supervisor AI is not trusted to enforce its own termination.

## 12. Cost-Control Ownership
Enforced by `ProviderManager` and `CostRouter`. Token limits, rate limits, and provider budgets already exist. The deterministic attempt cap in the Coordinator guarantees an upper bound on model invocations per session.

## 13. Failure/Safety Model
- **Supervisor Failure**: Coordinator aborts the loop, preserving the last successful artifact.
- **Luna/Pipeline Failure**: Existing pipeline error-handling (`GenerationFailed` event) applies; Supervisor may attempt to formulate a fix if attempts remain, otherwise fails safely.
- **Policy Overrides**: Odoo business logic (e.g. destructive DB modifications) inherently blocks AI actions via standard API bounds.

## 14. Required Contracts, if any
A new lightweight `SupervisorEvaluationContract` is required. It must structure the output of the Supervisor (e.g. `{ "satisfies_requirements": bool, "improvement_instruction": str, "findings": list }`) to guide the Coordinator's looping logic.

## 15. Reusable Existing Components
- `GenerationContext`, `GenerationRuntime`, `AIRuntimeAdapter`, `WebsiteGenerationPipeline`, `BuilderSessionService` state machine, `GenerationStateManager`.

## 16. Duplicate/Dead Paths Discovered
- `AIReviewFramework` (deprecated)
- `ReviewerAgent` and `SupervisorEngine` (multi-agent orchestrator)

## 17. Files/Classes that would be modified in a future implementation
- `GenerationCoordinator` (`core/generation_coordinator.py`)
- `BuilderSessionService` (`services/builder_session_service.py` - for manual entrypoint)

## 18. Files/Classes that must NOT be modified
- `WebsiteGenerationPipeline` and its engines (`ContentEngine`, `CodeGenerationEngine`, etc.)
- `AIRuntimeAdapter`
- `ProviderManager`
- `CostRouter`

## 19. Open Architectural Questions
- Should the Supervisor maintain conversation history across improvement loops, or evaluate statelessly on each iteration based purely on evidence?

## 20. Proposed Next Implementation Phase
Phase 48.1: Implement the `SupervisorEvaluationContract` and integrate the bounded evaluation loop into `GenerationCoordinator`, utilizing a stateless evaluation prompt.

ADR REQUIRED BEFORE IMPLEMENTATION
An ADR must decide the exact shape of the SupervisorEvaluationContract, the evidence payloads it will consume, and the strict rules governing manual improvement rejection logic.

## Phase 48.1 ADR Reconciliation
- **Existing Reviewer/Supervisor Inventory**: 
  - `AIReviewFramework` (deprecated legacy wrapper)
  - `ReviewerAgent` (unused, isolated multi-agent role)
  - `SupervisorEngine` (unused, isolated failure recovery logic)
  - `ConfidenceEvaluator` (narrow visual assessment logic)
- **Reachability Results**: None of the secondary agent roles (`ReviewerAgent`, `SupervisorEngine`, `ConfidenceEvaluator`) are reachable in the canonical execution path. `AIReviewFramework` is reachable via `BuilderSessionService.run_ai_review()` but acts as a deprecated bridge.
- **Canonical Ownership Decision**: All duplicate paths are rejected. The Supervisor will be embedded as a Role within `GenerationCoordinator`.
- **SupervisorEvaluationContract Design**: A structured data contract returning `satisfies_requirements` (bool), `findings` (list), `improvement_instruction` (string), and `rejection_reason` (string). It strictly does *not* mutate generation context.
- **Evidence Boundary**: Bounded to deterministic pipeline outputs (e.g. `composition_manifest`, `build_acceptance`, linter counts). The Supervisor will not receive unbounded repository code or logs.
- **Statefulness Decision**: **STATELESS**. The Supervisor evaluates only the current state of requirements and evidence, preventing unbounded token cost and compounding context hallucinations.
- **Attempt-Cap Ownership**: The `GenerationCoordinator` strictly owns and enforces the attempt cap. The Supervisor cannot override or manipulate this limit.
- **Manual Improvement Ownership**: Owned by `BuilderSessionService` invoking the Coordinator with `max_attempts=1`. The Supervisor must first accept/reject the manual request before any pipeline execution occurs.
- **Security Boundary**: The Supervisor operates purely on abstract requirements and evidence. It has zero access to credentials, API keys, Odoo secrets, or DB auth.
- **Cost Boundary**: Governed by the `ProviderManager` and strictly bounded by the Coordinator's deterministic attempt loop.
- **ADR Reference**: `ADR-0089: Bounded Supervisor AI Role Within Canonical Generation Orchestration`
- **Unresolved Questions**: None remaining for the conceptual architecture. Phase 48.2 implementation is ready to proceed.
