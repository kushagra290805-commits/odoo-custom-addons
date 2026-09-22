# ADR-0089: Bounded Supervisor AI Role Within Canonical Generation Orchestration

## 1. Context
Nexora Studio currently orchestrates deterministic website generation through a frozen pipeline. To increase generated quality, a "Supervisor" AI role is needed to evaluate output against requirements and provide guided corrections. However, previous attempts at adding review/supervisor features resulted in disconnected multi-agent frameworks, duplicate orchestration layers, and redundant evaluation paths.

## 2. Current Architecture
- `BuilderSessionService`: Top-level workflow and state machine owner.
- `GenerationCoordinator`: Owns the deterministic generation context, event lifecycle, and pipeline invocation.
- `WebsiteGenerationPipeline`: A strict sequence of deterministic generation engines (Requirement, Design, Content, Asset, Code, Validation).
- `ProviderManager` & `CostRouter`: Determine model selection, enforce quotas, and track telemetry.
- `ValidationEngine`: Generates deterministic post-generation evidence (e.g., build acceptance, linter issues, component metrics).

## 3. Problem
Integrating an AI Supervisor could easily introduce a secondary autonomous orchestration loop, violating the platform's deterministic bounds. If the Supervisor is allowed to loop indefinitely, bypass the canonical pipeline, access credentials directly, or manipulate context ownership improperly, it breaks system reliability and cost controls.

## 4. Decision
We will integrate the Supervisor AI strictly as a **Role** evaluated within the existing `GenerationCoordinator` loop, rather than a separate autonomous agent or alternative orchestrator. It will communicate via a strict `SupervisorEvaluationContract` and operate statelessly.

## 5. Supervisor Role
The Supervisor AI is an evaluation and planning entity. It does not execute code, write files, or invoke arbitrary tool calls. It is exclusively responsible for analyzing user requirements against bounded evidence and producing a structured instruction to guide the next pipeline execution.

## 6. Coordinator Ownership
The `GenerationCoordinator` is the absolute owner of the orchestration loop. It invokes the pipeline, invokes the Supervisor, applies the Supervisor's instructions to the context, and enforces the deterministic attempt cap. 

## 7. SupervisorEvaluationContract Semantics
The contract cleanly separates the Supervisor's intelligence from platform controls:
- **Input**: User goal, current execution instruction, and a bounded evidence projection.
- **Output**: 
  - `satisfies_requirements` (boolean)
  - `findings` (list of strings)
  - `improvement_instruction` (string)
  - `rejection_reason` (string, e.g., out of bounds, unsafe)
- **Constraint**: The Supervisor does **not** directly mutate `context.artifact.requirements`. Instead, it yields the `improvement_instruction`. The `GenerationCoordinator` deterministically merges this into a transient context field for the next pipeline run, preserving the canonical user requirements intact.

## 8. Evidence Boundary
The Supervisor is strictly prohibited from receiving unbounded context dumps (e.g., full repositories, complete logs, full browser DOMs). It operates exclusively on a formalized evidence projection, primarily sourced from the `GenerationContext.metadata`:
- The `composition_manifest`
- `build_acceptance` status
- Quantitative component metrics or truncated deterministic linter errors

## 9. Initial-Generation Loop
1. `BuilderSessionService` initiates generation via `GenerationCoordinator`.
2. Coordinator requests an initial instruction from the Supervisor based on raw requirements.
3. Coordinator invokes `WebsiteGenerationPipeline`.
4. Evidence is gathered via `ValidationEngine` and appended to context metadata.
5. Supervisor evaluates evidence via the `SupervisorEvaluationContract`.
6. If `satisfies_requirements` is false, and the cap is not reached, the Coordinator loops back to step 3 using the new `improvement_instruction`.
7. Loop terminates on acceptance or cap limit.

## 10. Manual-Improvement Flow
1. User requests a manual change via `BuilderSessionService`.
2. Supervisor evaluates the request against safety and scope constraints.
3. If safe, Supervisor produces a structured instruction.
4. Coordinator invokes the pipeline exactly **once** (`max_attempts=1`).
5. Execution stops and returns the result, regardless of subsequent evidence.

## 11. Attempt Cap
The attempt cap is strictly owned by the `GenerationCoordinator` (e.g., 1 initial execution + 3-5 bounded improvements). The Supervisor has no visibility into the cap and cannot manipulate it.

## 12. Stateless vs Stateful Decision
The Supervisor will be **stateless**. It will evaluate the current requirement and the latest evidence only. 
**Rationale**: This prevents runaway context growth, reduces token cost, avoids compounding hallucinations from previous incorrect assumptions, and isolates generation attempts for easier debugging and determinism.

## 13. Security Boundaries
The Supervisor must **never** receive API keys, database passwords, Odoo credentials, or access to the connector credential store. It operates solely on abstract requirements and deterministic evidence.

## 14. Cost Boundaries
Token cost and rate limits remain governed by `ProviderManager`. The `GenerationCoordinator` guarantees an upper bound on model invocations per session by enforcing the strict attempt cap.

## 15. Failure Behavior
If the Supervisor fails to produce a valid contract, the Coordinator terminates the loop safely, preserving the last known successful artifact. If the pipeline itself fails, the Coordinator publishes a standard `GenerationFailed` event and aborts further AI review.

## 16. Existing Reviewer/Supervisor Reconciliation
All existing alternative review/supervision paths are superseded and must be bypassed or deprecated:
- `AIReviewFramework` (Deprecated wrapper)
- `ReviewerAgent` (Multi-agent QA)
- `SupervisorEngine` (Failure recovery loop)
- `ConfidenceEvaluator` (Visual verification)

## 17. Alternatives Considered
- *Stateful Conversational Loop*: Rejected due to high token cost, exponential context growth, and reduced reproducibility.
- *Supervisor mutating context.requirements*: Rejected due to ownership violation. Requirements should remain the canonical user truth; transient AI instructions must remain distinct.
- *Multi-agent Supervisor*: Rejected due to unbounded autonomy risk and duplicate orchestration complexity.

## 18. Consequences
- **Positive**: Strict determinism, capped costs, safe failure modes, and clear architectural boundaries.
- **Negative**: The stateless model requires highly effective evidence projections, as the Supervisor cannot "remember" its previous mistakes directly.

## 19. Future Implementation Constraints
Implementation of Phase 48.2 must ensure that no secondary orchestrators are instantiated and that the `GenerationCoordinator` loop remains fully synchronous or explicitly managed within the existing event bus lifecycle.
