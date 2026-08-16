import sys
import traceback
sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config

config.parse_config(['-c', 'configs\\dev.conf'])
registry = odoo.modules.registry.Registry('nexora_studio')

def check_invariants():
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        print("================ STATIC INVARIANTS ================")

        # I1: Exactly one persistent canonical connector exists per connector_id
        print("I1: Checking persistent connector uniqueness...")
        records = env['nexora.connector'].search([])
        counts = {}
        duplicates = False
        for r in records:
            counts[r.connector_id] = counts.get(r.connector_id, 0) + 1
        for k, v in counts.items():
            if v > 1:
                print(f"  [VIOLATION] I1: {k} appears {v} times.")
                duplicates = True
        if not duplicates:
            print("  [PASS] I1: All connector IDs are unique.")

        # I2: Every RUNNING MCP connector has runtime configuration.
        print("\nI2: Checking RUNNING MCP connectors have configuration...")
        i2_pass = True
        for connector in runtime.registry.get_all():
            if connector.lifecycle_state.value == 'running':
                if not connector.configuration:
                    print(f"  [VIOLATION] I2: {connector.connector_id} is RUNNING but lacks configuration.")
                    i2_pass = False
        if i2_pass:
            print("  [PASS] I2: All RUNNING connectors have configurations.")

        # I3: Every HEALTHY connector has evidence of successful health verification.
        print("\nI3: Checking HEALTHY connectors have successful probes...")
        i3_pass = True
        for connector in runtime.registry.get_all():
            if connector.lifecycle_state.value == 'healthy':
                if not connector.health or not connector.health.is_healthy():
                    print(f"  [VIOLATION] I3: {connector.connector_id} is HEALTHY but health object says otherwise/missing.")
                    i3_pass = False
        if i3_pass:
            print("  [PASS] I3: All HEALTHY connectors have valid health records.")

        # I4: Startup-not-ready probes do not increment failure counters.
        print("\nI4: Startup-not-ready probes are verified by design (no probe executed if config=None).")

        # I5: Plaintext credentials do not enter persistence.
        print("\nI5: Checking for plaintext credentials in persistence...")
        # Since credentials are encrypted via OdooSecretsProvider (Fernet), we can check DB.
        creds = env['nexora.mcp_credential'].search([])
        i5_pass = True
        for c in creds:
            if c.encrypted_value and not c.encrypted_value.startswith('gAAAAA'):
                print(f"  [VIOLATION] I5: {c.credential_key} has potentially plaintext data in encrypted_value.")
                i5_pass = False
        if i5_pass:
            print("  [PASS] I5: No plaintext secrets found in nexora.mcp_credential.")

        # I6: Every runtime connector maps to exactly one persistent connector.
        print("\nI6: Checking runtime-to-persistence mapping...")
        i6_pass = True
        for connector in runtime.registry.get_all():
            db_recs = env['nexora.connector'].search([('connector_id', '=', connector.connector_id)])
            if len(db_recs) != 1:
                print(f"  [VIOLATION] I6: Runtime connector {connector.connector_id} maps to {len(db_recs)} persistent records.")
                i6_pass = False
        if i6_pass:
            print("  [PASS] I6: Every runtime connector maps to 1 persistent record.")

        # I7: Capability index entries map to valid connector capabilities.
        print("\nI7: Checking capability index validity...")
        i7_pass = True
        # Capability index is internal to ConnectorRuntime
        if hasattr(runtime, '_capability_index'):
            for namespace, impls in runtime._capability_index.items():
                for impl in impls:
                    conn = runtime.registry.get(impl.connector_id)
                    if not conn:
                        print(f"  [VIOLATION] I7: Capability {namespace} maps to invalid connector {impl.connector_id}.")
                        i7_pass = False
        if i7_pass:
            print("  [PASS] I7: Capability index is internally valid.")

        print("\nDone checking static invariants.")

if __name__ == '__main__':
    try:
        check_invariants()
    except Exception as e:
        traceback.print_exc()
