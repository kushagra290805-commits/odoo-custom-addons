def test_ui_sequence(env):
    Settings = env['res.config.settings'].with_user(1).with_context(active_test=False)
    
    catalog_rec = env['nexora.ai_model_catalog'].search([('model_id', '=', 'openrouter/free')], limit=1)
    
    # UI calls create
    settings_id = Settings.create({
        'nexora_openrouter_default_model_id': catalog_rec.id,
        'nexora_openrouter_api_key': 'foo',
        'nexora_openrouter_base_url': 'bar'
    })
    
    print(f"Created settings record {settings_id.id}")
    
    # UI calls execute on that ID
    settings_id.execute()
    env.cr.commit()
    
    # UI calls default_get
    print("Calling default_get...")
    default_vals = Settings.default_get(Settings._fields.keys())
    
    model_id_after = default_vals.get('nexora_openrouter_default_model_id')
    print(f"Model ID in default_get after reload: {model_id_after}")

if "env" in locals():
    test_ui_sequence(env)
