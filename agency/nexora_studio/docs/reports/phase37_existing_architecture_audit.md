# Phase 37 Existing Architecture Baseline Audit

## 1. Existing 3D-Related Implementation Inventory
- `models/spline_provider.py`: A standalone legacy provider that runs `@splinetool/runtime` inside `nexora.execution_sandbox_service`.
- `services/design/providers/provider_registry.py`: Defines `react_three_fiber` as a future target stub.
- `services/design/providers/react_provider.py`: Explicitly rejects any file containing `three` strings to enforce 2D bounds.
- `services/design/asset_planning_engine.py`: Provisions `3d_asset` visual components for tech/saas projects.
- `services/design/component_intelligence.py`: Defines UI components like `3d_scene` and `generic_3d_asset`.

## 2. Existing Website-Generation Pipeline
Located in `services/generation/workflows/generation_pipeline.py`. 
Enforces a strict execution sequence: `RequirementAnalyzer` -> `PlanningWorkflow` -> `PlatformRuntime` (AI) -> `Adapters` -> `DesignTranslator` -> `DesignValidator` -> `PatchEngine` -> `DocumentModel`.

## 3. Existing Capability-Resolution Path
Capabilities are injected into the AI context via `WorkflowContext.get_capabilities()`. These capabilities map directly to the `ConnectorCapabilityIndex` established by the UCP during MCP discovery.

## 4. Existing Connector/Tool Dispatch Path
Orchestrated capabilities are dispatched through `ConnectorRuntime.dispatch(req)`, which resolves the target MCP server, sends the JSON-RPC payload, and returns the result safely.

## 5. Existing Template/Component Source Path
The AI retrieves layouts and atomic configurations which are then parsed by Ecosystem Adapters (e.g., Aceternity UI, standard React) in `services/providers/component/`.

## 6. Existing Asset Pipeline
`services/design/asset_planning_engine.py` orchestrates asset metadata (`width`, `height`, `format`), while the actual binary/CDN resolution happens post-generation or via placeholder logic.

## 7. Existing Rendering/Runtime Path
The `RenderingProviderRegistry` instantiates a provider (currently `ReactRenderingProvider`) which validates the generated AST, project structure (`package.json`, `vite.config.js`), and syntactical correctness before finalizing the project workspace.

## 8. Duplicate/Dead Implementation Findings
- **DEAD/PARALLEL:** `models/spline_provider.py` relies on a bespoke `nexora.provider.spline` model and bypasses UCP entirely, hardcoding a node sandbox execution script. This violates Phase 39B architecture freeze directives.

## 9. Genuine Architectural Gaps
- The `RenderingProviderRegistry` has `react_three_fiber` as a stub. It cannot execute or validate 3D projects yet.
- `ReactRenderingProvider` actively blocks `three` references.
- No established prompt or system instruction tells the orchestrator how to safely emit React Three Fiber syntax using standard UCP components.

## 10. Exact Files/Modules That Should Be Modified
- `services/design/providers/provider_registry.py` (To activate `react_three_fiber`)
- `services/design/providers/react_three_fiber_provider.py` (NEW file: to implement the R3F validator/provider)
- `services/design/providers/react_provider.py` (To isolate or loosen the `three` prohibition when hybrid rendering is allowed)
- `services/generation/workflows/website_generation_workflow.py` or AI Prompt Definitions (To instruct the AI on R3F syntax retrieval via Tavily)

## 11. Exact Files/Modules That Should NOT Be Modified
- `services/generation/workflows/generation_pipeline.py` (Core pipeline remains unchanged)
- `services/connector/*` (UCP Architecture is completely frozen)
- `models/spline_provider.py` (Leave dead code alone or delete later, but do not integrate with it)
- `nexora.connector` database records.

## 12. Proposed Phase 37 Implementation Sequence
1. **Renderer Expansion:** Implement `ReactThreeFiberProvider` extending `ReactRenderingProvider`, overriding the `validate_project` rules to accept (and mandate) `@react-three/fiber` and `three` dependencies.
2. **Registry Activation:** Update `RenderingProviderRegistry` to lazy-load and resolve `react_three_fiber`.
3. **Capability Binding:** Update the generation orchestrator prompts/context to explicitly request `tavily_search` when it needs R3F boilerplate, ensuring compliance with the Credential Policy.
4. **End-to-End Test:** Execute a test generation requesting a 3D scene, proving it flows through UCP -> Tavily -> AI Orchestrator -> R3F Provider -> Validated Project.

## 13. Verification Gates
- **Gate 1:** Does the implementation require modifying `ConnectorRuntime`? (Must be NO)
- **Gate 2:** Is `FIRECRAWL_API_KEY` or `GITHUB_PERSONAL_ACCESS_TOKEN` used? (Must be NO)
- **Gate 3:** Are the output artifacts standard `.jsx` files? (Must be YES)
