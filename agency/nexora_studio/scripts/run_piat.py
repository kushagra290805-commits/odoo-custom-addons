# -*- coding: utf-8 -*-
import sys
import os
import time
import json
import traceback

sys.path.append(r'D:\ODOO\community\odoo')
import odoo
import odoo.tools
import odoo.modules.registry
odoo.tools.config.parse_config(['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])

print("Booting Odoo Registry...")
try:
    registry = odoo.modules.registry.Registry('nexora_studio')
except Exception as e:
    print(f"Failed to boot registry: {e}")
    sys.exit(1)

with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    
    try:
        from odoo.addons.nexora_studio.services.capabilities.resolver import CapabilityResolver
        from odoo.addons.nexora_studio.services.capabilities.bootstrap import RegistryBootstrapService
        from odoo.addons.nexora_studio.services.capabilities.repository import CapabilityRepository
        from odoo.addons.nexora_studio.services.capabilities.policy import CapabilityPolicyEngine
        from odoo.addons.nexora_studio.services.capabilities.security import SecurityLayer
        from odoo.addons.nexora_studio.services.capabilities.middleware import MiddlewarePipeline
        from odoo.addons.nexora_studio.services.capabilities.scheduler import ExecutionScheduler
        from odoo.addons.nexora_studio.services.capabilities.strategy import ExecutionStrategy
        from odoo.addons.nexora_studio.services.capabilities.executors.local import LocalToolExecutor
        from odoo.addons.nexora_studio.services.capabilities.router import UniversalCapabilityRouter
        from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType

        # Force Bootstrap Sync
        bootstrap = env['nexora.registry_bootstrap_service']
        print(bootstrap.execute_bootstrap())
        
        repo = CapabilityRepository(env)
        resolver = CapabilityResolver(repo)
        policy = CapabilityPolicyEngine()
        sec = SecurityLayer()
        mid = MiddlewarePipeline()
        sched = ExecutionScheduler(ExecutionStrategy())
        
        class ToolRegistryWrapper:
            def __init__(self, e):
                self.env = e
            def resolve_tool(self, tool_id):
                if tool_id == 'mcp.playwright': return (self.env.get('nexora.provider.playwright'), None)
                if tool_id == 'mcp.github': return (self.env.get('nexora.provider.github'), None)
                if tool_id == 'mcp.context7': return (self.env.get('nexora.provider.context7'), None)
                if tool_id == 'mcp.tavily': return (self.env.get('nexora.provider.tavily'), None)
                if tool_id == 'mcp.firecrawl': return (self.env.get('nexora.provider.firecrawl'), None)
                if tool_id == 'mcp.tool.terminal': return (self.env.get('nexora.provider.terminal'), None)
                if tool_id == 'local.gosom': return (self.env.get('nexora.provider.gosom'), None)
                if tool_id == 'local.spline': return (self.env.get('nexora.provider.spline'), None)
                if tool_id == 'mcp.threejs_docs': return (self.env.get('nexora.provider.threejs_docs'), None)
                if tool_id == 'mcp.r3f_docs': return (self.env.get('nexora.provider.r3f_docs'), None)
                if tool_id == 'mcp.drei_docs': return (self.env.get('nexora.provider.drei_docs'), None)
                if tool_id == 'mcp.gsap_docs': return (self.env.get('nexora.provider.gsap_docs'), None)
                if tool_id == 'mcp.mdn_docs': return (self.env.get('nexora.provider.mdn_docs'), None)
                return None

        tool_registry = ToolRegistryWrapper(env)
        executors = {
            ExecutionTargetType.LOCAL: LocalToolExecutor(tool_registry),
        }
        
        router = UniversalCapabilityRouter(resolver, policy, sec, mid, sched, executors)
        
        from odoo.addons.nexora_studio.services.capabilities.selection_engine import CapabilitySelectionEngine
        cse = CapabilitySelectionEngine(resolver, router)

        from odoo.addons.nexora_studio.services.planning.planner import IntelligentCapabilityPlanner
        from odoo.addons.nexora_studio.services.planning.plan_validator import PlanValidator
        from odoo.addons.nexora_studio.services.planning.plan_optimizer import PlanOptimizer
        from odoo.addons.nexora_studio.services.planning.orchestrator import PlanOrchestrator
        from odoo.addons.nexora_studio.services.design.engine import DesignIntelligenceEngine

        print("Booting PlatformRuntime to spawn MCP servers...")
        try:
            if 'nexora_studio.platform' in env:
                env['nexora_studio.platform'].get_runtime()
            else:
                print("Platform not found in env.")
        except Exception as e:
            print(f"Platform Runtime boot error: {e}")

        print("Waiting 3s for init...")
        time.sleep(3)

        design_engine = DesignIntelligenceEngine()
        planner = IntelligentCapabilityPlanner()
        validator = PlanValidator()
        optimizer = PlanOptimizer()
        orchestrator = PlanOrchestrator(cse)
        
        objectives = [
            "Build an Apple-style 3D landing page",
            "Research something generic"
        ]

        # Let's purposefully mark mcp.context7 as DEGRADED to test failover inside the plan
        from odoo.addons.nexora_studio.services.capabilities.health import ProviderHealthState
        cse.health.set_health('mcp.context7', ProviderHealthState.DEGRADED)

        for obj in objectives:
            print(f"\n--- PLANNING INTENT: {obj} ---")
            
            start = time.time()
            try:
                # 0. Design Blueprint
                blueprint = design_engine.generate_blueprint(obj)
                print(f"Generated Blueprint (Valid: {blueprint.is_valid}) - Rendering: {blueprint.rendering.strategy}, Component Count: {len(blueprint.component.abstract_components)}")
                if not blueprint.is_valid:
                    print(f"Blueprint Validation Errors: {blueprint.validation_errors}")
                    
                # 1. Plan
                plan = planner.plan(obj, blueprint=blueprint)
                print(f"Generated Plan with {len(plan.graph.steps)} steps.")
                
                # 2. Validate
                errors = validator.validate(plan)
                if errors:
                    print(f"Validation failed: {errors}")
                    continue
                    
                # 3. Optimize
                plan = optimizer.optimize(plan)
                print(f"Optimized Plan to {len(plan.graph.steps)} steps.")
                
                # 4. Orchestrate
                trace = orchestrator.execute_plan(plan)
                end = time.time()
                
                print(f"Plan Execution Latency: {(end-start)*1000:.2f}ms")
                print(f"Steps Completed: {trace.steps_completed}")
                print(f"Steps Failed: {trace.steps_failed}")
                print(f"Capability Trace: {[t['capability'] + ' -> ' + t['status'] for t in trace.capability_trace]}")
                
            except Exception as e:
                print(f"Exception during planning/execution: {type(e).__name__} - {e}")
                traceback.print_exc()
            
    except Exception as e:
        print(f"Setup Exception: {e}")
        traceback.print_exc()
