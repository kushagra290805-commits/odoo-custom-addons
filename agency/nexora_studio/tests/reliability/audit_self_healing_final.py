import sys
import os
import uuid
import time
import json
import threading
import concurrent.futures
import traceback
sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config

config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
registry = odoo.modules.registry.Registry('nexora_studio')

RUN_ID = str(uuid.uuid4())[:8]

def _setup_fixture(env, suffix, base_connector_id='github_mcp'):
    cid = f"test.mcp.final.{suffix}.{RUN_ID}"

    # Ensure no old fixture exists
    old = env['nexora.connector'].search([('connector_id', '=', cid)])
    if old:
        old.unlink()

    base_rec = env['nexora.connector'].search([('connector_id', '=', base_connector_id)], limit=1)
    base_conf = env['nexora.mcp_server_config'].search([('connector_id', '=', base_rec.id)], limit=1)

    rec = env['nexora.connector'].create({
        'connector_id': cid,
        'name': f'Final Test {suffix} {RUN_ID}',
        'connector_type_id': base_rec.connector_type_id.id,
        'state': 'registered',
        'health_status': 'unknown'
    })

    env['nexora.mcp_server_config'].create({
        'connector_id': rec.id,
        'command': base_conf.command,
        'args_json': base_conf.args_json,
        'transport_type': base_conf.transport_type,
        'authentication_location': base_conf.authentication_location,
        'authentication_name': base_conf.authentication_name,
        'authentication_scheme': base_conf.authentication_scheme,
        'credential_key': base_conf.credential_key,
    })
    env.cr.commit()
    return cid, rec

def get_runtime(env):
    from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
    bootstrap = ConnectorPlatformBootstrap.get_instance()
    bootstrap.bootstrap(env)
    return bootstrap.connector_runtime

def test_phase_c_stdio_death():
    print(f"\n--- PHASE C: REAL STDIO TRANSPORT DEATH ({RUN_ID}) ---")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        cid, rec = _setup_fixture(env, 'stdio_c', 'github_mcp')
        runtime = get_runtime(env)

        try:
            rec.action_enable()
            print("  [INFO] action_enable succeeded.")
        except Exception as e:
            print(f"  [ERROR] Failed to enable fixture: {e}")
            return

        env.cr.commit()

        connector = runtime.registry.get(cid)
        sdk_connector = runtime.dispatcher._active_connectors.get(cid)

        if not sdk_connector or not sdk_connector.transport:
            print("  [FAIL] Initial transport not created.")
            return

        print(f"  [T0] Transport operational.")

        old_transport_id = id(sdk_connector.transport) if sdk_connector and sdk_connector.transport else None

        # Invalidate manually by disconnecting
        try:
            sdk_connector.transport.disconnect()
            print(f"  [T1] Transport disconnected deliberately.")
        except Exception as e:
            print(f"  [ERROR] Failed to disconnect: {e}")

        print("  Triggering dispatch to cause failure interception...")
        try:
            from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionRequest, ConnectorRuntimeContext
            ctx = ConnectorRuntimeContext(connector_id=cid, session_id='test')
            req = ConnectorExecutionRequest(capability_namespace='tools.list', context=ctx)
            result = runtime.dispatch(req)
            print(f"  Dispatch result: {result.status}")
        except Exception as e:
            print(f"  Dispatch exception: {e}")

        print("  Waiting 5 seconds for recovery...")
        time.sleep(5)

        new_sdk = runtime.dispatcher._active_connectors.get(cid)
        new_transport_id = id(new_sdk.transport) if new_sdk and new_sdk.transport else None
        print(f"  [T2] New Transport ID: {new_transport_id}")

        if not new_sdk or not new_sdk.transport:
            print("  [FAIL] Transport was not recreated.")
            return

        if old_transport_id == new_transport_id:
            print("  [FAIL] Transport object ID did not change. Process was not recreated.")
        elif new_transport_id is None:
            print("  [FAIL] New transport is None.")
        else:
            print("  [PASS] Transport was recreated autonomously!")

if __name__ == '__main__':
    test_phase_c_stdio_death()
