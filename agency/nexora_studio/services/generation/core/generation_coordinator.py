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
        self.state_manager = GenerationStateManager()
        
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
        self.event_bus.subscribe(ProgressSubscriber(), priority=40)
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

    def start_generation(self, raw_requirements: str, session: Any, context_id: str) -> GenerationContext:
        """Starts or resumes a generation job safely."""
        from odoo.addons.nexora_studio.services.generation.events.events import GenerationStarted, GenerationCompleted, GenerationFailed
        try:
            # 1. Initialize or Load Context
            context = self.state_manager.load_checkpoint(context_id)
            if not context:
                _logger.info(f"Coordinator: Creating new generation context for {context_id}")
                artifact = WebsiteGenerationArtifact()
                context = GenerationContext(context_id=context_id, artifact=artifact)
                # Apply raw requirements
                from odoo.addons.nexora_studio.services.generation.core.generation_context import RequirementModel
                from dataclasses import replace
                new_reqs = replace(context.artifact.requirements, raw_input=raw_requirements)
                new_artifact = context.artifact.evolve(requirements=new_reqs)
                context = context.evolve(artifact=new_artifact)
                self.state_manager.save_checkpoint(context)
            else:
                _logger.info(f"Coordinator: Resuming context {context_id}")

            # P0-03: Inject planner blueprint if one exists for this session.
            # Must run after context is initialised (raw_input set) but before pipeline starts.
            context = self._inject_planner_blueprint(context, session)

            # Publish GenerationStarted
            self.event_bus.publish(GenerationStarted(
                session_id=str(getattr(session, 'id', context_id)),
                generation_id=context_id,
                correlation_id=context_id,
                current_state=context.state.name
            ))

            # 2. Lock Session (Optional depending on concurrency model)
            # In a robust implementation, this sets a DB lock on the BuilderSession.

            # 3. Create GenerationRuntime
            from odoo.addons.nexora_studio.services.generation.core.generation_runtime import GenerationRuntime
            workspace_path = session.workspace_id.workspace_path if hasattr(session, 'workspace_id') and session.workspace_id else "/tmp/fallback"
            
            runtime = GenerationRuntime(
                ai_provider_manager=self.orchestrator,
                workspace_path=workspace_path,
                event_bus=self.event_bus,
                state_manager=self.state_manager,
                session_id=str(getattr(session, 'id', context_id)),
                generation_id=context_id,
                initiated_by="system"
            )

            # 4. Delegate to Pipeline
            completed_context = self.pipeline.run(context, runtime)
            
            # Publish GenerationCompleted if successful, else it failed during pipeline loop
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
                return failed_ctx
            raise e

