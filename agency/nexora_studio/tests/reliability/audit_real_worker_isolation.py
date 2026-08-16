import os
import sys
import time
import multiprocessing

def worker_a(ready_event, test_done_event):
    sys.path.append('D:\\ODOO\\community\\odoo')
    import odoo
    from odoo.tools import config
    config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
    registry = odoo.modules.registry.Registry('nexora_studio')

    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        ConnectorPlatformBootstrap._run_async_reconciliation = lambda self, db_name: None

        bootstrap = ConnectorPlatformBootstrap()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        # Ensure connector is running and active
        conn = runtime.registry.get('github_mcp')
        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorLifecycleState

        # We need an active transport
        def on_transition(conn, from_state, to_state):
            print(f"[Worker A] TRANSITION: {conn.connector_id} {from_state.value} -> {to_state.value}")
        runtime.lifecycle_manager.register_transition_hook(on_transition)

        from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
        ctx = ExecutionContext(connector_id='github_mcp', request_id='worker_a', capability_namespace='init')
        runtime.dispatcher.initialize_and_verify(conn, ctx)
        runtime.capability_index.add('tools.list', 'github_mcp')
        print(f"[Worker A] Initial caps: {runtime.capability_index.get_all('tools.list')}")
        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorLifecycleState
        conn.lifecycle_state = ConnectorLifecycleState.RUNNING

        # Signal ready
        ready_event.set()

        # Wait a bit for Worker B to also get ready
        time.sleep(2.0)

        print("[Worker A] Simulating fatal transport crash...")
        # Crash transport
        sdk = runtime.dispatcher._active_connectors.get('github_mcp')
        if sdk and sdk.transport:
            sdk.transport.disconnect()

        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionRequest, ConnectorRuntimeContext
        exec_ctx = ConnectorRuntimeContext(connector_id='github_mcp', session_id='worker_a')
        req = ConnectorExecutionRequest(capability_namespace='tools.list', context=exec_ctx)

        print(f"[Worker A] Pre-dispatch state: is_running={conn.is_running}, caps={runtime.capability_index.get_all('tools.list')}")

        try:
            res = runtime.dispatch(req)
            print(f"[Worker A] Dispatch result: {res.status.value}, error: {res.error}")
        except Exception as e:
            print(f"[Worker A] Dispatch exception: {e}")

        print("[Worker A] Triggered recovery. Waiting 5s...")
        time.sleep(5.0)

        # Assert recovery
        new_sdk = runtime.dispatcher._active_connectors.get('github_mcp')
        if new_sdk and new_sdk.transport:
            print("[Worker A] SUCCESS: Transport autonomously recovered.")
        else:
            print("[Worker A] FAIL: Transport did not recover.")

        # Keep alive until test done
        test_done_event.wait()
        print("[Worker A] Exiting.")

def worker_b(ready_event, test_done_event):
    sys.path.append('D:\\ODOO\\community\\odoo')
    import odoo
    from odoo.tools import config
    config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
    registry = odoo.modules.registry.Registry('nexora_studio')

    # Wait for A to be ready
    ready_event.wait()

    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        ConnectorPlatformBootstrap._run_async_reconciliation = lambda self, db_name: None

        bootstrap = ConnectorPlatformBootstrap()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        conn = runtime.registry.get('github_mcp')
        def on_transition_b(conn, from_state, to_state):
            print(f"[Worker B] TRANSITION: {conn.connector_id} {from_state.value} -> {to_state.value}")
        runtime.lifecycle_manager.register_transition_hook(on_transition_b)

        from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
        ctx = ExecutionContext(connector_id='github_mcp', request_id='worker_b', capability_namespace='init')
        runtime.dispatcher.initialize_and_verify(conn, ctx)
        runtime.capability_index.add('tools.list', 'github_mcp')
        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorLifecycleState
        conn.lifecycle_state = ConnectorLifecycleState.RUNNING

        print("[Worker B] Initialized and operational.")

        # Wait 5 seconds while Worker A crashes and recovers
        time.sleep(5.0)

        # Assert B is unaffected
        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionRequest
        req = ConnectorExecutionRequest(capability_namespace='tools.list', context=ctx)
        res = runtime.dispatch(req)

        if res.status.value == "success":
            print("[Worker B] SUCCESS: Still fully operational and unaffected by Worker A.")
        else:
            print(f"[Worker B] FAIL: Worker B was affected! {res.error}")

        # Check DB State
        rec = env['nexora.connector'].search([('connector_id', '=', 'github_mcp')])
        if rec.state == 'failed':
            print("[Worker B] FAIL: Database state was mutated to FAILED.")
        else:
            print(f"[Worker B] SUCCESS: Database state remains {rec.state}.")

        test_done_event.set()
        print("[Worker B] Exiting.")

if __name__ == '__main__':
    print("==========================================================")
    print("PHASE 35.5 - ACTUAL MULTI-PROCESS WORKER ISOLATION")
    print("==========================================================")

    # Pre-flight setup: ensure DB is running
    sys.path.append('D:\\ODOO\\community\\odoo')
    import odoo
    from odoo.tools import config
    config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
    registry = odoo.modules.registry.Registry('nexora_studio')
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.connector'].search([('connector_id', '=', 'github_mcp')], limit=1)
        if rec:
            rec.state = 'running'
        env.cr.commit()

    ready_event = multiprocessing.Event()
    test_done_event = multiprocessing.Event()

    p_a = multiprocessing.Process(target=worker_a, args=(ready_event, test_done_event))
    p_b = multiprocessing.Process(target=worker_b, args=(ready_event, test_done_event))

    p_a.start()
    p_b.start()

    p_b.join()
    p_a.join()

    print("==========================================================")
    print("TEST COMPLETE")
    print("==========================================================")
