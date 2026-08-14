# -*- coding: utf-8 -*-
"""
Phase 23.11 Architecture Remediation End-to-End Validation
Proves the following pipeline:
CapabilityDiscoveryService
→ Capability Registry
→ CapabilityRepository
→ CapabilityResolver
→ UniversalCapabilityRouter
→ Executor
→ Provider
→ External Tool
→ Response
"""
import sys
import os

# Setup Odoo path
sys.path.append(r'D:\ODOO\community\odoo')
import odoo
import odoo.tools
import odoo.cli.server
import odoo.service.server

if __name__ == "__main__":
    odoo.tools.config.parse_config(['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])
    odoo.service.server.start(preload=['nexora_studio'], stop=True)
    import odoo.modules.registry
    registry = odoo.modules.registry.Registry('nexora_studio')
    
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        print("\n--- PHASE 23.11 REMEDIATION VERIFICATION ---\n")
        
        # 0. Clean registry for fresh discovery
        env['nexora.capability_registry'].search([]).unlink()
        
        # 1. CapabilityDiscoveryService -> Registry
        print("[1] Executing CapabilityDiscoveryService (Simulating ir.cron / post_init_hook)...")
        discovery_service = env['nexora.capability_discovery_service']
        discovered_count = discovery_service.execute_discovery()
        print(f"    [OK] Discovery executed. {discovered_count} manifests processed.")
        
        # 2. Capability Registry Verification
        registry_count = env['nexora.capability_registry'].search_count([])
        print(f"[2] Validating Capability Registry ORM...")
        print(f"    [OK] Registry populated with {registry_count} total capabilities.")
        
        if registry_count == 0:
            print("    [FAIL] Registry is empty. Aborting.")
            sys.exit(1)
            
        # 3. Full UCEL Pipeline Verification (Repository -> Resolver -> Router -> Executor)
        print("[3] Booting GenerationRuntime to verify UCEL pipeline execution...")
        from odoo.addons.nexora_studio.services.generation.core.generation_runtime import GenerationRuntime
        
        # Create a mock builder configuration first
        config = env['nexora.builder_configuration'].create({
            'name': 'E2E Config',
            'description': 'Test config'
        })
        
        # Create a mock builder session
        session = env['nexora.builder_session'].create({
            'name': 'E2E Verification Session',
            'status': 'running',
            'builder_configuration_id': config.id,
            'target_workspace_path': os.path.join(os.environ.get('TEMP', '/tmp'), 'nexora_test_workspace')
        })
        os.makedirs(session.target_workspace_path, exist_ok=True)
        
        # Mock Context & Dependencies for GenerationRuntime
        class MockEventBus:
            def publish(self, *args, **kwargs): pass
            def subscribe(self, *args, **kwargs): pass
            def emit(self, *args, **kwargs): pass
            
        class MockStateManager:
            def update_stage(self, *args, **kwargs): pass
            
        class MockAIProviderManager:
            pass
                
        runtime = GenerationRuntime(
            ai_provider_manager=MockAIProviderManager(),
            workspace_path=session.target_workspace_path,
            event_bus=MockEventBus(),
            state_manager=MockStateManager(),
            session_id=str(session.id),
            generation_id="e2e-gen-001"
        )
        
        # We also need a context mock for patch_engine etc if we were to test it fully
        class MockContext:
            def __init__(self, session, runtime):
                self.builder_session = session
                self.workspace_path = session.target_workspace_path
                self._data = {'generation_runtime': runtime}
            def get(self, key): return self._data.get(key)
            def set(self, key, value): self._data[key] = value
            
        context = MockContext(session, runtime)
        
        # Inject env into repository and local executor since we are outside an HTTP request context
        runtime.capability_repository.env = env
        runtime.tool_registry = env['nexora.tool_registry']
        # Also need to update the executor inside UniversalCapabilityRouter
        from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType
        local_executor = runtime.ucel_router.executors.get(ExecutionTargetType.LOCAL)
        if local_executor:
            local_executor.tool_registry = runtime.tool_registry
        
        print("    [OK] GenerationRuntime booted successfully.")
        
        # 4. Executor -> Provider -> External Tool -> Response
        print("[4] Routing 'echo' command through UniversalCapabilityRouter via mcp.tool.terminal...")
        
        try:
            result = runtime.tools.execute("mcp.tool.terminal", {
                "tool_id": "mcp.tool.terminal",
                "args": {
                    "command": "echo E2E_VERIFICATION_SUCCESS",
                    "cwd": context.workspace_path
                }
            }, runtime)
            
            # Print raw result for forensic visibility
            print(f"    Raw CapabilityResult: {result}")
            
            if hasattr(result, 'to_dict'):
                print(f"    ToolResult Dict: {result.to_dict()}")
                
            if hasattr(result, 'stdout'):
                out_str = result.stdout
            elif isinstance(result, list) and len(result) > 0 and 'text' in result[0]:
                out_str = result[0]['text'].strip()
            elif isinstance(result, dict) and 'stdout' in result:
                out_str = result['stdout'].strip()
            elif isinstance(result, str):
                out_str = result.strip()
            else:
                out_str = str(result)
                
            if "E2E_VERIFICATION_SUCCESS" in out_str:
                print("    [OK] Complete UCEL routing verified: Runtime -> Router -> Local Executor -> TerminalTool.")
                print("    [OK] SUCCESS: Complete architectural pipeline verified.")
            else:
                print(f"    [FAIL] Command did not return expected output. Output: {out_str}")
        except Exception as e:
            print(f"\n    [FAIL] during execution routing: {str(e)}")
            import traceback
            traceback.print_exc()
            
        print("\n--------------------------------------------\n")
