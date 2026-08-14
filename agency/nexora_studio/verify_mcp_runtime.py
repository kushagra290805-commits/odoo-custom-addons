import os
import sys

def verify():
    print("Starting MCP Runtime Verification Suite...")
    
    # Check plugin registry
    print("Verifying MCP plugin registry...")
    mcp_service = env['nexora.mcp_service']
    manifest = mcp_service.plugin_manifest()
    if manifest['runtime_type'] != 'mcp':
        print("ERROR: Invalid runtime_type in manifest.")
        sys.exit(1)
        
    print("Verifying Tool Registration...")
    
    # Manually register the capability for testing
    existing = env['nexora.capability_registry'].search([('capability_code', '=', 'mcp.tool.workspace')])
    if not existing:
        env['nexora.capability_registry'].create({
            'capability_id': 'workspace-tool-v1',
            'capability_code': 'mcp.tool.workspace',
            'display_name': 'Workspace Tool',
            'category': 'tool',
            'version': '1.0.0',
            'implementation_model': 'nexora.tool.workspace',
            'priority': 10,
            'checksum': 'dummy_hash',
            'state': 'capability.enabled'
        })
    else:
        existing.write({'state': 'capability.enabled'})
    env['nexora.capability_cache_service'].invalidate_cache()
    
    # Fetch from ToolRegistry instead of legacy mcp_registry
    tools = env['nexora.tool_registry'].get_registered_tools()
    
    # Serialize the tool IDs for legacy compatibility layer check
    adapter = env['nexora.mcp_protocol_adapter']
    tool_ids = adapter.serialize_registered_tools(tools)
    print(f"Registered tools (Serialized): {tool_ids}")
    
    # Just verify workspace is in there since we migrated it
    if 'workspace' not in tool_ids:
        print("ERROR: Missing workspace tool in registry.")
        sys.exit(1)
        
    # Setup mock session
    print("Creating mock builder session for MCP test...")
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
    
    print("Starting Runtimes...")
    session.action_start_runtime()
    
    print("Verifying Dependency Graph...")
    session_service = env['nexora.builder_session_service']
    plan = session_service.get_execution_plan(session)
    order = plan.get('startup', [])
    print(f"Startup Order: {order}")
    
    if order.index('workspace') > order.index('mcp') or order.index('git') > order.index('mcp') or order.index('ide') > order.index('mcp'):
        print("ERROR: MCP started before Workspace, Git, or IDE.")
        sys.exit(1)
        
    if order.index('mcp') > order.index('preview'):
        print("ERROR: MCP started after Preview.")
        sys.exit(1)
        
    print("Verifying MCP Startup...")
    mcp_runtime = env['nexora.runtime'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'mcp')], limit=1)
    if not mcp_runtime:
        print("ERROR: MCP Runtime not created.")
        sys.exit(1)
        
    if mcp_runtime.status != 'running' or mcp_runtime.health != 'healthy':
        print(f"ERROR: MCP Runtime in invalid state: {mcp_runtime.status}/{mcp_runtime.health}")
        events = env['nexora.runtime_event'].search([('builder_session_id', '=', session.id)])
        for e in events:
            print(f"EVENT {e.runtime_type} {e.event_type}: {e.message}")
        sys.exit(1)
        
    print("Verifying Builder Session MCP Metadata...")
    # Force recompute
    session._compute_mcp_metadata()
    if session.mcp_status != 'running' or session.mcp_server_state != 'online':
        print(f"ERROR: Builder Session MCP metadata out of sync: {session.mcp_status}/{session.mcp_server_state}")
        sys.exit(1)
        
    print("Verifying Tool Executions...")
    for legacy_t_id in ['filesystem', 'git', 'workspace', 'preview']:
        if legacy_t_id == 'workspace':
            # Use new ToolRegistry execution flow with translated ID
            internal_id = env['nexora.mcp_protocol_adapter'].deserialize_tool_id(legacy_t_id)
            res = env['nexora.tool_registry'].execute_tool(internal_id, session, command='status')
        else:
            model_name = f'nexora.mcp_tool_{legacy_t_id}'
            res = env[model_name].execute(session, 'status')
            
        if res.get('status') != 'success':
            print(f"ERROR: Tool {legacy_t_id} execution failed.")
            sys.exit(1)
            
    print("Verifying Event Timeline...")
    events = env['nexora.runtime_event'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'mcp')])
    event_types = [e.event_type for e in events]
    print(f"MCP Events: {event_types}")
    if 'mcp.started' not in event_types:
        print("ERROR: mcp.started event not found.")
        sys.exit(1)
        
    print("Verifying Reconnect/Refresh...")
    mcp_service.refresh_runtime(mcp_runtime)
    if mcp_runtime.health != 'healthy':
        print("ERROR: MCP Runtime refresh failed.")
        sys.exit(1)
        
    print("Verifying Recovery (Simulated Crash)...")
    mcp_runtime.status = 'error'
    session.action_recover_session()
    if mcp_runtime.status != 'running':
        print("ERROR: MCP Runtime did not recover.")
        sys.exit(1)
        
    print("Verifying Shutdown (Reverse Order)...")
    session.action_stop_runtime()
    if mcp_runtime.status != 'stopped':
        print("ERROR: MCP Runtime did not stop.")
        sys.exit(1)
        
    events = env['nexora.runtime_event'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'mcp')])
    if 'mcp.stopped' not in [e.event_type for e in events]:
        print("ERROR: mcp.stopped event not found.")
        sys.exit(1)
        
    print("Verification suite passed successfully.")

if __name__ == '__main__':
    verify()
