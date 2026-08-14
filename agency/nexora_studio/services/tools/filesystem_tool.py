# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult


class FilesystemTool(models.AbstractModel):
    _name = 'nexora.tool.filesystem'
    _inherit = 'nexora.tool.base'
    _description = 'Filesystem Operations Tool'

    def metadata(self):
        return {
            'capability_code': 'mcp.tool.fs',
            'display_name': 'Filesystem Tool',
            'category': 'tool',
            'version': '1.0.0',
            'author': 'Nexora Studio',
            'provider': 'nexora',
            'implementation_model': self._name,
            'supported_platforms': ['windows', 'linux', 'macos'],
            'supports_local': True,
            'supports_remote': False,
            'supports_async': False,
            'permissions': ['fs.read', 'fs.write'],
            'dependencies': [],
            'optional_dependencies': [],
            'minimum_runtime_version': '1.0.0',
            'metadata_version': '1.0'
        }

    def health(self):
        return True

    def validate(self, context, **kwargs):
        action = kwargs.get('action')
        if not action:
            raise ValueError("FilesystemTool requires an 'action'")

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        context = request.context
        kwargs = request.payload
        action = kwargs.get('action')
        path = kwargs.get('path')
        dest = kwargs.get('destination')
        content = kwargs.get('content')
        import os, shutil, time
        
        start_time = time.time()
        
        try:
            if action == 'create_folder':
                os.makedirs(path, exist_ok=True)
                return ProviderExecutionResult(success=True, data=f"Folder created: {path}", execution_ms=(time.time()*1000)-start_time)
            elif action == 'delete_folder':
                if os.path.exists(path): shutil.rmtree(path)
                return ProviderExecutionResult(success=True, data=f"Folder deleted: {path}", execution_ms=(time.time()*1000)-start_time)
            elif action == 'copy':
                if os.path.isdir(path): shutil.copytree(path, dest, dirs_exist_ok=True)
                else: shutil.copy2(path, dest)
                return ProviderExecutionResult(success=True, data=f"Copied {path} to {dest}", execution_ms=(time.time()*1000)-start_time)
            elif action == 'write_file':
                with open(path, 'w', encoding='utf-8') as f: f.write(content or "")
                return ProviderExecutionResult(success=True, data=f"File written: {path}", execution_ms=(time.time()*1000)-start_time)
            elif action == 'read_file':
                with open(path, 'r', encoding='utf-8') as f: data = f.read()
                return ProviderExecutionResult(success=True, data=data, execution_ms=(time.time()*1000)-start_time)
            else:
                return ProviderExecutionResult(success=False, error=[f"Unknown action {action}"])
        except Exception as e:
            return ProviderExecutionResult(success=False, error=[str(e)], execution_time=time.time()-start_time)
