import sys
import traceback
sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
from odoo.tools import config

config.parse_config(['-c', 'd:\\ODOO\\configs\\dev.conf'])
registry = odoo.modules.registry.Registry('nexora_studio')

def _dump_baseline():
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap

        # Trigger full reconciliation and bootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime

        target_ids = ['github_mcp', 'context7_mcp', 'firecrawl_mcp', 'penpot_mcp']

        for cid in target_ids:
            print(f'================ {cid} ================')

            # DB Info
            record = env['nexora.connector'].search([('connector_id', '=', cid)], limit=1)
            if record:
                print(f'DB Lifecycle    : {record.state}')
                print(f'DB Health       : {record.health_status}')
                print(f'DB Error State  : {record.error_message or "None"}')
            else:
                print('DB Record       : NOT FOUND')

            # Runtime Info
            connector = runtime.registry.get(cid)
            if connector:
                print(f'Runtime State   : {connector.lifecycle_state.value}')
                print(f'Config Present  : {bool(connector.configuration)}')

                print(f'Capability count: {len(connector.get_capabilities())}')

                if connector.health:
                    print(f'Health Counter  : status={connector.health.status.value}, '
                          f'failures={connector.health.consecutive_failures}, successes={connector.health.consecutive_successes}')
                else:
                    print('Health Object   : None')

                cred_record = env['nexora.mcp_credential'].search([('connector_id', '=', record.id)], limit=1) if record else None
                if cred_record:
                    print(f'Cred Metadata   : type={cred_record.credential_type}, key={cred_record.credential_key}')
                else:
                    print('Cred Metadata   : None')

                if connector.configuration:
                    print(f'Transport Type  : {connector.configuration.get_resolved_values().get("transport")}')

                if connector.active_session:
                    print(f'Active Session  : True (ID: {connector.active_session.session_id})')
                else:
                    print('Active Session  : False')
            else:
                print('Runtime Record  : NOT FOUND')
            print('')

if __name__ == '__main__':
    try:
        _dump_baseline()
    except Exception as e:
        traceback.print_exc()
