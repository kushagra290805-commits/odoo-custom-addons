# ADR-0055: Lifecycle Synchronization & State Reconciliation

**Status:** Accepted
**Date:** 2026-08-11

## Context

During Phase 29.6 provider testing, we discovered a lifecycle-state integrity bug where a connector remained persistently marked as `RUNNING` in the PostgreSQL database, despite the runtime session failing to start due to missing credentials. The UI misleadingly presented the connector as running and healthy.

This occurred due to three main factors:
1. **Unsafe DB Activation:** The UI operator action (`action_enable`) blindly updated the `state` field to `running` immediately, relying on a side-effect ORM `write` hook to trigger runtime initialization. If the initialization failed, the database state was sometimes left in `running`.
2. **Missing Deletion Hook:** Deleting a required credential (`nexora.mcp_credential.unlink()`) did not notify the runtime synchronizer, leaving the connector running but without valid credentials.
3. **Absence of Startup Reconciliation:** When the Odoo server restarted, it loaded the stale `RUNNING` state from the database without verifying if the runtime session could actually be successfully reconstructed and initialized. 

## Decision

To resolve the divergence between database state, runtime state, and health state, we strictly enforce the following invariants:

1. **Strict Definition of RUNNING:** A persisted lifecycle state must NOT claim `RUNNING` unless the connector runtime has successfully reconstructed and verified the connector.
   `RUNNING` specifically requires:
   - Valid persisted configuration
   - Required credentials resolved and decrypted
   - Runtime session successfully registered
   - MCP initialization/handshake successful
   - Required health validation successful

2. **Explicit Action Semantics:** `action_enable()` must mean "request activation", NOT "set database state to running." It must explicitly invoke the runtime activation pipeline. Only after the pipeline succeeds will the database state be persisted as `RUNNING`. If activation fails, the state transitions to `FAILED`.

3. **Deterministic Startup Reconciliation:** On startup, the persistence layer will load all connectors. Any connector persisting a state of `RUNNING` or `HEALTHY` must undergo a complete reconciliation process (re-initialization and handshake verification). If verification fails during startup, the connector state is immediately updated in the database to `FAILED`.

4. **Credential Invalidation Cascade:** Deleting or rotating a credential belonging to an active connector must unconditionally evict the runtime session and trigger state reconciliation, causing the connector to transition to `FAILED` if it can no longer operate.

## Consequences

- **Positive:** Database state (`nexora.connector.state`), runtime state (registration), and health state converge on the same truth. 
- **Positive:** Operators will no longer see a falsely `RUNNING` connector that is actually broken or missing credentials.
- **Negative:** Startup overhead slightly increases since previously running MCP connectors must undergo a real handshake to restore their `RUNNING` state. However, failure is isolated, and one broken connector will not prevent others from starting.
