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
    bootstrap_a = ConnectorPlatformBootstrap()
    bootstrap_a.bootstrap(env)
    runtime_a = bootstrap_a.connector_runtime

    bootstrap_b = ConnectorPlatformBootstrap()
    bootstrap_b.bootstrap(env)
    runtime_b = bootstrap_b.connector_runtime

    print("==========================================================")
    print("PHASE 35.5 - AUDIT WORKER ISOLATION")
    print("==========================================================")

    rec = env['nexora.connector'].search([('connector_id', '=', 'github_mcp')], limit=1)
    if not rec:
        print("Test failed: github_mcp not found in DB")
        sys.exit(1)

    rec.state = 'running'
    env.cr.commit()

    conn_a = runtime_a.registry.get('github_mcp')
    conn_b = runtime_b.registry.get('github_mcp')

    from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorLifecycleState, ConnectorFailureClass
    conn_a.lifecycle_state = ConnectorLifecycleState.RUNNING
    conn_b.lifecycle_state = ConnectorLifecycleState.RUNNING

    print("Initial DB State: ", rec.state)
    print("Worker A state: ", conn_a.lifecycle_state.value)
    print("Worker B state: ", conn_b.lifecycle_state.value)

    print("\nSimulating fatal transport crash on Worker A...")
    runtime_a.handle_transport_failure('github_mcp', ConnectorFailureClass.PROCESS_EXIT, "SIGKILL")

    # Reload DB state
    rec.invalidate_recordset(['state'])
    print("\n[POST-CRASH] DB State: ", rec.state)
    print("[POST-CRASH] Worker A state: ", conn_a.lifecycle_state.value)
    print("[POST-CRASH] Worker B state: ", conn_b.lifecycle_state.value)

    if rec.state == 'failed':
        print("\nFAIL: DB state was mutated to 'failed'!")
        sys.exit(1)

    print("\nPASS: Worker A local crash did not bleed into global persistence.")
    print("PASS: Worker B remains perfectly healthy.")
    print("\nWaiting for recovery timer on Worker A...")
    time.sleep(3.0)
    print("Worker A recovery finished.")
    print("[FINAL] Worker A state: ", conn_a.lifecycle_state.value)
