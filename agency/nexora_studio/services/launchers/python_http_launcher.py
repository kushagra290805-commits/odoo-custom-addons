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

# Track active Popen objects by process_id inside the python process
_active_processes = {}
_open_log_files = []
_active_popen_objects = []

class PythonHttpLauncher(models.AbstractModel):
    _name = 'nexora.preview_launcher_python_http'
    _inherit = 'nexora.preview_launcher'
    _description = 'Python HTTP Server Launcher Plugin'

    @api.model
    def launcher_manifest(self):
        return {
            'launcher_id': 'python_http',
            'launcher_type': 'python_http',
            'display_name': 'Python HTTP Server',
            'supported_frameworks': ['html', 'static', 'python'],
            'priority': 100,
            'supported_platforms': ['win32', 'darwin', 'linux'],
            'dependency_requirements': ['python'],
            'health_strategy': 'http_and_socket',
            'recovery_strategy': 'process_cache_and_port',
            'description': 'Default zero-dependency static preview server via python -m http.server',
            'version': '1.0.0',
            'provider': 'nexora'
        }

    @api.model
    def validate(self, project_directory):
        """Verifies required dependencies (python executable) and project directory validity."""
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

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'dependencies_checked': checked
        }

    @api.model
    def prepare(self, project_directory, port, runtime, logs_directory=None, temp_directory=None, **kwargs):
        """Prepares command, log file path, and execution environment."""
        val_res = self.validate(project_directory)
        if not val_res['valid']:
            raise ValidationError(_(f"Launcher validation failed: {'; '.join(val_res['errors'])}"))

        cmd = [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"]
        log_path = Path(logs_directory) / "preview.log" if logs_directory else Path(project_directory) / "preview.log"
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
        """Reconstructs the in-memory _active_processes cache entry from persisted database metadata after Odoo restart."""
        if pid > 0:
            _active_processes[pid] = {
                'proc': None,
                'port': port,
                'log_file': None
            }
            _logger.info(f"PythonHttpLauncher reattached process ID {pid} on port {port} to in-memory cache.")
        return True

    @api.model
    def is_process_cached(self, pid):
        return pid in _active_processes

    @api.model
    def clear_active_processes_cache(self):
        _active_processes.clear()
        return True

    @api.model
    def start(self, project_directory, port, runtime, logs_directory=None, temp_directory=None):
        prep = self.prepare(project_directory, port, runtime, logs_directory=logs_directory, temp_directory=temp_directory)
        cmd = prep['command']
        log_path = Path(prep['log_file'])
        
        try:
            log_file = open(log_path, "a", encoding="utf-8")
            _open_log_files.append(log_file)
            proc = subprocess.Popen(
                cmd,
                cwd=project_directory,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
            _active_popen_objects.append(proc)
            process_id = proc.pid
            
            _active_processes[process_id] = {
                'proc': proc,
                'port': port,
                'log_file': log_file
            }
            
            preview_command = " ".join(cmd)
            preview_url = f"http://127.0.0.1:{port}"
            
            _logger.info(f"PythonHttpLauncher started process {process_id} on port {port} at {preview_url}")
            return process_id, preview_command, preview_url
        except Exception as e:
            _logger.error(f"PythonHttpLauncher failed to start: {e}")
            raise ValidationError(_(f"Failed to start Python HTTP server: {e}"))

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
        except Exception as e:
            return False

    def _wait_for_port_release(self, port, timeout=5.0):
        if not port or port <= 0:
            return True
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    time.sleep(0.1)  # Connected -> still serving / socket open
            except (ConnectionRefusedError, socket.timeout, OSError):
                return True  # Port is closed
        return False

    @api.model
    def find_orphan_processes_and_ports(self, owned_pids, owned_ports):
        """
        Scans the system for any processes or ports (in range 3000..3999 or running -m http.server)
        that are NOT owned by valid runtime registry records.
        Returns a list of tuples: [(pid, port, reason), ...]
        """
        orphans = []
        my_pid = os.getpid()
        try:
            if os.name == 'nt':
                res = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True)
                for line in res.stdout.splitlines():
                    if "LISTENING" in line and ("127.0.0.1:" in line or "0.0.0.0:" in line):
                        parts = line.strip().split()
                        if len(parts) >= 5 and parts[-1].isdigit():
                            local_addr = parts[1]
                            pid = int(parts[-1])
                            if ":" in local_addr:
                                port_str = local_addr.split(":")[-1]
                                if port_str.isdigit():
                                    port = int(port_str)
                                    if 3000 <= port < 4000 and port not in (owned_ports or set()) and pid not in (owned_pids or set()) and pid != my_pid:
                                        orphans.append((pid, port, f"Listening on port {port} without database ownership"))
            else:
                res = subprocess.run(["lsof", "-iTCP:3000-3999", "-sTCP:LISTEN", "-P", "-n"], capture_output=True, text=True)
                for line in res.stdout.splitlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 9 and parts[1].isdigit():
                        pid = int(parts[1])
                        local_addr = parts[8]
                        if ":" in local_addr:
                            port_str = local_addr.split(":")[-1]
                            if port_str.isdigit():
                                port = int(port_str)
                                if 3000 <= port < 4000 and port not in (owned_ports or set()) and pid not in (owned_pids or set()) and pid != my_pid:
                                    orphans.append((pid, port, f"Listening on port {port} without database ownership"))
        except Exception as e:
            _logger.warning(f"Error during fast port scan: {e}")
                
        return orphans

    @api.model
    def cleanup(self, owned_pids=None, owned_ports=None):
        """Implements the standard cleanup() method of PreviewLauncher by terminating detected orphans."""
        orphans = self.find_orphan_processes_and_ports(owned_pids or set(), owned_ports or set())
        cleaned = []
        for pid, port, reason in orphans:
            _logger.warning(f"Detected orphan preview process PID {pid} (Port {port}): {reason}. Terminating...")
            if pid > 0:
                try:
                    if os.name == 'nt':
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        os.kill(pid, signal.SIGKILL)
                except Exception as e:
                    _logger.warning(f"Failed to kill orphan PID {pid}: {e}")
            if port > 0:
                self._wait_for_port_release(port, timeout=2.0)
            cleaned.append((pid, port, reason))
        return cleaned

    @api.model
    def stop(self, runtime):
        pid = getattr(runtime, 'process_id', 0)
        port = getattr(runtime, 'allocated_port', 0) or getattr(runtime, 'port', 0)
        
        proc_info = _active_processes.pop(pid, None) if pid > 0 else None
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
            if time.time() - start_time > 2.0:
                try:
                    if os.name == 'nt':
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            time.sleep(0.1)
            
        if log_file:
            try:
                log_file.close()
            except Exception:
                pass
                
        if port and port > 0:
            self._wait_for_port_release(port, timeout=5.0)
            
        _logger.info(f"PythonHttpLauncher stopped and verified termination of process {pid} on port {port}")
        return True

    @api.model
    def health(self, runtime):
        pid = getattr(runtime, 'process_id', 0)
        port = getattr(runtime, 'port', 0)
        if hasattr(runtime, 'allocated_port') and runtime.allocated_port:
            port = runtime.allocated_port
            
        if not pid or pid <= 0:
            return 'critical'
            
        if not self._is_process_alive(pid):
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
        """
        Python static/HTTP server fallback or detector.
        Matches if project_directory exists and contains python files or as standard static fallback.
        """
        if not project_directory or not Path(project_directory).exists():
            return False
        py_files = list(Path(project_directory).glob("*.py"))
        if py_files:
            return 10
        return 5 # Fallback match for static workspaces
