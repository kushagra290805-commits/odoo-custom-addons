# ADR-0013: MCP Runtime and Tool Layer

## Status
Accepted

## Context
As Nexora Studio evolves into an orchestrator for autonomous AI agents, we need a standardized, unified way for the runtime environment to execute tasks such as filesystem manipulation, git commands, terminal interactions, and browser automation. Currently, services like GenerationOrchestrator directly manipulate os, shutil, subprocess, and git. This tight coupling prevents AI agents (and MCP clients) from seamlessly interacting with the workspace through controlled, observable interfaces. 

We need to implement an MCP (Model Context Protocol) Runtime that exposes a Dynamic Tool Registry. 

## Decision
We will implement the **MCP Runtime** as a first-class citizen within the 
exora_studio runtime ecosystem.

1. **MCP Runtime as a Runtime Capability**: The MCP Runtime (untime_type = 'mcp') will be managed by the Builder Session. It will start after the IDE runtime and shut down before it.
2. **Tool Registry Architecture**: We will introduce a dynamic Tool Registry (services/tool_registry.py). Tools will self-register. There will be no hardcoded switch statements.
3. **Zero Framework Coupling**: Tools must be completely isolated from Odoo's ORM or web frameworks where possible. They receive a ToolContext and return a ToolResult.
4. **Local-First Architecture**: For Phase 8, the MCP runtime operates entirely locally, wrapping local filesystem and terminal commands. Future remote MCP server compatibility is designed into the abstract interface.
5. **No Tool-Specific Conditionals**: The registry will look up tools by 	ool_type. Services requesting tool execution will query the registry, not instantiate tools directly.
6. **Strict Separation of Concerns**: 	emplate_store must never know about the Tool Registry or MCP Runtime. All runtime operations are driven by 
exora_studio.

## Consequences
- **Positive**: Complete abstraction of system-level operations. Easy extensibility for future cloud tools (AWS, GCP, Kubernetes) without modifying core orchestrator logic.
- **Positive**: Every operation becomes observable, producing timeline events and standardized ToolResult objects.
- **Negative**: Increased complexity for simple operations (e.g., os.makedirs now requires a FilesystemTool invocation).

