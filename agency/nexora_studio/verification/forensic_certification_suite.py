import sys
import os
import json
import time

def run_integration_audit(env):
    print("==================================================")
    print("  NEXORA STUDIO - REGISTERED CAPABILITIES LIST")
    print("==================================================")
    
    records = env['nexora.capability_registry'].sudo().search([])
    for r in records:
        print(f"ID: {r.capability_id} | Provider: {r.provider} | Model: {r.implementation_model}")
        
if __name__ == "__main__":
    if 'env' in globals():
        run_integration_audit(env)
    else:
        print("Must be run via odoo-bin shell")
