import sys
import os

def verify(env):
    print('Starting AI Configuration Verification...')
    
    config_service = env['nexora.ai_configuration_service']
    provider_manager = env['nexora.ai_provider_manager']
    
    # 1. Check configured default provider
    default_provider = config_service.get_config('core', 'default_provider', 'openrouter')
    print(f'Default Provider: {default_provider}')
    
    # 2. Check credentials
    creds = config_service.get_provider_credentials(default_provider)
    if creds.get('api_key'):
        print(f'Credentials for {default_provider}: Found (length: {len(creds.get("api_key"))})')
    else:
        print(f'Credentials for {default_provider}: MISSING')
        
    # 3. Check active model
    active_model = config_service.get_active_model(default_provider)
    print(f'Active Model for {default_provider}: {active_model}')
    
    # 4. Check model catalog
    catalog_recs = env['nexora.ai_model_catalog'].search([
        ('provider', '=', default_provider),
        ('model_id', '=', active_model)
    ])
    if catalog_recs:
        print(f'Model Catalog: Found {active_model} (status: {catalog_recs[0].status})')
    else:
        print(f'Model Catalog: MISSING {active_model}')
        
    # 5. Check AIProviderManager resolution
    try:
        available_providers = provider_manager.get_available_providers()
        print(f'Available Providers (from ProviderManager): {[p["key"] for p in available_providers if p["available"]]}')
    except Exception as e:
        print(f'Error getting available providers: {e}')
        
    print('Verification complete.')

if "env" in locals():
    verify(env)
