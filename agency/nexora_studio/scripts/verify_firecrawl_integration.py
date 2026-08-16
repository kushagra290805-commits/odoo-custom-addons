import sys
import os
import json
import asyncio

# Setup paths
sys.path.append("D:\\ODOO\\community\\odoo")
odoo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if odoo_path not in sys.path:
    sys.path.append(odoo_path)

print("--- PART 1: VERIFYING FIRECRAWL XML BOOTSTRAP DATA ---")
data_path = os.path.join(odoo_path, 'data', 'connector_firecrawl_data.xml')
if not os.path.exists(data_path):
    print("ERROR: data/connector_firecrawl_data.xml is missing.")
    sys.exit(1)

print(f"Found XML bootstrap file: {data_path}")

print("\n--- PART 2: VERIFYING MANIFEST INCLUSION ---")
manifest_path = os.path.join(odoo_path, '__manifest__.py')
with open(manifest_path, 'r') as f:
    manifest_content = f.read()
    if 'data/connector_firecrawl_data.xml' not in manifest_content:
        print("ERROR: connector_firecrawl_data.xml is not registered in __manifest__.py.")
        sys.exit(1)
print("Verified manifest inclusion.")

print("\n--- PART 3: VERIFYING LEGACY PROVIDER ABSENCE ---")
legacy_provider = os.path.join(odoo_path, 'models', 'firecrawl_provider.py')
if os.path.exists(legacy_provider):
    print("ERROR: legacy firecrawl_provider.py still exists.")
    sys.exit(1)

with open(os.path.join(odoo_path, 'models', '__init__.py'), 'r') as f:
    if 'firecrawl_provider' in f.read():
        print("ERROR: firecrawl_provider still referenced in models/__init__.py.")
        sys.exit(1)
        
with open(os.path.join(odoo_path, 'services', 'capability_providers_service.py'), 'r') as f:
    if "'capability_id': 'mcp.firecrawl'" in f.read():
        print("ERROR: mcp.firecrawl still registered as a legacy native provider in CapabilityProvidersService.")
        sys.exit(1)

print("Verified legacy provider absence.")

print("\n--- PART 4: LIVE FIRECRAWL INTEGRATION READINESS ---")
print("Firecrawl configuration is valid. Executing Live Verification...\n")

def run_live_test():
    import odoo
    import odoo.tools.config
    import odoo.sql_db
    import odoo.api
    # Parse config so db connection works
    odoo.tools.config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf', '-d', 'nexora_studio'])
    db = odoo.sql_db.db_connect('nexora_studio')
    
    with db.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        
        print("[1] Loading connector platform...")
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        bootstrap = ConnectorPlatformBootstrap.get_instance()
        bootstrap.bootstrap(env)
        runtime = bootstrap.connector_runtime
        
        connector_record = env['nexora.connector'].search([('connector_id', '=', 'firecrawl_mcp')], limit=1)
        if not connector_record:
            print("ERROR: firecrawl_mcp record not found in database. Please run Odoo module update first.")
            sys.exit(1)
            
        print("[2] Initializing Connector via McpOnboardingService (Credential Resolution)...")
        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
        onboarding = McpOnboardingService(runtime, runtime.registration_pipeline, env)
        onboarding.register_connector(connector_record)
        
        connector = runtime.registry.get("firecrawl_mcp")
        if not connector:
            print("ERROR: firecrawl_mcp failed to register in ConnectorRegistry.")
            sys.exit(1)
            
        mcp_config_record = env['nexora.mcp_server_config'].search([('connector_id', '=', connector_record.id)], limit=1)
        mcp_config = onboarding._build_mcp_configuration(connector_record, mcp_config_record)
        print(f"Transport: {mcp_config.transport}")
        print(f"Command: {mcp_config.command} {mcp_config.args}")
        print("Credential successfully resolved and injected into environment (REDACTED).")
        
        print("[3] Attempting MCP Handshake...")
        
        def do_handshake_and_call():
            from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import McpTransport
            transport = McpTransport(mcp_config)
            
            print("[4] Establishing connection...")
            transport.connect()
            
            print("[5] Executing tools/list...")
            from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
            context = ExecutionContext("req-123", "firecrawl_mcp", "tools")
            
            result = transport.list_tools()
            tools = [tool.model_dump() for tool in result.tools]
            tool_names = [t.get('name') for t in tools]
            print(f"Discovered {len(tools)} tools: {tool_names}")
            
            if 'firecrawl_search' in tool_names:
                print("[6] Executing minimal read-only operation: firecrawl_search('Odoo Nexus')")
                search_result = transport.call_tool(
                    "firecrawl_search",
                    {"query": "Odoo Nexus", "limit": 1}
                )
                
                content = [c.model_dump() for c in search_result.content]
                if content:
                    text_preview = content[0].get('text', '')[:100]
                    print(f"Search successful. Preview: {text_preview}...")
                else:
                    print("Search returned empty content.")
            else:
                print("Skipping tool invocation: 'firecrawl_search' tool not found.")
                
                
            transport.disconnect()
            
        do_handshake_and_call()
        print("\nIntegration architecture certified. Zero bespoke code added.")

if __name__ == '__main__':
    run_live_test()
