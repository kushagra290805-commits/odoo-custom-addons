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
                'mcp.context7': [CapabilityManifest('mcp.context7', 'Context7 Documentation', ExecutionTargetType.LOCAL, '1.0', [], {}, {}, {'provider': 'upstash'})],
                'mcp.tavily': [CapabilityManifest('mcp.tavily', 'Tavily Web Research', ExecutionTargetType.LOCAL, '1.0', [], {}, {}, {'provider': 'tavily'})],
                'mcp.firecrawl': [CapabilityManifest('mcp.firecrawl', 'Firecrawl Web Extraction', ExecutionTargetType.LOCAL, '1.0', [], {}, {}, {'provider': 'firecrawl'})],
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
            if tool_id == 'mcp.context7':
                return (self.env['nexora.provider.context7'], None)
            if tool_id == 'mcp.tavily':
                return (self.env['nexora.provider.tavily'], None)
            if tool_id == 'mcp.firecrawl':
                return (self.env['nexora.provider.firecrawl'], None)
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
    
    # Bootstrap the platform so MCP servers start booting in the background
    print("Bootstrapping PlatformRuntime...")
    env['nexora_studio.platform'].get_runtime()

    # Give the event loop time to boot the docker container. We should wait 10 seconds.
    print("Waiting 10s for MCP Servers to start and connect...")
    time.sleep(10)

    # 1. GitHub
    print("\n[PART 2] EXECUTING GITHUB PROVIDER (mcp.github)")
    print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> GitHubProvider -> McpRuntimeManager")
    start = time.time()
    try:
        # Searching repository metadata
        payload = {
            "mcp_tool": "search_repositories",
            "query": "repo:odoo/odoo"
        }
        res_github = router.execute("mcp.github", {"args": payload})
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
        if res_playwright.success and 'data' in res_playwright.result[0]:
             # truncate screenshot for output
             data = res_playwright.result[0]['data']
             print(f"Title: {data.get('title')}")
             print(f"URL: {data.get('url')}")
             print(f"Content Length: {data.get('content_length')}")
             print(f"Screenshot Base64 Prefix: {data.get('screenshot_base64_prefix')}")
             
        else:
             print(f"Payload: {json.dumps(res_playwright.result, indent=2)}")
    except Exception as e:
        print(f"Playwright Execution Failed: {e}")

    # 3. Context7
    print("\n[PART 4] EXECUTING CONTEXT7 PROVIDER (mcp.context7)")
    print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> Context7Provider -> McpRuntimeManager")
    start = time.time()
    try:
        # Resolving library ID
        print("Executing: resolve-library-id")
        payload = {
            "mcp_tool": "resolve-library-id",
            "query": "react"
        }
        res_context7 = router.execute("mcp.context7", {"args": payload})
        end = time.time()
        print(f"Latency: {(end - start) * 1000:.2f}ms")
        print(f"Execution Target: {res_context7.logs[0] if res_context7.logs else 'Unknown'}")
        print(f"Success: {res_context7.success}")
        print(f"Payload: {json.dumps(res_context7.result, indent=2)}")
    except Exception as e:
        print(f"Context7 Execution Failed: {e}")

    # 4. Tavily
    print("\n[PART 5] EXECUTING TAVILY PROVIDER (mcp.tavily)")
    print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> TavilyProvider -> McpRuntimeManager")
    start = time.time()
    try:
        print("Executing: tavily_search")
        payload = {
            "mcp_tool": "tavily_search",
            "query": "artificial intelligence"
        }
        res_tavily = router.execute("mcp.tavily", {"args": payload})
        end = time.time()
        print(f"Latency: {(end - start) * 1000:.2f}ms")
        print(f"Execution Target: {res_tavily.logs[0] if res_tavily.logs else 'Unknown'}")
        print(f"Success: {res_tavily.success}")
        print(f"Payload: {json.dumps(res_tavily.result, indent=2)}")
    except Exception as e:
        print(f"Tavily Execution Failed: {e}")

    # 5. Firecrawl
    print("\n[PART 6] EXECUTING FIRECRAWL PROVIDER (mcp.firecrawl)")
    print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> FirecrawlProvider -> McpRuntimeManager")
    start = time.time()
    try:
        print("Executing: firecrawl_scrape")
        payload = {
            "mcp_tool": "firecrawl_scrape",
            "url": "https://example.com"
        }
        res_firecrawl = router.execute("mcp.firecrawl", {"args": payload})
        end = time.time()
        print(f"Latency: {(end - start) * 1000:.2f}ms")
        print(f"Execution Target: {res_firecrawl.logs[0] if res_firecrawl.logs else 'Unknown'}")
        print(f"Success: {res_firecrawl.success}")
        # Truncate content for logging if successful
        if res_firecrawl.success and res_firecrawl.result and 'data' in res_firecrawl.result[0]:
            try:
                # The data might be an array or string
                data = res_firecrawl.result[0]['data']
                print(f"Firecrawl scrape successful. Output keys/length: {len(str(data))}")
            except Exception:
                print(f"Payload: {json.dumps(res_firecrawl.result, indent=2)}")
        else:
            print(f"Payload: {json.dumps(res_firecrawl.result, indent=2)}")
    except Exception as e:
        print(f"Firecrawl Execution Failed: {e}")

if __name__ == '__main__':
    run_verification()

