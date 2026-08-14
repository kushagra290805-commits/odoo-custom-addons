import sys
import os

def fix_config(env):
    print('Starting AI Configuration Remediation...')
    
    config_service = env['nexora.ai_configuration_service']
    provider_manager = env['nexora.ai_provider_manager']
    
    default_provider = 'openrouter'
    
    print(f'Syncing catalog for {default_provider}...')
    provider_manager.sync_catalog(default_provider)
    
    print('Catalog synced. Retrieving models...')
    models = provider_manager.list_models(default_provider)
    if not models:
        print('No active models found in catalog after sync! Aborting.')
        return
        
    # Let's pick a fast/cheap model for testing, e.g., something from google or anthropic that is likely present.
    # Fallback to the first available if our preferred isn't found.
    preferred_models = ['google/gemini-2.5-flash', 'anthropic/claude-3-haiku', 'openai/gpt-4o-mini', 'google/gemini-pro']
    
    active_model = None
    for pref in preferred_models:
        if any(m['model_id'] == pref for m in models):
            active_model = pref
            break
            
    if not active_model:
        active_model = models[0]['model_id']
        
    print(f'Selected valid model: {active_model}')
    
    # Update config parameter
    config_service.set_active_model(default_provider, active_model)
    print('Updated config_service successfully.')
    
    # Verify the update
    new_active = config_service.get_active_model(default_provider)
    print(f'New active model for {default_provider}: {new_active}')
    env.cr.commit()
    print('Transaction committed.')

if "env" in locals():
    fix_config(env)
