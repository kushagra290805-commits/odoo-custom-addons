def check_router(env):
    srv = env['nexora.ai_configuration_service']
    for t in ['simple', 'medium', 'complex']:
        param_key = f'cost_router_tier_{t}'
        print(f"{param_key}:", srv.get_config('core', param_key, ''))
        
if "env" in locals():
    check_router(env)
