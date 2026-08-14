import sys
import os
import types
import json
import time

# Create a fake odoo namespace to satisfy imports
odoo = types.ModuleType('odoo')
sys.modules['odoo'] = odoo
tools = types.ModuleType('tools')
tools.config = {}
sys.modules['odoo.tools'] = tools

exceptions = types.ModuleType('exceptions')
class ValidationError(Exception): pass
class UserError(Exception): pass
exceptions.ValidationError = ValidationError
exceptions.UserError = UserError
sys.modules['odoo.exceptions'] = exceptions

fields = types.ModuleType('fields')
class DummyField:
    def __init__(self, *args, **kwargs): pass
    def __call__(self, *args, **kwargs): return self
    @classmethod
    def now(cls): return "2026-08-03"

class FieldModule(types.ModuleType):
    def __getattr__(self, name):
        return DummyField
        
fields = FieldModule('fields')
sys.modules['odoo.fields'] = fields

odoo._ = lambda x: x
sys.modules['odoo'].fields = fields
sys.modules['odoo']._ = odoo._

models = types.ModuleType('models')
class DummyModel:
    _name = "dummy"
    def __init__(self, env=None):
        self.env = env or {}
models.AbstractModel = DummyModel
sys.modules['odoo.models'] = models

api = types.ModuleType('api')
api.model = lambda f: f
sys.modules['odoo.api'] = api

import logging
logging.basicConfig(level=logging.INFO)

# Dynamically load the providers bypassing models/__init__.py
studio_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if studio_path not in sys.path:
    sys.path.insert(0, studio_path)

def load_class_from_file(filepath, classname):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dynamic_module", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, classname)

GitHubProvider = load_class_from_file(os.path.join(studio_path, 'models', 'github_provider.py'), 'GitHubProvider')
PlaywrightProvider = load_class_from_file(os.path.join(studio_path, 'models', 'playwright_provider.py'), 'PlaywrightProvider')

from services.execution_sandbox_service import ExecutionSandboxService
from services.capabilities.models import CapabilityManifest, ExecutionTargetType
from services.capabilities.router import UniversalCapabilityRouter
from services.capabilities.resolver import CapabilityResolver
from services.capabilities.repository import CapabilityRepository
from services.capabilities.policy import CapabilityPolicyEngine
from services.capabilities.security import SecurityLayer
from services.capabilities.middleware import MiddlewarePipeline
from services.capabilities.scheduler import ExecutionScheduler
from services.capabilities.strategy import ExecutionStrategy
from services.capabilities.executors.local import LocalToolExecutor
from services.capabilities.executors.remote import RemoteToolExecutor

print("--- PHASE 23.1A: END-TO-END PROVIDER EXECUTION VERIFICATION ---")

sandbox = ExecutionSandboxService(None) # Sandbox is AbstractModel, pass None for env

env = {
    'nexora.execution_sandbox_service': sandbox,
}

github_provider = GitHubProvider(env)
playwright_provider = PlaywrightProvider(env)

class MockToolRegistry:
    def resolve_tool(self, tool_id):
        if tool_id == 'mcp.playwright':
            return (playwright_provider, None)
        if tool_id == 'mcp.github':
            return (github_provider, None)
        return None

tool_registry = MockToolRegistry()

class CanonicalRepository(CapabilityRepository):
    def __init__(self):
        super().__init__(env=None)
        self._cache = {
            'mcp.github': [CapabilityManifest('mcp.github', 'GitHub API', ExecutionTargetType.LOCAL, '1.0', [], {}, {}, {'provider': 'github'})],
            'mcp.playwright': [CapabilityManifest('mcp.playwright', 'Playwright', ExecutionTargetType.LOCAL, '1.0', [], {}, {}, {'provider': 'microsoft'})],
        }

class MockTransport:
    def send(self, payload):
        return {"results": ["Should not be called if executed locally."]}

repo = CanonicalRepository()
resolver = CapabilityResolver(repo)
policy = CapabilityPolicyEngine()
sec = SecurityLayer()
mid = MiddlewarePipeline()
sched = ExecutionScheduler(ExecutionStrategy())

executors = {
    ExecutionTargetType.LOCAL: LocalToolExecutor(tool_registry),
    ExecutionTargetType.REMOTE: RemoteToolExecutor(MockTransport())
}

router = UniversalCapabilityRouter(resolver, policy, sec, mid, sched, executors)

# We must map odoo.addons.nexora_studio because GitHubProvider uses it to import MCP stuff
sys.modules['odoo.addons'] = types.ModuleType('addons')
sys.modules['odoo.addons.nexora_studio'] = types.ModuleType('nexora_studio')
import services
sys.modules['odoo.addons.nexora_studio'].services = services
sys.modules['odoo.addons.nexora_studio.services'] = services
sys.modules['odoo.addons.nexora_studio.services.runtime'] = __import__('services.runtime').runtime

# Execute GitHub
print("\n[PART 2] EXECUTING GITHUB PROVIDER (mcp.github)")
print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> GitHubProvider -> McpRuntimeManager")
start = time.time()
try:
    res_github = router.execute("mcp.github", {"query": "python"})
    end = time.time()
    print(f"Latency: {(end - start) * 1000:.2f}ms")
    print(f"Execution Target: {res_github.logs[0] if res_github.logs else 'Unknown'}")
    print(f"Success: {res_github.success}")
    print(f"Payload: {json.dumps(res_github.result, indent=2)}")
except Exception as e:
    print(f"GitHub Execution Failed: {e}")

# Execute Playwright
print("\n[PART 3] EXECUTING PLAYWRIGHT PROVIDER (mcp.playwright)")
print("Tracing Path: Router -> Resolver -> Repository -> LocalToolExecutor -> PlaywrightProvider -> ExecutionSandboxService")
start = time.time()
try:
    res_playwright = router.execute("mcp.playwright", {"action": "snapshot", "url": "https://example.com"})
    end = time.time()
    print(f"Latency: {(end - start) * 1000:.2f}ms")
    print(f"Execution Target: {res_playwright.logs[0] if res_playwright.logs else 'Unknown'}")
    print(f"Success: {res_playwright.success}")
    print(f"Payload: {json.dumps(res_playwright.result, indent=2)}")
except Exception as e:
    print(f"Playwright Execution Failed: {e}")

