import logging
from typing import Any, Optional
from odoo.addons.nexora_studio.services.generation.core.generation_context import GenerationContext, WebsiteGenerationArtifact
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import GenerationStateManager
from odoo.addons.nexora_studio.services.generation.pipeline.website_generation_pipeline import WebsiteGenerationPipeline

_logger = logging.getLogger(__name__)

class GenerationCoordinator:
    """
    Coordinates the execution of the generation process between the BuilderSessionService
    and the underlying WebsiteGenerationPipeline. Handles locking, initial state, and error boundaries.

    Phase 20A (P0-03): Injects an existing nexora.project_blueprint (produced by the Planner)
    into the WebsiteGenerationArtifact before pipeline execution so that generation does not
    rebuild planning from scratch when planning has already run.
    """
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        env = getattr(orchestrator, 'env', None)
        self.state_manager = GenerationStateManager(env=env)
        
        # Dependency Injection: Instantiate EventBus and register subscribers here
        from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import PipelineEventBus
        from odoo.addons.nexora_studio.services.generation.events.subscribers.logging_subscriber import LoggingSubscriber
        from odoo.addons.nexora_studio.services.generation.events.subscribers.telemetry_subscriber import TelemetrySubscriber
        from odoo.addons.nexora_studio.services.generation.events.subscribers.streaming_subscriber import StreamingSubscriber
        from odoo.addons.nexora_studio.services.generation.events.subscribers.progress_subscriber import ProgressSubscriber
        from odoo.addons.nexora_studio.services.generation.events.subscribers.plugin_subscriber import PluginSubscriber
        from odoo.addons.nexora_studio.services.generation.events.subscribers.deployment_subscriber import DeploymentSubscriber
        from odoo.addons.nexora_studio.services.generation.events.subscribers.agent_runtime_subscriber import AgentRuntimeSubscriber
        
        self.event_bus = PipelineEventBus()
        self.event_bus.subscribe(TelemetrySubscriber(), priority=10)
        self.event_bus.subscribe(LoggingSubscriber(), priority=20)
        self.event_bus.subscribe(StreamingSubscriber(), priority=30)
        self.event_bus.subscribe(ProgressSubscriber(env=env), priority=40)
        self.event_bus.subscribe(PluginSubscriber(), priority=50)
        self.event_bus.subscribe(DeploymentSubscriber(), priority=60)
        self.event_bus.subscribe(AgentRuntimeSubscriber(), priority=70)
        
        self.pipeline = WebsiteGenerationPipeline(orchestrator, self.state_manager, self.event_bus)

    # ------------------------------------------------------------------
    # P0-03: Planner Blueprint Injection
    # ------------------------------------------------------------------
    def _inject_planner_blueprint(self, context: GenerationContext, session: Any) -> GenerationContext:
        """
        Phase 20A (P0-03): If a nexora.project_blueprint already exists for this Builder Session,
        load its content and merge it into the WebsiteGenerationArtifact so that the pipeline
        does not redundantly re-run planning from raw requirements.

        The Planner remains the canonical owner of blueprint generation.
        This coordinator only reads the existing output — it never writes to it.

        Merge strategy:
          - raw_input is preserved from the original requirement.
          - If blueprint provides domain/navigation/seo, they override the empty defaults.
          - The artifact is evolved immutably (frozen dataclass).

        If no blueprint is found or reading fails, the context is returned unchanged
        so that the pipeline falls back to its own planning engines.
        """
        try:
            env = getattr(self.orchestrator, 'env', None)
            if env is None:
                return context

            session_id = getattr(session, 'id', None)
            if not session_id:
                return context

            blueprint = env['nexora.project_blueprint'].search(
                [('builder_session_id', '=', session_id)],
                limit=1,
            )
            if not blueprint:
                _logger.debug(
                    "P0-03: No project blueprint found for session %s — pipeline will run full planning.",
                    session_id,
                )
                return context

            import json

            # Read structured fields from the DB blueprint
            design_system_raw = blueprint.design_system_json or '{}'
            try:
                design_system = json.loads(design_system_raw)
            except (ValueError, TypeError):
                design_system = {}

            pages_raw = blueprint.pages_json or '[]'
            try:
                pages = json.loads(pages_raw)
            except (ValueError, TypeError):
                pages = []

            # Extract domain from information_architecture (best-effort string parse)
            info_arch = blueprint.information_architecture or ''
            nav_structure = blueprint.navigation_structure or ''
            seo_requirements = blueprint.seo_requirements or ''

            # Build an enhanced branding dict from the design_system blueprint field
            branding_from_blueprint = {}
            if isinstance(design_system, dict):
                colors = design_system.get('colors', {})
                if isinstance(colors, dict) and colors:
                    branding_from_blueprint['colors'] = colors
                typography = design_system.get('typography', {})
                if isinstance(typography, dict) and typography:
                    branding_from_blueprint['typography'] = typography

            # Build a goals list from pages if none are currently set
            page_goals = [p.get('name', '') for p in pages if isinstance(p, dict) and p.get('name')]

            # Current requirement model from artifact
            current_req = context.artifact.requirements

            # Only override fields that are empty in the current artifact
            from dataclasses import replace as dc_replace
            updated_req = dc_replace(
                current_req,
                # Preserve raw_input — it is the source of truth for the session intent
                branding=current_req.branding or branding_from_blueprint,
                seo=current_req.seo or ({'requirements': seo_requirements} if seo_requirements else {}),
                goals=current_req.goals or page_goals,
            )

            new_artifact = context.artifact.evolve(requirements=updated_req)

            # Attach blueprint metadata so engines can read it if needed
            new_metadata = dict(context.metadata)
            new_metadata['planner_blueprint_id'] = blueprint.id
            new_metadata['planner_blueprint_injected'] = True
            new_metadata['planner_blueprint_status'] = blueprint.status

            context = context.evolve(artifact=new_artifact, metadata=new_metadata)

            _logger.info(
                "P0-03: Planner blueprint (id=%s, status=%s) injected into GenerationContext %s.",
                blueprint.id, blueprint.status, context.context_id,
            )

        except Exception as exc:
            # Non-fatal: pipeline continues without blueprint injection
            _logger.warning(
                "P0-03: Failed to inject planner blueprint for session %s — continuing without it. Error: %s",
                getattr(session, 'id', 'unknown'), exc,
            )

        return context

    def start_generation(self, raw_requirements: str, session: Any, context_id: str, mode: str = 'FULL') -> GenerationContext:
        """Starts or resumes a generation job safely, implementing Phase 48.2 Supervisor Evaluator role."""
        from odoo.addons.nexora_studio.services.generation.events.events import GenerationStarted, GenerationCompleted, GenerationFailed
        from odoo.addons.nexora_studio.services.generation.core.generation_context import RequirementModel, SupervisorPrepareContract, SupervisorEvaluateContract, GenerationState
        from dataclasses import replace
        
        try:
            # 1. Initialize or Load Context
            context = self.state_manager.load_checkpoint(context_id)
            if not context:
                _logger.info(f"Coordinator: Creating new generation context for {context_id}")
                from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact
                artifact = WebsiteGenerationArtifact()
                context = GenerationContext(context_id=context_id, artifact=artifact)
                new_reqs = replace(context.artifact.requirements, raw_input=raw_requirements)
                new_artifact = context.artifact.evolve(requirements=new_reqs)
                context = context.evolve(artifact=new_artifact)
                self.state_manager.save_checkpoint(context)
            else:
                _logger.info(f"Coordinator: Resuming context {context_id}")

            # P0-03: Inject planner blueprint if one exists for this session.
            context = self._inject_planner_blueprint(context, session)

            # Publish GenerationStarted
            self.event_bus.publish(GenerationStarted(
                session_id=str(getattr(session, 'id', context_id)),
                generation_id=context_id,
                correlation_id=context_id,
                current_state=context.state.name
            ))

            # 3. Create GenerationRuntime
            from odoo.addons.nexora_studio.services.generation.core.generation_runtime import GenerationRuntime
            workspace = getattr(session, 'workspace_id', None)
            workspace_path = getattr(workspace, 'workspace_path', None)
            if not workspace_path:
                raise RuntimeError('Generation requires a session-owned managed workspace.')
            
            runtime = GenerationRuntime(
                ai_provider_manager=self.orchestrator,
                workspace_path=workspace_path,
                event_bus=self.event_bus,
                state_manager=self.state_manager,
                session_id=str(getattr(session, 'id', context_id)),
                generation_id=context_id,
                initiated_by="system",
                env=getattr(self.orchestrator, 'env', None),
            )

            # PHASE 48.2: EXACT ATTEMPT SEMANTICS
            MAX_PIPELINE_EXECUTIONS = 1 if mode == 'MANUAL' else 4
            
            # PHASE 48.2: SUPERVISOR PREPARE
            # Runs for BOTH initial and manual executions unconditionally.
            prepare_payload = {
                "raw_input": context.artifact.requirements.raw_input,
                "project_context": context.metadata.get("planner_blueprint_status", ""),
                "mode": mode
            }
            try:
                prepare_resp = runtime.ai.generate("supervisor_prepare", prepare_payload)
                prepare_contract = SupervisorPrepareContract(**prepare_resp)
            except Exception as e:
                _logger.error(f"Supervisor PREPARE failed: {e}")
                prepare_contract = SupervisorPrepareContract(is_valid=False, rejection_reason=str(e))
                
            if not prepare_contract.is_valid:
                _logger.error(f"Supervisor rejected requirements: {prepare_contract.rejection_reason}")
                raise RuntimeError(f"Supervisor rejected requirements: {prepare_contract.rejection_reason}")
                
            if prepare_contract.instruction:
                new_req = replace(context.artifact.requirements, current_supervisor_instruction=prepare_contract.instruction)
                context = context.evolve(artifact=context.artifact.evolve(requirements=new_req))

            completed_context = context
            
            # PHASE 48.2: SUPERVISOR EVALUATE LOOP
            for execution in range(1, MAX_PIPELINE_EXECUTIONS + 1):
                _logger.info(f"Coordinator Pipeline Execution: {execution} of {MAX_PIPELINE_EXECUTIONS}")
                
                # Execute exactly ONE pipeline run
                completed_context = self.pipeline.run(context, runtime)
                
                # If pipeline failed natively, restore checkpoint and stop
                if completed_context.state.name == "FAILED":
                    _logger.error("Pipeline failed; restoring last successful checkpoint.")
                    restored = self.state_manager.rollback(context.context_id)
                    return restored if restored else completed_context
                    
                # Save successful pipeline artifact as the new canonical checkpoint
                self.state_manager.save_checkpoint(completed_context)
                
                # Stop if max executions reached
                if execution == MAX_PIPELINE_EXECUTIONS:
                    break
                    
                # Evaluate via Supervisor
                evidence = completed_context.get_supervisor_evidence()
                try:
                    eval_resp = runtime.ai.generate("supervisor_evaluate", evidence)
                    eval_contract = SupervisorEvaluateContract(**eval_resp)
                except Exception as e:
                    _logger.error(f"Supervisor EVALUATE failed closed: {e}")
                    break
                    
                if eval_contract.satisfies_requirements:
                    _logger.info("Supervisor ACCEPTED artifact.")
                    break
                    
                if not eval_contract.improvement_instruction:
                    _logger.warning("Supervisor requested improvement but provided no instruction.")
                    break
                    
                # Inject instruction for next iteration and reset state to PENDING
                new_req = replace(completed_context.artifact.requirements, 
                                  current_supervisor_instruction=eval_contract.improvement_instruction)
                context = completed_context.evolve(
                    artifact=completed_context.artifact.evolve(requirements=new_req),
                    state=GenerationState.PENDING
                )
                _logger.info(f"Supervisor injected improvement instruction for execution {execution+1}")

            # Publish final completion event
            if completed_context.state.name == "COMPLETED":
                self.event_bus.publish(GenerationCompleted(
                    session_id=str(getattr(session, 'id', context_id)),
                    generation_id=context_id,
                    correlation_id=context_id,
                    current_state=completed_context.state.name
                ))
            
            return completed_context

        except Exception as e:
            _logger.error(f"Coordinator trapped fatal pipeline error: {e}", exc_info=True)
            self.event_bus.publish(GenerationFailed(
                session_id=str(getattr(session, 'id', context_id)),
                generation_id=context_id,
                correlation_id=context_id,
                current_state="FAILED",
                error=str(e)
            ))
            if 'context' in locals() and context:
                failed_ctx = self.state_manager.cancel(context)
                failed_ctx = failed_ctx.evolve(metadata={**failed_ctx.metadata, 'pipeline_error': str(e)})
                raise e
            raise e
