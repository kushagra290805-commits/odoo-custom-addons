import sys
import time
import os

sys.path.append(r'D:\ODOO\community\odoo')
import odoo
import odoo.tools
import odoo.modules.registry
odoo.tools.config.parse_config(['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])

registry = odoo.modules.registry.Registry('nexora_studio')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

    from odoo.addons.nexora_studio.services.generation.core.generation_context import GenerationContext
    from odoo.addons.nexora_studio.services.generation.pipeline.website_generation_pipeline import WebsiteGenerationPipeline

    class MockOrchestrator:
        def __init__(self, env):
            self.env = env
            self.workspace = type('W', (), {'write_file': lambda self, *args: None})()
            self.ai = type('A', (), {'generate': lambda self, *args, **kwargs: {"analysis": "{}"}})()

    class MockStateMgr:
        def __init__(self):
            self.logs = []
        def initialize_context(self, *a, **k):
            ctx = GenerationContext(session_id=1, intent="Build an Apple style SaaS site")
            ctx.artifact.requirements.raw_input = "Build an Apple style SaaS site"
            return ctx
        def save_context(self, *a, **k): pass
        def set_state(self, *a, **k): pass
        def set_error(self, *a, **k): pass

    orchestrator = MockOrchestrator(env)
    state_manager = MockStateMgr()
    
    pipeline = WebsiteGenerationPipeline(orchestrator, state_manager)
    ctx = state_manager.initialize_context()
    
    print("Running Pipeline...")
    try:
        # Just run requirement engine up to planning to verify they don't crash
        req_engine = pipeline.registry[ctx.current_state][0]
        res = req_engine.execute(ctx.artifact, orchestrator)
        print(f"RequirementEngine: {res.success}")
        
        ctx.artifact = res.artifact
        plan_engine = pipeline.registry[odoo.addons.nexora_studio.services.generation.core.generation_context.GenerationState.KNOWLEDGE_ENRICHMENT_COMPLETED][0]
        res2 = plan_engine.execute(ctx.artifact, orchestrator)
        print(f"PlanningEngine: {res2.success}")
        
        ctx.artifact = res2.artifact
        theme_engine = pipeline.registry[odoo.addons.nexora_studio.services.generation.core.generation_context.GenerationState.COMPONENTS_ENRICHED][0]
        res3 = theme_engine.execute(ctx.artifact, orchestrator)
        print(f"ThemeEngine: {res3.success}")
        
        print("Verification Passed.")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
