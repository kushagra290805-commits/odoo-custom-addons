import logging
import time
from typing import Any, Dict
from odoo.addons.nexora_studio.services.generation.core.generation_context import GenerationContext, GenerationState
from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import RequirementEngine
from odoo.addons.nexora_studio.services.generation.engines.planning_engine import PlanningEngine
from odoo.addons.nexora_studio.services.generation.engines.architecture_engine import ArchitectureEngine
from odoo.addons.nexora_studio.services.generation.engines.component_discovery_engine import ComponentDiscoveryEngine
from odoo.addons.nexora_studio.services.generation.engines.component_ranking_engine import ComponentRankingEngine
from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import ComponentIntelligenceEngine
from odoo.addons.nexora_studio.services.generation.engines.theme_engine import ThemeEngine
from odoo.addons.nexora_studio.services.generation.engines.template_resolution_engine import TemplateResolutionEngine
from odoo.addons.nexora_studio.services.generation.engines.design_orchestration_engine import DesignOrchestrationEngine
from odoo.addons.nexora_studio.services.generation.engines.asset_engine import AssetEngine
from odoo.addons.nexora_studio.services.generation.engines.content_engine import ContentEngine
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import CodeGenerationEngine
from odoo.addons.nexora_studio.services.generation.engines.optimization_engine import OptimizationEngine
from odoo.addons.nexora_studio.services.generation.engines.validation_engine import ValidationEngine
from odoo.addons.nexora_studio.services.generation.engines.preview_engine import PreviewEngine
from odoo.addons.nexora_studio.services.generation.engines.business_research_engine import BusinessResearchEngine
from odoo.addons.nexora_studio.services.generation.engines.knowledge_enrichment_engine import KnowledgeEnrichmentEngine
from odoo.addons.nexora_studio.services.generation.engines.review_engine import ReviewEngine

from odoo.addons.nexora_studio.services.generation.engines.workspace_generator_engine import WorkspaceGeneratorEngine

from odoo.addons.nexora_studio.services.generation.events.events import (
    StateTransitionStarted, StateTransitionCompleted,
    EngineStarted, EngineCompleted, EngineFailed
)
from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import PipelineEventBus

_logger = logging.getLogger(__name__)

