import sys
import json
import time

def run_debug():
    runtime = env['nexora_studio.platform'].get_runtime()
    mcp_runtime = runtime.get_runtime('mcp_runtime')
    time.sleep(10)
    
    catalog = mcp_runtime.catalog._capabilities
    print("All capabilities:")
    for cap_id in catalog.keys():
        print(f" - {cap_id}")
        if 'penpot' in cap_id:
            print(f"FOUND PENPOT CAP: {cap_id}")

if __name__ == '__main__':
    run_debug()
