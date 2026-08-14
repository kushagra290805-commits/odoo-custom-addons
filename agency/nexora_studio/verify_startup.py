# -*- coding: utf-8 -*-
"""
Verify Clean Startup
"""
import sys

def verify_startup(env):
    errors = []
    
    try:
        # Check Models
        assert 'nexora.telemetry_recorder' in env.registry.models, "telemetry_recorder model missing"
        assert 'nexora.ai_dashboard_service' in env.registry.models, "ai_dashboard_service model missing"
        assert 'nexora.ai_execution_history' in env.registry.models, "ai_execution_history model missing"
        
        # Check routes (can check if controllers are loaded via import)
        import odoo.addons.nexora_studio.controllers.ai_analytics_api
        
        # Try fetching the service
        dashboard_service = env['nexora.ai_dashboard_service']
        print("[PASS] Clean Startup Verification Successful")
    except Exception as e:
        print(f"[FAIL] Clean Startup Verification Failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    verify_startup(env)
