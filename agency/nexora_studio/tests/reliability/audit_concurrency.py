import sys
import uuid
import traceback
import threading
import concurrent.futures
sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config
import time

config.parse_config(['-c', 'configs\\dev.conf'])
registry = odoo.modules.registry.Registry('nexora_studio')

RUN_ID = str(uuid.uuid4())[:8]
CONNECTOR_ID = f"test.mcp.concurrency.{RUN_ID}"

def _run_in_thread(operation_name, worker_func):
    """Executes a function in its own Odoo cursor and Environment."""
    try:
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            return worker_func(env)
    except Exception as e:
        return {"error": str(e), "op": operation_name}

def op_register(env):
    try:
        env['nexora.connector'].create({
            'connector_id': CONNECTOR_ID,
            'name': 'Concurrency Test Connector',
            'connector_type_id': env['nexora.connector_type'].search([('type_code', '=', 'mcp')], limit=1).id,
            'state': 'registered'
        })
        env.cr.commit()
        return {"success": True, "op": "register"}
    except Exception as e:
        env.cr.rollback()
        return {"error": str(e), "op": "register"}

def op_enable(env):
    try:
        rec = env['nexora.connector'].search([('connector_id', '=', CONNECTOR_ID)], limit=1)
        if rec:
            rec.action_enable()
            env.cr.commit()
            return {"success": True, "op": "enable"}
        return {"error": "not_found", "op": "enable"}
    except Exception as e:
        env.cr.rollback()
        return {"error": str(e), "op": "enable"}

def op_disable(env):
    try:
        rec = env['nexora.connector'].search([('connector_id', '=', CONNECTOR_ID)], limit=1)
        if rec:
            rec.action_disable()
            env.cr.commit()
            return {"success": True, "op": "disable"}
        return {"error": "not_found", "op": "disable"}
    except Exception as e:
        env.cr.rollback()
        return {"error": str(e), "op": "disable"}

def op_health(env):
    try:
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        health = runtime.probe_health(CONNECTOR_ID)
        return {"success": True, "op": "health", "health_status": health.status.value if health else "unknown"}
    except Exception as e:
        return {"error": str(e), "op": "health"}

def run_concurrency_audit():
    print(f"================ PHASE E: CONCURRENCY AUDIT (RUN ID: {RUN_ID}) ================")
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        # Phase 1: Concurrent Registration
        print("Submitting 10 concurrent registration requests...")
        futures = [executor.submit(_run_in_thread, f"reg_{i}", op_register) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

        # Verify db state
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            records = env['nexora.connector'].search([('connector_id', '=', CONNECTOR_ID)])
            print(f"Total DB records created: {len(records)} (Expected: 1)")
            if len(records) > 1:
                print("  [VIOLATION] IntegrityError/Duplicate Registration occurred!")
            elif len(records) == 0:
                print("  [ERROR] No records created.")

        # Phase 2: Concurrent Enable/Disable/Health
        print("\nSubmitting 15 concurrent enable/disable/health requests...")
        funcs = [op_enable, op_disable, op_health] * 5
        futures = [executor.submit(_run_in_thread, f"mix_{i}", funcs[i]) for i in range(15)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

        print("\nResults Summary:")
        successes = sum(1 for r in results if r.get('success'))
        errors = [r for r in results if r.get('error')]
        print(f"Total Operations: {len(results)}")
        print(f"Successes: {successes}")
        print(f"Errors: {len(errors)}")

        # We expect many IntegrityErrors for the concurrent registration.
        # We want to ensure NO duplicate records exist and no deadlocks crashed the system.

        print("\nSample Errors encountered (expected race exceptions):")
        for e in errors[:5]:
            print(f"  Op {e['op']}: {e['error'][:80]}")

    # Teardown
    print("\nCleaning up disposable fixture...")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        env['nexora.connector'].search([('connector_id', '=', CONNECTOR_ID)]).unlink()
        env.cr.commit()
    print("Cleanup complete.")

if __name__ == '__main__':
    run_concurrency_audit()
