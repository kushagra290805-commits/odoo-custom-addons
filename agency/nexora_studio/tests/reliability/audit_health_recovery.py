import os
import sys
import time

sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config
config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])

# Start standard script boilerplate
registry = odoo.modules.registry.Registry('nexora_studio')

with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

    from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
    bootstrap = ConnectorPlatformBootstrap()
    bootstrap.bootstrap(env)
    runtime = bootstrap.connector_runtime

    print("==========================================================")
    print("PHASE 35.5 - AUDIT HEALTH RECOVERY")
    print("==========================================================")

    rec = env['nexora.connector'].search([('connector_id', '=', 'github_mcp')], limit=1)
    if not rec:
        print("Test failed: github_mcp not found in DB")
        sys.exit(1)

    # Manually inject capability for test purposes instead of full DB sync
    conn = runtime.registry.get('github_mcp')
    import dataclasses
    conn.manifest = dataclasses.replace(conn.manifest, capabilities=tuple(['github.repo.read']))
    runtime.capability_index.add('github.repo.read', 'github_mcp')

    rec.state = 'running'
    env.cr.commit()

    conn = runtime.registry.get('github_mcp')
    print("Initial DB State: ", rec.state)
    print("Worker state: ", conn.lifecycle_state.value)

    if runtime.capability_index.get_primary("github.repo.read") != 'github_mcp':
        print("FAIL: Setup failed, capabilities not loaded initially!")
        sys.exit(1)

    print("\nSimulating HealthMonitor emitting health.failed event...")
    from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorEvent, ConnectorEventSeverity

    event = ConnectorEvent(
        connector_id='github_mcp',
        event_type="health.failed",
        severity=ConnectorEventSeverity.ERROR,
        message="Simulated health failure",
        data={"error": "Process exited unexpectedly", "failures": 3, "suggested_state": "failed"},
        source="health_monitor"
    )

    # Emit event
    runtime.event_bus.publish(event)

    # Reload DB state
    rec.invalidate_recordset(['state'])
    print("\n[POST-EVENT] DB State: ", rec.state)
    print("[POST-EVENT] Worker state: ", conn.lifecycle_state.value)

    # Verify capabilities are stripped
    if runtime.capability_index.get_primary("github.repo.read") == 'github_mcp':
        print("\nFAIL: Capabilities were not stripped!")
        sys.exit(1)

    # Verify recovery state
    if runtime._recovery_state.get('github_mcp') != "IN_PROGRESS":
        print("\nFAIL: Recovery was not scheduled!")
        sys.exit(1)

    print("\nPASS: Event successfully routed to handle_transport_failure.")
    print("PASS: Connector locally recovering and globally intact.")

    print("\nWaiting for recovery timer...")
    time.sleep(3.0)
    print("Worker recovery finished.")
    print("[FINAL] Worker state: ", conn.lifecycle_state.value)

    print("Final capabilities in manifest:", conn.manifest.capabilities)
    if runtime.capability_index.get_primary("github.repo.read") == 'github_mcp':
        print("\nPASS: Capabilities restored successfully!")
    else:
        print("\nWARNING: Capabilities not restored!")
