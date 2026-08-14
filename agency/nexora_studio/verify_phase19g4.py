import os
import sys

def verify():
    print("Starting Phase 19G.4 Validation Suite...")
    
    print("1. Verifying MCP Protocol Adapter Registration...")
    if 'nexora.mcp_protocol_adapter' not in env:
        print("ERROR: MCP Protocol Adapter not registered.")
        sys.exit(1)
    adapter = env['nexora.mcp_protocol_adapter']
        
    print("2. Verifying Protocol Serialization Contract...")
    internal_id = 'mcp.tool.workspace'
    legacy_id = 'workspace'
    
    translated_external = adapter.serialize_tool_id(internal_id)
    if translated_external != legacy_id:
        print(f"ERROR: Serialization failed. Expected {legacy_id}, got {translated_external}")
        sys.exit(1)
        
    translated_internal = adapter.deserialize_tool_id(legacy_id)
    if translated_internal != internal_id:
        print(f"ERROR: Deserialization failed. Expected {internal_id}, got {translated_internal}")
        sys.exit(1)
        
    print("3. Verifying Workspace Tool Registration...")
    if 'nexora.tool.workspace' not in env:
        print("ERROR: Canonical Workspace Tool not registered.")
        sys.exit(1)
    workspace_tool = env['nexora.tool.workspace']

        
    meta = workspace_tool.metadata()
    if meta['capability_code'] != 'mcp.tool.workspace':
        print(f"ERROR: Incorrect capability code: {meta['capability_code']}")
        sys.exit(1)
        
    print("4. Verifying Tool Execution & Fallback Gaps...")
    
    # Create mock session
    workspace = env['nexora.workspace'].create({
        'name': 'MCP Test Workspace'
    })
    
    config = env['nexora.builder_configuration'].create({
        'name': 'MCP Test Config',
        'status': 'locked'
    })
    
    session = env['nexora.builder_session'].create({
        'name': 'MCP Verification Session',
        'builder_configuration_id': config.id,
        'workspace_id': workspace.id
    })
    
    # Test 'get_path'
    res_path = workspace_tool.execute(session, 'get_path')
    if res_path.get('status') != 'success' or 'path' not in res_path:
        print("ERROR: get_path failed to return path.")
        sys.exit(1)
    print(f"   get_path successfully returned: {res_path.get('path')}")
        
    # Test unsupported command fallback ('status' from legacy test)
    res_status = workspace_tool.execute(session, 'status')
    if res_status.get('status') != 'success' or res_status.get('message') != 'Executed workspace status.':
        print(f"ERROR: Fallback command failed. Got: {res_status}")
        sys.exit(1)
    print("   unsupported command correctly triggered fallback.")

    print("5. Verifying ToolRegistry Integration...")
    # Manually register the capability for testing
    existing = env['nexora.capability_registry'].search([('capability_code', '=', 'mcp.tool.workspace')])
    if not existing:
        # Use simple string literal since RuntimeEvents has missing constants
        env['nexora.capability_registry'].create({
            'capability_id': 'workspace-tool-v1',
            'capability_code': 'mcp.tool.workspace',
            'display_name': 'Workspace Tool',
            'category': 'tool',
            'version': '1.0.0',
            'implementation_model': 'nexora.tool.workspace',
            'priority': 10,
            'checksum': 'dummy_hash',
            'state': 'capability.enabled'  # This maps to CAPABILITY_ENABLED
        })
    else:
        existing.write({'state': 'capability.enabled'})
    
    # Refresh cache
    env['nexora.capability_cache_service'].invalidate_cache()
    registry_tools = env['nexora.tool_registry'].get_registered_tools()

    tool_codes = [t.get('tool_type') for t in registry_tools if t.get('tool_type')]
    
    if 'mcp.tool.workspace' not in tool_codes:
        print("ERROR: workspace_tool not discovered by CapabilityCacheService.")
        sys.exit(1)
        
    # Test list serialization
    external_tools = adapter.serialize_registered_tools(registry_tools)
    if 'workspace' not in external_tools:
        print("ERROR: MCP Protocol Adapter failed to serialize registered tools list.")
        sys.exit(1)
        
    print("All standalone Phase 19G.4 validation gates passed successfully.")

if __name__ == '__main__':
    verify()
