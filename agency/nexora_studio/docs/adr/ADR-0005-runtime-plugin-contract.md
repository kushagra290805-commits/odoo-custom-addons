# ADR-0005
## Title
Runtime Plugin Contract

## Status
Accepted

## Date
2026-07-11

## Context
Following the implementation of the Metadata-Driven Registry (ADR-0002) and the Runtime Resource Architecture (ADR-0004), Nexora Studio is moving towards integrating multiple external runtime environments: Git, Preview Servers, MCP contexts, AI environments, and Docker containers. 

To ensure the `RuntimeService` remains decoupled and adheres strictly to the Open/Closed Principle (as achieved in Phase 5B), we must establish a formal contract that every runtime implementation adheres to. This prevents the orchestrator from containing hardcoded implementation logic.

## Decision
We formally define the **Runtime Plugin Contract**. Any future runtime (e.g., Git Runtime, Preview Server) must adhere to this standard. The `RuntimeService` will strictly interact with implementations exclusively through this contract.

### 1. Registration Mechanism
Plugins must declare their existence to the `RuntimeService` without modifying the core registry logic.
- **Mapping**: The plugin must be added to the registry mapping linking a `runtime_type` string (e.g., `'git'`) to the Odoo service model name (e.g., `'nexora.git_service'`).
- **Database Representation**: Every plugin corresponds to a specific `runtime_type` value in the `nexora.runtime` model's selection field.

### 2. Lifecycle Methods
Every plugin service must expose the following interface methods. The `RuntimeService` will dynamically dispatch to these via `getattr(service, action)(runtime)`.
- `start_runtime_instance(self, runtime)`: Provisions resources, creates local contexts, or spawns background processes. Must update `runtime.endpoint`, `runtime.port`, or `runtime.process_id` if applicable.
- `stop_runtime_instance(self, runtime)`: Gracefully terminates processes, closes network ports, or releases locks. Must not destroy persistent data (like the physical workspace).
- `restart_runtime_instance(self, runtime)`: Sequentially executes stop and start logic.
- `refresh_runtime(self, runtime)`: Performs a lightweight status check to see if the runtime is still active and functioning.
- `check_health(self, runtime)`: A deeper diagnostic check that updates `runtime.health` (`healthy`, `warning`, `critical`, `unknown`).

### 3. Dependency Declaration
Runtimes do not start in a vacuum; they depend on each other (e.g., a Git repository requires a physical Workspace).
- **Orchestrator Resolution**: The `RuntimeService` manages the startup order natively. Plugins do not call other plugins to ensure they are started. 
- **Implicit Dependency**: The plugin contract dictates that if a plugin expects a prerequisite (like a workspace path), it retrieves that data from the sibling `nexora.runtime` records belonging to the same `BuilderSession`, assuming the orchestrator has already started them.

### 4. Configuration Requirements
- Plugins must not store static configuration in the runtime record.
- If a plugin requires project-specific configuration (e.g., "target deployment URL" or "git remote URL"), it must query the immutable `nexora.builder_configuration` associated with the `BuilderSession`.

### 5. Capability Advertisement
- A plugin's capabilities are advertised via its presence in the Runtime Registry. 
- If a plugin has advanced features, they should be persisted dynamically in the `metadata_json` field on the `nexora.runtime` record, allowing the frontend IDE (Antigravity) to read and utilize them without requiring schema changes.

### 6. Failure and Recovery Behavior
- **Fail-Fast**: If `start_runtime_instance` encounters an unrecoverable error, it must raise a standard Odoo `ValidationError`.
- **State bubbling**: The `RuntimeService` catches this error, transitions the `runtime.status` to `error`, and `health` to `critical`, halting the startup sequence for any dependent runtimes.
- **No Silent Failures**: Background crashes must be detectable via `check_health()`. If a daemon process dies, `check_health` must update the `nexora.runtime` state to `error` so the orchestrator can flag it in the UI.

## Consequences

**Positive:**
- Complete decoupling of specific integrations (Git, Preview) from the core orchestrator.
- New runtimes can be introduced simply by extending the Odoo selection field and creating a conforming service.
- Unified state management and error handling across all diverse systems.

**Negative:**
- Requires strict discipline; developers cannot take shortcuts by having the Git service directly invoke the Workspace service. All communication must flow through the shared database state or registry.
