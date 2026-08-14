import sys
import os
import asyncio
import json
import types

def _setup_mock():
    # Mock odoo and its modules
    odoo = types.ModuleType('odoo')
    sys.modules['odoo'] = odoo
    
    tools = types.ModuleType('tools')
    tools.config = {}
    sys.modules['odoo.tools'] = tools
    
    exceptions = types.ModuleType('exceptions')
    sys.modules['odoo.exceptions'] = exceptions
    
    models = types.ModuleType('models')
    class DummyModel:
        pass
    models.AbstractModel = DummyModel
    models.Model = DummyModel
    models.TransientModel = DummyModel
    sys.modules['odoo.models'] = models
    
    api = types.ModuleType('api')
    api.model = lambda f: f
    sys.modules['odoo.api'] = api
    
    # We want to import `services.runtime.mcp...` but avoid `services/__init__.py` running.
    # So we inject a fake 'services' package into sys.modules.
    studio_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    if studio_path not in sys.path:
        sys.path.insert(0, studio_path)
        
    services_pkg = types.ModuleType('services')
    services_pkg.__path__ = [os.path.join(studio_path, 'services')]
    sys.modules['services'] = services_pkg

_setup_mock()

async def run_validation():
    print("[1] Loading GitHub MCP Runtime test...")
    
    pat = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not pat:
        pat = input("\nPlease enter your GITHUB_PERSONAL_ACCESS_TOKEN: ")
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = pat.strip()
    
    os.environ["NEXORA_MCP_REGISTRY_PATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "config", "mcp_registry.json"))
    print(f"[2] Registry Path set to: {os.environ['NEXORA_MCP_REGISTRY_PATH']}")
    
    # Import the MCP modules natively as `services.runtime.mcp.*`
    from services.runtime.mcp.mcp_server_registry import McpServerRegistry
    from services.runtime.mcp.mcp_capability_catalog import McpCapabilityCatalog
    from services.runtime.mcp.mcp_runtime_manager import McpRuntimeManager
    from services.runtime.mcp.mcp_tool_router import McpToolRouter
    from services.runtime.mcp.mcp_models import McpState
    
    registry = McpServerRegistry()
    catalog = McpCapabilityCatalog()
    manager = McpRuntimeManager(registry, catalog)
    router = McpToolRouter(manager, catalog)
    
    print("[3] Initiating Runtime Manager startup...")
    await manager.startup()
    
    client = manager.clients.get("github_mcp")
    if not client:
        print("ERROR: github_mcp not found in manager.")
        return
        
    print(f"[4] GitHub MCP Status: {client.state}")
    if client.state != McpState.READY:
        print("ERROR: Client failed to reach READY state.")
        return
        
    print(f"[5] Successfully discovered {len(catalog._capabilities)} tools!")
    
    tool_to_run = "search_repositories"
    args = {"query": "language:python stars:>10000"}
    
    if tool_to_run not in catalog._capabilities:
        print(f"Tools list: {list(catalog._capabilities.keys())}")
        
    try:
        print(f"[6] Executing '{tool_to_run}' via Router...")
        result = await router.execute_capability(tool_to_run, args)
        print("\n--- EXECUTION RESULT ---")
        print(json.dumps(result, indent=2))
        print("------------------------")
    except Exception as e:
        print(f"Error executing tool: {e}")
        
    print("[7] Shutting down...")
    await manager.shutdown()
    print("Done!")

if __name__ == '__main__':
    asyncio.run(run_validation())
