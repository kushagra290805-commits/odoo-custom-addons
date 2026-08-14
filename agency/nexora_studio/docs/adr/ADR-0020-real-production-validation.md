# ADR-0020: Real Production Validation

## Status
Accepted

## Context
Phase 8C introduced production-grade generation orchestrations but relied on `MockProvider` and stubbed dependency/preview executions for safety. Phase 8C.1 eliminates these safety rails. The system must execute end-to-end using authentic AI models, true package managers, real Git operations, and live local preview servers to validate the enterprise readiness of the Generation Engine.

## Decision
1. **Ollama Auto-Discovery:** `AIProviderFactory` will proactively query `localhost:11434/api/tags`. If an Ollama model is available, it becomes the default provider.
2. **Authentic Operations:**
   - **Dependencies:** `DependencyResolutionStage` will synchronously invoke `npm install` within the target workspace.
   - **Git:** `RuntimeBootstrapStage` will execute `git init`, `add`, and `commit`.
   - **Preview:** `RuntimeBootstrapStage` will execute `npm run dev` in a detached, managed subprocess and ping its health endpoint.
3. **Report Generation:** The verification suite will compile a holistic diagnostic report documenting AI latencies, token counts, network bindings, and package manager stdout.

## Consequences
- **Positive:** Unlocks verifiable, end-to-end application generation. Proves the orchestrator's capability to yield live applications.
- **Negative:** Verification becomes slower and requires a functional Node.js/Ollama host environment. Generation failures due to external factors (e.g., NPM network issues) will trip rollbacks.
