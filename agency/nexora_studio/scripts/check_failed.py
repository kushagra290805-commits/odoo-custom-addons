import sys
sys.path.append('D:\\ODOO\\community\\odoo')
import odoo
import odoo.tools.config
import odoo.sql_db
import odoo.api

odoo.tools.config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf', '-d', 'nexora_studio'])
db = odoo.sql_db.db_connect('nexora_studio')

with db.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    connectors = env['nexora.connector'].search([('state', '=', 'failed')])
    for c in connectors:
        print(f'Connector: {c.connector_id}')
        print(f'State: {c.state}')
        print(f'Health: {c.health_status}')
        print(f'Status Message: {getattr(c, "status_message", "N/A")}')
        print(f'Health Detail: {getattr(c, "health_detail", "N/A")}')
        print('-'*40)
