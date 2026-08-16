import os
import sys
import time

sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config
config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])

print("==========================================================")
print("PHASE 35.5 - ACTUAL HEALTH MONITOR RECOVERY")
print("==========================================================")

registry = odoo.modules.registry.Registry('nexora_studio')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
    bootstrap = ConnectorPlatformBootstrap()
    bootstrap.bootstrap(env)
    runtime = bootstrap.connector_runtime

    conn = runtime.registry.get('github_mcp')
    if not conn:
        print("FAIL: github_mcp not found in registry.")
        sys.exit(1)

    # Ensure it's running and initialized
    from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
    ctx = ExecutionContext(connector_id='github_mcp', request_id='init', capability_namespace='init')
    runtime.dispatcher.initialize_and_verify(conn, ctx)

    sdk = runtime.dispatcher._active_connectors.get('github_mcp')
    if not sdk or not sdk.transport:
        print("FAIL: Transport not initialized.")
        sys.exit(1)

    print("[T0] Transport operational.")

    # Intentionally break the transport without telling the runtime (simulate spontaneous failure)
    print("[T1] Breaking transport silently...")
    sdk.transport.disconnect()

    print("[T2] Simulating Cron health probes...")
    # The health monitor requires FAILED_AFTER_FAILURES (default 3) to trigger health.failed
    for i in range(1, 5):
        print(f"  Probe #{i}...")
        runtime.probe_health('github_mcp')

        # Check if recovery started
        if runtime._recovery_state.get('github_mcp') == "IN_PROGRESS":
            print("  [SUCCESS] Recovery state triggered!")
            break
        time.sleep(0.5)

    if runtime._recovery_state.get('github_mcp') != "IN_PROGRESS":
        print("FAIL: Health monitor did not trigger recovery.")
        sys.exit(1)

    print("[T3] Waiting 5 seconds for recovery to finish...")
    time.sleep(5.0)

    new_sdk = runtime.dispatcher._active_connectors.get('github_mcp')
    if new_sdk and new_sdk.transport and id(new_sdk.transport) != id(sdk.transport):
        print("PASS: Transport was recreated autonomously via true health monitor path!")
    else:
        print("FAIL: Transport was not recreated.")
        sys.exit(1)

print("==========================================================")
print("TEST COMPLETE")
print("==========================================================")
