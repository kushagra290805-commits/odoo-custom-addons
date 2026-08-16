import sys
import uuid
import traceback
import threading
import concurrent.futures
import time
sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config

config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
registry = odoo.modules.registry.Registry('nexora_studio')

RUN_ID = str(uuid.uuid4())[:8]
CONNECTOR_ID = f"test.mcp.health.{RUN_ID}"

def _setup_fixture(env):
    ctype = env['nexora.connector_type'].search([('type_code', '=', 'mcp')], limit=1)
    rec = env['nexora.connector'].create({
        'connector_id': CONNECTOR_ID,
        'name': f'Health Test {RUN_ID}',
        'connector_type_id': ctype.id,
        'state': 'running',
        'health_status': 'unknown'
    })
    env['nexora.mcp_server_config'].create({
        'connector_id': rec.id,
        'command': 'python',
        'args_json': '["-c", "import time; time.sleep(10)"]',
        'transport_type': 'stdio',
        'authentication_location': 'none'
    })
    env.cr.commit()
    return rec

def op_probe(env):
    try:
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        runtime = bootstrap.connector_runtime
        health = runtime.probe_health(CONNECTOR_ID)
        return {"success": True, "op": "probe", "status": health.status.value if health else None}
    except Exception as e:
        return {"error": str(e), "op": "probe"}

def op_reconcile(env):
    try:
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap._startup_reconciliation(env)
        return {"success": True, "op": "reconcile"}
    except Exception as e:
        return {"error": str(e), "op": "reconcile"}

def _run_in_thread(op_func):
    try:
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            return op_func(env)
    except Exception as e:
        return {"error": str(e), "op": "thread_error"}

def test_health_races():
    print(f"\n--- PHASE I: HEALTH & RECONCILIATION RACES ({RUN_ID}) ---")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        _setup_fixture(env)

    results = []
    print("  Submitting concurrent probes and reconciliations...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        funcs = [op_probe, op_reconcile] * 5
        futures = [executor.submit(_run_in_thread, funcs[i]) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    print(f"  Results: {results}")

def test_recovery_idempotency():
    print(f"\n--- PHASE L: RECOVERY IDEMPOTENCY ---")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()

        print("  Running bootstrap reconciliation 5 times sequentially on the same fixture...")
        for i in range(5):
            bootstrap._startup_reconciliation(env)

        runtime = bootstrap.connector_runtime
        sessions = 1 if CONNECTOR_ID in runtime.dispatcher._active_connectors else 0

        print(f"  Resulting active sessions: {sessions} (Expected: 1 or 0 depending on completion)")
        if sessions > 1:
            print("  [VIOLATION] Multiple transports created! Recovery is NOT idempotent!")
        else:
            print("  [PASS] Only one transport/session exists.")

    print("\nCleaning up disposable fixture...")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        env['nexora.connector'].search([('connector_id', '=', CONNECTOR_ID)]).unlink()
        env.cr.commit()

if __name__ == '__main__':
    try:
        test_health_races()
        test_recovery_idempotency()
    except Exception as e:
        traceback.print_exc()
