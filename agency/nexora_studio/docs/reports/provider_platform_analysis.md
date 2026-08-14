# Existing Architecture Analysis: Provider Framework Fragmentation (Phase 15A Report)

**Date:** July 2026  
**Type:** Strictly Read-Only Architecture Analysis  
**Scope:** Existing Provider Implementations Across `services/ai/`, `services/design/`, `services/mcp_*`, `preview_service.py`, `workspace_service.py`, and `plugin_manager.py`  

---

## Executive Summary

Before implementing the **Unified Provider Platform** defined in **ADR-0029**, we conducted a thorough audit of all existing provider systems within the Nexora Studio Odoo backend (`nexora_studio`) and the Nexora Console frontend (`nexora-console`). Our analysis confirms that while each subsystem exhibits high cohesion within its own domain, the overall platform suffers from **six fragmented provider categories** that duplicate cross-cutting concerns, enforce inconsistent error handling, and complicate frontend UI state management.

This report catalogs the existing architecture, identifies areas of duplicated logic and shared responsibilities, and highlights critical architectural debt to be eradicated during consolidation.

---

## 1. Current Provider Categories & Implementations

| Category | Primary Backend Codebase Location | Existing Registry / Manager Class | Existing Adapters / Implementations | Key Lifecycle Limitations |
| :--- | :--- | :--- | :--- | :--- |
| **1. AI Providers** | `services/ai/` | `AIProviderManager`, `ProviderExecutionPolicy`, `ProviderHealthService` | `OpenAIAdapter`, `ClaudeAdapter`, `GeminiAdapter`, `OllamaAdapter`, `OpenRouterAdapter`, `NvidiaAdapter` | Custom 4-tier routing; independent ping-based health checks; ad-hoc JSON configuration schemas. |
| **2. MCP Providers** | `services/mcp_service.py`<br>`services/mcp_registry.py`<br>`services/tool_registry.py` | `McpService`, `ToolRegistry` | Local filesystem tool, Git tool, Preview tool, Workspace tool | Direct Odoo method execution; zero external stdio/SSE network transport adapters; no shared caching. |
| **3. Preview Providers**| `services/preview_service.py`<br>`services/preview_launcher.py` | `PreviewService` | `ViteLauncher`, `PythonHttpLauncher`, `CustomServerLauncher` | Process ID and port allocation lifecycle (3000–3999); socket polling health check; no connection to AI health service. |
| **4. Design Providers** | `services/design/design_provider.py`<br>`penpot_provider.py` | Standalone factory / service calls | `PenpotProvider`, `ReactRenderingProvider` | Domain-specific JSX/template synthesis; no standardized capability discovery or health probing. |
| **5. Asset Providers** | `services/design/asset_planning_engine.py`<br>`asset_domain.py` | `AssetPlanningEngine` | Declarative plans (`PromptSpecification`, `AssetPlan`); **stubbed** external fetchers | Zero binary storage orchestration; no external search/fetch adapters (Unsplash, Pixabay, Google Fonts stubbed). |
| **6. Workspace Providers**| `services/workspace_service.py`<br>`services/plugin_manager.py` | `WorkspaceService`, `PluginManager`, `CapabilityDiscoveryService` | Physical disk directory trees, Git subprocesses, runtime plugins | OS file CRUD and subprocess execution; independent manifest validation (`plugin_manifest_validator.py`). |

---

## 2. Analysis of Duplicated Logic & Cross-Cutting Concerns

Our AST and architectural trace revealed extensive duplication of foundational infrastructure across the six categories:

```mermaid
flowchart TD
    subgraph Duplicated Concerns Across 6 Categories
        Auth[1. Authentication & Secret Vaulting]
        Health[2. Health Probing & Circuit Breaking]
        Config[3. Configuration Schemas & Manifests]
        Cache[4. Caching & TTL Invalidation]
        Policy[5. Execution Policies & Fallback Routing]
    </flowchart>
    
    AI[AI Provider Framework] --> Auth & Health & Config & Cache & Policy
    MCP[MCP Server Framework] --> Auth & Health & Config & Cache
    Preview[Preview Launcher System] --> Health & Config
    Design[Design & Asset Providers] --> Config & Cache
```

