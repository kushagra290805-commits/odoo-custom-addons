import sys
import json
import time

def run_verification():
    print("--- PHASE 23.1A: END-TO-END PROVIDER EXECUTION VERIFICATION ---")
    
    from odoo.addons.nexora_studio.services.capabilities.router import UniversalCapabilityRouter
    from odoo.addons.nexora_studio.services.capabilities.resolver import CapabilityResolver
    from odoo.addons.nexora_studio.services.capabilities.repository import CapabilityRepository
    from odoo.addons.nexora_studio.services.capabilities.policy import CapabilityPolicyEngine
    from odoo.addons.nexora_studio.services.capabilities.security import SecurityLayer
    from odoo.addons.nexora_studio.services.capabilities.middleware import MiddlewarePipeline
    from odoo.addons.nexora_studio.services.capabilities.scheduler import ExecutionScheduler
    from odoo.addons.nexora_studio.services.capabilities.strategy import ExecutionStrategy
    from odoo.addons.nexora_studio.services.capabilities.executors.local import LocalToolExecutor
    from odoo.addons.nexora_studio.services.capabilities.executors.remote import RemoteToolExecutor
    from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType
    print(f"Number of models in env: {len(env.registry.models)}")
    if 'nexora.execution_sandbox_service' not in env:
        print("WARNING: nexora.execution_sandbox_service is NOT in env!")
        print("Attempting to dynamically load it...")
        from odoo.addons.nexora_studio.services.execution_sandbox_service import ExecutionSandboxService
        # Add to registry manually for testing
        env.registry.models['nexora.execution_sandbox_service'] = ExecutionSandboxService
        # We need to build it
        ExecutionSandboxService._build_model(env.registry, env.cr)

    # Force repo cache to route to LOCAL just like canonical environment would if local is preferred.
    class CanonicalRepository(CapabilityRepository):

        def __init__(self, env):
            super().__init__(env=env)
            from odoo.addons.nexora_studio.services.capabilities.models import CapabilityManifest
            self._cache = {
                'mcp.context7': [CapabilityManifest('mcp.context7', 'Context7 Documentation', ExecutionTargetType.LOCAL, '1.0', [], {}, {}, {'provider': 'upstash'})],
            }

    repo = CanonicalRepository(env)
    
    class ToolRegistryWrapper:
        def __init__(self, e):
            self.env = e
        def resolve_tool(self, tool_id):
            if tool_id == 'mcp.context7':
                return (self.env['nexora.provider.context7'], None)
            return None

    tool_registry = ToolRegistryWrapper(env)
    
    class MockTransport:
        def send(self, payload):
            return {"results": ["Should not be called if executed locally."]}
            
    executors = {
        ExecutionTargetType.LOCAL: LocalToolExecutor(tool_registry),
        ExecutionTargetType.REMOTE: RemoteToolExecutor(MockTransport())
    }

    resolver = CapabilityResolver(repo)
    policy = CapabilityPolicyEngine()
    sec = SecurityLayer()
    mid = MiddlewarePipeline()
    sched = ExecutionScheduler(ExecutionStrategy())

    router = UniversalCapabilityRouter(resolver, policy, sec, mid, sched, executors)

    # 1. Context7
    print("\n[PART 2] EXECUTING CONTEXT7 PROVIDER (mcp.context7)")
    print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> Context7Provider -> McpRuntimeManager")
    start = time.time()
    try:
        # Give the event loop time to boot the MCP Server
        print("Waiting 10s for MCP Server to start and connect...")
        time.sleep(10)
        
        # Resolving library ID
        print("Executing: resolve-library-id")
        payload = {
            "mcp_tool": "resolve-library-id",
            "libraryName": "react"
        }
        res_context7 = router.execute("mcp.context7", {"args": payload})
        end = time.time()
        print(f"Latency: {(end - start) * 1000:.2f}ms")
        print(f"Execution Target: {res_context7.logs[0] if res_context7.logs else 'Unknown'}")
        print(f"Success: {res_context7.success}")
        print(f"Payload: {json.dumps(res_context7.result, indent=2)}")
        
        # Query Docs
        print("\nExecuting: query-docs")
        payload2 = {
            "mcp_tool": "query-docs",
            "libraryId": "facebook/react",
            "query": "useEffect hook"
        }
        res_context7_2 = router.execute("mcp.context7", {"args": payload2})
        print(f"Success: {res_context7_2.success}")
        if res_context7_2.success and 'data' in res_context7_2.result[0] and res_context7_2.result[0]['data'].get('status') == 'success':
            # truncate output
            content = str(res_context7_2.result[0]['data'].get('content', ''))
            print(f"Docs retrieved! Length: {len(content)}. Preview: {content[:200]}...")
        else:
            print(f"Payload: {json.dumps(res_context7_2.result, indent=2)}")
            
    except Exception as e:
        print(f"Context7 Execution Failed: {e}")

if __name__ == '__main__':
    run_verification()

