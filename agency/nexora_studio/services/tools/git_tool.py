# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult

import time

class GitTool(models.AbstractModel):
    _name = 'nexora.tool.git'
    _inherit = 'nexora.tool.base'
    _description = 'Git Operations Tool'

    def metadata(self):
        return {
            'capability_code': 'mcp.tool.git',
            'display_name': 'Git Tool',
            'category': 'tool',
            'version': '1.0.0',
            'author': 'Nexora Studio',
            'provider': 'nexora',
            'implementation_model': self._name,
            'supported_platforms': ['windows', 'linux', 'macos'],
            'supports_local': True,
            'supports_remote': False,
            'supports_async': False,
            'permissions': ['sys.exec', 'fs.read', 'fs.write'],
            'dependencies': ['mcp.tool.terminal'],
            'optional_dependencies': [],
            'minimum_runtime_version': '1.0.0',
            'metadata_version': '1.0'
        }

    def health(self): return True
    def validate(self, context, **kwargs):
        if not kwargs.get('action'): raise ValueError("GitTool requires an 'action'")

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        context = request.context
        kwargs = request.payload
        action = kwargs.get('action')
        cwd = kwargs.get('cwd', '.')
        
        start_time = time.time()
        
        try:
            session_id = context.get('builder_session_id') or context.get('session_id')
            if not session_id:
                return ProviderExecutionResult(success=False, error=["Missing session context for GitTool"])
                
            git_service = self.env['nexora.git_service']
            
            if action == 'init':
                res = git_service.init_session_repo(session_id)
                if res.get('status') == 'error':
                    return ProviderExecutionResult(success=False, error=[res.get('error')])
                return ProviderExecutionResult(success=True, data={'message': 'Initialized git repository'})
                
            elif action == 'commit':
                message = kwargs.get('message', 'Automatic tool update')
                res = git_service.commit_session(session_id, message)
                if res.get('status') == 'error':
                    return ProviderExecutionResult(success=False, error=[res.get('error')])
                return ProviderExecutionResult(success=True, data={'message': 'Committed successfully'})
                
            else:
                return ProviderExecutionResult(success=False, error=[f"Unknown action {action}"])
                
        except Exception as e:
            return ProviderExecutionResult(success=False, error=[str(e)], execution_time=time.time()-start_time)
