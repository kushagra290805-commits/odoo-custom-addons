def test_wipeout(env):
    Settings = env['res.config.settings'].with_context(active_test=False)
    
    # 1. Set a model initially
    env['ir.config_parameter'].sudo().set_param('nexora.openrouter.default_model', 'openrouter/free')
    env.cr.commit()
    print("Initial model set to openrouter/free")
    
    # 2. Emulate web client saving WITHOUT the model field
    settings = Settings.create({
        'nexora_openrouter_timeout': 125,
        'nexora_openrouter_api_key': 'foo'
    })
    
    print("Calling execute() with no model field...")
    settings.execute()
    env.cr.commit()
    
    # 3. Check what is in the db
    val = env['ir.config_parameter'].sudo().get_param('nexora.openrouter.default_model')
    print(f"Model in db after save: {val}")

if "env" in locals():
    test_wipeout(env)
