# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import ValidationError
import subprocess
import sys
import os
import signal
import socket
import time
import shutil
from pathlib import Path
import logging

_logger = logging.getLogger(__name__)

_active_vite_processes = {}
_open_vite_log_files = []
_active_vite_popen_objects = []

class ViteLauncher(models.AbstractModel):
    _name = 'nexora.preview_launcher_vite'
    _inherit = 'nexora.preview_launcher'
    _description = 'Vite Development Server Launcher Plugin'

    @api.model
    def launcher_manifest(self):
        return {
            'launcher_id': 'vite',
            'launcher_type': 'vite',
            'display_name': 'Vite Development Server',
            'supported_frameworks': ['vite', 'react', 'vue', 'svelte', 'js'],
            'priority': 200,
            'supported_platforms': ['win32', 'darwin', 'linux'],
            'dependency_requirements': ['node', 'npm'],
            'health_strategy': 'http_and_socket',
            'recovery_strategy': 'process_cache_and_port',
            'description': 'Blazing fast frontend build and dev server via Vite and Node.js',
            'version': '1.0.0',
            'provider': 'nexora'
        }

    @api.model
    def validate(self, project_directory):
        errors = []
        warnings = []
        checked = {}

        node_path = shutil.which('node') or shutil.which('node.exe')
        if not node_path:
            errors.append("Node.js executable not found in system PATH.")
            checked['node'] = False
        else:
            checked['node'] = node_path

        npm_path = shutil.which('npm') or shutil.which('npm.cmd')
        if not npm_path:
            errors.append("npm executable not found in system PATH.")
            checked['npm'] = False
        else:
            checked['npm'] = npm_path

        if not project_directory or not Path(project_directory).exists():
            errors.append(f"Project directory '{project_directory}' does not exist.")
            checked['project_directory'] = False
        else:
            checked['project_directory'] = True
            pkg_path = Path(project_directory) / "package.json"
            if not pkg_path.exists():
                errors.append("package.json not found inside Vite project directory.")
                checked['package.json'] = False
            else:
                checked['package.json'] = True

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'dependencies_checked': checked
        }

    @api.model
    def prepare(self, project_directory, port, runtime, logs_directory=None, temp_directory=None, **kwargs):
        val_res = self.validate(project_directory)
        if not val_res['valid']:
            raise ValidationError(_(f"ViteLauncher validation failed: {'; '.join(val_res['errors'])}"))

        npm_bin = val_res['dependencies_checked'].get('npm') or ('npm.cmd' if os.name == 'nt' else 'npm')
        cmd = [npm_bin, "run", "dev", "--", "--port", str(port), "--host", "127.0.0.1"]
        
        log_path = Path(logs_directory) / "preview_vite.log" if logs_directory else Path(project_directory) / "preview_vite.log"
        if not log_path.parent.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env['PORT'] = str(port)

        return {
            'ready': True,
            'command': cmd,
            'env': env,
            'log_file': str(log_path)
        }

    @api.model
    def reattach(self, pid, port):
        if pid > 0:
            _active_vite_processes[pid] = {
                'proc': None,
                'port': port,
                'log_file': None
            }
            _logger.info(f"ViteLauncher reattached process ID {pid} on port {port} to in-memory cache.")
        return True

    @api.model
    def start(self, project_directory, port, runtime, logs_directory=None, temp_directory=None):
        prep = self.prepare(project_directory, port, runtime, logs_directory=logs_directory, temp_directory=temp_directory)
        cmd = prep['command']
        log_path = Path(prep['log_file'])
        env = prep['env']
        
        try:
            log_file = open(log_path, "a", encoding="utf-8")
            _open_vite_log_files.append(log_file)
            proc = subprocess.Popen(
                cmd,
                cwd=project_directory,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
            _active_vite_popen_objects.append(proc)
            process_id = proc.pid
            
            _active_vite_processes[process_id] = {
                'proc': proc,
                'port': port,
                'log_file': log_file
            }
            
            preview_command = " ".join(cmd)
            preview_url = f"http://127.0.0.1:{port}"
            
            _logger.info(f"ViteLauncher started process {process_id} on port {port} at {preview_url}")
            return process_id, preview_command, preview_url
        except Exception as e:
            _logger.error(f"ViteLauncher failed to start: {e}")
            raise ValidationError(_(f"Failed to start Vite server: {e}"))

    @api.model
    def _is_process_alive(self, pid):
        if not pid or pid <= 0:
            return False
        try:
            if os.name == 'nt':
                res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                return str(pid) in res.stdout
            else:
                os.kill(pid, 0)
                return True
        except Exception:
            return False

    def _wait_for_port_release(self, port, timeout=5.0):
        if not port or port <= 0:
            return True
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    time.sleep(0.1)
            except (ConnectionRefusedError, socket.timeout, OSError):
                return True
        return False

    @api.model
    def cleanup(self, owned_pids=None, owned_ports=None):
        return []

    @api.model
    def stop(self, runtime):
        pid = getattr(runtime, 'process_id', 0)
        port = getattr(runtime, 'allocated_port', 0) or getattr(runtime, 'port', 0)
        
        proc_info = _active_vite_processes.pop(pid, None) if pid > 0 else None
        proc = proc_info['proc'] if proc_info else None
        log_file = proc_info['log_file'] if proc_info else None
        if not port and proc_info:
            port = proc_info.get('port', 0)
            
        if not pid or pid <= 0:
            if port and port > 0:
                self._wait_for_port_release(port, timeout=3.0)
            return True
            
        if proc:
            try:
                proc.terminate()
            except OSError:
                pass
                
        try:
            if os.name == 'nt':
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
            
        if proc:
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    if os.name == 'nt':
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proc.wait(timeout=3.0)
                except (subprocess.TimeoutExpired, OSError):
                    pass
            except OSError:
                pass
                
        start_time = time.time()
        while time.time() - start_time < 5.0:
            if not self._is_process_alive(pid):
                break
            time.sleep(0.1)
            
        if log_file:
            try:
                log_file.close()
            except Exception:
                pass
                
        if port and port > 0:
            self._wait_for_port_release(port, timeout=5.0)
            
        return True

    @api.model
    def health(self, runtime):
        pid = getattr(runtime, 'process_id', 0)
        port = getattr(runtime, 'port', 0)
        if hasattr(runtime, 'allocated_port') and runtime.allocated_port:
            port = runtime.allocated_port
            
        if not pid or pid <= 0 or not self._is_process_alive(pid):
            return 'critical'
            
        if port > 0:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    pass
            except (socket.timeout, ConnectionRefusedError, OSError):
                pass
                
        return 'healthy'

    @api.model
    def detect_project(self, project_directory):
        if not project_directory or not Path(project_directory).exists():
            return False
        p_path = Path(project_directory)
        pkg_path = p_path / "package.json"
        if not pkg_path.exists():
            return False
            
        for cfg in ["vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs"]:
            if (p_path / cfg).exists():
                return 20 # Exact high-priority score for Vite config match
                
        try:
            content = pkg_path.read_text(encoding="utf-8")
            if '"vite"' in content or "'vite'" in content:
                return 18
        except Exception:
            pass
            
        return False
