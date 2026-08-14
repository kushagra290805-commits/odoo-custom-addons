import os
import subprocess
from typing import Dict, Any
from odoo.addons.nexora_studio.services.connector.sdk.transport import BaseTransport
from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import RuntimeException, TimeoutException
from .configuration import LocalCliConfiguration

class LocalCliTransport(BaseTransport):
    """
    Subprocess-based transport for executing commands locally.
    Handles stdout, stderr, timeout, and cancellation.
    """
    
    def __init__(self):
        self._active_processes = []
        
    def connect(self, context: ExecutionContext) -> None:
        pass  # No persistent connection needed for CLI

    def disconnect(self, context: ExecutionContext) -> None:
        """Tear down any active subprocesses."""
        for proc in self._active_processes:
            try:
                proc.kill()
            except Exception:
                pass
        self._active_processes.clear()

    def send_request(self, payload: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Payload format:
        {
            "command": str | List[str],
            "working_directory": str (optional),
            "env": Dict[str, str] (optional),
            "timeout": float (optional)
        }
        """
        config = LocalCliConfiguration(context.configuration_snapshot)
        
        command = payload.get("command")
        if not command:
            raise RuntimeException(error_code="MISSING_COMMAND", user_safe_message="Payload missing 'command'", technical_message="Payload missing 'command'")
            
        # Parse configuration
        working_dir = payload.get("working_directory", config.working_directory)
        timeout = payload.get("timeout", config.default_timeout_seconds)
        
        # Merge environment variables
        env = os.environ.copy()
        env.update(config.environment_variables)
        env.update(payload.get("env", {}))
        
        use_shell = config.shell
        if isinstance(command, list) and use_shell:
            command = " ".join(command)

        try:
            # Spawn process
            proc = subprocess.Popen(
                command,
                shell=use_shell,
                cwd=working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self._active_processes.append(proc)
            
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate() # flush
                raise TimeoutException(error_code="COMMAND_TIMEOUT", user_safe_message=f"Command timed out after {timeout} seconds.", technical_message=f"Command timed out after {timeout} seconds.")
                
            finally:
                if proc in self._active_processes:
                    self._active_processes.remove(proc)

            return {
                "stdout": stdout[:config.max_output_size_bytes],
                "stderr": stderr[:config.max_output_size_bytes],
                "exit_code": proc.returncode
            }
            
        except TimeoutException:
            raise
        except Exception as e:
            raise RuntimeException(error_code="EXECUTION_FAILED", user_safe_message=f"Failed to execute command: {e}", technical_message=f"Failed to execute command: {e}")
