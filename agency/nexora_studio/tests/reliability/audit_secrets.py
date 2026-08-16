import sys
import os

sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config

def test_secrets():
    config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
    registry = odoo.modules.registry.Registry('nexora_studio')

    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

        print("==========================================================")
        print("PHASE 35.5 - SECRETS AUDIT")
        print("==========================================================")

        recs = env['nexora.connector'].search([])
        all_passed = True

        for rec in recs:
            if hasattr(rec, 'api_key'):
                print(f"FAIL: {rec.connector_id} has a plaintext 'api_key' attribute!")
                all_passed = False

            if getattr(rec, 'api_key_id', False):
                print(f"SUCCESS: {rec.connector_id} uses secure 'api_key_id' relation.")

            # Check config parameter for secret
            if getattr(rec, 'api_key_id', False):
                secret_key = rec.api_key_id.key
                if "API_KEY" in secret_key or "TOKEN" in secret_key:
                    pass
                else:
                    print(f"WARNING: {rec.connector_id} api_key_id key is suspicious: {secret_key}")

        if all_passed:
            print("SUCCESS: No plaintext secrets found on connector records.")
        else:
            print("FAIL: Plaintext secrets found.")

if __name__ == "__main__":
    test_secrets()