### 2.1 Duplicated Authentication & Secret Vaulting
- **AI Adapters:** Retrieve API keys via `request.env['ir.config_parameter'].sudo().get_param('agency.openai_api_key')` or custom database fields on provider records, manually injecting bearer headers into HTTP requests.
- **Penpot Provider:** Manages its own OAuth / Token authentication (`penpot_auth.py`), storing tokens in custom session models and injecting headers via a standalone `PenpotClient`.
- **MCP Servers:** Store connection strings and authentication tokens inside `nexora.mcp_server` database records without utilizing a centralized secret vault or encryption provider.

### 2.2 Duplicated Health Monitoring & Circuit Breaking
- **AI Health Service (`provider_health_service.py`):** Implements a ping mechanism and circuit breaker (recording consecutive errors in Odoo memory/DB) specifically for LLM endpoints.
- **Preview Service (`preview_service.py`):** Implements an independent socket polling mechanism (`_check_socket()`) to verify if a Vite dev server is responding on its allocated port.
- **MCP Service (`mcp_service.py`):** Performs ad-hoc health checks upon server initialization without circuit breaking or background degradation tracking.

### 2.3 Duplicated Configuration & Manifest Validation
- **AI Configuration:** Validated via `ai_configuration_service.py` using custom dictionary inspection.
- **Plugin Manifests:** Validated via `plugin_manifest_validator.py` using a separate schema validator.
- **Preview Launchers:** Validated via `preview_launcher.py` by scanning physical disk files (`vite.config.js`, `package.json`).

---

## 3. Shared Responsibilities & Split-Brain Contention

We identified several areas where Odoo and the Nexora Console frontend contend for state or execution governance:
1. **Preview Lifecycle Execution:** The active UI (`PreviewPanel.tsx`) calls Odoo REST endpoints to start/stop dev servers, while parallel frontend toolbar buttons call local client-side command wrappers (`previewCommands.startPreview()`) operating on an in-memory virtual filesystem.
2. **State Caching:** Odoo caches AI model resolutions (`model_resolution_service.py`) and capability manifests (`capability_cache_service.py`), while the frontend console simultaneously maintains 25 Zustand client stores (`aiStore`, `previewStore`, `projectStore`, `providerStore`) that cache and mutate the exact same domain data without real-time synchronization.

---

## 4. Architectural Debt & Extension Points

| Architectural Debt Item | Location in Current Codebase | Operational & Developer Impact | Target Consolidation Strategy |
| :--- | :--- | :--- | :--- |
| **Fragmented Exception Hierarchy** | All adapter packages | AI raises `AIExecutionError`; Preview raises `LauncherError`; MCP raises `McpToolError`. Callers cannot implement generic error retry or UI notification logic. | Establish a universal `ProviderException` hierarchy (`AuthenticationError`, `HealthDegradedError`, `RateLimitError`, `ExecutionError`). |
| **Lack of Unified Observability** | `services/` | While `nexora.runtime_event` records timeline events, provider-specific latency, token usage, and payload sizes are logged inconsistently across subsystems. | Enforce mandatory emission of standardized `ProviderEvent` objects from `ProviderExecutionContext`. |
| **Stubbed Asset Providers** | `services/design/` | `AssetPlanningEngine` outputs placeholder URLs because no external search/fetch adapters exist for Unsplash, Pixabay, or Google Fonts. | Implement `AssetProvider` extending `BaseProvider` to plug external media APIs cleanly into the design orchestrator. |
| **Inaccessible MCP Tools** | `services/mcp_service.py` | Internal tools cannot be invoked by external AI clients (Cursor, Claude Desktop) due to missing network transport adapters. | Implement stdio and SSE transport bridges within the unified provider lifecycle. |

---

## 5. Conclusion & Transition to Abstraction Design

The existing architecture provides solid domain implementations but lacks an overarching OS contract. In **PART 3**, we design the unified interfaces (`BaseProvider`, `ProviderMetadata`, `ProviderCapability`, etc.) that will encapsulate these six categories into a cohesive, polymorphic framework without modifying existing runtime logic.
