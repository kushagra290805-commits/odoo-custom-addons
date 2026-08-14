# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import logging
import json
import os

_logger = logging.getLogger(__name__)

# In-memory flag: ensure recovery runs only once per Odoo worker restart
_init_done = False


class IDEService(models.AbstractModel):
    """
    IDE Runtime Plugin — implements the full nexora.runtime_plugin lifecycle contract.

    Registers as Runtime Capability 'ide' with priority 175 and dependencies
    ['workspace', 'git']. Kahn's topological sorting algorithm in RuntimeService
    automatically computes:

        Startup:  Workspace (100) → Git (150) → IDE (175) → Preview (200)
        Shutdown: Preview → IDE → Git → Workspace

    No ordering is hardcoded here, in BuilderSessionService, or in RuntimeService.

    Dynamic Launcher Discovery:
        Mirrors PreviewService.get_all_launchers(). Discovers all subclasses of
        nexora.ide_launcher, scores each via detect(workspace_path), and selects
        the highest-scoring launcher. Zero IDE-specific conditionals.

    Public API (delegates to runtime lifecycle):
        start_ide(session)
        stop_ide(session)
        restart_ide(session)
        attach_workspace(session, workspace_path)
        detach_workspace(session)
        get_ide_status(session)

    ADR Reference: ADR-0009 §5
    """
    _name = 'nexora.ide_service'
    _inherit = 'nexora.runtime_plugin'
    _description = 'IDE Runtime Service Plugin'

    @api.model
    def plugin_manifest(self):
        return {
            'name': 'IDE Runtime',
            'runtime_type': 'ide',
            'version': '1.0.0',
            'provider': 'nexora',
            'priority': 175,               # Between Git (150) and Preview (200)
            'dependencies': ['workspace', 'git'],
            'supports_health_checks': True,
            'restart_policy': 'on_failure',
            'description': 'Framework-agnostic IDE lifecycle manager and workspace synchronization service.',
            'capabilities': ['launch', 'attach', 'detach', 'monitor', 'recover']
        }

    # ----------------------------------------------------------
    # Launcher Discovery (mirrors PreviewService pattern exactly)
    # ----------------------------------------------------------

    @api.model
    def get_all_launchers(self):
        """
        Dynamically discovers and returns all registered IDE launcher plugin services.
        Sorted by priority descending (highest priority evaluated first during detection).
        Contains zero IDE-specific conditionals.
        """
        launchers = []
        base_model = self.env.registry['nexora.ide_launcher']
        for model_name, model_cls in self.env.registry.models.items():
            if model_name != 'nexora.ide_launcher' and issubclass(model_cls, base_model):
                service = self.env.get(model_name)
                if service is not None:
                    try:
                        manifest = service.launcher_manifest()
                        launchers.append((manifest.get('priority', 100), service))
                    except Exception as e:
                        _logger.warning(f"IDEService: Failed to load launcher manifest for {model_name}: {e}")
        launchers.sort(key=lambda x: x[0], reverse=True)
        return [service for _, service in launchers]

    @api.model
    def detect_launcher(self, workspace_path):
        """
        Score-based dynamic launcher selection across all discovered IDE launchers.
        No if/elif IDE-type checks. Entirely metadata-driven.
        Falls back to the first registered launcher if no positive score is detected.
        """
        best_score = -1
        best_launcher = None

        for launcher in self.get_all_launchers():
            try:
                score = launcher.detect(workspace_path)
                if isinstance(score, bool):
                    score = launcher.launcher_manifest().get('priority', 100) if score else -1
                if isinstance(score, (int, float)) and score > best_score:
                    best_score = score
                    best_launcher = launcher
            except Exception as e:
                _logger.warning(f"IDEService: Error during detect() on launcher: {e}")

        if best_launcher is not None and best_score >= 0:
            return best_launcher

        # Fallback: return highest-priority available launcher
        all_launchers = self.get_all_launchers()
        if all_launchers:
            return all_launchers[0]

        raise ValidationError(_("No IDE launcher plugins are registered in the runtime registry."))

    @api.model
    def resolve_launcher(self, launcher_id):
        """
        Resolves a launcher by its launcher_id string. Used when a specific launcher
        has been previously persisted in runtime.metadata_json.
        """
        if not launcher_id:
            return self.detect_launcher('')

        for launcher in self.get_all_launchers():
            try:
                manifest = launcher.launcher_manifest()
                if manifest.get('launcher_id') == launcher_id:
                    return launcher
            except Exception as e:
                _logger.warning(f"IDEService: Failed checking manifest during resolve_launcher: {e}")

        raise ValidationError(_(f"No IDE launcher plugin registered for id '{launcher_id}'."))

    # ----------------------------------------------------------
    # Initialization & Recovery
    # ----------------------------------------------------------

    @api.model
    def _ensure_initialized(self):
        """Ensures startup recovery runs only once per Odoo worker restart."""
        global _init_done
        if not _init_done:
            _init_done = True
            try:
                self.initialize_service()
            except Exception as e:
                _logger.error(f"IDEService: Failed during initialization: {e}")

    @api.model
    def initialize_service(self):
        """
        On Odoo restart: scan all nexora.runtime records with runtime_type='ide'.
        Attempt to reattach live IDE processes. Mark dead ones as stopped.
        Delegates orphan cleanup to all launcher plugins.
        """
        _logger.info("IDEService: Initializing — recovering IDE runtimes across all discovered launchers...")
        global _init_done
        _init_done = True
        IDEService._init_done = True   # Class-level guard (checked by runtime_service)
        self.env.flush_all()

        ide_runtimes = self.env['nexora.runtime'].search([('runtime_type', '=', 'ide')])
        owned_pids = set()

        for runtime in ide_runtimes:
            meta = {}
            try:
                raw = getattr(runtime, 'metadata_json', '') or '{}'
                meta = json.loads(raw)
            except Exception:
                pass

            pid = meta.get('ide_pid', 0) or runtime.process_id
            workspace_path = meta.get('workspace_path', '') or runtime.endpoint
            launcher_id = meta.get('launcher_id', '')
            attachment_status = meta.get('attachment_status', 'detached')

            # Skip runtimes already running and attached — externally-managed IDEs
            # (pid=0 is valid for IDEs not yet self-reporting their PID)
            if runtime.status == 'running' and attachment_status == 'attached':
                owned_pids.add(pid) if pid else None
                continue

            if attachment_status == 'attached' and pid and pid > 0:
                try:
                    launcher = self.resolve_launcher(launcher_id) if launcher_id else self.detect_launcher(workspace_path)
                except Exception:
                    launcher = None

                alive = False
                if launcher is not None and hasattr(launcher, 'reattach'):
                    try:
                        alive = launcher.reattach(pid, workspace_path)
                    except Exception as e:
                        _logger.warning(f"IDEService: reattach failed for PID {pid}: {e}")

                if alive:
                    _logger.info(f"IDEService: Reattached IDE runtime ID {runtime.id} (PID {pid})")
                    owned_pids.add(pid)
                    now = fields.Datetime.now()
                    runtime.write({
                        'status': 'running',
                        'health': 'healthy',
                        'last_activity': now
                    })
                    continue

            # Recovery failed — mark stopped
            now = fields.Datetime.now()
            meta['attachment_status'] = 'detached'
            meta['ide_pid'] = 0
            runtime.write({
                'status': 'stopped',
                'health': 'critical',
                'process_id': 0,
                'endpoint': '',
                'stopped_at': now,
                'last_activity': now,
                'metadata_json': json.dumps(meta)
            })

        # Delegate orphan cleanup to all launchers
        for launcher in self.get_all_launchers():
            try:
                if hasattr(launcher, 'cleanup'):
                    launcher.cleanup(owned_pids)
            except Exception as e:
                _logger.warning(f"IDEService: Orphan cleanup error for {launcher._name}: {e}")

        _logger.info("IDEService: Initialization complete.")
        return True

    # ----------------------------------------------------------
    # RuntimePlugin Lifecycle Contract (ADR-0005)
    # ----------------------------------------------------------

    @api.model
    def start_runtime_instance(self, runtime):
        """
        Starts the IDE runtime:
          1. Resolve workspace path from the session's workspace runtime.
          2. Detect the best IDE launcher.
          3. Validate.
          4. Launch and persist metadata.
        """
        self._ensure_initialized()
        session = runtime.builder_session_id
        workspace_path = self._get_workspace_path(session)

        launcher = self.detect_launcher(workspace_path)

        val_result = launcher.validate(workspace_path)
        if not val_result['valid']:
            _logger.warning(f"IDEService: Launcher validation warnings: {val_result['errors']}")
            # IDE launch is soft-fail by design: workspace may not have an open IDE yet
            # We attach anyway, health will reflect actual state

        session_context = {
            'session_uuid': session.session_uuid,
            'workspace_uuid': session.workspace_id.workspace_uuid if session.workspace_id else '',
        }

        result = launcher.launch(workspace_path, session_context, runtime)

        now = fields.Datetime.now()
        pid = result.get('pid', 0)
        manifest = launcher.launcher_manifest()

        # Persist launch state into generic runtime fields
        runtime.write({
            'status': 'running',
            'health': 'healthy',
            'endpoint': workspace_path,
            'process_id': pid,
            'version': manifest.get('version', '1.0.0'),
            'started_at': now,
            'last_activity': now,
        })

        _logger.info(f"IDEService: IDE runtime started (launcher={manifest.get('launcher_id')}, workspace={workspace_path})")

    @api.model
    def stop_runtime_instance(self, runtime):
        """Stops the IDE runtime by resolving the launcher and calling stop()."""
        self._ensure_initialized()
        launcher = self._resolve_launcher_from_runtime(runtime)

        launcher.stop(runtime)

        now = fields.Datetime.now()
        runtime.write({
            'status': 'stopped',
            'health': 'critical',
            'process_id': 0,
            'endpoint': '',
            'stopped_at': now,
            'last_activity': now,
        })
        _logger.info(f"IDEService: IDE runtime stopped (runtime ID {runtime.id})")

    @api.model
    def restart_runtime_instance(self, runtime):
        """Restarts the IDE runtime: stop then start."""
        self.stop_runtime_instance(runtime)
        self.start_runtime_instance(runtime)

    @api.model
    def recover_runtime_instance(self, runtime):
        """
        Recovery hook called by BuilderSessionService.recover_session().
        Attempts to reattach the IDE process from persisted metadata.
        """
        self._ensure_initialized()
        meta = {}
        try:
            raw = getattr(runtime, 'metadata_json', '') or '{}'
            meta = json.loads(raw)
        except Exception:
            pass

        pid = meta.get('ide_pid', 0) or runtime.process_id
        workspace_path = meta.get('workspace_path', '') or runtime.endpoint
        launcher_id = meta.get('launcher_id', '')

        try:
            launcher = self.resolve_launcher(launcher_id) if launcher_id else self.detect_launcher(workspace_path)
        except Exception:
            launcher = None

        alive = False
        if launcher is not None:
            try:
                alive = launcher.reattach(pid, workspace_path)
            except Exception as e:
                _logger.warning(f"IDEService: recover reattach failed: {e}")

        now = fields.Datetime.now()
        if alive:
            runtime.write({
                'status': 'running',
                'health': 'healthy',
                'last_activity': now
            })
            _logger.info(f"IDEService: IDE runtime recovered (PID {pid})")
        elif workspace_path:
            # Relaunch using the persisted workspace_path from metadata — avoids
            # calling _get_workspace_path() which can fail if workspace runtime
            # endpoint is not yet restored during recovery.
            _logger.info(f"IDEService: IDE process not alive — re-launching at '{workspace_path}'.")
            session = runtime.builder_session_id
            session_context = {
                'session_uuid': session.session_uuid,
                'workspace_uuid': session.workspace_id.workspace_uuid if session.workspace_id else '',
            }
            if launcher is None:
                launcher = self.detect_launcher(workspace_path)
            try:
                result = launcher.launch(workspace_path, session_context, runtime)
                pid_new = result.get('pid', 0)
                manifest = launcher.launcher_manifest()
                runtime.write({
                    'status': 'running',
                    'health': 'healthy',
                    'endpoint': workspace_path,
                    'process_id': pid_new,
                    'version': manifest.get('version', '1.0.0'),
                    'started_at': now,
                    'last_activity': now,
                })
                _logger.info(f"IDEService: IDE runtime re-launched during recovery (launcher={manifest.get('launcher_id')}, workspace={workspace_path})")
            except Exception as relaunch_ex:
                import traceback
                _logger.error(f"IDEService: re-launch failed during recovery: {relaunch_ex}\n{traceback.format_exc()}")
        else:
            # No persisted workspace path — fall back to full start_runtime_instance
            _logger.info("IDEService: IDE process not alive, no persisted path — full re-launch via start_runtime_instance.")
            self.start_runtime_instance(runtime)

    @api.model
    def check_health(self, runtime):
        """Checks IDE health via the launcher plugin and updates runtime.health."""
        self._ensure_initialized()
        launcher = self._resolve_launcher_from_runtime(runtime)

        health_status = launcher.health(runtime)
        now = fields.Datetime.now()
        runtime.write({
            'health': health_status,
            'last_activity': now
        })
        if health_status == 'critical' and runtime.status == 'running':
            runtime.status = 'error'
        return health_status

    @api.model
    def refresh_runtime(self, runtime):
        """Refresh runtime state (delegates to check_health)."""
        self.check_health(runtime)

    # ----------------------------------------------------------
    # Public Convenience API
    # ----------------------------------------------------------

    @api.model
    def start_ide(self, session):
        """Public API: Start IDE runtime for the session."""
        runtime = self._get_ide_runtime(session)
        return self.start_runtime_instance(runtime)

    @api.model
    def stop_ide(self, session):
        """Public API: Stop IDE runtime for the session."""
        runtime = self._get_ide_runtime(session)
        return self.stop_runtime_instance(runtime)

    @api.model
    def restart_ide(self, session):
        """Public API: Restart IDE runtime for the session."""
        runtime = self._get_ide_runtime(session)
        return self.restart_runtime_instance(runtime)

    @api.model
    def attach_workspace(self, session, workspace_path):
        """
        Public API: Attach (or re-attach) a workspace path to the IDE runtime.
        Updates the sidecar file and runtime metadata.
        """
        runtime = self._get_ide_runtime(session)
        launcher = self._resolve_launcher_from_runtime(runtime)
        session_context = {
            'session_uuid': session.session_uuid,
            'workspace_uuid': session.workspace_id.workspace_uuid if session.workspace_id else '',
        }
        return launcher.launch(workspace_path, session_context, runtime)

    @api.model
    def detach_workspace(self, session):
        """Public API: Detach workspace from IDE runtime."""
        runtime = self._get_ide_runtime(session)
        launcher = self._resolve_launcher_from_runtime(runtime)
        return launcher.stop(runtime)

    @api.model
    def get_ide_status(self, session):
        """
        Public API: Returns structured IDE runtime status.
        Used by AI agents, MCP integrations, and UI components.
        """
        runtime = self._get_ide_runtime(session)
        launcher = self._resolve_launcher_from_runtime(runtime)
        return launcher.get_runtime_info(runtime)

    @api.model
    def open_workspace_in_explorer(self, session):
        """
        Public API: Opens the session's workspace path in Windows Explorer via the resolved launcher.
        Handles missing directories gracefully with a user-facing error.
        """
        workspace_path = session.ide_workspace_path
        if not workspace_path and session.workspace_id:
            workspace_path = session.workspace_id.workspace_path
        if not workspace_path:
            try:
                workspace_path = self._get_workspace_path(session)
            except Exception:
                pass

        if not workspace_path or not os.path.exists(workspace_path):
            raise ValidationError(_("The workspace directory does not exist or is inaccessible: %s") % (workspace_path or 'Not specified'))

        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'ide')
        ], limit=1)

        if runtime:
            launcher = self._resolve_launcher_from_runtime(runtime)
        else:
            launcher = self.detect_launcher(workspace_path)

        return launcher.open_in_explorer(workspace_path)

    # ----------------------------------------------------------
    # Internal Helpers
    # ----------------------------------------------------------

    @api.model
    def _get_workspace_path(self, session):
        """Resolves the project directory path from the session's workspace runtime."""
        workspace_runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'workspace')
        ], limit=1)

        if not workspace_runtime:
            raise ValidationError(_("Workspace runtime not found for this session. Cannot start IDE."))

        return self.env['nexora.workspace_service'].get_project_directory(workspace_runtime)

    @api.model
    def _get_ide_runtime(self, session):
        """Finds or raises for the IDE nexora.runtime record owned by the session."""
        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'ide')
        ], limit=1)
        if not runtime:
            raise ValidationError(_("IDE runtime record not found for this session."))
        return runtime

    @api.model
    def _resolve_launcher_from_runtime(self, runtime):
        """Resolves the launcher from the persisted launcher_id in runtime.metadata_json."""
        meta = {}
        try:
            raw = getattr(runtime, 'metadata_json', '') or '{}'
            meta = json.loads(raw)
        except Exception:
            pass

        launcher_id = meta.get('launcher_id', '')
        workspace_path = meta.get('workspace_path', '') or runtime.endpoint or ''

        try:
            if launcher_id:
                return self.resolve_launcher(launcher_id)
        except Exception:
            pass

        return self.detect_launcher(workspace_path)
