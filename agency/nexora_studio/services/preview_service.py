# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import socket
import time
import os
import urllib.request
import logging

_logger = logging.getLogger(__name__)

class PreviewService(models.AbstractModel):
    _name = 'nexora.preview_service'
    _inherit = 'nexora.runtime_plugin'
    _description = 'Preview Runtime Service Registry and Lifecycle Manager'

    # In-memory flag to ensure automatic startup recovery once per Odoo worker restart
    _init_done = False

    @api.model
    def plugin_manifest(self):
        return {
            'name': 'Live Preview Server',
            'runtime_type': 'preview',
            'version': '1.0.0',
            'provider': 'nexora',
            'priority': 200,
            'dependencies': ['workspace', 'ide'],
            'supports_health_checks': True,
            'restart_policy': 'on_failure',
            'description': 'Framework-agnostic live preview server lifecycle manager and dynamic port allocator.'
        }

    @api.model
    def _ensure_initialized(self):
        """Ensures startup recovery and orphan cleanup have run since Odoo restart."""
        if not PreviewService._init_done:
            PreviewService._init_done = True
            try:
                self.initialize_service()
            except Exception as e:
                _logger.error(f"Failed during PreviewService initialization: {e}")

    @api.model
    def get_all_launchers(self):
        """
        Dynamically discovers and returns all registered launcher plugin services.
        Sorted by priority descending.
        """
        launchers = []
        base_model = self.env.registry['nexora.preview_launcher']
        for model_name, model_cls in self.env.registry.models.items():
            if model_name != 'nexora.preview_launcher' and issubclass(model_cls, base_model):
                service = self.env.get(model_name)
                if service is not None:
                    try:
                        manifest = service.launcher_manifest()
                        launchers.append((manifest.get('priority', 100), service))
                    except Exception as e:
                        _logger.warning(f"Failed to load launcher manifest for {model_name}: {e}")
        launchers.sort(key=lambda x: x[0], reverse=True)
        return [service for _, service in launchers]

    @api.model
    def resolve_launcher(self, launcher_id):
        """
        Dynamically resolves the launcher plugin service matching `launcher_id` (or backward compatible `launcher_type`).
        Contains zero hardcoded framework or launcher type checks.
        """
        if not launcher_id:
            launcher_id = 'python_http'
            
        for launcher in self.get_all_launchers():
            try:
                manifest = launcher.launcher_manifest()
                if manifest.get('launcher_id') == launcher_id or manifest.get('launcher_type') == launcher_id:
                    return launcher
            except Exception as e:
                _logger.warning(f"Failed checking manifest during resolve_launcher: {e}")
                
        raise ValidationError(_(f"No preview launcher plugin registered for id/type '{launcher_id}'."))

    @api.model
    def detect_launcher(self, project_directory):
        """
        Dynamically selects the appropriate launcher plugin by testing `detect_project(project_directory)`
        across all discovered launcher services in the registry.
        Contains zero hardcoded framework checks or conditional branches.
        """
        best_score = -1
        best_launcher = None
        
        for launcher in self.get_all_launchers():
            try:
                score = launcher.detect_project(project_directory)
                if isinstance(score, bool):
                    score = launcher.launcher_manifest().get('priority', 100) if score else -1
                if isinstance(score, (int, float)) and score > best_score:
                    best_score = score
                    best_launcher = launcher
            except Exception as e:
                _logger.warning(f"Error during detect_project on launcher: {e}")
                
        if best_launcher is not None and best_score >= 0:
            return best_launcher
            
        return self.resolve_launcher('python_http')

    @api.model
    def initialize_service(self):
        """
        Enumerate all nexora.preview_runtime records across all discovered launchers.
        Reattaches valid running servers across Odoo restarts, marks failed/dead
        runtimes as stopped, and delegates orphan cleanup dynamically across all launcher plugins.
        """
        _logger.info("Initializing PreviewService: Recovering runtimes across all discovered launchers and cleaning up orphans...")
        PreviewService._init_done = True
        self.env.flush_all()
        all_preview_runtimes = self.env['nexora.preview_runtime'].search([])
        
        owned_pids = set()
        owned_ports = set()
        
        for preview_rt in all_preview_runtimes:
            runtime = preview_rt.runtime_id
            pid = preview_rt.process_id
            port = preview_rt.allocated_port or (runtime.port if runtime else 0)
            url = preview_rt.preview_url or (runtime.endpoint if runtime else f"http://127.0.0.1:{port}")
            
            _logger.info(f"initialize_service checking preview_rt ID {preview_rt.id}: PID={pid}, Port={port}, URL={url}")
            if pid and pid > 0 and port and port > 0:
                try:
                    launcher = self.resolve_launcher(preview_rt.launcher_type)
                except Exception as e:
                    _logger.warning(f"resolve_launcher failed: {e}")
                    launcher = None
                    
                # Verify 1: Process still exists
                process_alive = launcher._is_process_alive(pid) if (launcher is not None and hasattr(launcher, '_is_process_alive')) else False
                
                # Verify 2: Port is listening
                port_listening = False
                if process_alive:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                            port_listening = True
                    except (ConnectionRefusedError, socket.timeout, OSError):
                        port_listening = False
                        
                # Verify 3: Endpoint responds
                endpoint_responds = False
                if port_listening:
                    try:
                        with urllib.request.urlopen(url, timeout=1.0) as resp:
                            if resp.status < 500:
                                endpoint_responds = True
                    except Exception:
                        endpoint_responds = False
                        
                if process_alive and port_listening and endpoint_responds:
                    _logger.info(f"Reattaching healthy preview runtime ID {preview_rt.id} (PID {pid}, Port {port})")
                    if launcher is not None and hasattr(launcher, 'reattach'):
                        launcher.reattach(pid, port)
                    owned_pids.add(pid)
                    owned_ports.add(port)
                    
                    now = fields.Datetime.now()
                    preview_rt.write({
                        'last_health_check': now,
                        'last_activity': now
                    })
                    if runtime:
                        runtime.write({
                            'status': 'running',
                            'health': 'healthy',
                            'endpoint': url,
                            'port': port,
                            'process_id': pid,
                            'last_activity': now
                        })
                    continue
                else:
                    _logger.warning(f"Preview runtime ID {preview_rt.id} failed recovery checks (PID alive: {process_alive}, Port listening: {port_listening}, Endpoint responds: {endpoint_responds}). Cleaning up state...")
                    if (process_alive or port_listening) and launcher and hasattr(launcher, 'stop'):
                        launcher.stop(preview_rt)
            
            # If checks failed or pid <= 0 -> Mark stopped and clear state
            now = fields.Datetime.now()
            preview_rt.write({
                'process_id': 0,
                'allocated_port': 0,
                'preview_url': '',
                'stopped_at': now,
                'last_activity': now
            })
            if runtime:
                runtime.write({
                    'status': 'stopped',
                    'health': 'critical',
                    'endpoint': '',
                    'port': 0,
                    'process_id': 0,
                    'stopped_at': now,
                    'last_activity': now
                })
                
        # Dynamically delegate Orphan Process Detection & Cleanup to all registered launcher plugins
        for launcher in self.get_all_launchers():
            try:
                if hasattr(launcher, 'cleanup'):
                    launcher.cleanup(owned_pids, owned_ports)
            except Exception as e:
                _logger.warning(f"Error during orphan cleanup for launcher {launcher._name}: {e}")
            
        _logger.info("PreviewService initialization and dynamic orphan cleanup completed.")
        return True

    @api.model
    def allocate_port(self):
        """
        Allocates an available port on the host machine starting at 3000.
        Checks active nexora.preview_runtime allocations and socket binding.
        """
        self._ensure_initialized()
        used_ports = set(self.env['nexora.preview_runtime'].search([('allocated_port', '>', 0)]).mapped('allocated_port'))
        
        for port in range(3000, 4000):
            if port in used_ports:
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", port))
                    return port
            except OSError:
                continue
                
        raise ValidationError(_("No available ports found for Preview Runtime between 3000 and 3999."))

    @api.model
    def release_port(self, runtime):
        """Releases the allocated port for the given runtime instance."""
        preview_rt = self._get_or_create_preview_runtime(runtime)
        if preview_rt and preview_rt.allocated_port > 0:
            preview_rt.allocated_port = 0

    @api.model
    def _get_or_create_preview_runtime(self, runtime):
        preview_rt = self.env['nexora.preview_runtime'].search([('runtime_id', '=', runtime.id)], limit=1)
        if not preview_rt:
            launcher_id = 'python_http'
            try:
                session = runtime.builder_session_id
                workspace_runtime = self.env['nexora.runtime'].search([
                    ('builder_session_id', '=', session.id),
                    ('runtime_type', '=', 'workspace')
                ], limit=1)
                if workspace_runtime:
                    ws_service = self.env['nexora.workspace_service']
                    project_dir = ws_service.get_project_directory(workspace_runtime)
                    if project_dir:
                        launcher = self.detect_launcher(project_dir)
                        manifest = launcher.launcher_manifest()
                        launcher_id = manifest.get('launcher_id') or manifest.get('launcher_type') or 'python_http'
            except Exception as e:
                _logger.warning(f"Could not dynamically detect launcher during creation: {e}")
                
            preview_rt = self.env['nexora.preview_runtime'].create({
                'runtime_id': runtime.id,
                'launcher_type': launcher_id,
                'allocated_port': 0
            })
        return preview_rt

    @api.model
    def validate_launcher_dependencies(self, runtime):
        """Validates launcher dependencies for the given runtime without hardcoded checks."""
        self._ensure_initialized()
        preview_rt = self._get_or_create_preview_runtime(runtime)
        launcher = self.resolve_launcher(preview_rt.launcher_type)
        session = runtime.builder_session_id
        workspace_runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'workspace')
        ], limit=1)
        project_dir = self.env['nexora.workspace_service'].get_project_directory(workspace_runtime) if workspace_runtime else ''
        return launcher.validate(project_dir)

    @api.model
    def start_runtime_instance(self, runtime):
        self.start_preview(runtime)

    @api.model
    def stop_runtime_instance(self, runtime):
        self.stop_preview(runtime)

    @api.model
    def restart_runtime_instance(self, runtime):
        self.restart_preview(runtime)

    @api.model
    def refresh_runtime(self, runtime):
        self.sync_runtime_state(runtime)

    @api.model
    def start_preview(self, runtime):
        """Starts the preview server process using the dynamically resolved launcher."""
        self._ensure_initialized()
        session = runtime.builder_session_id
        workspace_runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'workspace')
        ], limit=1)
        if not workspace_runtime:
            raise ValidationError(_("Workspace runtime not found for this session."))
            
        ws_service = self.env['nexora.workspace_service']
        project_dir = ws_service.get_project_directory(workspace_runtime)
        logs_dir = ws_service.get_logs_directory(workspace_runtime)
        temp_dir = ws_service.get_temp_directory(workspace_runtime)
        
        preview_rt = self._get_or_create_preview_runtime(runtime)
        
        # Re-detect launcher if workspace project directory framework changed or if default was assigned
        detected_launcher = self.detect_launcher(project_dir)
        detected_id = detected_launcher.launcher_manifest().get('launcher_id', 'python_http')
        if preview_rt.launcher_type != detected_id:
            preview_rt.launcher_type = detected_id
            
        if not preview_rt.allocated_port or preview_rt.allocated_port <= 0:
            preview_rt.allocated_port = self.allocate_port()
            
        launcher = self.resolve_launcher(preview_rt.launcher_type)
        
        # Validate through launcher contract before spawning
        val_res = launcher.validate(project_dir)
        if not val_res['valid']:
            raise ValidationError(_(f"Launcher dependency/project validation failed: {'; '.join(val_res['errors'])}"))
            
        pid, cmd, url = launcher.start(project_dir, preview_rt.allocated_port, preview_rt, logs_directory=logs_dir, temp_directory=temp_dir)
        
        now = fields.Datetime.now()
        preview_rt.write({
            'process_id': pid,
            'preview_command': cmd,
            'preview_url': url,
            'started_at': now,
            'last_activity': now,
            'last_health_check': now
        })
        
        runtime.write({
            'status': 'running',
            'health': 'healthy',
            'endpoint': url,
            'port': preview_rt.allocated_port,
            'process_id': pid,
            'started_at': now,
            'last_activity': now
        })

    @api.model
    def stop_preview(self, runtime):
        """
        Stops the preview server process via the dynamically resolved launcher plugin.
        Ensures the underlying process is terminated and the port is confirmed closed
        before marking the runtime state as stopped or clearing allocated_port.
        """
        self._ensure_initialized()
        preview_rt = self._get_or_create_preview_runtime(runtime)
        launcher = self.resolve_launcher(preview_rt.launcher_type)
        port_to_check = preview_rt.allocated_port or runtime.port
        
        # 1. Terminate process via launcher (launcher waits until process table and port are released)
        launcher.stop(preview_rt)
        
        # 2. Confirm the port is actually closed before clearing allocated_port
        if port_to_check and port_to_check > 0:
            start_check = time.time()
            while time.time() - start_check < 5.0:
                try:
                    with socket.create_connection(("127.0.0.1", port_to_check), timeout=0.3):
                        time.sleep(0.1)
                except (ConnectionRefusedError, socket.timeout, OSError):
                    break
                    
        # 3. Release port now that process and socket are confirmed closed
        self.release_port(runtime)
        
        now = fields.Datetime.now()
        preview_rt.write({
            'process_id': 0,
            'preview_url': '',
            'stopped_at': now,
            'last_activity': now
        })
        
        # 4. Update runtime state only AFTER underlying process exited
        runtime.write({
            'status': 'stopped',
            'health': 'critical',
            'endpoint': '',
            'process_id': 0,
            'stopped_at': now,
            'last_activity': now
        })
        
        # 5. Ensure check_health() reports critical after shutdown
        self.check_health(runtime)

    @api.model
    def restart_preview(self, runtime):
        """Restarts the preview server process."""
        self.stop_preview(runtime)
        self.start_preview(runtime)

    @api.model
    def check_health(self, runtime):
        """Checks the health of the preview server process via the launcher plugin."""
        self._ensure_initialized()
        preview_rt = self._get_or_create_preview_runtime(runtime)
        launcher = self.resolve_launcher(preview_rt.launcher_type)
        
        health_status = launcher.health(preview_rt)
        now = fields.Datetime.now()
        
        preview_rt.last_health_check = now
        runtime.write({
            'health': health_status,
            'last_activity': now
        })
        if health_status == 'critical' and runtime.status == 'running':
            runtime.status = 'error'
        return health_status

    @api.model
    def get_preview_url(self, runtime):
        self._ensure_initialized()
        preview_rt = self._get_or_create_preview_runtime(runtime)
        return preview_rt.preview_url

    @api.model
    def get_preview_status(self, runtime):
        """Returns structured runtime status conforming to the Phase 6E Health Contract across all frameworks."""
        self._ensure_initialized()
        preview_rt = self._get_or_create_preview_runtime(runtime)
        launcher = self.resolve_launcher(preview_rt.launcher_type)
        info = launcher.get_runtime_info(preview_rt)
        # Ensure backward compatibility with any older check requiring allocated_port or preview_command top-level
        info['allocated_port'] = preview_rt.allocated_port
        info['preview_command'] = preview_rt.preview_command
        info['launcher_type'] = preview_rt.launcher_type
        return info

    @api.model
    def sync_runtime_state(self, runtime):
        self.check_health(runtime)
