# Gap Analysis

## 1. Provider & Platform Subsystem
- **What already exists?** A fully production-ready provider abstraction layer. Synchronous HTTP routing, Provider Registry, Model Catalogs, Cost Ledger, and Telemetry (Audit Logs/Metrics).
- **What still needs implementation?** Streaming responses (Server-Sent Events) and multi-agent interaction memory (Agent Runtime context handling).
- **What should not be rebuilt?** Do NOT rebuild the HTTP request layer, the retry logic, the provider configurations, or the Cost/Telemetry tracking. Any new streaming logic must patch into `BaseAIAdapter`.

## 2. Builder Orchestration Subsystem
- **What already exists?** `BuilderSessionService`, `WebsiteGenerationPipeline` (JSON Blueprints), and `GenerationStageRegistry` (Physical codebase mutation).
- **What still needs implementation?** Merging the split orchestration paths. The `WebsiteGenerationPipeline` must be extended to actually emit code (replacing the legacy `stage_06` mutation scripts), creating a single cohesive pipeline from Requirements -> Blueprint -> Code. Multi-agent delegation needs to be built into this unified pipeline.
- **What should not be rebuilt?** Do NOT rebuild `GenerationContext`, the engine interfaces (`BaseGenerationEngine`), or the DAG state manager. The current pipeline framework is solid; it is just incomplete.

## 3. Design & Penpot Subsystem
- **What already exists?** `DesignOrchestrator`, DIP Validators, `PenpotDesignProvider` (which successfully pulls layouts and tokens).
- **What still needs implementation?** A continuous synchronization mechanism so that updates in the Builder IDE push back to Penpot, and vice-versa (two-way sync).
- **What should not be rebuilt?** Do NOT rebuild the `DesignOrchestrator` routing or the `DesignProvider` interface.

## 4. Workspaces & Runtimes Subsystem
- **What already exists?** `WorkspaceService`, robust file I/O, `RuntimeService` managing Vite `Preview`, `Git`, and `IDE` sandbox launchers.
- **What still needs implementation?** Advanced sandboxing (Docker/microVMs) if true multi-tenant security is required.
- **What should not be rebuilt?** Do NOT rebuild the port allocation logic, the launcher interfaces, or the local process management hooks.

## 5. Deployment & Client Portal
- **What already exists?** Nothing.
- **What still needs implementation?** 100% of the Deployment subsystem (pushing code to staging/production Vercel/Netlify/AWS). 100% of the Client Portal (a web interface where clients review, comment on, and approve the generated site).
- **What should not be rebuilt?** N/A.

### Strategic Summary
The primary architectural gap blocking true end-to-end multi-agent capabilities is the **fractured generation pipeline**. The JSON Blueprint engines do not speak directly to the Code Generation mutation stages. Fixing this (while reusing the existing `GenerationContext`) and adding **Streaming/Agent Runtime** are the immediate prerequisites before building Deployment.
