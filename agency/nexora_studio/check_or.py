def check_or(env):
    srv = env['nexora.ai_configuration_service']
    creds = srv.get_provider_credentials('openrouter')
    adapter = env['nexora.ai_adapter.openrouter']
    print("Is available?", adapter.is_available(creds))
    import requests
    key = creds.get('api_key')
    r = requests.get('https://openrouter.ai/api/v1/models', headers={'Authorization': f'Bearer {key}'})
    print("Status code:", r.status_code)
    print("Response:", r.text[:200])

if "env" in locals():
    check_or(env)
