# Capability Matrix

| Capability | Status | Evidence / Notes |
| :--- | :--- | :--- |
| **Provider Routing** | Implemented | `AIProviderManager`, `CostRouter` |
| **Tool Calling** | Implemented | `MCPRegistry`, `MCPToolBase` |
| **Architecture Engine** | Implemented | `WebsiteGenerationPipeline` -> `ArchitectureEngine` |
| **Layout Engine** | Implemented | `DesignOrchestrator` -> `LayoutEngine` |
| **Component Generation** | Implemented | `DesignOrchestrator` -> `DesignSystemEngine` |
| **Asset Generation** | Implemented | `DesignOrchestrator` -> `AssetPlanningEngine` |
| **Preview** | Implemented | `PreviewService`, `ViteLauncher`, `PythonHttpLauncher` |
| **Project Management** | Partially Implemented | `NexoraProject`, `NexoraProjectRequest` models exist but lack workflows. |
| **Builder Planning** | Partially Implemented | `PlanningEngine` constructs deterministic sitemaps but relies heavily on hardcoded DOMAIN_TEMPLATES. |
| **Code Generation** | Partially Implemented | Exists only in legacy `stage_06_ai_code_generation.py`, not in modern Pipeline. |
| **Agent Runtime** | Planned | No multi-agent actor models or conversational delegation currently exists. |
| **Testing** | Planned | `stage_10_tests` exists but is largely stubbed. |
| **Streaming** | Missing | `AIProviderManager` uses synchronous HTTP exclusively. |
| **RAG** | Missing | No vector database or document chunking implementation exists. |
| **Deployment** | Missing | No cloud provisioning or GitOps deployment logic exists. |
| **Client Approval** | Missing | No external client portal exists. |
| **Legacy Template Cloning**| Deprecated | `template_store` procedural merging is flagged for removal. |
