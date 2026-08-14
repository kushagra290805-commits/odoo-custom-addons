# ADR 0046: Documentation & 3D Intelligence Provider Foundation

## Status
Accepted

## Context
As Nexora Studio evolves its Universal Capability Execution Layer (UCEL) to support dynamic 3D website generation, the AI Generation Engine requires real-time access to authoritative, version-accurate documentation for 3D and animation libraries. Relying solely on the foundational LLM weights leads to hallucinations and outdated API usage.

To solve this, we need to integrate a suite of specialized Documentation MCP Providers for:
- Three.js
- React Three Fiber
- Drei
- GSAP
- MDN (Web APIs & CSS)

These providers must integrate flawlessly into the existing architecture defined by ADR-0044 (Canonical Provider Contract) and ADR-0045 (Strict Architecture Hardening), utilizing the existing `mcp_registry.json` schema, `RegistryBootstrapService`, and MCP transport adapters.

## Decision
We will expand the Provider Platform by registering the following MCP providers:
1. **Three.js Documentation MCP** (`mcp.threejs_docs`)
2. **React Three Fiber Documentation MCP** (`mcp.r3f_docs`)
3. **Drei Documentation MCP** (`mcp.drei_docs`)
4. **GSAP Documentation MCP** (`mcp.gsap_docs`)
5. **MDN Documentation MCP** (`mcp.mdn_docs`)

### Architectural Invariants
1. **No Duplicate Infrastructure**: All providers will utilize the existing `RegistryBootstrapService` and `mcp_registry.json`. No new databases, synchronization scripts, or ad-hoc orchestration layers will be created.
2. **Canonical Contract**: All executions will use the `ProviderExecutionRequest` and return a `ProviderExecutionResult`. The `ProviderCompatibilityAdapter` will handle these transparently if they are MCP servers.
3. **Schema Evolution**: The `mcp_registry.json` schema will be extended to include new operational metadata:
   - `category`
   - `tags`
   - `version`
   - `startup_strategy`
   - `authentication`
   - `health_check`

## Consequences
- **Positive**: The generation engine gains precise, real-time access to specialized 3D and animation knowledge. 
- **Positive**: Zero architectural drift. The UCEL remains the single point of orchestration.
- **Negative**: Increased initialization time during the first invocation of these documentation tools as the MCP servers spin up (mitigated by asynchronous/lazy loading).
