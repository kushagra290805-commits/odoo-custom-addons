import sys
import time

sys.path.append('D:\\ODOO\\community\\odoo')

import odoo
from odoo.tools import config

def test_post_restart():
    config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
    registry = odoo.modules.registry.Registry('nexora_studio')

    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

        core_connectors = ['github_mcp', 'context7_mcp', 'firecrawl_mcp', 'penpot_mcp']
        print("Resetting core connectors to 'running' state in DB...")
        env['nexora.connector'].search([('connector_id', 'in', core_connectors)]).write({'state': 'running'})
        cr.commit()

        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        print("Wait for background reconciliation to finish...")
        time.sleep(5.0)

        print("==========================================================")
        print("PHASE 35.5 - POST-RESTART CORE CONNECTORS VERIFICATION")
        print("==========================================================")

        core_connectors = ['github_mcp', 'context7_mcp', 'firecrawl_mcp', 'penpot_mcp']

        all_passed = True

        for cid in core_connectors:
            rec = env['nexora.connector'].search([('connector_id', '=', cid)])

            # Since these are core connectors, they should exist in config.
            conn = runtime.registry.get(cid)
            if not conn:
                print(f"FAIL: {cid} not found in registry.")
                all_passed = False
                continue

            if not conn.is_running:
                print(f"FAIL: {cid} is not RUNNING in registry (state={conn.lifecycle_state}).")
                all_passed = False
                continue

            if rec.state != 'running':
                print(f"FAIL: {cid} database state is {rec.state}, expected running. Reason: {rec.failure_reason}")
                all_passed = False
                continue

            print(f"SUCCESS: {cid} is running and reconciled.")

        if all_passed:
            print("SUCCESS: Post-restart core connectors check passed.")
        else:
            print("FAIL: Core connectors check failed.")

        print("==========================================================")


if __name__ == "__main__":
    test_post_restart()
