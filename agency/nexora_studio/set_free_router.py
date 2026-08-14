def set_free_router(env):
    print('Starting AI Configuration Update...')
    
    config_service = env['nexora.ai_configuration_service']
    default_provider = 'openrouter'
    active_model = 'openrouter/free'
    
    # Update config parameter
    config_service.set_active_model(default_provider, active_model)
    print('Updated config_service successfully.')
    
    # Verify the update
    new_active = config_service.get_active_model(default_provider)
    print(f'New active model for {default_provider}: {new_active}')
    env.cr.commit()
    print('Transaction committed.')

if "env" in locals():
    set_free_router(env)
