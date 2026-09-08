# -*- coding: utf-8 -*-
from odoo import models, api
import logging
import subprocess
import os
import tempfile

_logger = logging.getLogger(__name__)

class ExecutionSandboxService(models.AbstractModel):
    _name = 'nexora.execution_sandbox_service'
    _description = 'Production Execution Sandbox Service'

    @api.model
    def _allowed_execution_roots(self):
        """Phase 47.11 (U9.2): the truthful command-execution allow-list.

        Command execution is confined to bounded workspace locations:
          * the Odoo/add-on workspace (existing behaviour),
          * the configured managed-workspace root (``nexora.workspace_root``),
            which is where generated workspaces actually live, and
          * the OS temp dir, where controlled/ephemeral generated workspaces
            are materialized during tests and controlled generation.

        The managed root is read from the existing configuration contract used
        by ``nexora.workspace_service`` — no second workspace manager and no
        hardcoded generated-project root.
        """
        roots = [os.path.abspath(r'D:\ODOO')]
        try:
            managed_root = self.env['ir.config_parameter'].sudo().get_param('nexora.workspace_root')
            if managed_root:
                roots.append(os.path.abspath(managed_root))
        except Exception:
            pass
        try:
            roots.append(os.path.abspath(tempfile.gettempdir()))
        except Exception:
            pass
        return roots

    @api.model
    def is_within_allowed_roots(self, path):
        """Return True when ``path`` resolves inside an allowed execution root."""
        if not path:
            return False
        ap = os.path.abspath(path)
        for root in self._allowed_execution_roots():
            if ap == root or ap.startswith(root + os.sep):
                return True
        return False

    @api.model
    def execute_local(self, cmd, cwd=None, env=None, timeout=30):
        """
        Executes a command locally with strict workspace restrictions.
        """
        _logger.info(f"Sandbox executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}")

        # Enforce Workspace Restrictions
        if cwd and not self.is_within_allowed_roots(cwd):
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
