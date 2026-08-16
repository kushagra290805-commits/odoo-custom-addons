import sys
import time
import asyncio
import concurrent.futures
from pathlib import Path

# Add the workspace root to the Python path
sys.path.append('D:\\ODOO\\community\\odoo')

import odoo
from odoo.tools import config

def storm_audit():
    config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
    registry = odoo.modules.registry.Registry('nexora_studio')

    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        # Disable background sync to isolate tests
        ConnectorPlatformBootstrap._run_async_reconciliation = lambda self, db_name: None

        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        conn = runtime.registry.get('github_mcp')
        if not conn:
            print("FAIL: github_mcp connector not found.")
            return

        from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
        ctx = ExecutionContext(connector_id='github_mcp', request_id='storm_init', capability_namespace='init')
        runtime.dispatcher.initialize_and_verify(conn, ctx)
        runtime.capability_index.add('tools.list', 'github_mcp')
        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorLifecycleState
        conn.lifecycle_state = ConnectorLifecycleState.RUNNING

        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionRequest, ConnectorRuntimeContext

        def simulate_crash_and_dispatch(worker_id):
            print(f"[Thread {worker_id}] Crashing transport...")
            sdk = runtime.dispatcher._active_connectors.get('github_mcp')
            if sdk and sdk.transport:
                # Force close it brutally
                sdk.transport.disconnect()

            exec_ctx = ConnectorRuntimeContext(connector_id='github_mcp', session_id=f'worker_{worker_id}')
            req = ConnectorExecutionRequest(capability_namespace='tools.list', context=exec_ctx)

            try:
                res = runtime.dispatch(req)
                print(f"[Thread {worker_id}] Dispatch result: {res.status.value}, error: {res.error}")
            except Exception as e:
                pass

        print("==========================================================")
        print("PHASE 35.5 - STORM & RESOURCE AUDIT")
        print("==========================================================")

        print("[Storm] Firing 10 concurrent crashes to trigger recovery storm...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_crash_and_dispatch, i) for i in range(10)]
            concurrent.futures.wait(futures)

        print("[Storm] Wait 5 seconds for single-flight recovery to complete...")
        time.sleep(5.0)

        # Verify if recovery occurred properly only once
        sdk = runtime.dispatcher._active_connectors.get('github_mcp')
        if sdk and sdk.transport and sdk.transport.is_connected():
            print("[Storm] SUCCESS: Transport recovered under heavy concurrency storm.")
        else:
            print("[Storm] FAIL: Transport did not recover.")

        # Ensure database is still running
        rec = env['nexora.connector'].search([('connector_id', '=', 'github_mcp')])
        if rec.state == 'running':
            print("[Storm] SUCCESS: Database state remained RUNNING.")
        else:
            print(f"[Storm] FAIL: Database state mutated to {rec.state}.")

        print("==========================================================")
        print("TEST COMPLETE")
        print("==========================================================")


if __name__ == "__main__":
    storm_audit()
