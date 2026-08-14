def test_settings_execute(env):
    Settings = env['res.config.settings'].with_context(active_test=False)
    
    catalog_rec = env['nexora.ai_model_catalog'].search([('model_id', '=', 'openrouter/free')], limit=1)
    
    # In the UI, Odoo creates the transient record and then calls execute()
    settings = Settings.create({
        'nexora_openrouter_default_model_id': catalog_rec.id
    })
    
    print("Calling execute()...")
    settings.execute()
    env.cr.commit()
    
    print("Getting values...")
    new_settings_vals = Settings.get_values()
    
    model_id_after = new_settings_vals.get('nexora_openrouter_default_model_id')
    print(f"Model ID in settings after reload: {model_id_after}")
    
    raw_val = env['ir.config_parameter'].sudo().get_param('nexora.openrouter.default_model')
    print(f"Raw ir.config_parameter val: {raw_val}")

if "env" in locals():
    test_settings_execute(env)
