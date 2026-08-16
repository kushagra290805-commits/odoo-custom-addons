import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.tools.config
import odoo.sql_db
import odoo.api

odoo.tools.config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf', '-d', 'nexora_studio'])
db = odoo.sql_db.db_connect('nexora_studio')

with db.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

    print("\n============================================================")
    print("1. INVENTORY ALL MCP CONNECTORS")
    print("============================================================")

    connectors = env['nexora.connector'].search([])

    print(f"{'ID':<4} | {'NAME':<35} | {'CONNECTOR_ID':<20} | {'TYPE':<10} | {'EN':<3} | {'STATE':<10} | {'HEALTH':<10} | {'LAST_CHECK':<20} | {'VERSION':<7} | {'TRANSPORT':<10} | {'COMMAND':<40} | {'CRED_KEY':<15} | {'STARTUP'}")
    print("-" * 220)

    for c in connectors:
        type_code = c.connector_type_id.type_code if c.connector_type_id else 'unknown'
        mcp_config = env['nexora.mcp_server_config'].search([('connector_id', '=', c.id)], limit=1)

        transport = mcp_config.transport_type if mcp_config else 'N/A'
        command = mcp_config.command if mcp_config else 'N/A'
        cred_key = mcp_config.credential_key if mcp_config else 'N/A'
        startup = mcp_config.startup_policy if mcp_config else 'N/A'

        name = (c.name or '').replace('|', ' ')
        cid = (c.connector_id or '').replace('|', ' ')
        state = str(c.state)
        health = str(c.health_status)
        last_check = str(c.last_health_check)

        print(f"{c.id:<4} | {name:<35} | {cid:<20} | {type_code:<10} | {str(c.enabled)[0]:<3} | {state:<10} | {health:<10} | {last_check:<20} | {c.version:<7} | {transport:<10} | {command:<40} | {cred_key:<15} | {startup}")

    print("\n============================================================")
    print("6. CREDENTIAL AUDIT")
    print("============================================================")

    from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
    secrets = OdooSecretsProvider(env)
    all_secret_keys = secrets.list_keys()

    for c in connectors:
        mcp_config = env['nexora.mcp_server_config'].search([('connector_id', '=', c.id)], limit=1)
        if not mcp_config:
            continue

        cred_key = mcp_config.credential_key
        # also check env_vars_json if it exists and asks for injection
        env_vars = mcp_config.get_env_vars_dict() if hasattr(mcp_config, 'get_env_vars_dict') else {}

        required_creds = []
        if cred_key:
            required_creds.append(cred_key)

        # Firecrawl relies on implicit injection now, so we can just check if any secret exists for connector
        connector_secrets = [k for k in all_secret_keys if k.startswith(f"{c.connector_id}:")]

        if required_creds:
            for key in required_creds:
                composite = f"{c.connector_id}:{key}"
                status = "PRESENT" if composite in all_secret_keys else "MISSING / INVALID REFERENCE"
                print(f"Connector: {c.connector_id:<20} | Credential: {key:<20} | Status: {status}")
        elif connector_secrets:
            print(f"Connector: {c.connector_id:<20} | Credential: (Implicit)           | Status: PRESENT ({len(connector_secrets)} keys)")
        else:
            print(f"Connector: {c.connector_id:<20} | Credential: (None)               | Status: NOT REQUIRED / MISSING")

