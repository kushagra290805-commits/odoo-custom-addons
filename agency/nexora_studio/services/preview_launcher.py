# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

class PreviewLauncher(models.AbstractModel):
    _name = 'nexora.preview_launcher'
    _description = 'Abstract Preview Launcher Plugin Base Class'

    @api.model
    def launcher_manifest(self):
        """
        Returns launcher metadata conforming to Phase 6E contract:
        {
            'launcher_id': str,             # e.g., 'python_http', 'static_file', 'vite'
            'launcher_type': str,           # backward compatible alias for launcher_id
            'display_name': str,            # e.g., 'Python HTTP Server'
            'supported_frameworks': list,   # e.g., ['python', 'html', 'static']
            'priority': int,                # e.g., 100, 200 (higher priority tested first during detection)
            'supported_platforms': list,    # e.g., ['win32', 'darwin', 'linux']
            'dependency_requirements': list,# e.g., ['python'] or ['node', 'npm']
            'health_strategy': str,         # e.g., 'http_and_socket'
            'recovery_strategy': str,       # e.g., 'process_cache_and_port'
            'description': str,
            'version': str,
            'provider': str
        }
        """
        raise NotImplementedError("Launchers must implement launcher_manifest")

    @api.model
    def validate(self, project_directory):
        """
        Verifies required dependencies and project validity before startup.
        Returns structured validation dict:
        {
            'valid': bool,
            'errors': list,                # List of error message strings if invalid
            'warnings': list,              # List of warning message strings
            'dependencies_checked': dict   # e.g., {'node': True, 'npm': True}
        }
        """
        raise NotImplementedError("Launchers must implement validate")

    @api.model
    def prepare(self, project_directory, port, runtime, **kwargs):
        """
        Prepares the execution environment before startup (e.g., configures command, env vars, log paths).
        Returns dict with preparation metadata: {'ready': bool, 'command': list, 'env': dict, 'log_file': str}
        """
        raise NotImplementedError("Launchers must implement prepare")

    @api.model
    def start(self, project_directory, port, runtime, logs_directory=None, temp_directory=None):
        """
        Spawns the preview process using validated and prepared settings.
        Returns: tuple(process_id: int, preview_command: str, preview_url: str)
        """
        raise NotImplementedError("Launchers must implement start")

    @api.model
    def stop(self, runtime):
        """
        Gracefully terminates the preview server process and releases ports.
        Returns: bool
        """
        raise NotImplementedError("Launchers must implement stop")

    @api.model
    def restart(self, project_directory, port, runtime, logs_directory=None, temp_directory=None):
        """
        Restarts the preview server process.
        Returns: tuple(process_id: int, preview_command: str, preview_url: str)
        """
        self.stop(runtime)
        return self.start(project_directory, port, runtime, logs_directory=logs_directory, temp_directory=temp_directory)

    @api.model
    def health(self, runtime):
        """
        Verifies if the preview server process is alive/healthy.
        Returns: str ('healthy' or 'critical')
        """
        raise NotImplementedError("Launchers must implement health")

    @api.model
    def reattach(self, pid, port):
        """Reconstructs in-memory process cache after Odoo server restart."""
        raise NotImplementedError("Launchers must implement reattach")

    @api.model
    def cleanup(self, owned_pids=None, owned_ports=None):
        """Scans for and cleanly terminates any unmanaged orphan processes of this launcher strategy."""
        return []

    @api.model
    def get_runtime_info(self, runtime):
        """
        Exposes standardized, structured runtime information identical across all frameworks.
        Returns:
        {
            'status': str,
            'health': str,
            'pid': int,
            'port': int,
            'endpoint': str,
            'process_information': dict,
            'last_health_check': str,
            'last_activity': str
        }
        """
        pid = getattr(runtime, 'process_id', 0)
        port = getattr(runtime, 'port', 0)
        if hasattr(runtime, 'allocated_port') and runtime.allocated_port:
            port = runtime.allocated_port
        url = getattr(runtime, 'endpoint', '') or (getattr(runtime, 'preview_url', '') if hasattr(runtime, 'preview_url') else f"http://127.0.0.1:{port}")
        
        health_status = self.health(runtime) if pid and pid > 0 else 'critical'
        status = getattr(runtime, 'status', 'stopped') if pid and pid > 0 else 'stopped'
        
        last_check = getattr(runtime, 'last_health_check', None)
        last_act = getattr(runtime, 'last_activity', None)
        
        return {
            'status': status,
            'health': health_status,
            'pid': pid,
            'port': port,
            'endpoint': url if pid > 0 else '',
            'process_information': {
                'launcher_id': self.launcher_manifest().get('launcher_id', ''),
                'display_name': self.launcher_manifest().get('display_name', ''),
                'command': getattr(runtime, 'preview_command', '') if hasattr(runtime, 'preview_command') else ''
            },
            'last_health_check': fields.Datetime.to_string(last_check) if last_check else fields.Datetime.to_string(fields.Datetime.now()),
            'last_activity': fields.Datetime.to_string(last_act) if last_act else fields.Datetime.to_string(fields.Datetime.now())
        }

    @api.model
    def detect_project(self, project_directory):
        """
        Inspects the project directory (`package.json`, `index.html`, etc.) to determine if this launcher handles the workspace.
        Returns: bool or int (match score >= 0, where higher score indicates stronger framework fit).
        """
        return False
