def patch(env):
    import os
    filepath = r'd:\ODOO\custom-addons\agency\nexora_studio\models\res_config_settings.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We will inject print statements into set_values and get_values
    if "import logging" not in content:
        content = "import logging\n_logger = logging.getLogger(__name__)\n" + content
        content = content.replace("def set_values(self):", "def set_values(self):\n        _logger.warning('--- set_values CALLED ---')\n        _logger.warning(f'self.nexora_openrouter_default_model_id: {self.nexora_openrouter_default_model_id.id}')")
        content = content.replace("def get_values(self):", "def get_values(self):\n        _logger.warning('--- get_values CALLED ---')")
        content = content.replace("res['nexora_openrouter_default_model_id'] = catalog.id", "res['nexora_openrouter_default_model_id'] = catalog.id\n                _logger.warning(f'get_values SETTING: {catalog.id}')")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched!")
    else:
        print("Already patched!")

if "env" in locals():
    patch(env)
