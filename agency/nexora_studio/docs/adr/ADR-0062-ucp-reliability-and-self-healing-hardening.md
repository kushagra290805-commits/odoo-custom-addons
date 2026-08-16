# ADR-0062: UCP Reliability and Self-Healing Hardening

## 1. Context and Problem Statement
Phase 35.3 identified multiple reliability defects in the Universal Connector Platform (UCP):
1. **Concurrency Races:** Duplicate connector records could be created.
2. **Lazy Readiness:** Connectors could be marked `RUNNING` before credentials, transport, and handshakes were validated.
3. **Ghost Connectors:** A transport could die, but UCP would continue advertising the capability and leaving the connector in `RUNNING`/`HEALTHY` state until the cron job eventually caught it (or failed requests accumulated).
4. **No Self-Healing:** Once a transport died or failed, there was no autonomous backoff-based recovery loop to restore it.
5. **Capability Stale Indexing:** Capabilities from dead transports remained in the index.

## 2. Decision: Ownership Boundaries & UCP vs GoSOM
UCP is strictly responsible for managing the low-level lifecycle, process ownership, configuration mapping, health, and protocol handshake of connectors. GoSOM is responsible for higher-level autonomous selection, planning, and goal resolution.
**Therefore, self-healing of low-level transports MUST belong to UCP.**
GoSOM should NEVER recreate a subprocess, parse credentials, or interact with SSE layers. It routes to capabilities; UCP ensures those capabilities point to healthy transports.

## 3. Decision: Process-Local Recovery (No Parallel Orchestration)
Odoo is deployed across multiple worker processes. The `ConnectorRuntime` is instantiated **once per process**. Therefore, MCP transport subprocesses are entirely local to each Python process.
- **Recovery will be orchestrated entirely within `ConnectorRuntime` process-locally.**
- **No separate global `ConnectorRecoveryManager` will be created.**
- A lightweight, single-flight in-memory loop (`_recovery_locks`, `threading.Timer`) inside `ConnectorRuntime` will handle the backoff retries.

## 4. Decision: Registration vs. Initialization
We must prevent duplicating the "re-register to recover" anti-pattern.
- `McpOnboardingService` will remain the owner of Odoo-layer configuration parsing and DB pipeline registration.
- `ConnectorDispatcher` will expose a canonical `initialize_and_verify(connector)` primitive.
- Both Odoo Registration and Runtime Recovery will call this primitive to physically boot the transport, perform the handshake, and verify readiness.

## 5. Decision: Persistence Uniqueness
- We use Odoo's native `_sql_constraints` (`nexora_connector_id_uniq`).
- It maps directly to PostgreSQL's `UNIQUE` constraint.
- We verified that 10 concurrent requests yield exactly 1 record and 9 `IntegrityError` exceptions.

## 6. Decision: Readiness Semantics
- `RUNNING` implies strictly that the connector is **operationally ready**.
- Action Enable will synchronously invoke the canonical initialization primitive. If it fails, `state = 'failed'` is persisted, and the connector is NOT placed in the capability index.

## 7. Decision: Capability Invalidation
- When a failure is detected by the Dispatcher or Health Monitor, `ConnectorRuntime.handle_transport_failure()` is invoked.
- It immediately removes all capabilities for that `connector_id` from the in-memory `CapabilityIndex`.
- It shuts down the dead transport to prevent resource leaks.
- Only upon successful recovery are capabilities re-added.

## 8. Explicit Non-Goals
- We will NOT create a parallel "Recovering" database state; recovery is an internal runtime transition.
- We will NOT implement cross-process global locks for recovery, as transports are local.
- We will NOT retry deterministic configuration errors indefinitely.
