# MCP & Plugin Readiness Audit (Phase 4 Audit Report)

**Date:** July 2026  
**Type:** Strictly Read-Only Architecture Audit  
**Scope:** Plugin Framework & MCP Subsystem (`services/mcp_*.py`, `services/plugin_*.py`, `services/tool_registry.py`)  

---

## Executive Summary

This report evaluates the readiness of the **Nexora Studio Plugin and Model Context Protocol (MCP) Framework**. Our audit confirms that an initial, partial MCP implementation already exists within Odoo (`nexora.mcp_registry`, `nexora.mcp_service`, `nexora.mcp_server`, and `nexora.tool_registry`). The framework successfully abstracts local workspace tools (filesystem, Git, preview) into standardized tool definitions. However, it currently lacks a true network transport layer (stdio/SSE/JSON-RPC), external authentication, and dynamic third-party MCP server discovery—key capabilities that must be built in **Phase 15C**.

---

## 1. Existing Plugin Framework & Registry Architecture

### 1.1 Plugin Package Manager (`nexora.plugin_manager`)
The plugin framework is structured around package lifecycle management:
- **Manifest Validation:** `PluginManifestValidator` (`nexora.plugin_manifest_validator`) parses JSON/YAML plugin manifests, verifying required fields (`name`, `version`, `provider`, `dependencies`, `capabilities`).
- **Lifecycle Control:** `PluginLifecycleService` (`nexora.plugin_lifecycle_service`) handles installation, enabling, disabling, upgrading, and downgrading of plugins via `PluginDescriptor` models (`models/plugin_descriptor.py`).
- **Repository Abstraction:** `PluginRepository` and `PluginRepositoryFactory` provide interfaces for fetching plugin packages from local or remote repositories.

### 1.2 Capability & Tool Registries
- **Capability Registry (`nexora.capability_registry`):** Central database catalog storing all registered features, categorized by type (`tool`, `runtime`, `provider`, `theme`).
- **Tool Registry (`nexora.tool_registry`):** Wraps `CapabilityCacheService` (`nexora.capability_cache_service`) to dynamically discover and execute tools where `category == 'tool'`.
- **Execution Flow:** When `ToolRegistry.execute_tool(tool_id, context, **kwargs)` is called, it resolves the target Odoo model from cache, executes `tool.validate(context, **kwargs)`, and invokes `tool.execute(context, **kwargs)`.

---

## 2. Existing Partial MCP Implementation Analysis

We discovered that an early-stage MCP abstraction layer is already present in `services/mcp_registry.py`, `services/mcp_service.py`, and `services/mcp_server.py`:

| MCP Module / Class | Odoo Model Name | Current Status & Capabilities | Existing Limitations |
| :--- | :--- | :--- | :--- |
| **`MCPRegistry`** | `nexora.mcp_registry` | **Partially Implemented.** Discovers local tool models (`nexora.mcp_tool_filesystem`, `nexora.mcp_tool_git`, `nexora.mcp_tool_workspace`, `nexora.mcp_tool_preview`) and calls `get_definition()`. | Uses a hardcoded list of `tool_models` instead of querying the database registry dynamically. |
| **`MCPToolBase`** | `nexora.mcp_tool_base` | **Abstract Base Model.** Enforces standard tool contract: `get_definition()`, `validate()`, `execute()`, `shutdown()`. | Only supports local Python Odoo model execution; no remote JSON-RPC execution. |
| **`MCPService`** | `nexora.mcp_service` | **Runtime Plugin.** Inherits from `nexora.runtime_plugin`. Discovers capabilities, emits WebSocket lifecycle events (`mcp.started`, `mcp.ready`), and sets runtime status. | Sets hardcoded endpoint `mcp://local`; does not spawn an actual network protocol server. |
| **`MCPServer`** | `nexora.mcp_server` | **State Simulator.** Creates a simulated server session UUID, records heartbeat, and tracks connected IDE metadata. | Does not listen on stdio or Server-Sent Events (SSE). It acts purely as an Odoo state tracking record. |

---

## 3. Deep-Dive: Built-In MCP Tools

The following local MCP tools are currently registered in `MCPRegistry`:
1. **Filesystem Tool (`nexora.mcp_tool_filesystem`):** Exposes `capabilities: ['read', 'write', 'list', 'create', 'delete', 'rename', 'move', 'search', 'replace']`. Routes execution directly to `nexora.filesystem_service`.
2. **Git Tool (`nexora.mcp_tool_git`):** Exposes `capabilities: ['status', 'commit', 'branch', 'checkout', 'pull', 'push', 'diff', 'log']`. Routes execution directly to `nexora.git_service`.
3. **Workspace Tool (`nexora.mcp_tool_workspace`):** Exposes workspace creation, archive, and wipeout operations. Routes execution to `nexora.workspace_service`.
4. **Preview Tool (`nexora.mcp_tool_preview`):** Exposes preview start, stop, reload, and HMR injection. Routes execution to `nexora.preview_service`.

---

## 4. Gap & Readiness Assessment for Phase 15C

| Architectural Dimension | Current Readiness Status | Required Upgrade for Phase 15C (MCP Framework) |
| :--- | :--- | :--- |
| **Tool Abstraction** | 🟢 **Ready** (`MCPToolBase` exists) | Preserve existing `get_definition()`, `validate()`, `execute()` contract. |
| **Transport Abstraction** | 🔴 **Missing** (Hardcoded `mcp://local`) | Build an asynchronous transport adapter layer supporting stdio and HTTP Server-Sent Events (SSE) / JSON-RPC 2.0. |
| **External Authentication** | 🔴 **Missing** (Odoo session only) | Implement API token / OAuth authentication for external MCP clients and servers connecting over HTTP/SSE. |
| **Dynamic Registry** | 🟡 **Partial** (Hardcoded in `MCPRegistry`) | Re-wire `MCPRegistry.get_all_tools()` to query `nexora.capability_registry` dynamically, allowing third-party npm/pip MCP servers to register without code edits. |
