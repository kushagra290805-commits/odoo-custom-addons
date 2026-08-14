import sys
import time
import os
import json
import traceback
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

sys.path.append(r'D:\ODOO\community\odoo')
import odoo
import odoo.tools
import odoo.modules.registry
odoo.tools.config.parse_config(['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])

registry = odoo.modules.registry.Registry('nexora_studio')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

    from odoo.addons.nexora_studio.services.generation.core.generation_context import GenerationContext
    from odoo.addons.nexora_studio.services.generation.core.generation_coordinator import GenerationCoordinator
    from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import PipelineEventBus
    from odoo.addons.nexora_studio.services.capabilities.selection_engine import CapabilitySelectionEngine
    from odoo.addons.nexora_studio.services.capabilities.resolver import CapabilityResolver
    from odoo.addons.nexora_studio.services.capabilities.repository import CapabilityRepository
    from odoo.addons.nexora_studio.services.capabilities.router import UniversalCapabilityRouter
    from odoo.addons.nexora_studio.services.capabilities.policy import CapabilityPolicyEngine
    from odoo.addons.nexora_studio.services.capabilities.security import SecurityLayer
    from odoo.addons.nexora_studio.services.capabilities.middleware import MiddlewarePipeline
    from odoo.addons.nexora_studio.services.capabilities.scheduler import ExecutionScheduler
    from odoo.addons.nexora_studio.services.capabilities.strategy import ExecutionStrategy
    from odoo.addons.nexora_studio.services.capabilities.executors.local import LocalToolExecutor
    from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType

    print("--- STARTING PRODUCTION RUNTIME E2E TRACE ---")
    
    class MockSession:
        def __init__(self, e):
            self.id = 999
            self.workspace_id = type('W', (), {'workspace_path': '/tmp/test_workspace'})()
            self.builder_configuration_id = type('C', (), {'status': 'draft'})()

    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Create the capability routing layer
    repo = CapabilityRepository(env)
    resolver = CapabilityResolver(repo)
    
    class ToolRegistryWrapper:
        def __init__(self, e): self.env = e
        def resolve_tool(self, tool_id):
            if tool_id == 'mcp.tavily': return (self.env.get('nexora.provider.tavily'), None)
            if tool_id == 'mcp.search': return (self.env.get('nexora.provider.tavily'), None)
            return None
            
    tool_registry = ToolRegistryWrapper(env)
    executors = {ExecutionTargetType.LOCAL: LocalToolExecutor(tool_registry)}
    
    router = UniversalCapabilityRouter(resolver, CapabilityPolicyEngine(), SecurityLayer(), MiddlewarePipeline(), ExecutionScheduler(ExecutionStrategy()), executors)
    cse = CapabilitySelectionEngine(resolver, router)
    
    class ProductionOrchestrator:
        def __init__(self, env):
            self.env = env
            self.workspace = type('W', (), {'write_file': lambda self, *args: None})()
            self.ai = type('A', (), {'generate': lambda self, *args, **kwargs: {"analysis": "{}"}})()
            
        def route_request(self, *args, **kwargs):
            class DummyResponse:
                def __init__(self, s, d, e, m):
                    self.success = s
                    self.data = d
                    self.error = e
                    self.metrics = m
                def get(self, key, default=None):
                    return self.data.get(key, default)
            return DummyResponse(True, {"analysis": {"layout_strategy": "sidebar"}}, {}, 50)
            
        def execute(self, *args, **kwargs):
            class DummyResponse:
                def __init__(self, s, d, e, m):
                    self.success = s
                    self.data = d
                    self.error = e
                    self.metrics = m
                def get(self, key, default=None):
                    return self.data.get(key, default)
            return DummyResponse(True, {"components": [{"component_id": "test", "name": "test", "score": 1}]}, {}, 50)

    orchestrator = ProductionOrchestrator(env)
    
    coordinator = GenerationCoordinator(orchestrator)
    session = MockSession(env)
    
    # Track events
    event_log = []
    class EventTracker:
        def notify(self, event):
            event_log.append(f"{event.__class__.__name__}: {getattr(event, 'current_state', '')} {getattr(event, 'message', '')}")
    
    coordinator.event_bus.subscribe(EventTracker(), priority=1)
    
    req_input = "Generate a premium Apple-style SaaS landing page with subtle 3D interactions, GSAP animations, responsive design, and high Lighthouse performance."
    
    try:
        print("Starting coordinator...")
        start_time = time.time()
        final_context = coordinator.start_generation(req_input, session, "trace-001")
        end_time = time.time()
        
        print("\n--- RESULTS ---")
        print(f"Final State: {final_context.state}")
        print(f"Duration: {end_time - start_time:.2f}s")
        print("\n--- METADATA COLLECTED ---")
        for k, v in final_context.metadata.items():
            print(f"{k}: {v}")
            
        print("\n--- EVENT TRACE ---")
        for e in event_log:
            print(e)
            
    except Exception as e:
        print(f"FAILED E2E: {e}")
        traceback.print_exc()

