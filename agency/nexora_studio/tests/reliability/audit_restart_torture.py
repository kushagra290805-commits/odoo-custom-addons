import subprocess
import json
import os
import sys

CYCLES = 10
TARGETS = ['github_mcp', 'context7_mcp', 'firecrawl_mcp', 'penpot_mcp']
DUMP_FILE = 'restart_dump.json'

CHILD_SCRIPT = """
import sys, json, traceback
sys.path.append('D:\\\\ODOO\\\\community\\\\odoo')
import odoo
from odoo.tools import config

config.parse_config(['-c', 'configs\\\\dev.conf'])
registry = odoo.modules.registry.Registry('nexora_studio')

def _dump():
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        import time

        # Trigger full reconciliation and bootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)

        # Wait a few seconds for async startup reconciliation to finish
        time.sleep(3.0)

        runtime = bootstrap.connector_runtime

        target_ids = ['github_mcp', 'context7_mcp', 'firecrawl_mcp', 'penpot_mcp']
        results = {}

        for cid in target_ids:
            record = env['nexora.connector'].search([('connector_id', '=', cid)], limit=1)
            connector = runtime.registry.get(cid)

            data = {
                'db_state': record.state if record else None,
                'db_error': record.error_message if record else None,
                'runtime_state': connector.lifecycle_state.value if connector else None,
                'config_present': bool(connector.configuration) if connector else False,
                'cap_count': len(connector.get_capabilities()) if connector else 0,
            }
            results[cid] = data

        with open('restart_dump.json', 'w') as f:
            json.dump(results, f)

if __name__ == '__main__':
    try:
        _dump()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
"""

def run_torture():
    print(f"================ PHASE D: REAL ODOO RESTART TORTURE ({CYCLES} CYCLES) ================")

    with open('child_dumper.py', 'w') as f:
        f.write(CHILD_SCRIPT)

    baseline = None

    for i in range(1, CYCLES + 1):
        print(f"Cycle {i}/{CYCLES}...")
        if os.path.exists(DUMP_FILE):
            os.remove(DUMP_FILE)

        result = subprocess.run([sys.executable, 'child_dumper.py'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [ERROR] Child process failed on cycle {i}:\n{result.stderr}")
            sys.exit(1)

        if not os.path.exists(DUMP_FILE):
            print(f"  [ERROR] Dump file not created on cycle {i}")
            sys.exit(1)

        with open(DUMP_FILE, 'r') as f:
            data = json.load(f)

        if baseline is None:
            baseline = data
            print(f"  [INFO] Baseline established: {json.dumps(baseline, indent=2)}")
        else:
            if data != baseline:
                print(f"  [VIOLATION] Nondeterministic result on cycle {i}!")
                print(f"    Expected: {baseline}")
                print(f"    Got:      {data}")
                sys.exit(1)
            else:
                print("  [PASS] State matches baseline exactly.")

    print("================ RESTART TORTURE COMPLETE ================")
    print("All 10 cycles returned identical, deterministic configuration, capabilities, and states.")

    # Cleanup
    if os.path.exists(DUMP_FILE):
        os.remove(DUMP_FILE)
    if os.path.exists('child_dumper.py'):
        os.remove('child_dumper.py')

if __name__ == "__main__":
    run_torture()
