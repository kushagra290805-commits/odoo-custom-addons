def patch_get(env):
    filepath = r'd:\ODOO\custom-addons\agency\nexora_studio\models\res_config_settings.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "res['nexora_openrouter_default_model_id'] = catalog.id" in content:
        content = content.replace("res['nexora_openrouter_default_model_id'] = catalog.id", 
            "res['nexora_openrouter_default_model_id'] = catalog.id\n                print('GET_VALUES SETTING MODEL ID TO', catalog.id)")
        content = content.replace("return res", "print('GET_VALUES RETURNING', res)\n        return res")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched get_values!")

if "env" in locals():
    patch_get(env)
