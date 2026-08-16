import sys
from pathlib import Path

# Add the workspace root to the Python path
sys.path.append('D:\\ODOO\\community\\odoo')

import odoo
from odoo.tools import config

def db_integrity_audit():
    config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
    registry = odoo.modules.registry.Registry('nexora_studio')

    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

        print("==========================================================")
        print("PHASE 35.5 - DATABASE INTEGRITY AUDIT")
        print("==========================================================")

        recs = env['nexora.connector'].search([])
        print(f"Total Connectors: {len(recs)}")

        ids = []
        duplicates = False
        orphans = False
        for rec in recs:
            print(f"- {rec.connector_id}: state={rec.state}, capabilities={len(rec.capability_ids)}")
            if rec.connector_id in ids:
                print(f"FAIL: Duplicate connector_id found: {rec.connector_id}")
                duplicates = True
            ids.append(rec.connector_id)

            for cap in rec.capability_ids:
                if cap.connector_id.id != rec.id:
                    print(f"FAIL: Orphan capability found: {cap.namespace} points to {cap.connector_id.id} but should point to {rec.id}")
                    orphans = True

        caps = env['nexora.connector_capability'].search([])
        for cap in caps:
            if not cap.connector_id:
                print(f"FAIL: Capability {cap.namespace} has no connector_id assigned!")
                orphans = True

        if not duplicates and not orphans:
            print("SUCCESS: Database integrity verified.")
        else:
            print("FAIL: Database integrity violations found.")

        print("==========================================================")


if __name__ == "__main__":
    db_integrity_audit()
