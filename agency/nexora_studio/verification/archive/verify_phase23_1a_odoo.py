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
                'mcp.github': [CapabilityManifest('mcp.github', 'GitHub API', ExecutionTargetType.LOCAL, '1.0', [], {}, {}, {'provider': 'github'})],
                'mcp.playwright': [CapabilityManifest('mcp.playwright', 'Playwright', ExecutionTargetType.LOCAL, '1.0', [], {}, {}, {'provider': 'microsoft'})],
            }

    repo = CanonicalRepository(env)
    
    class ToolRegistryWrapper:
        def __init__(self, e):
            self.env = e
        def resolve_tool(self, tool_id):
            if tool_id == 'mcp.playwright':
                return (self.env['nexora.provider.playwright'], None)
            if tool_id == 'mcp.github':
                return (self.env['nexora.provider.github'], None)
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

    # 1. GitHub
    print("\n[PART 2] EXECUTING GITHUB PROVIDER (mcp.github)")
    print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> GitHubProvider -> McpRuntimeManager")
    start = time.time()
    try:
        res_github = router.execute("mcp.github", {"args": {"query": "python"}})
        end = time.time()
        print(f"Latency: {(end - start) * 1000:.2f}ms")
        print(f"Execution Target: {res_github.logs[0] if res_github.logs else 'Unknown'}")
        print(f"Success: {res_github.success}")
        print(f"Payload: {json.dumps(res_github.result, indent=2)}")
    except Exception as e:
        print(f"GitHub Execution Failed: {e}")

    # 2. Playwright
    print("\n[PART 3] EXECUTING PLAYWRIGHT PROVIDER (mcp.playwright)")
    print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> PlaywrightProvider -> ExecutionSandboxService")
    start = time.time()
    try:
        res_playwright = router.execute("mcp.playwright", {"args": {"action": "snapshot", "url": "https://example.com"}})
        end = time.time()
        print(f"Latency: {(end - start) * 1000:.2f}ms")
        print(f"Execution Target: {res_playwright.logs[0] if res_playwright.logs else 'Unknown'}")
        print(f"Success: {res_playwright.success}")
        print(f"Payload: {json.dumps(res_playwright.result, indent=2)}")
    except Exception as e:
        print(f"Playwright Execution Failed: {e}")

if __name__ == '__main__':
    run_verification()

