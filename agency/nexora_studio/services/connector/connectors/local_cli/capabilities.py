from typing import Dict, Any
from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
from odoo.addons.nexora_studio.services.connector.sdk.transport import BaseTransport
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import RuntimeException

def execute_shell(parameters: Dict[str, Any], context: ExecutionContext, transport: BaseTransport) -> Dict[str, Any]:
    """Synchronous blocking execution of a shell command."""
    command = parameters.get("command")
    if not command:
        raise RuntimeException(error_code="MISSING_COMMAND", user_safe_message="Parameter 'command' is required.", technical_message="Parameter 'command' is required for shell.execute.")
        
    import os
    working_directory = parameters.get("cwd") or parameters.get("working_directory")
    if working_directory and not os.path.isdir(working_directory):
        raise RuntimeException(error_code="INVALID_CWD", user_safe_message=f"Invalid working directory: {working_directory}", technical_message=f"Invalid working directory: {working_directory}")
        
    timeout = parameters.get("timeout")
    if timeout is not None and (not isinstance(timeout, (int, float)) or timeout < 0):
        raise RuntimeException(error_code="INVALID_TIMEOUT", user_safe_message=f"Invalid timeout: {timeout}", technical_message=f"Invalid timeout: {timeout}")
        
    payload = {
        "command": command,
        "working_directory": working_directory,
        "env": parameters.get("env", {}),
        "timeout": timeout
    }
    
    return transport.send_request(payload, context)

def spawn_process(parameters: Dict[str, Any], context: ExecutionContext, transport: BaseTransport) -> Dict[str, Any]:
    """
    Spawns a process. In this basic implementation, it executes and returns the result, 
    but theoretically could return a PID for async tracking in a more advanced transport.
    For Phase 27.0, we just map it to execute_shell as a proof-of-concept.
    """
    return execute_shell(parameters, context, transport)

def kill_process(parameters: Dict[str, Any], context: ExecutionContext, transport: BaseTransport) -> Dict[str, Any]:
    """Kills a process by PID."""
    pid = parameters.get("pid")
    if not pid:
        raise RuntimeException(error_code="MISSING_PID", user_safe_message="Parameter 'pid' is required.", technical_message="Parameter 'pid' is required for process.kill.")
        
    # Example of a capability wrapping OS-specific logic into a generic payload
    import platform
    if platform.system() == "Windows":
        cmd = f"taskkill /F /PID {pid}"
    else:
        cmd = f"kill -9 {pid}"
        
    payload = {"command": cmd}
    return transport.send_request(payload, context)

def install_dependency(parameters: Dict[str, Any], context: ExecutionContext, transport: BaseTransport) -> Dict[str, Any]:
    """Installs a dependency (e.g. pip package)."""
    package = parameters.get("package")
    if not package:
        raise RuntimeException(error_code="MISSING_PACKAGE", user_safe_message="Parameter 'package' is required.", technical_message="Parameter 'package' is required for dependency.install.")
        
    payload = {"command": f"pip install {package}"}
    return transport.send_request(payload, context)
