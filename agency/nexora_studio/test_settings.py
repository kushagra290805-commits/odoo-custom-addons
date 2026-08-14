def test_settings(env):
    Settings = env['res.config.settings'].with_context(active_test=False)
    
    # 1. Create a transient record mimicking saving from UI
    catalog_rec = env['nexora.ai_model_catalog'].search([('model_id', '=', 'openrouter/free')], limit=1)
    print(f"Catalog record for openrouter/free: {catalog_rec.id if catalog_rec else None}")
    
    settings = Settings.create({
        'nexora_openrouter_default_model_id': catalog_rec.id
    })
    
    print("Setting values...")
    settings.set_values()
    env.cr.commit()
    
    # 2. Mimic reloading settings page
    print("Getting values...")
    new_settings_vals = Settings.get_values()
    
    model_id_after = new_settings_vals.get('nexora_openrouter_default_model_id')
    print(f"Model ID in settings after reload: {model_id_after}")
    
    # Check ir.config_parameter
    raw_val = env['ir.config_parameter'].sudo().get_param('nexora.openrouter.default_model')
    print(f"Raw ir.config_parameter val: {raw_val}")

if "env" in locals():
    test_settings(env)
