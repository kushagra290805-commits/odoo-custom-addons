"""Quick script to discover what tools tavily_mcp actually exposes."""

def discover_tavily_tools():
    from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
    bootstrap = ConnectorPlatformBootstrap.get_instance()
    bootstrap.bootstrap(env)
    runtime = bootstrap.connector_runtime

    from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
    from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionRequest, ConnectorRuntimeContext

    onboarding = McpOnboardingService(runtime, runtime.registration_pipeline, env)
    record = env['nexora.connector'].search([('connector_id', '=', 'tavily_mcp')], limit=1)
    onboarding.deregister_connector('tavily_mcp')
    onboarding.register_connector(record)

    ctx = ConnectorRuntimeContext(connector_id='tavily_mcp', session_id='discover_tools')
    req = ConnectorExecutionRequest(capability_namespace='tools.list', context=ctx, timeout_seconds=30.0)
    result = runtime.dispatcher.dispatch(req)
    print("tools.list success:", result.success)
    if result.success and result.data:
        tools = result.data.get('tools', [])
        for t in tools:
            print(f"  Tool: {t.get('name')} — {t.get('description', '')[:60]}")
    else:
        print("Error:", result.error)

if __name__ == '__main__':
    discover_tavily_tools()
