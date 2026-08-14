import json

def test_resolve(env):
    print("--- REAL RUNTIME RESOLVER TEST ---")
    try:
        from odoo.addons.nexora_studio.services.capabilities.repository import CapabilityRepository
        repo = CapabilityRepository(env=env)
        
        target = 'local.playwright'
        manifests = repo.get_manifests_by_namespace(target)
        
        print(f"Target: {target}")
        print(f"Returned Manifests count: {len(manifests)}")
        for m in manifests:
            print(f"Manifest: {m.namespace} ({m.target_type})")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during resolution: {e}")

if __name__ == "__main__":
    if 'env' in globals():
        test_resolve(env)
    else:
        print("Must be run via odoo-bin shell")
