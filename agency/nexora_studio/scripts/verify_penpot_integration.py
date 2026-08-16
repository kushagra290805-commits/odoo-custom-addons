# -*- coding: utf-8 -*-
import sys
import os

def run_integration_test():
    print("==================================================")
    print("PENPOT MCP INTEGRATION TEST")
    print("==================================================")
    
    endpoint = os.environ.get('PENPOT_ENDPOINT')
    if not endpoint:
        print("BLOCKED: PENPOT_ENDPOINT environment variable is required.")
        sys.exit(1)
        
    print(f"Testing against endpoint: {endpoint}")
    
    # Locate connector
    connector = env['nexora.connector'].search([('connector_id', '=', 'penpot_mcp')], limit=1)
    if not connector:
        print("BLOCKED: penpot_mcp connector not found.")
        sys.exit(1)
        
    config = env['nexora.mcp_server_config'].search([('connector_id', '=', connector.id)], limit=1)
    if not config:
        print("BLOCKED: mcp_server_config not found.")
        sys.exit(1)
        
    # Temporarily apply endpoint for test
    orig_endpoint = config.command
    config.command = endpoint
    
    from odoo.addons.nexora_studio.services.connector.onboarding.connection_tester import McpConnectionTester
    from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService

    def onboarding_factory(rt, pipeline, e):
        return McpOnboardingService(rt, pipeline, e)

    tester = McpConnectionTester(
        onboarding_service_factory=onboarding_factory,
        odoo_env=env,
    )
    
    result = tester.test(connector)
    
    # Restore original endpoint
    config.command = orig_endpoint
    
    if result.success:
        print(f"Integration Test: PASS (Latency: {result.latency_ms}ms, Tools: {result.tool_count})")
        sys.exit(0)
    else:
        print(f"Integration Test: FAIL ({result.error_message})")
        sys.exit(1)

if __name__ == '__main__':
    run_integration_test()
