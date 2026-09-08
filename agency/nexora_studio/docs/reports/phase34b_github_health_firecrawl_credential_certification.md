# Phase 34B: GitHub Health Diagnostic & Firecrawl Credential Certification

## 1. GitHub Health Diagnostic

### 1.1 Origin of the Failure
The persistent error `"Connector instance could not be created or is not running"` displayed in the GitHub MCP UI originated from a combination of a **race condition** at startup and a **stale error state** in the database.

During server startup (e.g., when the background Odoo process restarts), the `ConnectorPlatformBootstrap` runs synchronously and loads connectors from the database via `sync_from_odoo()`. At this stage, connectors are instantiated as unconfigured skeletons (`configuration=None`). Full configuration—including credential resolution—is deferred to the asynchronous `McpStartupReconciliationThread`.

If the Odoo health check cron (`_cron_check_health`) triggers in a different thread *before* the async reconciliation thread finishes configuring the `github_mcp` connector, the `ConnectorDispatcher.probe_health()` method attempts to initialize the unconfigured connector (passing `{}` for configuration). The `McpConnectorFactory` creates an `McpTransport` with `command=""`, which immediately crashes. This immediate failure causes the `probe_health` method to return `None`, setting the status to `failed` and logging the error message.

### 1.2 Proof of Ephemeral Race Condition vs Architectural Defect
Testing confirmed that this is an ephemeral timing issue rather than a core architectural defect in the Universal Connector Platform:
1. When manually triggering the health cron *immediately* upon script execution (without waiting), the health probe failed with the exact error message.
2. When introducing a `time.sleep(5)` delay before triggering the health cron—allowing the `McpStartupReconciliationThread` to complete the `McpOnboardingService.register_connector` flow—the health probe returned **healthy** and fully operational.
3. The only reason the error message persisted in the UI for hours (despite subsequent successful background cron runs) was a generic defect in `nexora_connector._cron_check_health`: it updated the `error_message` field on failure but **never cleared it** upon recovery.

### 1.3 Minimal Fix Applied
Since the architectural behavior of deferring configuration to an async thread is intentional (to prevent blocking startup), no massive architectural refactor was needed. The only required fix was addressing the stale error message persistence.

**Change made in `nexora_connector.py`:**
Modified `_cron_check_health` to explicitly clear the `error_message` when a connector recovers from a `failed` state.
```python
if health_result.status.value == 'failed':
    update_vals['error_message'] = getattr(health_result, 'error_detail', '')
else:
    update_vals['error_message'] = False
```
This minimal, safe fix ensures that the UI accurately reflects current health checks instead of permanently displaying the first ephemeral failure.

---

## 2. Firecrawl Credential Migration

### 2.1 Credential Resolution
The goal was to align the Firecrawl credentials with the canonical architecture (`FIRECRAWL_API_KEY` -> `nexora.mcp_credential` -> `OdooCredentialResolver`).

An audit of the existing Firecrawl records revealed:
- The canonical XML-owned connector record (`database ID 63`).
- A manually duplicated record (`database ID 40`) created via the UI, which contained the actual working API key but under a typoed key name (`FIRECRAWL__API_KEY`).

### 2.2 Migration Process
To correctly bind the credentials without exposing the actual secret:
1. A Python script (`test_firecrawl_cred.py`) was used via the `OdooSecretsProvider` to fetch the real API key from the typoed credential (`FIRECRAWL__API_KEY`).
2. The exact secret value was migrated directly to the correct canonical key (`FIRECRAWL_API_KEY`) attached to the canonical XML-backed Firecrawl record (ID 63).
3. The `is_set` flag was updated to `True` for `FIRECRAWL_API_KEY`.
4. The manual, typoed credential record (`FIRECRAWL__API_KEY`) was deleted from both the database and the secrets provider to prevent conflicts.

**Result:** The actual secret is successfully bound to the canonical connector.
**Verification:** `credential = PRESENT`.

---

**Status:** Phase 34B Certification Complete. No architectural changes were necessary; the Connector Platform remains stable and robust.
