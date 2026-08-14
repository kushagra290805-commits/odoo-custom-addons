# -*- coding: utf-8 -*-
from odoo import models, api
import logging
import subprocess
import os

_logger = logging.getLogger(__name__)

class ExecutionSandboxService(models.AbstractModel):
    _name = 'nexora.execution_sandbox_service'
    _description = 'Production Execution Sandbox Service'

    @api.model
    def execute_local(self, cmd, cwd=None, env=None, timeout=30):
        """
        Executes a command locally with strict workspace restrictions.
        """
        _logger.info(f"Sandbox executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        
        # Enforce Workspace Restrictions
        if cwd and not cwd.startswith(os.path.abspath(r'D:\ODOO')):
            return {'success': False, 'error': 'Sandbox violation: execution attempted outside allowed workspace.'}
            
        # Production Execution
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                env=env, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired as e:
            _logger.error(f"Sandbox execution timed out: {e}")
            return {'success': False, 'error': 'Timeout expired', 'stderr': str(e)}
        except Exception as e:
            _logger.error(f"Sandbox execution failed: {e}")
            return {'success': False, 'error': str(e)}
