import logging
import sys
import traceback

def main(env):
    print("\n=== 5. Lifecycle Consistency ===")
    providers = env['nexora.provider.registry'].search([])
    for p in providers:
        print(f"Provider: {p.provider_id}")
        print(f"  Config: {p.config_state}")
        print(f"  Connectivity: {p.connectivity_state}")
        print(f"  Auth: {p.auth_state}")
        print(f"  Catalog Sync: {p.catalog_sync_status}")
        print(f"  Lifecycle: {p.lifecycle_state}")
        print("-" * 40)
        
    print("\n=== 6. End-to-end Verification ===")
    test_providers = ['nvidia', 'openrouter', 'airouter', 'groq', 'ollama']
    for p_id in test_providers:
        print(f"Testing connection for {p_id}...")
        try:
            res = env['nexora.ai_provider_manager'].test_connection(p_id)
            print(f"Result for {p_id}: {res}")
            
            # Fetch latest state and model count
            prov = env['nexora.provider.registry'].search([('provider_id', '=', p_id)], limit=1)
            models_count = env['nexora.ai_model_catalog'].search_count([('provider', '=', p_id), ('status', '=', 'active')])
            
            print(f"  Connectivity: {prov.connectivity_state}")
            print(f"  Auth: {prov.auth_state}")
            print(f"  Catalog Status: {prov.catalog_sync_status}")
            print(f"  Lifecycle: {prov.lifecycle_state}")
            print(f"  Available Models: {models_count}")
        except Exception as e:
            print(f"Error testing {p_id}: {e}")
            traceback.print_exc()
        print("=" * 50)

if __name__ == '__main__':
    main(env)
    env.cr.rollback()
