# -*- coding: utf-8 -*-
"""
Builder Session Service — the single orchestration layer of Nexora Studio.

Coordinates the complete developer workflow:
  - Workspace lifecycle
  - Runtime lifecycle
  - Preview lifecycle
  - Git lifecycle
  - AI Provider Manager integration
  - Context Builder / Patch Engine integration
  - Generation pipeline execution
  - AI Review pipeline execution
  - Session state machine
  - Progress tracking
  - Runtime Event integration

No provider-specific logic. All AI requests go through AIProviderManager.
"""
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError
from ..models.runtime_event_constants import RuntimeEvents
import logging
import os
import shutil

_logger = logging.getLogger(__name__)

# ── Valid state transitions ──────────────────────────────────────
_TRANSITIONS = {
    'draft':            ['preparing', 'cancelled'],
    'preparing':        ['generating', 'failed', 'cancelled'],
    'generating':       ['ai_reviewing', 'failed', 'cancelled'],
    'ai_reviewing':     ['developer_review', 'failed', 'cancelled'],
    'developer_review': ['running', 'generating', 'approved', 'failed', 'cancelled'],
    'running':          ['testing', 'developer_review', 'generating', 'failed', 'cancelled'],
    'testing':          ['qa', 'developer_review', 'failed', 'cancelled'],
    'qa':               ['client_review', 'developer_review', 'failed', 'cancelled'],
    'client_review':    ['approved', 'developer_review', 'failed', 'cancelled'],
    'approved':         ['deploying', 'cancelled'],
    'deploying':        ['completed', 'failed'],
    'completed':        [],
    'failed':           ['draft', 'preparing'],
    'cancelled':        ['draft'],
}


