import sys
sys.path.append(r'D:\ODOO\community\odoo')
import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
from odoo.api import Environment
import odoo.service.server

def check_db(env):
    try:
        env.cr.execute("ALTER TABLE nexora_connector ADD CONSTRAINT nexora_connector_id_uniq UNIQUE (connector_id)")
        print("Constraint added manually.")
    except Exception as e:
        print("Failed to add constraint manually:", e)
        env.cr.rollback()

    env.cr.execute("SELECT conname FROM pg_constraint WHERE conrelid = (SELECT oid FROM pg_class WHERE relname='nexora_connector')")
    constraints = env.cr.fetchall()
    print("ALL Constraints:", constraints)

if __name__ == "__main__":
    config.parse_config(['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])
    odoo.service.server.start(preload=['nexora_studio'], stop=True)
    registry = Registry('nexora_studio')
    with registry.cursor() as cr:
        env = Environment(cr, 1, {})
        check_db(env)
