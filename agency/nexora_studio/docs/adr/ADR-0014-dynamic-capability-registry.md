# ADR-0014: Dynamic Capability Registry

## Status
Accepted

## Context
Currently, the MCP Runtime dynamically discovers tools by scanning Odoo's Python model registry (self.env.registry) for classes inheriting from 
exora.tool.base. While functional, this couples tool discovery to code-level inheritance and Odoo's startup behavior, making versioning, dynamic enablement/disablement, remote integration, and capability metadata management complex.

As we scale Nexora Studio to support Preview Runtimes, Deployment Runtimes, AI Agents, and external Cloud Providers, we need a robust, metadata-driven approach. 

## Decision
We will introduce a central 
exora.capability_registry model. All tools, preview environments, cloud services, and AI extensions will self-register into this database-backed registry. The system will rely exclusively on this metadata (capability code, version, enablement status, priority) rather than Python class structures.

### Architecture Constraints
1. **Metadata Driven**: Tools and extensions must register themselves into the Capability Registry during installation or discovery. Execution resolves via database queries (e.g., capability_code, enabled=True, ersion).
2. **Versioning and Swapping**: The registry supports multiple implementations (e.g., preview_v1, preview_v2, preview_remote). Only one version should be active per code at a time.
3. **Local and Remote Capabilities**: The registry tracks whether an implementation is supports_local and/or supports_remote.
4. **Lifecycle Hooks**: Every capability exposes install(), uninstall(), enable(), disable(), upgrade(), health(), and alidate().
5. **No Hardcoded Links**: The MCP Runtime must never hardcode capabilities or manual lists.
6. **Backward Compatibility**: Existing tools (Filesystem, Git, Terminal, Browser, Preview) will be auto-migrated into this registry without breaking existing sessions.

## Consequences
- **Positive**: Complete Open/Closed Principle compliance. Future capabilities (Docker, AWS, Gemini, Playwright) can be added purely by creating a model and dropping its metadata into the registry.
- **Positive**: Operations and admins can toggle tools via UI (disabling insecure tools, switching preview engine versions) without code changes.
- **Negative**: Adds a slight database lookup overhead compared to in-memory Python class scanning, which we will mitigate via caching in the Runtime.
