# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult

import subprocess
import time

class TerminalTool(models.AbstractModel):
    _name = 'nexora.tool.terminal'
    _inherit = 'nexora.tool.base'
    _description = 'Terminal Operations Tool'

    def metadata(self):
        return {
            'capability_code': 'mcp.tool.terminal',
            'display_name': 'Terminal Tool',
            'category': 'tool',
            'version': '1.0.0',
            'author': 'Nexora Studio',
            'provider': 'nexora',
            'implementation_model': self._name,
            'supported_platforms': ['windows', 'linux', 'macos'],
            'supports_local': True,
            'supports_remote': False,
            'supports_async': True,
            'permissions': ['sys.exec'],
            'dependencies': [],
            'optional_dependencies': [],
            'minimum_runtime_version': '1.0.0',
            'metadata_version': '1.0'
        }

    def health(self): return True

    def validate(self, context, **kwargs):
        if not kwargs.get('command'): raise ValueError("TerminalTool requires a 'command'")

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        context = request.context
        kwargs = request.payload
        command = kwargs.get('command')
        cwd = kwargs.get('cwd', '.')
        
        start_time = time.time()
        try:
            result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
            if result.returncode == 0:
                return ProviderExecutionResult(success=True, data=result.stdout, execution_ms=(time.time()*1000)-start_time)
            else:
                return ProviderExecutionResult(success=False, error=[result.stderr], execution_ms=(time.time()*1000)-start_time)
        except Exception as e:
            return ProviderExecutionResult(success=False, error=[str(e)], execution_time=time.time()-start_time)
