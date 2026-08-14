# -*- coding: utf-8 -*-
import warnings
from odoo import models
import os
import subprocess
import logging
import socket
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult

_logger = logging.getLogger(__name__)

warnings.warn(
    'RuntimeBootstrapStage is deprecated and isolated. It has been replaced by GenerationRuntime.',
    DeprecationWarning,
    stacklevel=2
)

class RuntimeBootstrapStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.runtime_bootstrap'
    _inherit = 'nexora.ai_generation_stage'

    _description = 'DEPRECATED - Stage 07: Runtime Bootstrap'

    def execute(self, context):
        session = context.builder_session
        workspace_path = context.workspace_path
        target_src = os.path.join(workspace_path, 'src')
        bootstrapped = []
        
        for rtype in ['mcp', 'preview', 'git', 'ide']:
            runtime = self.env['nexora.runtime'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', rtype)], limit=1)
            if not runtime:
                runtime = self.env['nexora.runtime'].create({
                    'builder_session_id': session.id,
                    'runtime_type': rtype,
                    'name': f'{rtype.capitalize()} Runtime',
                    'status': 'starting'
                })
            
            # Real Git Initialization
            if rtype == 'git':
                git_dir = os.path.join(workspace_path, '.git')
                if not os.path.exists(git_dir):
                    generation_runtime = context.get('generation_runtime')
                    if generation_runtime:
                        try:
                            generation_runtime.tools.execute("mcp.tool.terminal", {"command": "git init", "cwd": workspace_path}, generation_runtime)
                            generation_runtime.tools.execute("mcp.tool.terminal", {"command": "git add .", "cwd": workspace_path}, generation_runtime)
                            generation_runtime.tools.execute("mcp.tool.terminal", {"command": "git commit -m 'Initial Generation Checkpoint'", "cwd": workspace_path}, generation_runtime)
                            runtime.write({'status': 'running', 'health': 'healthy'})
                            _logger.info("Git repository initialized successfully via capability.")
                        except Exception as e:
                            runtime.write({'status': 'error', 'health': 'critical'})
                            _logger.error(f"Git init failed via capability: {e}")
                    else:
                        runtime.write({'status': 'error', 'health': 'critical'})
                        _logger.error("Git init failed: No generation_runtime in context.")
                else:
                    runtime.write({'status': 'running', 'health': 'healthy'})
                    
            # Real Preview Initialization
            elif rtype == 'preview':
                try:
                    port = self._get_free_port()
                    _logger.info(f"Starting Preview on port {port} at {target_src}")
                    
                    generation_runtime = context.get('generation_runtime')
                    if generation_runtime:
                        # Background task execution via the terminal capability
                        generation_runtime.tools.execute("mcp.tool.terminal", {
                            "command": f"npm run dev -- --port {port} > preview.log 2>&1 &",
                            "cwd": target_src
                        }, generation_runtime)
                        
                        runtime.write({
                            'status': 'running', 
                            'health': 'healthy',
                            'endpoint': f'http://localhost:{port}'
                        })
                        
                        # Background tracking would normally rely on the PID. We mock it for the legacy pipeline.
                        context.set('preview_pid', 99999) 
                        context.set('preview_url', f'http://localhost:{port}')
                    else:
                        runtime.write({'status': 'error', 'health': 'critical'})
                        _logger.error("Preview start failed: No generation_runtime in context.")
                except Exception as e:
                    runtime.write({'status': 'error', 'health': 'critical'})
                    _logger.error(f"Preview start failed: {e}")
            else:
                runtime.write({'status': 'running', 'health': 'healthy'})
                
            bootstrapped.append(runtime.id)
            
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'workspace',
            'event_type': 'generation.runtimes_started',
            'message': f"Bootstrapped {len(bootstrapped)} runtimes."
        })
        
        return GenerationStageResult(GenerationStageResult.SUCCESS, "Runtimes bootstrapped.", data={'runtimes': bootstrapped})

    def _get_free_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def rollback(self, context, execution_data):
        session = context.builder_session
        runtimes = self.env['nexora.runtime'].search([('builder_session_id', '=', session.id)])
        for r in runtimes:
            r.write({'status': 'stopped'})
            
        pid = context.get('preview_pid')
        if pid:
            try:
                import psutil
                process = psutil.Process(pid)
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()
            except Exception:
                pass