class WebsiteGenerationPipeline:
    def __init__(self, orchestrator, state_manager, event_bus: PipelineEventBus = None):
        self.orchestrator = orchestrator
        self.state_manager = state_manager
        self.event_bus = event_bus or PipelineEventBus()
        
        # Configurable Pipeline Registry mapping Current State -> (Engine, Next State)
        self.registry = {
            GenerationState.PENDING: (RequirementEngine(orchestrator), GenerationState.REQUIREMENTS_CAPTURED),
            GenerationState.REQUIREMENTS_CAPTURED: (BusinessResearchEngine(orchestrator), GenerationState.BUSINESS_RESEARCH_COMPLETED),
            GenerationState.BUSINESS_RESEARCH_COMPLETED: (KnowledgeEnrichmentEngine(orchestrator), GenerationState.KNOWLEDGE_ENRICHMENT_COMPLETED),
            GenerationState.KNOWLEDGE_ENRICHMENT_COMPLETED: (PlanningEngine(orchestrator), GenerationState.PLANNING_COMPLETED),
            GenerationState.PLANNING_COMPLETED: (ArchitectureEngine(orchestrator), GenerationState.ARCHITECTURE_COMPLETED),
            GenerationState.ARCHITECTURE_COMPLETED: (ComponentDiscoveryEngine(orchestrator), GenerationState.COMPONENTS_DISCOVERED),
            GenerationState.COMPONENTS_DISCOVERED: (ComponentRankingEngine(orchestrator), GenerationState.COMPONENTS_RANKED),
            GenerationState.COMPONENTS_RANKED: (ComponentIntelligenceEngine(orchestrator), GenerationState.COMPONENTS_ENRICHED),
            GenerationState.COMPONENTS_ENRICHED: (ThemeEngine(orchestrator), GenerationState.DESIGN_COMPLETED),
            GenerationState.DESIGN_COMPLETED: (TemplateResolutionEngine(orchestrator), GenerationState.TEMPLATE_RESOLVED),
            GenerationState.TEMPLATE_RESOLVED: (DesignOrchestrationEngine(orchestrator), GenerationState.DESIGN_ORCHESTRATED),
            GenerationState.DESIGN_ORCHESTRATED: (AssetEngine(orchestrator), GenerationState.ASSETS_GENERATED),
            GenerationState.ASSETS_GENERATED: (WorkspaceGeneratorEngine(orchestrator), GenerationState.WORKSPACE_PREPARED),
            GenerationState.WORKSPACE_PREPARED: (CodeGenerationEngine(orchestrator), GenerationState.CODE_GENERATION_COMPLETED),
            GenerationState.CODE_GENERATION_COMPLETED: (ReviewEngine(orchestrator), GenerationState.REVIEW_COMPLETED),
            GenerationState.REVIEW_COMPLETED: (ValidationEngine(orchestrator), GenerationState.VALIDATION_COMPLETED),
            GenerationState.VALIDATION_COMPLETED: (PreviewEngine(orchestrator), GenerationState.PREVIEW_READY),
            GenerationState.PREVIEW_READY: (OptimizationEngine(orchestrator), GenerationState.DEPLOYMENT_READY),
        }

    def run(self, context: GenerationContext, runtime: 'GenerationRuntime' = None) -> GenerationContext:
        pipeline_start_time = time.time()
        _logger.info(f"Starting Generation Pipeline {context.context_id}")
        
        session_id = runtime.metadata.session_id if runtime else context.context_id
        
        total_steps = len(self.registry)
        current_step_idx = 0
        
        while context.state in self.registry:
            if self.state_manager.check_interruption(context.context_id):
                context = context.evolve(state=GenerationState.INTERRUPTED)
                self.state_manager.save_checkpoint(context)
                _logger.warning(f"Pipeline interrupted at state {context.state.name}")
                return context

            engine, next_state = self.registry[context.state]
            state_name = context.state.name
            engine_name = engine.__class__.__name__
            
            if runtime and hasattr(runtime, 'hooks'):
                runtime.hooks.before_state_transition(state_name, next_state.name)
                
            self.event_bus.publish(StateTransitionStarted(
                session_id=session_id,
                generation_id=context.context_id,
                correlation_id=context.context_id,
                current_state=state_name,
                next_state=next_state.name
            ))
            
            max_retries = 2
            for attempt in range(max_retries):
                engine_start_time = time.time()
                try:
                    self.event_bus.publish(EngineStarted(
                        session_id=session_id,
                        generation_id=context.context_id,
                        correlation_id=context.context_id,
                        current_state=state_name,
                        engine_name=engine_name,
                        metadata={'attempt': attempt + 1}
                    ))
                    
                    if runtime and hasattr(runtime, 'hooks'):
                        runtime.hooks.before_execute(engine_name, context.artifact)
                        
                    # Engine Interface
                    scoped_runtime = runtime.get_scoped_view(engine.__class__) if runtime else None
                    result = engine.execute(context.artifact, scoped_runtime or runtime)
                    
                    if runtime and hasattr(runtime, 'hooks'):
                        runtime.hooks.after_execute(engine_name, result)
                    
                    if not result.success:
                        raise ValueError(f"Engine execution failed: {result.error}")
                        
                    engine_duration = time.time() - engine_start_time
                    
                    self.event_bus.publish(EngineCompleted(
                        session_id=session_id,
                        generation_id=context.context_id,
                        correlation_id=context.context_id,
                        current_state=state_name,
                        engine_name=engine_name,
                        metadata={'duration_ms': round(engine_duration * 1000, 2)}
                    ))
                    
                    # Reconstruct Context and advance state
                    new_metadata = dict(context.metadata)
                    new_metadata.update(result.metadata)
                    new_metadata[f"{state_name}_latency_ms"] = round(engine_duration * 1000, 2)
                    
                    context = context.evolve(artifact=result.artifact, metadata=new_metadata)
                    
                    percentage = ((current_step_idx + 1) / total_steps) * 100
                    context = self.state_manager.update_progress(context, next_state, percentage, f"Completed {state_name} in {engine_duration:.2f}s")
                    
                    self.event_bus.publish(StateTransitionCompleted(
                        session_id=session_id,
                        generation_id=context.context_id,
                        correlation_id=context.context_id,
                        current_state=next_state.name
                    ))
                    
                    if runtime and hasattr(runtime, 'hooks'):
                        runtime.hooks.after_state_transition(state_name, next_state.name)
                        
                    break
                except Exception as e:
                    self.event_bus.publish(EngineFailed(
                        session_id=session_id,
                        generation_id=context.context_id,
                        correlation_id=context.context_id,
                        current_state=state_name,
                        engine_name=engine_name,
                        error=str(e),
                        metadata={'attempt': attempt + 1}
                    ))
                    
                    if attempt == max_retries - 1:
                        context = self.state_manager.cancel(context)
                        raise e
                    else:
                        _logger.info(f"Recovering/Retrying {state_name}...")
                        context = self.state_manager.rollback(context.context_id) or context
            
            current_step_idx += 1
                
        pipeline_duration = time.time() - pipeline_start_time
        new_meta = dict(context.metadata)
        new_meta["total_generation_time_ms"] = round(pipeline_duration * 1000, 2)
        
        # If we reached the end of the registry, we are essentially COMPLETED
        if context.state == GenerationState.DEPLOYMENT_READY:
             context = context.evolve(state=GenerationState.COMPLETED, metadata=new_meta)
        else:
             context = context.evolve(metadata=new_meta)
             
        self.state_manager.save_checkpoint(context)
        _logger.info(f"Generation Pipeline {context.context_id} completed successfully in {pipeline_duration:.2f}s.")
        return context
