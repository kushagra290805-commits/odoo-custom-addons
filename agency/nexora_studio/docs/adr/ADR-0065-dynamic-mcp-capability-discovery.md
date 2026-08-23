# ADR 0065: Dynamic MCP Capability Discovery

## Status
Accepted

## Context
In Phase 39, we established the core Connector Platform Architecture (UCP) with static capabilities declared in the `ConnectorManifest`. However, MCP servers often provide dynamic capabilities (tools, resources, prompts) that can change over time. 

Previously, `McpOnboardingService` and `McpCapabilityDiscoveryService` could discover these tools and persist them to `nexora.mcp_discovered_tool`, but the generation platform (UCEL) had no way to automatically discover or route execution to these dynamic tools. This resulted in developers having to write manual Python wrapper capabilities for every individual MCP tool they wanted to expose.

Furthermore, we identified several bugs related to connector lifecycle management and isolated test execution that created inconsistencies in the runtime state.

## Decision
We decided to evolve the existing architecture to fully support dynamic MCP capability discovery and execution without requiring parallel capability registries or connector-specific Python code.

1. **Connector Execution Target:** Introduce `ConnectorExecutionTarget` (`ExecutionTargetType.CONNECTOR`) as a native UCEL execution target. This acts as the canonical bridge between the Universal Capability Execution Layer (UCEL) and the Universal Connector Platform (UCP) ConnectorRuntime.
2. **Capability Repository Extension:** Extend `CapabilityRepository` to dynamically query and serve capabilities directly from `nexora.mcp_discovered_tool`. Dynamic capabilities are assigned the namespace format `{connector_id}.{tool_name}`.
3. **Health-Aware Capability Filtering:** `CapabilityRepository` must check the associated connector's `health_status` and `state`. If a connector is not `RUNNING` or `HEALTHY`, its dynamic tools are completely hidden from UCEL discovery.
4. **Namespace Translation:** `ConnectorExecutionTarget` intercepts requests for `{connector_id}.{tool_name}` and rewrites them into standard `tools.call` requests targeted at the specific connector ID, mapping the arguments transparently.
5. **Lifecycle State Integrity:**
    - The `McpConnectionTester` bug was fixed to use the global runtime for `RUNNING` connectors instead of creating conflicting ephemeral runtimes.
    - A dual capability index rebuild bug in `McpOnboardingService` was resolved by removing the redundant manual rebuild call and relying on `ConnectorRuntime`'s health transition triggers.
    - A max recovery attempt limit (3 attempts) was added to `ConnectorRuntime`'s `_attempt_recovery`, transitioning connectors to `FAILED` and persisting the state to the DB.

## Consequences
- **Positive:** Adding a new MCP server automatically exposes all its tools to the generation platform without any custom Python code.
- **Positive:** UCEL remains agnostic of MCP specifics, treating dynamic tools just like any other execution target.
- **Positive:** System stability and runtime predictability are improved through better lifecycle state synchronization and health-aware capability filtering.
- **Negative:** UCEL will issue more database queries during capability resolution to discover dynamic tools, although this is mitigated by the existing caching mechanism.

## References
- ADR-0050: Universal Connector Platform Foundation
- ADR-0051: MCP Onboarding Platform
