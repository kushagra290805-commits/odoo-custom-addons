def test_default_get(env):
    Settings = env['res.config.settings'].with_context(active_test=False)
    fields = [
        'nexora_openrouter_api_key',
        'nexora_openrouter_base_url',
        'nexora_openrouter_default_model_id',
        'nexora_openrouter_enabled',
        'nexora_openrouter_timeout'
    ]
    res = Settings.default_get(fields)
    print("default_get returned:")
    print(res)

if "env" in locals():
    test_default_get(env)