class BuilderSessionService(models.AbstractModel):
    _name = 'nexora.builder_session_service'
    _description = 'Builder Session Orchestrator'

    # =================================================================
    # SESSION LIFECYCLE
    # =================================================================

    @api.model
    def create_session(self, vals):
        """Create a new Builder Session and initialize capability discovery."""
        session = self.env['nexora.builder_session'].create(vals)
        self._emit_event(session, RuntimeEvents.SESSION_CREATED, 'Builder Session created and initialized.')
        try:
            with self.env.cr.savepoint():
                self.env['nexora.runtime_service'].discover_runtimes(session)
        except Exception as e:
            _logger.warning('Error during runtime discovery on session create: %s', e)
        return session

    @api.model
    def transition_state(self, session, new_state, reason=''):
        """
        Transition session to a new state with validation.
        Persists every transition via RuntimeEvent.
        """
        old_state = session.status
        allowed = _TRANSITIONS.get(old_state, [])
        if new_state not in allowed:
            raise ValidationError(_(
                'Invalid state transition: %s -> %s. Allowed: %s'
            ) % (old_state, new_state, ', '.join(allowed)))

        session.status = new_state
        session.last_activity = fields.Datetime.now()

        self._emit_event(
            session, RuntimeEvents.SESSION_STATE_CHANGED,
            f'State: {old_state} -> {new_state}. {reason}'.strip(),
        )
        _logger.info(
            'Session %s: %s -> %s %s',
            session.session_uuid, old_state, new_state, reason,
        )
        return True

    # =================================================================
    # WORKSPACE MANAGEMENT
    # =================================================================

    @api.model
    def create_workspace(self, session, workspace_vals=None):
        """Create and link a workspace to the session."""
        if session.workspace_id:
            raise ValidationError(_('Session already has a workspace.'))

        ws_vals = workspace_vals or {}
        ws_vals.setdefault('name', f'{session.name} Workspace')

        if session.target_workspace_path:
            ws_vals['workspace_path'] = session.target_workspace_path
            ws_vals['initialized_at'] = fields.Datetime.now()
            ws_vals['status'] = 'ready'
            ws_vals['health'] = 'healthy'

        workspace = self.env['nexora.workspace'].create(ws_vals)
        session.workspace_id = workspace.id

        if not workspace.initialized_at:
            workspace.action_initialize_workspace()

        self._emit_event(
            session, RuntimeEvents.WORKSPACE_CREATED,
            f'Workspace created: {workspace.workspace_path}',
        )
        return workspace

    @api.model
    def open_workspace(self, session):
        """Open an existing workspace — verify and refresh health."""
        ws = self._require_workspace(session)
        ws_service = self.env['nexora.workspace_service']
        health = ws_service.get_workspace_health(ws)
        if health == 'missing':
            raise ValidationError(_('Workspace directory is missing on disk.'))
        ws.health = 'healthy' if health == 'valid' else 'partial'
        self._emit_event(session, RuntimeEvents.WORKSPACE_OPENED, f'Workspace opened: {ws.workspace_path}')
        return ws

    @api.model
    def archive_workspace(self, session):
        """Archive workspace — create a tarball snapshot and mark archived."""
        ws = self._require_workspace(session)
        ws_path = ws.workspace_path
        if not ws_path or not os.path.isdir(ws_path):
            raise ValidationError(_('Workspace directory does not exist.'))

        archive_dir = os.path.join(os.path.dirname(ws_path), '_archives')
        os.makedirs(archive_dir, exist_ok=True)
        archive_name = f'{ws.workspace_slug or ws.workspace_uuid}_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}'
        archive_path = shutil.make_archive(
            os.path.join(archive_dir, archive_name), 'zip', ws_path
        )
        ws.status = 'archived'
        self._emit_event(session, RuntimeEvents.WORKSPACE_ARCHIVED, f'Workspace archived to {archive_path}')
        return archive_path

    @api.model
    def clone_workspace(self, session, source_session):
        """Clone workspace from another session."""
        source_ws = self._require_workspace(source_session)
        if not source_ws.workspace_path or not os.path.isdir(source_ws.workspace_path):
            raise ValidationError(_('Source workspace directory does not exist.'))

        ws_service = self.env['nexora.workspace_service']
        root_path = ws_service._get_workspace_root()
        new_slug = f'{session.session_uuid[:8]}_clone'
        new_path = str(root_path / new_slug)

        shutil.copytree(source_ws.workspace_path, new_path)

        new_ws = self.env['nexora.workspace'].create({
            'name': f'{session.name} Workspace (Clone)',
            'workspace_path': new_path,
            'workspace_slug': new_slug,
            'status': 'ready',
            'health': 'healthy',
            'initialized_at': fields.Datetime.now(),
        })
        session.workspace_id = new_ws.id
        self._emit_event(session, RuntimeEvents.WORKSPACE_CLONED, f'Workspace cloned from session {source_session.session_uuid}')
        return new_ws

    @api.model
    def restore_workspace(self, session, archive_path):
        """Restore workspace from an archive."""
        if not os.path.isfile(archive_path):
            raise ValidationError(_(f'Archive not found: {archive_path}'))

        ws = self._require_workspace(session)
        ws_path = ws.workspace_path
        if ws_path and os.path.isdir(ws_path):
            shutil.rmtree(ws_path)

        shutil.unpack_archive(archive_path, ws_path)
        ws.status = 'ready'
        ws.health = 'healthy'
        self._emit_event(session, RuntimeEvents.WORKSPACE_RESTORED, f'Workspace restored from {archive_path}')
        return ws

    @api.model
    def cleanup_workspace(self, session):
        """Remove temporary files from workspace (node_modules, .next, cache, temp)."""
        ws = self._require_workspace(session)
        ws_path = ws.workspace_path
        if not ws_path or not os.path.isdir(ws_path):
            return False

        cleanup_dirs = ['node_modules', '.next', 'dist', '.cache']
        removed = []
        for d in cleanup_dirs:
            target = os.path.join(ws_path, d)
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
                removed.append(d)

        # Clean temp and cache subdirs
        for subdir in ['temp', 'cache']:
            target = os.path.join(ws_path, subdir)
            if os.path.isdir(target):
                for item in os.listdir(target):
                    item_path = os.path.join(target, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                removed.append(f'{subdir}/*')

        self._emit_event(session, RuntimeEvents.WORKSPACE_CLEANED, f'Cleaned: {", ".join(removed) or "nothing to clean"}')
        return removed

    # =================================================================
    # RUNTIME MANAGEMENT
    # =================================================================

    @api.model
    def validate_runtime(self, session):
        """Validate that configuration is locked before starting runtimes."""
        if not session.builder_configuration_id:
            raise ValidationError(_('Builder Session must have a Builder Configuration.'))
        if session.builder_configuration_id.status == 'draft':
            raise ValidationError(_('Builder Configuration must be locked before starting.'))
        return True

    @api.model
    def start_session(self, session):
        """Start all runtimes in topological dependency order."""
        self.validate_runtime(session)

        session.runtime_state = 'starting'
        session.runtime_started_at = fields.Datetime.now()
        self._emit_event(session, RuntimeEvents.SESSION_STATE_CHANGED, 'Initiating topological startup of Builder Session.')

        runtime_service = self.env['nexora.runtime_service']
        runtimes = runtime_service.discover_runtimes(session)
        order = runtime_service.build_dependency_graph()

        sorted_runtimes = sorted(
            runtimes,
            key=lambda r: order.index(r.runtime_type) if r.runtime_type in order else 999,
        )

        for idx, runtime in enumerate(sorted_runtimes):
            runtime.status = 'starting'
            self._emit_event(session, RuntimeEvents.RUNTIME_STARTED, f'Starting runtime: {runtime.runtime_type}', runtime=runtime)
            try:
                runtime_service._dispatch_runtime(runtime, 'start_runtime_instance')
                runtime.status = 'running'
                runtime.health = 'healthy'
                runtime.started_at = fields.Datetime.now()
                runtime.last_activity = fields.Datetime.now()
                self._emit_event(session, RuntimeEvents.RUNTIME_STARTED, f'Runtime {runtime.runtime_type} started.', runtime=runtime)
            except Exception as e:
                runtime.status = 'error'
                runtime.health = 'critical'
                _logger.error('Failed to start runtime %s: %s', runtime.runtime_type, e)
                self._emit_event(session, RuntimeEvents.RUNTIME_CRASHED, f'Runtime {runtime.runtime_type} failed: {e}', runtime=runtime)

                for aborted in sorted_runtimes[idx + 1:]:
                    aborted.status = 'stopped'
                    aborted.health = 'unknown'
                    self._emit_event(session, RuntimeEvents.RUNTIME_STOPPED, f'Aborted startup of {aborted.runtime_type}.', runtime=aborted)

                session.runtime_errors = str(e)
                self._update_session_health_and_state(session)
                return f'Session started with errors: {session.runtime_health}'

        self._update_session_health_and_state(session)
        self._emit_event(session, RuntimeEvents.RUNTIME_HEALTH_CHECK, 'All runtimes started successfully.')
        _logger.info('Session %s started successfully.', session.session_uuid)
        return 'Session started successfully.'

    @api.model
    def stop_session(self, session):
        """Stop all runtimes in reverse topological order."""
        if session.runtime_state not in ['running', 'busy', 'error', 'starting']:
            return 'Session is not currently active.'

        session.runtime_state = 'stopping'
        self._emit_event(session, RuntimeEvents.SESSION_STATE_CHANGED, 'Initiating reverse topological shutdown.')

        runtime_service = self.env['nexora.runtime_service']
        runtimes = self.env['nexora.runtime'].search([('builder_session_id', '=', session.id)])
        order = runtime_service.build_dependency_graph()

        sorted_runtimes = sorted(
            runtimes,
            key=lambda r: order.index(r.runtime_type) if r.runtime_type in order else -1,
            reverse=True,
        )

        for runtime in sorted_runtimes:
            if runtime.status == 'stopped' and runtime.process_id == 0:
                continue
            runtime.status = 'stopping'
            self._emit_event(session, RuntimeEvents.RUNTIME_STOPPED, f'Stopping runtime: {runtime.runtime_type}', runtime=runtime)
            try:
                with self.env.cr.savepoint():
                    runtime_service._dispatch_runtime(runtime, 'stop_runtime_instance')
                runtime.status = 'stopped'
                runtime.stopped_at = fields.Datetime.now()
                runtime.last_activity = fields.Datetime.now()
                self._emit_event(session, RuntimeEvents.RUNTIME_STOPPED, f'Runtime {runtime.runtime_type} stopped.', runtime=runtime)
            except Exception as e:
                runtime.status = 'stopped'
                runtime.last_activity = fields.Datetime.now()
                _logger.error('Error stopping runtime %s: %s', runtime.runtime_type, e)
                self._emit_event(session, RuntimeEvents.RUNTIME_CRASHED, f'Error stopping {runtime.runtime_type}: {e}', runtime=runtime)

        session.runtime_state = 'stopped'
        session.runtime_stopped_at = fields.Datetime.now()
        session.runtime_last_activity = fields.Datetime.now()
        self._emit_event(session, RuntimeEvents.RUNTIME_STOPPED, 'Builder Session stopped.')
        _logger.info('Session %s stopped.', session.session_uuid)
        return 'Session stopped successfully.'

    @api.model
    def restart_session(self, session):
        """Stop and restart the session."""
        self._emit_event(session, RuntimeEvents.RUNTIME_RESTARTED, 'Restarting Builder Session.')
        self.stop_session(session)
        self.env['nexora.runtime_service'].build_dependency_graph()
        return self.start_session(session)

    @api.model
    def recover_session(self, session):
        """Reattach active processes after Odoo restart or crash."""
        self._emit_event(session, RuntimeEvents.RUNTIME_RECOVERED, 'Initiating recovery.')
        runtime_service = self.env['nexora.runtime_service']
        order = runtime_service.build_dependency_graph()

        runtimes = self.env['nexora.runtime'].search([('builder_session_id', '=', session.id)])
        sorted_runtimes = sorted(
            runtimes,
            key=lambda r: order.index(r.runtime_type) if r.runtime_type in order else 999,
        )

        for runtime in sorted_runtimes:
            try:
                cap = self.env['nexora.runtime_capability'].search(
                    [('runtime_type', '=', runtime.runtime_type)], limit=1
                )
                service_name = cap.plugin_service if cap else False
                service = self.env.get(service_name) if service_name else None
                if service is not None and hasattr(service, 'recover_runtime_instance'):
                    service.recover_runtime_instance(runtime)
                else:
                    runtime_service._dispatch_runtime(runtime, 'refresh_runtime')
                if runtime.status == 'running':
                    runtime.health = 'healthy'
                    self._emit_event(session, RuntimeEvents.RUNTIME_RECOVERED, f'Runtime {runtime.runtime_type} recovered.', runtime=runtime)
            except Exception as e:
                import traceback
                _logger.error('Could not recover runtime %s: %s\n%s', runtime.runtime_type, e, traceback.format_exc())

        self._update_session_health_and_state(session)
        self._emit_event(session, RuntimeEvents.RUNTIME_RECOVERED, 'Recovery completed.')
        return 'Session recovered successfully.'

    @api.model
    def destroy_session(self, session):
        """Stop runtimes, delete workspace, close session."""
        self.stop_session(session)

        if session.workspace_id:
            workspace = session.workspace_id
            try:
                with self.env.cr.savepoint():
                    session.write({'workspace_id': False})
                    self.env['nexora.workspace_service'].delete_workspace(workspace)
                    workspace.unlink()
            except Exception as e:
                _logger.warning('Error during workspace cleanup: %s', e)

        session.status = 'cancelled'
        session.closed_at = fields.Datetime.now()
        self._emit_event(session, RuntimeEvents.SESSION_DESTROYED, 'Builder Session destroyed.')
        return True

    # =================================================================
    # GIT MANAGEMENT
    # =================================================================

    @api.model
    def git_initialize(self, session):
        """Initialize a git repository in the workspace."""
        ws = self._require_workspace(session)
        git_service = self.env['nexora.git_service']
        runtime = self._get_git_runtime(session)
        git_service.git_init(runtime)
        self._emit_event(session, RuntimeEvents.GIT_INITIALIZED, 'Git repository initialized.')
        return True

    @api.model
    def git_stage_and_commit(self, session, message):
        """Stage all changes and commit."""
        runtime = self._get_git_runtime(session)
        git_service = self.env['nexora.git_service']
        git_service.git_commit(runtime, message)
        self._emit_event(session, RuntimeEvents.GIT_COMMITTED, f'Committed: {message}')
        return True

    @api.model
    def git_checkpoint(self, session, label=''):
        """Create a named checkpoint (tagged commit)."""
        runtime = self._get_git_runtime(session)
        git_service = self.env['nexora.git_service']
        checkpoint_msg = f'[Nexora Checkpoint] {label}' if label else '[Nexora Checkpoint]'
        git_service.git_commit(runtime, checkpoint_msg)

        # Tag the checkpoint
        ws_path = git_service._get_workspace_path(runtime)
        tag_name = f'checkpoint_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}'
        git_service._run_git(ws_path, ['tag', tag_name])

        self._emit_event(session, RuntimeEvents.GIT_CHECKPOINT_CREATED, f'Checkpoint: {tag_name} - {label}')
        return tag_name

    @api.model
    def git_rollback(self, session, commit_hash):
        """Rollback to a specific commit."""
        runtime = self._get_git_runtime(session)
        git_service = self.env['nexora.git_service']
        ws_path = git_service._get_workspace_path(runtime)
        git_service._run_git(ws_path, ['revert', '--no-commit', f'{commit_hash}..HEAD'])
        git_service._run_git(ws_path, ['commit', '-m', f'[Nexora] Rollback to {commit_hash[:8]}'])
        git_service._sync_state_to_db(runtime)
        self._emit_event(session, RuntimeEvents.GIT_ROLLBACK, f'Rolled back to {commit_hash[:8]}')
        return True

    @api.model
    def git_restore_checkpoint(self, session, tag_name):
        """Restore workspace to a checkpoint tag."""
        runtime = self._get_git_runtime(session)
        git_service = self.env['nexora.git_service']
        ws_path = git_service._get_workspace_path(runtime)

        stdout, _, code = git_service._run_git(ws_path, ['rev-parse', tag_name], raise_on_error=False)
        if code != 0:
            raise ValidationError(_(f'Checkpoint tag not found: {tag_name}'))

        commit_hash = stdout.strip()
        return self.git_rollback(session, commit_hash)

    @api.model
    def git_diff_summary(self, session):
        """Return a summary of uncommitted changes."""
        runtime = self._get_git_runtime(session)
        git_service = self.env['nexora.git_service']
        ws_path = git_service._get_workspace_path(runtime)

        stat_out, _, _ = git_service._run_git(ws_path, ['diff', '--stat'], raise_on_error=False)
        short_out, _, _ = git_service._run_git(ws_path, ['diff', '--shortstat'], raise_on_error=False)

        return {
            'stat': stat_out,
            'shortstat': short_out,
        }

    # =================================================================
    # AI INTEGRATION
    # =================================================================

    @api.model
    def run_generation(self, session, mode='FULL', targets=None):
        """
        Execute the generation pipeline through the GenerationCoordinator and WebsiteGenerationPipeline.
        """
        self.transition_state(session, 'generating', 'Generation pipeline started.')
        session.generation_attempts += 1
        session.last_generation_at = fields.Datetime.now()

        try:
            from odoo.addons.nexora_studio.services.generation.core.generation_coordinator import GenerationCoordinator
            
            # The orchestrator is standard env or whatever is needed by AI calls
            orchestrator = self.env['nexora.ai_provider_manager']
            coordinator = GenerationCoordinator(orchestrator)
            
            # Prompt could be taken from session requirements
            raw_requirements = session.project_name or ""
            context_id = str(session.session_uuid)
            
            result_context = coordinator.start_generation(raw_requirements, session, context_id)

            if result_context and result_context.state.name == "COMPLETED":
                self.transition_state(session, 'ai_reviewing', 'Generation completed, entering AI review.')
            else:
                raise Exception(f"Pipeline did not complete successfully. State: {result_context.state.name if result_context else 'None'}")
            return True
        except Exception as e:
            _logger.error('Generation failed for session %s: %s', session.session_uuid, e)
            self._emit_event(session, RuntimeEvents.SESSION_ERROR, f'Generation failed: {e}')
            self.transition_state(session, 'failed', f'Generation failed: {e}')
            raise

    @api.model
    def cancel_generation(self, session):
        """Request graceful cancellation of an active generation pipeline."""
        self.transition_state(session, 'cancelled', 'User requested graceful cancellation.')
        self._emit_event(session, RuntimeEvents.SESSION_STATE_CHANGED, 'Graceful cancellation requested.')
        # Assuming GenerationStateManager reads session status or another mechanism interrupts it
        return True

    @api.model
    def run_ai_review(self, session):
        """Run the AI review stages via AIReviewFramework."""
        self._emit_event(session, RuntimeEvents.AI_REVIEW_STARTED, 'AI review pipeline started.')

        from odoo.addons.nexora_studio.services.generation.core.ai_review_framework import AIReviewFramework
        
        try:
            orchestrator = self.env['nexora.ai_provider_manager']
            review_framework = AIReviewFramework(orchestrator)
            
            # Since we just generated code, we would ideally read the workspace or provide context
            code_payload = "MOCK CODE PAYLOAD FOR REVIEW"
            
            # Self Reflection
            session.current_stage = "AI Self Reflection"
            reflection = review_framework.perform_self_reflection(code_payload, session)
            
            # Bug Fix
            if reflection and reflection.get('status') == 'success' and reflection.get('issues'):
                session.current_stage = "AI Automated Bug Fix"
                review_framework.automated_bug_fix(reflection.get('issues'), code_payload, session)
                
            _logger.info('AI review stages completed.')
        except Exception as e:
            _logger.error('AI review failed: %s', e)
            self._emit_event(session, RuntimeEvents.SESSION_ERROR, f'AI review failed: {e}')

        self._emit_event(session, RuntimeEvents.AI_REVIEW_COMPLETED, 'AI review pipeline completed.')
        self.transition_state(session, 'developer_review', 'AI review completed, awaiting developer review.')
        return True

    @api.model
    def apply_ai_patch(self, session, prompt):
        """Request an AI patch on the current workspace."""
        ws = self._require_workspace(session)
        ws_path = ws.workspace_path

        provider_manager = self.env['nexora.ai_provider_manager']
        context_builder = self.env['nexora.context_builder']
        patch_engine = self.env['nexora.patch_engine']

        # Build context
        ai_ctx = context_builder.build(session)
        context_text = context_builder.to_prompt_text(ai_ctx)

        full_prompt = f'{context_text}\n\n## Developer Request\n{prompt}'

        # Route through AI
        response = provider_manager.route_request(
            'code_generation', full_prompt,
            parameters={'temperature': 0.3, 'max_tokens': 8192}
        )

        if response.get('error'):
            raise UserError(response['error'])

        # Apply via Patch Engine
        patch_result = patch_engine.apply(
            ws_path, response['response'],
            session_id=session.id, stage_name='Developer AI Patch',
        )

        # Audit
        provider_manager.log_audit(
            session_id=session.id, stage='Developer AI Patch',
            provider=response['provider'], model=response['model'],
            prompt=full_prompt, response=response['response'],
            parameters={'temperature': 0.3},
            diff=response.get('patch_diff', ''),
            files=', '.join(patch_result.get('applied_files', [])),
            execution_time=response.get('execution_time', 0),
            token_usage=response.get('token_usage', 0),
            error='; '.join(patch_result.get('errors', [])) or None,
        )

        self._emit_event(
            session, RuntimeEvents.AI_PATCH_APPLIED,
            f'{len(patch_result.get("applied_files", []))} files patched.'
        )
        return patch_result

    # =================================================================
    # SESSION STATUS & HEALTH
    # =================================================================

    @api.model
    def get_session_health(self, session):
        """Aggregate session health from all runtime records."""
        runtimes = self.env['nexora.runtime'].search([('builder_session_id', '=', session.id)])

        root_failed = False
        any_failed = False
        any_degraded = False
        all_healthy = True

        for r in runtimes:
            if r.status in ['error', 'failed'] or r.health in ['critical', 'failed']:
                any_failed = True
                all_healthy = False
                cap = self.env['nexora.runtime_capability'].search(
                    [('runtime_type', '=', r.runtime_type)], limit=1
                )
                if cap and cap.startup_priority <= 150:
                    root_failed = True
            elif r.health in ['warning', 'degraded']:
                any_degraded = True
                all_healthy = False
            elif r.status != 'running':
                all_healthy = False

        if root_failed or (any_failed and not runtimes):
            overall = 'failed'
        elif any_failed or any_degraded:
            overall = 'degraded'
        elif all_healthy and len(runtimes) > 0:
            overall = 'healthy'
        else:
            overall = 'unknown'

        session.runtime_health = overall
        return {
            'health': overall,
            'runtimes': {
                r.runtime_type: {'status': r.status, 'health': r.health}
                for r in runtimes
            },
        }

    @api.model
    def _update_session_health_and_state(self, session):
        """Reconcile session health and runtime_state."""
        health_info = self.get_session_health(session)
        overall = health_info['health']

        if overall == 'failed':
            session.runtime_state = 'error'
        elif overall in ('degraded', 'healthy'):
            session.runtime_state = 'running'
            if overall == 'healthy':
                session.runtime_errors = False
        else:
            if session.runtime_state not in ['starting', 'stopping', 'stopped']:
                session.runtime_state = 'stopped'
        session.runtime_last_activity = fields.Datetime.now()
        return overall

    @api.model
    def get_session_status(self, session):
        """Structured status dictionary."""
        if session.workspace_id:
            self.env['nexora.runtime_service'].refresh_runtime(session)
        self._update_session_health_and_state(session)
        return {
            'status': session.status,
            'runtime_state': session.runtime_state,
            'runtime_health': session.runtime_health,
            'progress': session.progress_percent,
            'current_stage': session.current_stage,
            'generation_attempts': session.generation_attempts,
        }

    @api.model
    def get_execution_plan(self, session):
        """Return topological startup/shutdown plan."""
        runtime_service = self.env['nexora.runtime_service']
        order = runtime_service.build_dependency_graph()
        return {'startup': list(order), 'shutdown': list(reversed(order))}

    @api.model
    def get_runtime_graph(self, session):
        """Return the runtime dependency graph."""
        runtime_service = self.env['nexora.runtime_service']
        runtime_service.synchronize_runtime_capabilities()
        capabilities = self.env['nexora.runtime_capability'].search([('enabled', '=', True)])
        nodes = [cap.runtime_type for cap in capabilities]
        edges = []
        for cap in capabilities:
            for dep in cap.dependency_ids:
                edges.append({'from': dep.runtime_type, 'to': cap.runtime_type})
        return {'nodes': nodes, 'edges': edges}

    # =================================================================
    # PROGRESS TRACKING
    # =================================================================

    @api.model
    def update_progress(self, session, stage_name, completed, total):
        """Update session progress tracking fields."""
        session.current_stage = stage_name
        session.completed_stages = completed
        session.total_stages = total
        session.progress_percent = (completed / total * 100) if total > 0 else 0
        session.last_activity = fields.Datetime.now()

    # =================================================================
    # VALIDATION
    # =================================================================

    @api.model
    def validate_session(self, session):
        """Comprehensive session validation."""
        errors = []

        # Workspace
        if not session.workspace_id:
            errors.append('No workspace linked.')
        elif not session.workspace_id.workspace_path:
            errors.append('Workspace path not set.')
        elif not os.path.isdir(session.workspace_id.workspace_path):
            errors.append('Workspace directory does not exist on disk.')

        # Configuration
        if not session.builder_configuration_id:
            errors.append('No builder configuration linked.')
        elif session.builder_configuration_id.status == 'draft':
            errors.append('Builder configuration is still in draft.')

        # AI Provider
        try:
            pm = self.env['nexora.ai_provider_manager']
            providers = pm.get_available_providers()
            available = [p for p in providers if p.get('available')]
            if not available:
                errors.append('No AI provider is available.')
        except Exception:
            errors.append('AI Provider Manager check failed.')

        # Git
        if session.workspace_id and session.workspace_id.workspace_path:
            git_dir = os.path.join(session.workspace_id.workspace_path, '.git')
            if not os.path.isdir(git_dir):
                errors.append('Git repository not initialized.')

        return {'valid': len(errors) == 0, 'errors': errors}

    # =================================================================
    # RUNTIME EVENTS
    # =================================================================

    @api.model
    def _emit_event(self, session, event_type, message, runtime=None, runtime_type='session'):
        """Emit a lifecycle event."""
        try:
            with self.env.cr.savepoint():
                r_type = runtime_type
                if runtime and hasattr(runtime, 'runtime_type') and runtime.runtime_type:
                    r_type = runtime.runtime_type
                self.env['nexora.runtime_event'].create({
                    'builder_session_id': session.id,
                    'runtime_id': runtime.id if runtime and hasattr(runtime, 'id') else False,
                    'runtime_type': r_type,
                    'event_type': event_type,
                    'timestamp': fields.Datetime.now(),
                    'message': message,
                })
        except Exception as e:
            _logger.warning('Could not emit event %s for session %s: %s', event_type, session.id, e)

    @api.model
    def get_runtime_events(self, session, limit=50):
        """Return chronological event list."""
        events = self.env['nexora.runtime_event'].search(
            [('builder_session_id', '=', session.id)], limit=limit
        )
        return [{
            'id': ev.id,
            'runtime_type': ev.runtime_type,
            'event_type': ev.event_type,
            'timestamp': str(ev.timestamp),
            'message': ev.message,
        } for ev in events]

    # =================================================================
    # HELPERS
    # =================================================================

    def _require_workspace(self, session):
        """Get workspace or raise."""
        ws = session.workspace_id
        if not ws:
            raise ValidationError(_('Session has no workspace.'))
        return ws

    def _get_git_runtime(self, session):
        """Get the git runtime for a session."""
        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'git'),
        ], limit=1)
        if not runtime:
            raise ValidationError(_('No Git runtime found for this session.'))
        return runtime

    # =================================================================
    # BACKWARD COMPATIBILITY ALIASES (Phase 6A-6E)
    # =================================================================

    @api.model
    def start_runtime(self, session):
        return self.start_session(session)

    @api.model
    def stop_runtime(self, session):
        return self.stop_session(session)

    @api.model
    def restart_runtime(self, session):
        return self.restart_session(session)

    @api.model
    def get_runtime_status(self, session):
        status_dict = self.get_session_status(session)
        return status_dict['runtime_state']
