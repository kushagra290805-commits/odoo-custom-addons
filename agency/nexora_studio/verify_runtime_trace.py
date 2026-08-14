import sys
import logging

def verify(env):
    print("=== RUNTIME TRACE: BUILDER SESSION -> GENERATION ===")
    
    # Check if WebsiteGenerationService exists
    if 'nexora.website_generation_service' in env:
        print("[FOUND] nexora.website_generation_service is registered.")
    else:
        print("[MISSING] nexora.website_generation_service is NOT registered.")
        
    # Check Generation Stage Registry
    if 'nexora.generation_stage_registry' in env:
        registry = env['nexora.generation_stage_registry']
        stages = registry.get_stages()
        print(f"[REGISTRY] Found {len(stages)} stages in generation_stage_registry:")
        for idx, stage in enumerate(stages):
            print(f"  Stage {idx+1:02d}: {stage._name}")
            if hasattr(stage, 'execute'):
                print(f"    - Has execute() method")
            if hasattr(stage, 'validate'):
                print(f"    - Has validate() method")
    
    print("\n=== RUNTIME TRACE: GENERATION_ORCHESTRATOR ===")
    if 'nexora.generation_orchestrator' in env:
        print("[FOUND] nexora.generation_orchestrator is registered.")
    else:
        print("[MISSING] nexora.generation_orchestrator is NOT registered.")
        
    if 'nexora.pipeline_service' in env:
        print("[FOUND] nexora.pipeline_service is registered.")
    else:
        print("[MISSING] nexora.pipeline_service is NOT registered. (This explains why GenerationOrchestrator fails if used)")

    print("\n=== RUNTIME TRACE: CostRouter ===")
    if 'nexora.cost_router' in env:
        router = env['nexora.cost_router']
        print(f"[FOUND] nexora.cost_router is registered. Methods: {[m for m in dir(router) if not m.startswith('_')]}")
    
    print("\nTrace completed.")

if "env" in locals():
    verify(env)
