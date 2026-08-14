# -*- coding: utf-8 -*-
import json
import logging
import traceback
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LegacyJobContext
#
# Phase 20A (P0-01): Renamed from GenerationContext to LegacyJobContext.
# This is the mutable, DB-job-bound context used by GenerationOrchestrator.
# The canonical immutable GenerationContext lives at:
#   services/generation/core/generation_context.py
# Do NOT import or reference this class outside generation_orchestrator.py.
# ---------------------------------------------------------------------------
class LegacyJobContext:
    def __init__(self, job):
        self.job = job
        self.builder_session = job.builder_session_id if hasattr(job, 'builder_session_id') else None
        self.workspace_path = job.target_workspace_path
        self.runtime_ids = {}
        self.variables = {}
        self.template_versions = {}
        self.compatibility_results = {}
        self.execution_metadata = {}
        self.stage_data = {}

        if job.metadata_json:
            try:
                data = json.loads(job.metadata_json)
                if 'context_state' in data:
                    self.__dict__.update(data['context_state'])
                    # Re-map job object
                    self.job = job
            except Exception as e:
                _logger.warning(f"Could not load context state: {e}")

    def save_state(self):
        state = {k: v for k, v in self.__dict__.items() if k != 'job' and k != 'builder_session'}
        return state

    def set(self, key, value):
        self.stage_data[key] = value

    def get(self, key, default=None):
        return self.stage_data.get(key, default)

