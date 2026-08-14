# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import ValidationError
import subprocess
import sys
import os
import signal
import socket
import time
from pathlib import Path
import logging

_logger = logging.getLogger(__name__)

_active_static_processes = {}
_open_static_log_files = []
_active_static_popen_objects = []

class StaticFileLauncher(models.AbstractModel):
    _name = 'nexora.preview_launcher_static_file'
    _inherit = 'nexora.preview_launcher'
    _description = 'Static File Server Launcher Plugin'

    @api.model
    def launcher_manifest(self):
        return {
            'launcher_id': 'static_file',
            'launcher_type': 'static_file',
            'display_name': 'Static File Server',
            'supported_frameworks': ['static', 'html'],
            'priority': 80,
            'supported_platforms': ['win32', 'darwin', 'linux'],
            'dependency_requirements': ['python'],
            'health_strategy': 'http_and_socket',
            'recovery_strategy': 'process_cache_and_port',
            'description': 'Lightweight static file preview server for pure HTML/CSS/JS workspaces',
            'version': '1.0.0',
            'provider': 'nexora'
        }

    @api.model
    def validate(self, project_directory):
        errors = []
        warnings = []
        checked = {}

        if not sys.executable or not Path(sys.executable).exists():
            errors.append("Python executable not found in system environment.")
            checked['python'] = False
        else:
            checked['python'] = str(sys.executable)

        if not project_directory or not Path(project_directory).exists():
            errors.append(f"Project directory '{project_directory}' does not exist.")
            checked['project_directory'] = False
        else:
            checked['project_directory'] = True
            html_files = list(Path(project_directory).glob("*.html"))
            if not html_files and not (Path(project_directory) / "index.html").exists():
                warnings.append("No index.html or HTML files found directly inside project directory.")

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
            raise ValidationError(_(f"StaticFileLauncher validation failed: {'; '.join(val_res['errors'])}"))

        cmd = [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"]
        log_path = Path(logs_directory) / "preview_static.log" if logs_directory else Path(project_directory) / "preview_static.log"
        if not log_path.parent.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)

        return {
            'ready': True,
            'command': cmd,
            'env': os.environ.copy(),
            'log_file': str(log_path)
        }

    @api.model
    def reattach(self, pid, port):
        if pid > 0:
            _active_static_processes[pid] = {
                'proc': None,
                'port': port,
                'log_file': None
            }
            _logger.info(f"StaticFileLauncher reattached process ID {pid} on port {port} to in-memory cache.")
        return True

    @api.model
    def start(self, project_directory, port, runtime, logs_directory=None, temp_directory=None):
        prep = self.prepare(project_directory, port, runtime, logs_directory=logs_directory, temp_directory=temp_directory)
        cmd = prep['command']
        log_path = Path(prep['log_file'])
        
        try:
            log_file = open(log_path, "a", encoding="utf-8")
            _open_static_log_files.append(log_file)
            proc = subprocess.Popen(
                cmd,
                cwd=project_directory,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
            _active_static_popen_objects.append(proc)
            process_id = proc.pid
            
            _active_static_processes[process_id] = {
                'proc': proc,
                'port': port,
                'log_file': log_file
            }
            
            preview_command = " ".join(cmd)
            preview_url = f"http://127.0.0.1:{port}"
            
            _logger.info(f"StaticFileLauncher started process {process_id} on port {port} at {preview_url}")
            return process_id, preview_command, preview_url
        except Exception as e:
            _logger.error(f"StaticFileLauncher failed to start: {e}")
            raise ValidationError(_(f"Failed to start Static File server: {e}"))

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
        
        proc_info = _active_static_processes.pop(pid, None) if pid > 0 else None
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
        if (p_path / "index.html").exists() and not (p_path / "package.json").exists():
            return 15 # Strong fit for pure static HTML workspace without Node build steps
        return False
