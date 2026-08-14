# Component Inventory

| Subsystem | Classification | Notes |
| :--- | :--- | :--- |
| **Platform (Core/Odoo)** | Production Ready | Robust base services, ORM, security groups. |
| **Provider Registry** | Production Ready | Live registry of AI models via `nexora.provider_registry`. |
| **Provider Manager** | Production Ready | Dynamic routing, retries, fallbacks. |
| **Catalog Service** | Production Ready | Live catalog sync logging (`ai_catalog_sync_log`). |
| **Cost Router** | Production Ready | Enforces cost tiers (e.g. `Tier 1: Claude 3.5 Sonnet`, `Tier 3: Llama 3`). |
| **Telemetry** | Production Ready | `TelemetryRecorder`, Cost Ledger, `RuntimeEvents` strictly decoupled from execution. |
| **Dashboard** | Production Ready | Real-time AI dashboard metrics via `ai_analytics_api`. |
| **Console** | Production Ready | React/Vite Developer Console frontend (`nexora-console`). |
| **Auth** | Production Ready | Custom session management (`nexora.auth.session`). |
| **Workspace** | Production Ready | Host filesystem management (`WorkspaceService`), physical path resolution. |
| **Runtime** | Production Ready | `RuntimeService` managing `IDE`, `Preview`, `Git`, `MCP`. |
| **Builder** | Partially Implemented | `BuilderSessionService` exists but execution paths are highly fractured. |
| **Website Generation Pipeline**| Partially Implemented | Exists as two parallel implementations (`Engines` vs `Stages`). |
| **Design Intelligence Platform**| Partially Implemented | `BlueprintValidator` and various Engines exist, but rely on orchestrator coupling. |
| **Penpot Integration** | Functionally Complete | Full design orchestration (`PenpotDesignProvider`). |
| **Frontend Templates** | Functionally Complete | `assets/frontend-templates` static React/Vite scaffolds. |
| **Template Store** | Dead | Legacy monolithic system in `shared/template_store`. |
| **Deployment** | Missing | No engines or modules exist for physical production deployment. |
| **Client Portal** | Missing | No frontend client approval portal exists. |
