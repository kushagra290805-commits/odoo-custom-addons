# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import os

class IDELauncher(models.AbstractModel):
    """
    Abstract base class defining the IDE Launcher Contract.

    All IDE launcher plugins must inherit from this model and implement every
    abstract method. Concrete launchers are discovered dynamically by IDEService
    using score-based launcher selection (identical to PreviewService/PreviewLauncher).

    Current implementations:
        nexora.ide_launcher_antigravity  — Antigravity IDE

    Future implementations (plug-in without modifying IDEService):
        nexora.ide_launcher_vscode       — Visual Studio Code
        nexora.ide_launcher_cursor       — Cursor
        nexora.ide_launcher_windsurf     — Windsurf
        nexora.ide_launcher_zed         — Zed

    ADR Reference: ADR-0009 §3 — IDE Launcher Abstraction
    """
    _name = 'nexora.ide_launcher'
    _description = 'Abstract IDE Launcher Plugin Base Class'

    @api.model
    def launcher_manifest(self):
        """
        Returns launcher metadata conforming to the Phase 6G IDE Launcher Contract:
        {
            'launcher_id': str,              # e.g., 'antigravity', 'vscode', 'cursor'
            'display_name': str,             # e.g., 'Antigravity IDE'
            'priority': int,                 # Detection priority (higher wins)
            'supported_platforms': list,     # e.g., ['win32', 'darwin', 'linux']
            'dependency_requirements': list, # e.g., ['antigravity_ide']
            'description': str,
            'version': str,
            'provider': str
        }
        """
        raise NotImplementedError("IDE Launchers must implement launcher_manifest()")

    @api.model
    def detect(self, workspace_path):
        """
        Inspects the host environment to determine whether this IDE is available and
        matches the given workspace. Returns a match score (int >= 0) or False.
        Higher score indicates stronger fit. IDEService selects the highest-scoring launcher.
        """
        return False

    @api.model
    def validate(self, workspace_path):
        """
        Verifies IDE availability and workspace validity before launch.
        Returns:
        {
            'valid': bool,
            'errors': list,
            'warnings': list,
            'dependencies_checked': dict
        }
        """
        raise NotImplementedError("IDE Launchers must implement validate()")

    @api.model
    def launch(self, workspace_path, session_context, runtime):
        """
        Attaches the IDE to the given workspace. For IDEs managed externally (e.g.,
        Antigravity), this means recording the active process PID and workspace mapping.
        For IDEs launched by Odoo (future), this spawns the process.

        Args:
            workspace_path: str — absolute path to the project root
            session_context: dict — {'session_uuid': str, 'workspace_uuid': str}
            runtime: nexora.runtime record

        Returns: dict with launch metadata:
        {
            'pid': int,
            'ide_name': str,
            'workspace_path': str,
            'attachment_status': str   # 'attached' | 'detached' | 'error'
        }
        """
        raise NotImplementedError("IDE Launchers must implement launch()")

    @api.model
    def stop(self, runtime):
        """
        Detaches the IDE from the workspace. Clears PID and workspace metadata.
        Returns: bool
        """
        raise NotImplementedError("IDE Launchers must implement stop()")

    @api.model
    def restart(self, workspace_path, session_context, runtime):
        """
        Restarts the IDE attachment. Default implementation: stop then launch.
        Returns: dict (same structure as launch())
        """
        self.stop(runtime)
        return self.launch(workspace_path, session_context, runtime)

    @api.model
    def health(self, runtime):
        """
        Verifies whether the IDE process is alive and the workspace remains open.
        Returns: str — 'healthy' or 'critical'
        """
        raise NotImplementedError("IDE Launchers must implement health()")

    @api.model
    def reattach(self, pid, workspace_path):
        """
        Reconstructs in-memory state after Odoo server restart by verifying the IDE
        process at `pid` is still alive and has `workspace_path` open.
        Returns: bool — True if successfully reattached
        """
        raise NotImplementedError("IDE Launchers must implement reattach()")

    @api.model
    def cleanup(self, owned_pids=None):
        """
        Scans for and clears unmanaged IDE process records. Called during service
        initialization to clean up orphan state from prior sessions.
        Returns: list of cleared PIDs
        """
        return []

    @api.model
    def get_runtime_info(self, runtime):
        """
        Returns standardized, structured runtime information identical across all
        IDE launcher implementations.

        Returns:
        {
            'status': str,
            'health': str,
            'pid': int,
            'ide_name': str,
            'ide_version': str,
            'workspace_path': str,
            'attachment_status': str,
            'last_health_check': str,
            'last_activity': str,
            'launcher_info': dict
        }
        """
        import json
        meta = {}
        try:
            raw = getattr(runtime, 'metadata_json', '') or '{}'
            meta = json.loads(raw)
        except Exception:
            pass

        pid = meta.get('ide_pid', 0) or getattr(runtime, 'process_id', 0)
        workspace_path = meta.get('workspace_path', '') or getattr(runtime, 'endpoint', '')
        health_status = self.health(runtime) if pid and pid > 0 else 'critical'
        status = getattr(runtime, 'status', 'stopped')

        last_check = getattr(runtime, 'last_activity', None)
        manifest = self.launcher_manifest()

        return {
            'status': status,
            'health': health_status,
            'pid': pid,
            'ide_name': manifest.get('display_name', 'IDE'),
            'ide_version': manifest.get('version', '1.0.0'),
            'workspace_path': workspace_path,
            'attachment_status': meta.get('attachment_status', 'detached'),
            'last_health_check': fields.Datetime.to_string(last_check) if last_check else fields.Datetime.to_string(fields.Datetime.now()),
            'last_activity': fields.Datetime.to_string(last_check) if last_check else fields.Datetime.to_string(fields.Datetime.now()),
            'launcher_info': {
                'launcher_id': manifest.get('launcher_id', ''),
                'display_name': manifest.get('display_name', ''),
            }
        }

    @api.model
    def open_in_explorer(self, workspace_path):
        """
        Opens the workspace directory in the host system's file explorer (Windows Explorer).
        Handles missing directories gracefully with a clean user-facing ValidationError.
        """
        if not workspace_path or not os.path.exists(workspace_path):
            raise ValidationError(_("The workspace directory does not exist or is inaccessible: %s") % (workspace_path or 'Not specified'))
        try:
            if os.name == 'nt':
                os.startfile(workspace_path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open' if os.name == 'posix' else 'open', workspace_path])
            return True
        except Exception as e:
            raise ValidationError(_("Failed to open workspace directory in Explorer: %s") % e)

