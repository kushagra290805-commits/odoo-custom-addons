# Nexora Studio Architecture Inventory (Phase 1 Audit Report)

**Date:** July 2026  
**Type:** Strictly Read-Only Architecture Audit  
**Scope:** Odoo Custom Addon (`nexora_studio`)  

---

## Executive Summary

This document provides a comprehensive, structured inventory of the existing **Nexora Studio (`nexora_studio`)** Odoo 19 Community custom addon. The addon serves as the backend operating system and rendering engine for the enterprise digital service agency, managing AI execution, builder sessions, workspace virtualization, Git version control, and website design orchestration.

---

## 1. Module Overview & Dependencies (`__manifest__.py`)
- **Addon Name:** Nexora Studio (`nexora_studio`)
- **Version:** 1.0.0
- **License:** LGPL-3
- **Core Odoo Dependencies:** `base`, `mail`, `contacts`, `crm`, `project`, `website`, `template_store`
- **Application Classification:** Installable, Application (`application = True`)

---

## 2. Comprehensive Directory & Package Inventory

### 2.1 Database Models (`models/`)
Contains 34 Python model files defining ORM data tables and abstract capabilities:
- **Core Builder & Sessions:** `builder_session.py`, `builder_configuration.py`, `builder_conversation.py`, `builder_session_patch.py`, `builder_session_mcp.py`
- **Workspace & Version Control:** `workspace.py`, `git_runtime.py`
- **AI & Providers:** `ai_model_catalog.py`, `ai_audit_log.py`, `ai_execution_history.py`, `ai_catalog_sync_log.py`
- **Runtime & Capabilities:** `runtime.py`, `runtime_capability.py`, `runtime_event.py`, `runtime_event_constants.py`, `capability_registry.py`, `preview_runtime.py`, `plugin_descriptor.py`
- **Project & Generation Workflows:** `project_management.py`, `project_planner.py`, `generation_job_override.py`, `generation_stage_context.py`, `generation_stage_override.py`, `generation_stage_result.py`
- **Registry & Capabilities:** `registry_capability.py`, `registry_category.py`, `registry_component.py`, `registry_navigation.py`, `registry_service.py`
- **System & Auth:** `res_config_settings.py`, `res_users.py`, `nexora_audit_log.py`, `nexora_auth_session.py`
- **Framework Abstractions:** `source_framework/` (submodule)

### 2.2 Core Business Services (`services/`)
Contains 45 primary service modules and 8 domain subdirectories:
- **Session & Builder Services:** `builder_session_service.py` (35KB+ core engine), `builder_configuration_service.py`, `builder_assistant_service.py`, `builder_health_service.py`, `session_service.py`
- **Runtime & IDE Launchers:** `runtime_service.py`, `ide_service.py`, `ide_launcher.py`, `preview_service.py`, `preview_launcher.py`, `runtime_version_service.py`, `runtime_plugin.py`
- **Workspace & File Manipulation:** `workspace_service.py`, `workspace_file_service.py`, `git_service.py`
- **MCP & Plugin Architecture:** `mcp_registry.py`, `mcp_service.py`, `mcp_server.py`, `plugin_manager.py`, `plugin_lifecycle_service.py`, `plugin_installer_service.py`, `plugin_manifest_validator.py`, `plugin_repository.py`, `plugin_repository_factory.py`, `tool_registry.py`
- **Capabilities & Caching:** `capability_discovery_service.py`, `capability_cache_service.py`, `capability_lifecycle_service.py`, `cache_backends.py`
- **System, User & Auth:** `auth_service.py`, `user_service.py`, `permission_service.py`, `audit_service.py`, `error_codes.py`, `compatibility_service.py`, `semantic_version_service.py`, `metadata_version_service.py`
- **Project Planning & Graphs:** `project_planner_service.py`, `dependency_graph_service.py`, `model_resolution_service.py`

