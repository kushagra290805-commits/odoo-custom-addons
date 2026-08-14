import sys
import os
import logging
import json

sys.path.append(r'D:\ODOO\community\odoo')
import odoo
from odoo.modules.registry import Registry

logging.basicConfig(level=logging.INFO)

def run_investigation():
    odoo.tools.config.parse_config(['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])
    registry = Registry('nexora_studio')
    
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        
        providers = ['openrouter', 'airouter', 'ollama', 'groq', 'nvidia']
        
        print("\n--- 1. DATABASE STATE AUDIT ---")
        for p_id in providers:
            reg = env['nexora.provider.registry'].search([('provider_id', '=', p_id)], limit=1)
            if not reg:
                print(f"{p_id}: NOT FOUND")
                continue
            
            key_len = len(reg.api_key) if reg.api_key else 0
            
            print(f"Provider: {p_id}")
            print(f"  api_key length: {key_len}")
            print(f"  base_url: {reg.base_url}")
            print(f"  compatibility_profile: {reg.compatibility_profile}")
            print(f"  lifecycle_state: {reg.lifecycle_state}")
            print(f"  health_indicator: {reg.health_status}")
            print(f"  authentication_status: {reg.authentication_status}")
            print(f"  catalog_sync_status: {reg.catalog_sync_status}")
            print(f"  catalog_last_sync: {reg.catalog_last_sync}")
            
            try:
                print(f"  last_successful_sync: {reg.last_successful_sync}")
                print(f"  last_failed_sync: {reg.last_failed_sync}")
                print(f"  sync_retry_count: {reg.sync_retry_count}")
            except Exception:
                print("  (New sync fields not accessible)")
            print("")

        print("\n--- 2. ADAPTER RESOLUTION MATRIX ---")
        pm = env['nexora.ai_provider_manager']
        for p_id in providers:
            reg = env['nexora.provider.registry'].search([('provider_id', '=', p_id)], limit=1)
            if not reg: continue
            
            try:
                adapter = pm.get_adapter(p_id)
                print(f"Provider: {p_id}")
                print(f"  Profile: {reg.compatibility_profile}")
                print(f"  Adapter Class: {adapter.__class__.__name__}")
                print(f"  Has fetch_catalog: {hasattr(adapter, 'fetch_catalog')}")
                print(f"  Has run_diagnostics: {hasattr(adapter, 'run_diagnostics')}")
            except Exception as e:
                print(f"Provider {p_id} adapter resolution error: {e}")
            print("")
            
        print("\n--- 3. CREDENTIAL SOURCE AUDIT (Configuration Service) ---")
        config_service = env['nexora.ai_configuration_service']
        for p_id in ['openrouter', 'airouter', 'ollama']:
            try:
                cred = config_service.get_provider_credentials(p_id)
                key_len = len(cred.get('api_key', '')) if cred.get('api_key') else 0
                print(f"{p_id} get_provider_credentials(): key length = {key_len}, base_url = {cred.get('base_url')}")
            except Exception as e:
                print(f"{p_id} credentials error: {e}")

        print("\n--- 4. OLLAMA DIAGNOSTICS TEST TRACE ---")
        ollama_reg = env['nexora.provider.registry'].search([('provider_id', '=', 'ollama')], limit=1)
        if ollama_reg:
            print(f"Ollama base_url: {ollama_reg.base_url}")
            try:
                # Mock requests to see what it's trying to hit
                adapter = pm.get_adapter('ollama')
                if hasattr(adapter, 'run_diagnostics'):
                    print("OllamaAdapter has run_diagnostics. Will execute manually to see trace.")
                    # Let's inspect the code instead
            except Exception as e:
                pass

if __name__ == '__main__':
    run_investigation()
