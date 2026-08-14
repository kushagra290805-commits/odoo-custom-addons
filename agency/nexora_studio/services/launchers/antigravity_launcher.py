# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import json
import logging
import os
import shutil
import subprocess
import urllib.parse
from datetime import datetime, timezone
import psutil

_logger = logging.getLogger(__name__)

# Cache: { session_uuid: {'pid': int, 'start_time': float, 'heartbeat': str} }
_active_antigravity_processes = {}

class AntigravityIDELauncher(models.AbstractModel):
    _name = 'nexora.ide_launcher_antigravity'
    _inherit = 'nexora.ide_launcher'
    _description = 'Antigravity IDE Launcher Plugin'

    @api.model
    def launcher_manifest(self):
        return {
            'launcher_id': 'antigravity',
            'display_name': 'Antigravity IDE',
            'priority': 200,
            'supported_platforms': ['win32', 'darwin', 'linux'],
            'dependency_requirements': ['antigravity_ide'],
            'description': 'First-class Antigravity IDE workspace attachment and session synchronization.',
            'version': '1.0.0',
            'provider': 'nexora'
        }

    @api.model
    def detect(self, workspace_path):
        try:
            if workspace_path and os.path.isdir(workspace_path):
                sidecar = os.path.join(workspace_path, '.nexora_session.json')
                if os.path.exists(sidecar):
                    return self.launcher_manifest().get('priority', 200)
            return self.launcher_manifest().get('priority', 200)
        except Exception:
            return 0

    @api.model
    def validate(self, workspace_path):
        errors = []
        warnings = []
        checked = {}

        if not workspace_path:
            errors.append("Workspace path is empty or not provided.")
            checked['workspace_path'] = False
        elif not os.path.isdir(workspace_path):
            errors.append(f"Workspace directory '{workspace_path}' does not exist.")
            checked['workspace_path'] = False
        else:
            checked['workspace_path'] = True
            if not os.access(workspace_path, os.W_OK):
                warnings.append(f"Workspace directory '{workspace_path}' may not be writable.")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'dependencies_checked': checked
        }

    @api.model
    def _is_workspace_open_in_ide(self, workspace_path):
        if not workspace_path or not os.path.exists(workspace_path):
            return False
        norm_path = os.path.normcase(os.path.abspath(workspace_path)).replace('\\', '/')
        storage_candidates = [
            os.path.expandvars(r'%APPDATA%\Antigravity IDE\User\globalStorage\storage.json'),
            os.path.expandvars(r'%APPDATA%\Antigravity\User\globalStorage\storage.json')
        ]
        for storage_path in storage_candidates:
            if os.path.exists(storage_path):
                try:
                    with open(storage_path, 'r', encoding='utf-8', errors='ignore') as f:
                        data = json.load(f)
                    windows_state = data.get('windowsState', {})
                    opened_windows = list(windows_state.get('openedWindows', []))
                    last_active = windows_state.get('lastActiveWindow', {})
                    if isinstance(last_active, dict) and last_active:
                        opened_windows.append(last_active)
                    for win in opened_windows:
                        if isinstance(win, dict):
                            folder_url = win.get('folder', '') or win.get('workspace', {}).get('configPath', '')
                            if folder_url:
                                decoded = urllib.parse.unquote(folder_url)
                                if norm_path in os.path.normcase(decoded).replace('\\', '/'):
                                    return True
                except Exception:
                    pass
        return False

    @api.model
    def _find_root_ide_pid(self):
        ide_names = ('antigravity ide.exe', 'antigravity.exe', 'antigravity ide', 'antigravity', 'code.exe', 'code')
        candidates = {}
        for p in psutil.process_iter(['pid', 'name', 'ppid', 'create_time']):
            try:
                name = (p.info['name'] or '').lower()
                if any(name.startswith(n) for n in ide_names):
                    candidates[p.info['pid']] = p
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        for pid, p in candidates.items():
            try:
                ppid = p.info['ppid']
                if ppid not in candidates:
                    return pid, p.info['create_time']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return 0, 0.0

    @api.model
    def launch(self, workspace_path, session_context, runtime):
        session_uuid = session_context.get('session_uuid', '')
        workspace_uuid = session_context.get('workspace_uuid', '')
        
        # 1. Database is source of truth, check runtime metadata first
        meta = {}
        if runtime:
            raw = getattr(runtime, 'metadata_json', '') or '{}'
            try:
                meta = json.loads(raw)
            except Exception:
                pass
        
        pid = meta.get('ide_pid', 0)
        start_time = meta.get('process_start_time', 0.0)
        
        # Sync cache with database if missing
        if session_uuid not in _active_antigravity_processes and pid > 0:
            _active_antigravity_processes[session_uuid] = {
                'pid': pid,
                'start_time': start_time,
                'heartbeat': meta.get('heartbeat_timestamp')
            }
            
        cached = _active_antigravity_processes.get(session_uuid, {})
        pid = cached.get('pid', pid)
        start_time = cached.get('start_time', start_time)

        # 2. Check live process
        is_alive = False
        if pid > 0:
            try:
                p = psutil.Process(pid)
                if start_time and abs(p.create_time() - start_time) < 1.0:
                    is_alive = True
                elif not start_time:
                    is_alive = True
            except psutil.NoSuchProcess:
                pass

        if not is_alive and os.environ.get('INTEGRATION_MODE', '0') == '1':
            root_pid, root_start_time = self._find_root_ide_pid()
            if root_pid > 0 and os.path.exists(os.path.join(workspace_path, '.nexora_session.json')):
                if self._is_workspace_open_in_ide(workspace_path):
                    pid, start_time = root_pid, root_start_time
                    is_alive = True

        # Write sidecar
        sidecar_path = os.path.join(workspace_path, '.nexora_session.json')
        sidecar_data = {
            'session_uuid': session_uuid,
            'workspace_uuid': workspace_uuid,
            'project_root': workspace_path,
            'runtime_status': runtime.status if runtime else 'starting',
            'attachment_status': 'attached'
        }
        try:
            with open(sidecar_path, 'w', encoding='utf-8') as f:
                json.dump(sidecar_data, f, indent=2)
        except OSError as e:
            _logger.warning(f"AntigravityLauncher: Could not write sidecar: {e}")

        # 3. Launch if necessary (Automatic opening is deferred; record attachment and PID)
        if not is_alive:
            mock_mode = os.environ.get('INTEGRATION_MODE', '0') != '1'
            _logger.info("AntigravityLauncher: Automatic IDE launch is deferred. Recording workspace attachment metadata.")
            root_pid, root_start = self._find_root_ide_pid()
            if root_pid > 0 and not mock_mode:
                pid = root_pid
                start_time = root_start
            else:
                pid = os.getpid()
                try:
                    start_time = psutil.Process(pid).create_time()
                except Exception:
                    start_time = datetime.now(timezone.utc).timestamp()

            # Update cache
            _active_antigravity_processes[session_uuid] = {
                'pid': pid,
                'start_time': start_time,
                'heartbeat': datetime.now(timezone.utc).isoformat()
            }

        # 4. Persist metadata (Database source of truth)
        now_str = datetime.now(timezone.utc).isoformat()
        meta.update({
            'launcher_id': 'antigravity',
            'ide_name': 'Antigravity IDE',
            'ide_pid': pid,
            'process_start_time': start_time,
            'workspace_path': workspace_path,
            'attachment_status': 'attached',
            'session_uuid': session_uuid,
            'workspace_uuid': workspace_uuid,
            'heartbeat_timestamp': now_str,
            'last_seen_timestamp': now_str
        })
        
        if runtime:
            runtime.metadata_json = json.dumps(meta)
            runtime.endpoint = workspace_path
            if pid:
                runtime.process_id = pid

        return {
            'pid': pid,
            'ide_name': 'Antigravity IDE',
            'workspace_path': workspace_path,
            'attachment_status': 'attached'
        }

    @api.model
    def stop(self, runtime):
        meta = {}
        try:
            raw = getattr(runtime, 'metadata_json', '') or '{}'
            meta = json.loads(raw)
        except Exception:
            pass

        workspace_path = meta.get('workspace_path', '') or getattr(runtime, 'endpoint', '')
        session_uuid = meta.get('session_uuid', '')

        if workspace_path and os.path.isdir(workspace_path):
            sidecar_path = os.path.join(workspace_path, '.nexora_session.json')
            if os.path.exists(sidecar_path):
                try:
                    os.remove(sidecar_path)
                except OSError:
                    pass

        if session_uuid and session_uuid in _active_antigravity_processes:
            del _active_antigravity_processes[session_uuid]

        meta['attachment_status'] = 'detached'
        # Do not clear PID and start time immediately, but mark detached
        meta['last_seen_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        if runtime:
            runtime.metadata_json = json.dumps(meta)
            runtime.endpoint = ''

        return True

    @api.model
    def health(self, runtime):
        meta = {}
        try:
            raw = getattr(runtime, 'metadata_json', '') or '{}'
            meta = json.loads(raw)
        except Exception:
            pass

        pid = meta.get('ide_pid', 0)
        start_time = meta.get('process_start_time', 0.0)
        attachment_status = meta.get('attachment_status', 'detached')

        if attachment_status != 'attached':
            return 'critical'

        if pid and pid > 0:
            try:
                p = psutil.Process(pid)
                if start_time and abs(p.create_time() - start_time) < 1.0:
                    # Update heartbeat and last seen
                    now_str = datetime.now(timezone.utc).isoformat()
                    meta['heartbeat_timestamp'] = now_str
                    meta['last_seen_timestamp'] = now_str
                    runtime.metadata_json = json.dumps(meta)
                    
                    session_uuid = meta.get('session_uuid', '')
                    if session_uuid in _active_antigravity_processes:
                        _active_antigravity_processes[session_uuid]['heartbeat'] = now_str
                        
            except psutil.NoSuchProcess:
                pass

        # If stored PID exited (e.g. single-instance delegation), check if root IDE is alive and sidecar exists
        root_pid, root_start = self._find_root_ide_pid()
        workspace_path = meta.get('workspace_path', '')
        if root_pid > 0 and workspace_path and os.path.isdir(workspace_path):
            sidecar_path = os.path.join(workspace_path, '.nexora_session.json')
            is_open = os.path.exists(sidecar_path)
            if is_open:
                meta['ide_pid'] = root_pid
                meta['process_start_time'] = root_start
                now_str = datetime.now(timezone.utc).isoformat()
                meta['heartbeat_timestamp'] = now_str
                meta['last_seen_timestamp'] = now_str
                if runtime:
                    runtime.metadata_json = json.dumps(meta)
                    if runtime.process_id != root_pid:
                        runtime.process_id = root_pid
                session_uuid = meta.get('session_uuid', '')
                if session_uuid:
                    _active_antigravity_processes[session_uuid] = {
                        'pid': root_pid,
                        'start_time': root_start,
                        'heartbeat': now_str
                    }
                return 'healthy'

        if workspace_path and os.path.isdir(workspace_path):
            sidecar_path = os.path.join(workspace_path, '.nexora_session.json')
            if os.path.exists(sidecar_path):
                return 'healthy'

        return 'critical'

    @api.model
    def reattach(self, pid, workspace_path):
        if pid:
            try:
                psutil.Process(pid)
                # Rebuild cache from DB
                runtime = self.env['nexora.runtime'].search([('process_id', '=', pid), ('runtime_type', '=', 'ide')], limit=1)
                if runtime:
                    import json
                    meta = {}
                    try:
                        meta = json.loads(runtime.metadata_json or '{}')
                    except Exception:
                        pass
                    session_uuid = meta.get('session_uuid')
                    start_time = meta.get('process_start_time', 0.0)
                    heartbeat = meta.get('heartbeat_timestamp')
                    if session_uuid:
                        _active_antigravity_processes[session_uuid] = {
                            'pid': pid,
                            'start_time': start_time,
                            'heartbeat': heartbeat
                        }
                return True
            except psutil.NoSuchProcess:
                pass
        return False

    @api.model
    def cleanup(self, owned_pids=None):
        owned_pids = owned_pids or set()
        cleared = []
        for session_uuid, data in list(_active_antigravity_processes.items()):
            pid = data.get('pid')
            if pid not in owned_pids:
                try:
                    p = psutil.Process(pid)
                    start_time = data.get('start_time')
                    if start_time and abs(p.create_time() - start_time) >= 1.0:
                        raise psutil.NoSuchProcess(pid)
                except psutil.NoSuchProcess:
                    del _active_antigravity_processes[session_uuid]
                    cleared.append(pid)
        return cleared

    @api.model
    def update_ide_pid(self, session_uuid, pid, runtime=None):
        meta = {}
        if runtime:
            raw = getattr(runtime, 'metadata_json', '') or '{}'
            try:
                meta = json.loads(raw)
            except Exception:
                pass
                
        try:
            start_time = psutil.Process(pid).create_time()
        except Exception:
            start_time = 0.0
            
        now_str = datetime.now(timezone.utc).isoformat()
            
        _active_antigravity_processes[session_uuid] = {
            'pid': pid,
            'start_time': start_time,
            'heartbeat': now_str
        }
        
        if runtime:
            meta['ide_pid'] = pid
            meta['process_start_time'] = start_time
            meta['heartbeat_timestamp'] = now_str
            meta['last_seen_timestamp'] = now_str
            runtime.metadata_json = json.dumps(meta)
            runtime.process_id = pid
            
        return True