### 2.3 AI Subsystem (`services/ai/`)
Contains 19 specialized modules for AI orchestration and LLM adapter routing:
- **Core Management:** `provider_manager.py`, `ai_configuration_service.py`, `provider_execution_policy.py`, `provider_health_service.py`, `cost_router.py`
- **Context & Intelligence:** `context_builder.py`, `template_analyzer.py`, `patch_engine.py`, `ai_execution_context.py`
- **LLM Provider Adapters:** `base_adapter.py`, `openai_adapter.py`, `generic_openai_adapter.py`, `claude_adapter.py`, `gemini_adapter.py`, `openrouter_adapter.py`, `ollama_adapter.py`, `nvidia_adapter.py`, `test_adapter.py`

### 2.4 Design & Rendering Engine (`services/design/`)
Contains 27 modules for design intelligence, blueprinting, and multi-provider code generation:
- **Orchestration & Providers:** `design_orchestrator.py`, `design_provider.py`, `domain_enums.py`, `providers/provider_registry.py`, `providers/react_provider.py` (43KB+ React TSX generator), `providers/rendering_provider.py`
- **Design Intelligence & Domains:** `component_intelligence.py` (33KB+ component resolution engine), `component_manifest.py`, `design_system.py`, `design_system_engine.py`, `design_system_validator.py`, `design_blueprint.py`, `blueprint_engine.py`, `blueprint_validator.py`
- **Layout, Content & Assets:** `layout_domain.py` (40KB+ layout engine), `layout_engine.py`, `layout_validator.py`, `content_domain.py`, `content_intelligence_engine.py`, `asset_domain.py`, `asset_planning_engine.py`, `asset_content_validator.py`
- **Interactions & Reference Libraries:** `interaction_model.py`, `interaction_builder.py`, `react_component_library.py` (64KB+ reference TSX component catalog), `render_domain.py`
- **Penpot Design Integration:** `penpot_provider.py`, `penpot_client.py`, `penpot_auth.py`

### 2.5 Controllers (`controllers/`)
Contains 11 HTTP/REST controllers exposing endpoints to external clients and the FastAPI BFF:
- **Core APIs:** `ai_api.py`, `builder_session_api.py`, `workspace_api.py`, `project_api.py`, `runtime_api.py`, `client_provisioning_api.py`
- **Session & Auth Controllers:** `auth_controller.py`, `user_controller.py`, `session_controller.py`, `audit_controller.py`

### 2.6 Plugins & Extensions (`plugins/`)
Contains 11 domain plugin subdirectories (currently structured as extension namespaces/folders):
- `anthropic/`, `aws/`, `cloudflare/`, `core/` (contains `browser/`, `filesystem/`, `git/`, `preview/`, `terminal/`), `custom/`, `docker/`, `gemini/`, `github/`, `openai/`, `playwright/`, `supabase/`

### 2.7 Security (`security/`)
- `security_groups.xml`: Defines security groups (`group_nexora_user`, `group_nexora_manager`, `group_nexora_admin`).
- `ir.model.access.csv`: Enforces Access Control Lists (ACLs) across all 34 custom models.
- `permission_registry.py`: Programmatic role and capability verification.

### 2.8 Data & Scheduled Jobs (`data/`)
- **Seed Data:** `registry_seed_data.xml`, `nexora_seed_data.xml`, `openrouter_config.xml` (pre-configured OpenRouter LLM models and cost routing tables).
- **Scheduled Cron Jobs:** `ai_catalog_cron.xml` (defines automated background job `nexora.ai_model_catalog.cron_sync_openrouter_catalog` to synchronize provider model pricing and availability).
- **Views (`views/`):** 11 XML backend UI view definitions for Odoo admin interface (`workspace_views.xml`, `builder_session_views.xml`, `res_config_settings_views.xml`, `runtime_views.xml`, etc.).
- **Wizards (`wizard/`):** Currently empty (no transient interactive wizards defined).

---

## 3. Summary Assessment

The `nexora_studio` addon is a mature, highly structured backend engine. It successfully isolates LLM provider routing (`services/ai/`), design orchestration (`services/design/`), and IDE/workspace virtualization (`services/`), providing an authoritative Python foundation for the Nexora Studio platform.
