import sys
import os

def restore_provider():
    import odoo.tools.config as config
    config.parse_config(['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])
    import odoo.modules.registry as registry
    reg = registry.Registry('nexora_studio')
    with reg.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        RegistryModel = env['nexora.provider.registry']
        existing = RegistryModel.search([('provider_id', '=', 'openrouter')])
        if not existing:
            print("Restoring openrouter...")
            RegistryModel.create({
                'provider_id': 'openrouter',
                'name': 'OpenRouter',
                'category': 'ai',
                'compatibility_profile': 'openai_compatible',
                'base_url': 'https://openrouter.ai/api/v1',
                'lifecycle_state': 'CONFIGURED',
                'is_active': True
            })
            print("Restored.")
        else:
            print("openrouter already exists.")

if __name__ == '__main__':
    # Add Odoo to path
    sys.path.append(r'D:\ODOO\community\odoo')
    import odoo
    restore_provider()
