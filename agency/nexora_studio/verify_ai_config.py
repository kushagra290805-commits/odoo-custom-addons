import sys

def run():
    print("=== STARTING AI CONFIGURATION SERVICE E2E TRACE ===")
    
    # Check that ProviderManager route_request works without error
    manager = env['nexora.ai_provider_manager']
    
    print("\n--- Listing Available Providers ---")
    providers = manager.get_available_providers()
    print("Available Providers:", providers)

    print("\n--- Route Request ---")
    try:
        res = manager.route_request('simple_task', 'Hello AI, reply with a JSON object {"status": "ok"}')
        print(f"Routing success! Output: {res}")
    except Exception as e:
        print(f"Routing failed! {e}")
        import traceback
        traceback.print_exc()

    print("\n=== AI CONFIGURATION SERVICE E2E TRACE COMPLETE ===")

try:
    run()
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
sys.exit(0)
