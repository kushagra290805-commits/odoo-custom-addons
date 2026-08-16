import sys
import uuid
import traceback
import time
import subprocess
import json
sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config

config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
registry = odoo.modules.registry.Registry('nexora_studio')

RUN_ID = str(uuid.uuid4())[:8]

def _setup_fixture(env, suffix, transport='stdio', command='python', args='["-c", "print(\'mock\')"]'):
    cid = f"test.mcp.fail.{suffix}.{RUN_ID}"
    ctype = env['nexora.connector_type'].search([('type_code', '=', 'mcp')], limit=1)
    rec = env['nexora.connector'].create({
        'connector_id': cid,
        'name': f'Fail Test {suffix}',
        'connector_type_id': ctype.id,
        'state': 'registered'
    })
    env['nexora.mcp_server_config'].create({
        'connector_id': rec.id,
        'command': command,
        'args_json': args,
        'transport_type': transport,
        'startup_policy': 'eager',
        'authentication_location': 'none',
        'credential_key': 'MOCK_KEY' if suffix == 'cred' else False
    })
    return cid, rec

def test_credential_failures():
    print(f"\n--- PHASE F: CREDENTIAL FAILURE INJECTION ---")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        cid, rec = _setup_fixture(env, 'cred')

        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        # Test A: Missing Credential
        print("  Test A: Enabling with missing credential...")
        try:
            rec.action_enable()
            print("    [VIOLATION] Enable succeeded despite missing credential.")
        except Exception as e:
            print(f"    [PASS] Enable failed gracefully: {e}")

        env.cr.rollback()

def test_transport_failures():
    print(f"\n--- PHASE G: TRANSPORT FAILURE INJECTION ---")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        cid, rec = _setup_fixture(env, 'trans', command='python', args='["-c", "import time; time.sleep(60)"]')
        env.cr.commit()

        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        print("  1. Enabling stdio connector...")
        try:
            rec.action_enable()
            print("     Enabled successfully.")
        except Exception as e:
            print(f"     [ERROR] Enable failed: {e}")

        print("  2. Terminating underlying process...")
        dispatcher = runtime.dispatcher
        sdk_connector = dispatcher._active_connectors.get(cid)
        if sdk_connector and sdk_connector.transport:
            try:
                # Force kill the process
                sdk_connector.transport._process.kill()
                print("     Process killed.")

                print("  3. Probing health...")
                health = runtime.probe_health(cid)
                print(f"     Health Status: {health.status.value if health else 'unknown'}")
            except Exception as e:
                print(f"     [ERROR] Transport manipulation failed: {e}")
        else:
            print("     [ERROR] No active session/transport found.")

def test_protocol_failures():
    print(f"\n--- PHASE H: MCP PROTOCOL FAILURE INJECTION ---")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        bad_script = "print('GARBAGE_JSON_RESPONSE')"
        cid, rec = _setup_fixture(env, 'proto', command='python', args=f'["-c", "{bad_script}"]')
        env.cr.commit()

        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        print("  1. Enabling malformed MCP connector...")
        try:
            rec.action_enable()
            print("     [VIOLATION] Enable succeeded despite protocol failure.")
        except Exception as e:
            print(f"     [PASS] Enable correctly failed: {e}")

    # Cleanup all fixtures
    print("\nCleaning up disposable fixtures...")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        env['nexora.connector'].search([('connector_id', 'like', f'test.mcp.fail.%{RUN_ID}')]).unlink()
        env.cr.commit()

if __name__ == '__main__':
    try:
        test_credential_failures()
        test_transport_failures()
        test_protocol_failures()
    except Exception as e:
        traceback.print_exc()
