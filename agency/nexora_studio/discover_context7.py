import os
import asyncio
import json
from odoo.addons.nexora_studio.services.runtime.mcp.registry_provider import JsonRegistryProvider
from odoo.addons.nexora_studio.services.runtime.mcp.mcp_runtime_adapter import McpRuntimeAdapter

def main():
    mcp_path = os.path.join(r'D:\ODOO', 'custom-addons', 'agency', 'nexora_studio', 'config', 'mcp_registry.json')
    provider = JsonRegistryProvider(mcp_path)
    adapter = McpRuntimeAdapter(provider)
    adapter.initialize()
    
    import time
    time.sleep(10) # wait for boot
    
    print("Capabilities:", list(adapter.catalog._capabilities.keys()))
    adapter.shutdown()

if __name__ == '__main__':
    main()