class GenerationOrchestrator(models.AbstractModel):
    _name = 'nexora.generation_orchestrator'
    _description = 'Website Generation Orchestrator'

    @api.model
    def execute_job(self, job):
        """
        Main entry point for website generation orchestration.
        """
        if job.status not in ('queued', 'paused', 'failed', 'rolled_back'):
            return

        job.status = 'running'
        if not job.start_time:
            job.start_time = fields.Datetime.now()

        context = LegacyJobContext(job)
        
        stages = job.pipeline_id.stage_ids.filtered(lambda s: s.active).sorted(key=lambda s: (s.sequence, s.id))
        
        # Resume capability: skip completed stages
        pending_stages = [s for s in stages if s.id not in job.completed_stage_ids.ids]
        
        try:
            for stage in pending_stages:
                job.current_stage_id = stage.id
                _logger.info(f"Orchestrator: Executing stage {stage.name}")
                self._emit_job_event(job, context, 'generation.stage.started', f"Starting stage {stage.name}", stage)
                
                # Dynamic discovery via service_name mapping
                stage_model = self.env[stage.service_name]
                
                result = stage_model.execute(job, stage, context)
                if result and hasattr(result, 'status') and result.status == 'failure':
                    raise Exception(f"Stage {stage.name} failed: {getattr(result, 'message', 'Unknown error')}")
                
                # Checkpoint
                if hasattr(stage_model, 'checkpoint'):
                    stage_model.checkpoint(job, stage, context)
                
                job.completed_stage_ids = [(4, stage.id)]
                self._persist_context(job, context)
                
                self._emit_job_event(job, context, 'generation.stage.completed', f"Completed stage {stage.name}", stage)
            
            # Post-pipeline logic (Builder Session)
            self._finalize_generation(job, context)
            
        except Exception as e:
            error_msg = f"{e}\n{traceback.format_exc()}"
            _logger.error(f"Generation failed: {error_msg}")
            job.error_message = error_msg
            job.status = 'failed'
            job.end_time = fields.Datetime.now()
            self._emit_job_event(job, context, 'generation.failed', f"Generation failed at stage {job.current_stage_id.name if job.current_stage_id else 'unknown'}: {e}")
            self.env['nexora.generation_service']._append_log(job, 'error', error_msg, job.current_stage_id.id if job.current_stage_id else False)

    @api.model
    def rollback_job(self, job):
        """
        Executes rollback logic in reverse topological order.
        """
        if job.status in ('draft', 'queued', 'completed'):
            raise UserError(_("Cannot rollback in current state."))
            
        context = LegacyJobContext(job)
        
        stages_to_rollback = job.pipeline_id.stage_ids.filtered(
            lambda s: s.id in job.completed_stage_ids.ids and s.can_rollback
        ).sorted(key=lambda s: (-s.sequence, -s.id))
        
        try:
            for stage in stages_to_rollback:
                _logger.info(f"Orchestrator: Rolling back stage {stage.name}")
                stage_model = self.env[stage.service_name]
                
                if hasattr(stage_model, 'rollback'):
                    stage_model.rollback(job, stage, context)
                if hasattr(stage_model, 'cleanup'):
                    stage_model.cleanup(job, stage, context)
                
                job.completed_stage_ids = [(3, stage.id)]
                
            job.status = 'rolled_back'
            self._emit_job_event(job, context, 'generation.rolled_back', "Rollback completed.")
        except Exception as e:
            error_msg = f"{e}\n{traceback.format_exc()}"
            job.error_message = error_msg
            self._emit_job_event(job, context, 'generation.rollback_failed', f"Rollback failed: {e}")

    @api.model
    def _finalize_generation(self, job, context):
        """
        Finalizes the generation job. If the job already belongs to a Builder Session,
        it updates that session instead of creating a new one.
        """
        session_service = self.env['nexora.builder_session_service']
        
        job.status = 'completed' if job.status == 'running' else job.status
        job.end_time = fields.Datetime.now()
        
        if job.builder_session_id:
            session = job.builder_session_id
            
            if job.status == 'completed':
                import json
                try:
                    metadata = json.loads(job.pipeline_id.metadata_json or '{}')
                    policy = metadata.get('completion_policy', {})
                    session.status = policy.get('status', 'developer_review')
                    session.current_stage = policy.get('current_stage', 'Awaiting Review')
                except Exception:
                    session.status = 'developer_review'
                    session.current_stage = 'Awaiting Review'
            elif job.status == 'failed':
                session.status = 'failed'
                session.current_stage = 'Failed'
                
            self._emit_job_event(job, context, 'generation.completed', f"Generation finished with status {job.status}.")
            return
        
        # Legacy fallback for jobs without a session (should not happen in new architecture)
        config = self.env['nexora.builder_configuration'].create({
            'name': f"Config for {job.name}",
            'status': 'locked',
        })
        
        import re
        slug = re.sub(r'[^a-zA-Z0-9_.-]', '_', job.name.lower())
        workspace = self.env['nexora.workspace'].create({
            'name': f"Workspace for {job.name}",
            'workspace_slug': slug
        })
        workspace.write({'workspace_path': job.target_workspace_path, 'initialized_at': fields.Datetime.now(), 'status': 'ready', 'health': 'healthy'})
        
        session_vals = {
            'name': f"Session for {job.name}",
            'builder_configuration_id': config.id,
            'workspace_id': workspace.id,
            'originating_job_uuid': job.job_uuid,
        }
        session = session_service.create_session(session_vals)
        context.builder_session = session
        self._emit_job_event(job, context, 'generation.builder_session_created', f"Builder Session created: {session.name}")
        
        session_service.start_session(session)
        self._emit_job_event(job, context, 'generation.runtimes_started', "Workspace, Git, IDE, MCP and Preview runtimes started.")
        self._emit_job_event(job, context, 'generation.completed', "Generation completed successfully.")

    @api.model
    def _persist_context(self, job, context):
        try:
            metadata = json.loads(job.metadata_json) if job.metadata_json else {}
            metadata['context_state'] = context.save_state()
            job.metadata_json = json.dumps(metadata, indent=4)
        except Exception as e:
            _logger.warning(f"Failed to persist context: {e}")

    @api.model
    def _emit_job_event(self, job, context, event_name, message, stage=None):
        """
        Standardized timeline event emission.
        """
        self.env['nexora.runtime_event'].create({
            'generation_job_id': job.id,
            'builder_session_id': context.builder_session.id if hasattr(context, 'builder_session') and context.builder_session else False,
            'event_type': event_name,
            'message': message,
            'timestamp': fields.Datetime.now(),
            'runtime_type': 'generation_orchestrator',
        })
        self.env['nexora.generation_service']._append_log(job, 'info', message, stage.id if stage else False)

    @api.model
    def generate_website(self, builder_session_id, mode='FULL', targets=None, force=False):
        """
        DEPRECATED (Phase 20A P0-02) — Compatibility wrapper only.

        The canonical generation entry point is:
            BuilderSessionService.run_generation(session, mode, targets)

        This method remains for backward compatibility with any callers that
        have not yet been migrated. It will be removed in Phase 20 P3.
        Do NOT add execution logic here.
        """
        import warnings
        warnings.warn(
            "GenerationOrchestrator.generate_website() is deprecated. "
            "Use BuilderSessionService.run_generation() instead. "
            "This compatibility wrapper will be removed in Phase 20 P3.",
            DeprecationWarning,
            stacklevel=2,
        )
        _logger.warning(
            "[DEPRECATED] GenerationOrchestrator.generate_website(builder_session_id=%s) called. "
            "Delegating to BuilderSessionService.run_generation(). "
            "Migrate callers to BuilderSessionService.run_generation() directly.",
            builder_session_id,
        )

        session = self.env['nexora.builder_session'].browse(builder_session_id)
        if not session.exists():
            raise ValueError(f"Builder session {builder_session_id} does not exist.")

        # Delegate to the canonical implementation. All logic lives there.
        session_service = self.env['nexora.builder_session_service']
        return session_service.run_generation(session, mode=mode, targets=targets)
